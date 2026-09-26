"""
Per-strategy causal backtest.

Replays each plan on its own book (not a portfolio). Signals use confirmed
bars only. AI is not called: a signal that survives geometry and hard veto
is treated as approved.

Costs match ``app.core.causal_backtest`` (HL taker 0.045% per side + 1 bp
slip per fill). Funding is an extra drag when ``fundingHistory`` covers the
hold. Fill-cooldown inside ``BaseStrategy`` compares against the wall clock,
so this runner enforces cooldown on bar time instead.

CLI::

    python -m app.core.strategy_backtest --symbols BTC ETH SOL
    python -m app.core.strategy_backtest --no-fetch --cache-dir data/ohlcv

Official ``candleSnapshot`` only keeps the most recent 5000 candles per
interval. 1m-dependent plans (SuperTrend, rocket, waterfall) therefore replay
only the short overlap where 1m still exists. 1h plans see the longer 1h window.
"""
from __future__ import annotations

import argparse
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

import pandas as pd

from app.core.causal_backtest import (
    ClosedTrade,
    DEFAULT_SLIP_FRAC,
    TAKER_FEE,
    TradeStats,
    bar_bracket_exit,
    chronological_holdout,
    funding_drag_r,
    gross_r,
    group_stats,
    net_r,
    sample_size_note,
    sl_fraction,
    summarize_trades,
    valid_bracket,
)
from app.core.hl_ohlcv import (
    INTERVAL_MS,
    SCANNER_WHITELIST,
    describe_span,
    ensure_symbol_cache,
    interval_td,
    slice_asof,
)
from app.core.trade_thesis import (
    ACTION_TIGHTEN_SL,
    DEAD_FLATTEN_ACTIONS,
    break_even_sl,
    compute_thesis_dead_streak,
    should_apply_be_tighten,
)
from app.core.trailing_logic import compute_trailing_decision, freeze_initial_sl
from app.core.weekend_pause import is_strategy_weekend_paused

FOCUS = ("supertrend", "trend_lt", "range_lt", "rocket", "waterfall")
OPTIONAL = ("spark", "ember")
DEFAULT_SYMBOLS = SCANNER_WHITELIST

PLAN_META_KEYS = (
    "range_high",
    "range_low",
    "range_mid",
    "cascade_ema9",
    "cascade_high",
    "cascade_low",
)


@dataclass(frozen=True)
class StrategySpec:
    name: str
    primary: str
    step: str
    required: Tuple[str, ...]
    regime_gate: bool
    bb_filter: bool
    mtf: bool
    thesis_tf: str
    optional: bool = False


SPECS: Dict[str, StrategySpec] = {
    "supertrend": StrategySpec("supertrend", "15m", "15m", ("15m", "1m"), True, True, False, "15m"),
    "trend_lt": StrategySpec("trend_lt", "1h", "1h", ("1h",), False, False, True, "1h"),
    "range_lt": StrategySpec("range_lt", "1h", "1h", ("1h",), False, False, False, "1h"),
    "rocket": StrategySpec("rocket", "15m", "5m", ("15m", "1m"), True, False, False, "15m"),
    "waterfall": StrategySpec("waterfall", "15m", "5m", ("15m", "1m"), True, False, False, "15m"),
    "spark": StrategySpec("spark", "5m", "3m", ("5m", "1m", "15m"), True, False, False, "5m", True),
    "ember": StrategySpec("ember", "5m", "3m", ("5m", "1m", "15m"), True, False, False, "5m", True),
}


def _classes() -> Dict[str, type]:
    from strategies.ember import StrategyEmber
    from strategies.range_lt import StrategyRangeLT
    from strategies.rocket import StrategyRocket
    from strategies.spark import StrategySpark
    from strategies.supertrend import StrategySupertrend
    from strategies.trend_lt import StrategyTrendLT
    from strategies.waterfall import StrategyWaterfall

    return {
        "supertrend": StrategySupertrend,
        "trend_lt": StrategyTrendLT,
        "range_lt": StrategyRangeLT,
        "rocket": StrategyRocket,
        "waterfall": StrategyWaterfall,
        "spark": StrategySpark,
        "ember": StrategyEmber,
    }


def make_strategy(name: str, config: Mapping[str, Any]):
    cls = _classes()[name]
    strat = cls(config.get(name) or {})
    strat.name = name
    return strat


def warmup_bars(name: str, strategy) -> int:
    if name in ("supertrend", "trend_lt"):
        try:
            ema = int(strategy.get_param("ema_filter_period", 200) or 200)
        except (TypeError, ValueError):
            ema = 200
        return ema + 15
    if name == "range_lt":
        try:
            look = int(strategy.get_param("structure_lookback", 72) or 72)
        except (TypeError, ValueError):
            look = 72
        return look + 20
    return 80


def cooldown_delta(strategy) -> pd.Timedelta:
    try:
        minutes = int(strategy.get_param("cooldown_minutes", 0) or 0)
    except (TypeError, ValueError):
        minutes = 0
    return pd.Timedelta(minutes=max(0, minutes))


def regime_threshold(config: Mapping[str, Any]) -> float:
    params = ((config or {}).get("supertrend") or {}).get("params") or {}
    try:
        return float(params.get("adx_threshold", 22) or 22)
    except (TypeError, ValueError):
        return 22.0


def _align_ts(ts: Any, index: pd.DatetimeIndex) -> pd.Timestamp:
    out = pd.Timestamp(ts)
    idx_tz = getattr(index, "tz", None)
    if idx_tz is not None:
        return out.tz_localize("UTC") if out.tzinfo is None else out.tz_convert(idx_tz)
    if out.tzinfo is not None:
        return out.tz_convert("UTC").tz_localize(None)
    return out


def _empty_diag() -> Dict[str, int]:
    return {
        "decisions": 0,
        "signals": 0,
        "geometry_veto": 0,
        "hard_veto": 0,
        "bb_block": 0,
        "weekend_skips": 0,
        "regime_skips": 0,
        "cooldown_skips": 0,
        "direction_block": 0,
        "invalid_bracket": 0,
        "unresolved": 0,
        "errors": 0,
        "state_updates": 0,
    }


def _add_diag(total: Dict[str, int], part: Mapping[str, int]) -> None:
    for key, value in part.items():
        total[key] = int(total.get(key, 0)) + int(value)


def build_decisions(
    frames: Mapping[str, pd.DataFrame],
    spec: StrategySpec,
    warmup: int,
) -> pd.DatetimeIndex:
    """Decision timestamps: the open of a bar, i.e. the moment the previous bar closed."""
    primary = frames.get(spec.primary)
    if primary is None or primary.empty or len(primary.index) <= warmup:
        return pd.DatetimeIndex([])
    ready = primary.index[warmup]
    step_min = INTERVAL_MS[spec.step] // 60_000
    if spec.step == spec.primary:
        idx = primary.index[warmup:]
    else:
        source = frames.get("1m")
        if source is None or source.empty:
            return pd.DatetimeIndex([])
        keep = [
            ts
            for ts in source.index
            if ts.second == 0
            and ts.microsecond == 0
            and ts.minute % step_min == 0
            and ts >= ready
        ]
        idx = pd.DatetimeIndex(keep)
    if "1m" in spec.required:
        one = frames.get("1m")
        if one is None or one.empty or len(one.index) < 30:
            return pd.DatetimeIndex([])
        idx = idx[idx >= one.index[30]]
    if getattr(idx, "tz", None) is None and getattr(primary.index, "tz", None) is not None:
        idx = idx.tz_localize("UTC")
    return idx


def build_regime_table(df: pd.DataFrame, threshold: float) -> pd.DataFrame:
    """15m regime at each bar open, using only that bar and earlier (engine rules)."""
    from app.services.indicators import ta

    close = df["close"]
    adx = ta.adx(df["high"], df["low"], close, length=14)["ADX"]
    slope = adx - adx.shift(1)
    regime_adx = pd.Series("RANGE", index=df.index, dtype=object)
    regime_adx = regime_adx.mask((adx > float(threshold)) & (slope >= -3), "TREND")
    ema9 = ta.ema(close, length=9)
    ema20 = ta.ema(close, length=20)
    green = close > df["open"]
    red = close < df["open"]
    bull = (close > ema9) & (ema9 > ema20) & green & green.shift(1) & (close > df["high"].shift(1))
    bear = (close < ema9) & (ema9 < ema20) & red & red.shift(1) & (close < df["low"].shift(1))
    bull = bull.fillna(False)
    bear = bear.fillna(False)
    regime = regime_adx.copy()
    regime = regime.mask(bear, "TREND_BEAR_STRONG")
    regime = regime.mask(bull & ~bear, "TREND_BULL_STRONG")
    return pd.DataFrame({"regime": regime, "regime_adx": regime_adx, "adx": adx}, index=df.index)


def build_bb_table(df: pd.DataFrame) -> pd.DataFrame:
    close = df["close"]
    sma = close.rolling(20).mean()
    std = close.rolling(20).std()
    return pd.DataFrame(
        {"close": close, "upper": sma + 2.0 * std, "lower": sma - 2.0 * std},
        index=df.index,
    )


def build_adx_series(df: pd.DataFrame) -> pd.Series:
    from app.services.indicators import ta

    return ta.adx(df["high"], df["low"], df["close"], length=14)["ADX"]


def _confirmed_key(index: pd.DatetimeIndex, t: Any, interval: str):
    cutoff = _align_ts(t, index) - interval_td(interval)
    prior = index[index <= cutoff]
    if len(prior) == 0:
        return None
    return prior[-1]


def lookup_regime(table: Optional[pd.DataFrame], t: Any) -> Tuple[str, str]:
    if table is None or table.empty:
        return "UNKNOWN", "UNKNOWN"
    key = _confirmed_key(table.index, t, "15m")
    if key is None:
        return "UNKNOWN", "UNKNOWN"
    row = table.loc[key]
    return str(row["regime"]), str(row["regime_adx"])


def bb_blocks(table: Optional[pd.DataFrame], side: str, t: Any) -> bool:
    if table is None or table.empty:
        return False
    key = _confirmed_key(table.index, t, "15m")
    if key is None:
        return False
    row = table.loc[key]
    if pd.isna(row["upper"]) or pd.isna(row["lower"]):
        return False
    px = float(row["close"])
    if side == "BUY" and px >= float(row["upper"]) * 0.99:
        return True
    if side == "SELL" and px <= float(row["lower"]) * 1.01:
        return True
    return False


def _adx_value(series: Optional[pd.Series], t: Any, interval: str) -> Optional[float]:
    if series is None or series.empty:
        return None
    key = _confirmed_key(series.index, t, interval)
    if key is None:
        return None
    try:
        value = float(series.loc[key])
    except (TypeError, ValueError):
        return None
    if value != value:
        return None
    return value


def entry_regime(
    spec: StrategySpec,
    strategy,
    regime_15m: str,
    primary_adx: Optional[float],
) -> str:
    if spec.regime_gate:
        return regime_15m or "UNKNOWN"
    if spec.name == "range_lt":
        try:
            cap = float(strategy.get_param("adx_max", 18) or 18)
        except (TypeError, ValueError):
            cap = 18.0
        if primary_adx is None:
            return "UNKNOWN"
        return "RANGE" if primary_adx <= cap else "TREND"
    try:
        thr = float(strategy.get_param("adx_threshold", 18) or 18)
    except (TypeError, ValueError):
        thr = 18.0
    if primary_adx is None:
        return "UNKNOWN"
    return "TREND" if primary_adx >= thr else "RANGE"


def _windows(
    frames: Mapping[str, pd.DataFrame],
    t: Any,
    *,
    context_bars: int,
    trigger_bars: int,
) -> Dict[str, pd.DataFrame]:
    out: Dict[str, pd.DataFrame] = {}
    for key in ("1m", "3m", "5m", "15m", "1h", "4h"):
        frame = frames.get(key)
        if frame is None or getattr(frame, "empty", True):
            continue
        n = trigger_bars if key == "1m" else context_bars
        out[key] = slice_asof(frame, t, n).copy()
    return out


def _indicator_context(df: Optional[pd.DataFrame]) -> Dict[str, Any]:
    from app.services.indicators import ta
    from app.utils.market_metrics import confirmed_volume_ratio_pct

    ctx: Dict[str, Any] = {}
    if df is None or getattr(df, "empty", True) or len(df) < 30:
        return ctx
    closed = df.iloc[:-1] if len(df) >= 2 else df
    tail = closed.tail(250)
    try:
        rsi = ta.rsi(tail["close"], length=14)
        adx = ta.adx(tail["high"], tail["low"], tail["close"], length=14)["ADX"]
        macd = ta.macd(tail["close"])
        ctx["current_price"] = float(tail["close"].iloc[-1])
        ctx["rsi"] = float(rsi.iloc[-1])
        ctx["rsi_val"] = ctx["rsi"]
        ctx["adx"] = float(adx.iloc[-1])
        ctx["adx_val"] = ctx["adx"]
        ctx["macd_hist"] = float(macd["MACDh"].iloc[-1])
        if len(rsi) >= 2 and pd.notna(rsi.iloc[-1]) and pd.notna(rsi.iloc[-2]):
            ctx["rsi_slope"] = float(rsi.iloc[-1] - rsi.iloc[-2])
    except (TypeError, ValueError, IndexError, KeyError):
        pass
    try:
        vol = confirmed_volume_ratio_pct(df)
        if vol is not None:
            ctx["volume_ratio"] = float(vol)
    except Exception:
        pass
    return ctx


def _mtf_line(df: Optional[pd.DataFrame], label: str) -> str:
    from app.services.indicators import Indicators

    if df is None or getattr(df, "empty", True) or len(df) < 30:
        return f"{label}: insufficient data"
    idx = -2 if len(df) >= 2 else -1
    close = df["close"]
    ema50 = close.ewm(span=50, adjust=False).mean()
    try:
        price = float(close.iloc[idx])
        ema_val = float(ema50.iloc[idx])
    except (TypeError, ValueError):
        return f"{label}: insufficient data"
    bias = "BULLISH" if price >= ema_val else "BEARISH"
    dist = ((price - ema_val) / ema_val) * 100.0 if ema_val else 0.0
    st_dir = "N/A"
    try:
        st = Indicators.supertrend(df["high"], df["low"], df["close"], period=10, multiplier=3.0)
        direction = int(st["Direction"].iloc[idx])
        st_dir = "BULLISH" if direction > 0 else "BEARISH"
    except Exception:
        pass
    adx_val = 0.0
    try:
        adx_df = Indicators.adx(df["high"], df["low"], df["close"], 14)
        adx_val = float(adx_df["ADX"].iloc[idx])
    except Exception:
        pass
    aligned = "ALIGNED" if bias == st_dir else "MIXED"
    return (
        f"{label}: bias={bias} ST={st_dir} ({aligned}) "
        f"ADX={adx_val:.1f} close_vs_ema50={dist:+.2f}%"
    )


def _funding_asof(funding: Optional[pd.DataFrame], t: Any) -> Optional[float]:
    if funding is None or getattr(funding, "empty", True):
        return None
    ts = _align_ts(t, funding.index)
    prev = funding.loc[:ts]
    if prev.empty:
        return None
    try:
        return float(prev["funding_rate"].iloc[-1])
    except (TypeError, ValueError, KeyError):
        return None


def _allows(strategy, side: str) -> bool:
    if side == "BUY":
        return bool(strategy.get_param("allow_longs", True))
    if side == "SELL":
        return bool(strategy.get_param("allow_shorts", True))
    return False


def _weekend(name: str, config: Mapping[str, Any], t: Any) -> bool:
    ts = pd.Timestamp(t)
    now = ts.to_pydatetime()
    return is_strategy_weekend_paused(name, config, now=now)


def choose_exit_frame(
    frames: Mapping[str, pd.DataFrame],
    entry_time: Any,
    primary: str,
) -> Tuple[str, pd.DataFrame]:
    """Finest cached interval that already exists at the entry (covers the trade forward)."""
    best_name = primary
    best_ms = INTERVAL_MS.get(primary, 10**12)
    entry = pd.Timestamp(entry_time)
    for name, frame in frames.items():
        ms = INTERVAL_MS.get(name)
        if ms is None or frame is None or getattr(frame, "empty", True):
            continue
        first = frame.index[0]
        if _align_ts(entry, frame.index) < first:
            continue
        if ms < best_ms:
            best_name = name
            best_ms = ms
    frame = frames.get(best_name)
    if frame is None or frame.empty:
        raise KeyError(best_name)
    return best_name, frame


def closed_bars_between(
    df: pd.DataFrame,
    entry_time: Any,
    until: Any,
    interval: pd.Timedelta,
    *,
    after_open: Any = None,
) -> pd.DataFrame:
    """
    Bars that opened at or after the fill and that have closed by ``until``.

    ``after_open`` excludes bars already applied (their open time).
    """
    if df is None or df.empty:
        return df.iloc[0:0]
    entry = _align_ts(entry_time, df.index)
    end = _align_ts(until, df.index)
    opens = df.index
    closes = opens + interval
    mask = (opens >= entry) & (closes <= end)
    if after_open is not None:
        mask = mask & (opens > _align_ts(after_open, df.index))
    return df.loc[mask]


def _close_trade(
    position: Mapping[str, Any],
    exit_price: float,
    exit_time: Any,
    reason: str,
    funding: Optional[pd.DataFrame],
    *,
    taker: float,
    slip: float,
) -> ClosedTrade:
    entry = float(position["entry"])
    initial_sl = float(position["initial_sl"])
    side = str(position["side"])
    frac = sl_fraction(entry, initial_sl)
    g = gross_r(side, entry, exit_price, initial_sl)
    net = net_r(g, sl_frac=frac, taker=taker, slip=slip)
    drag, covered = funding_drag_r(side, position["entry_time"], exit_time, frac, funding)
    trailed = abs(float(position["sl"]) - initial_sl) > max(1e-9, abs(entry) * 1e-8)
    if trailed and reason == "sl":
        reason = "sl_trailed"
    return ClosedTrade(
        strategy=str(position["strategy"]),
        symbol=str(position["symbol"]),
        side=side,
        entry_time=position["entry_time"],
        exit_time=exit_time,
        entry=entry,
        exit=float(exit_price),
        initial_sl=initial_sl,
        initial_tp=float(position["initial_tp"]),
        gross_r=float(g),
        net_r=float(net),
        net_r_funding=float(net - drag),
        funding_r=float(drag),
        funding_covered=bool(covered),
        sl_frac=float(frac),
        exit_reason=reason,
        regime=str(position["regime"]),
        bars_held=int(position["bars_held"]),
        exit_tf=str(position["exit_tf"]),
    )


def _manage_close(
    strategy,
    position: Dict[str, Any],
    close_px: float,
    close_t: Any,
    frames: Mapping[str, pd.DataFrame],
    spec: StrategySpec,
    *,
    context_bars: int,
    thesis_minutes: int,
) -> bool:
    """Update the working stop from the bar close. Return True to flatten at this close."""
    trade = position["trade"]
    trade["sl"] = float(position["sl"])
    decision = compute_trailing_decision(trade, float(close_px))
    if decision is not None:
        position["sl"] = float(decision.new_sl)
        trade["sl"] = float(decision.new_sl)
    if not _is_boundary(close_t, thesis_minutes):
        return False
    if not getattr(strategy, "supports_trade_thesis", lambda: False)():
        return False
    thesis_df = slice_asof(frames.get(spec.thesis_tf), close_t, context_bars)
    if thesis_df is None or thesis_df.empty:
        return False
    thesis_df = thesis_df.copy()
    try:
        verdict = strategy.evaluate_trade_thesis(
            trade, float(close_px), df=thesis_df, extra_data=None
        )
        if verdict is not None and hasattr(strategy, "finalize_thesis_verdict"):
            verdict = strategy.finalize_thesis_verdict(trade, float(close_px), thesis_df, verdict)
    except Exception:
        return False
    if verdict is None:
        return False
    prev = trade.get("thesis_status")
    trade["thesis_dead_streak"] = compute_thesis_dead_streak(
        prev,
        verdict.status,
        int(trade.get("thesis_dead_streak") or 0),
    )
    trade["thesis_status"] = verdict.status
    trade["thesis_action"] = verdict.action
    if verdict.action == ACTION_TIGHTEN_SL:
        target = (
            float(verdict.tighten_sl)
            if verdict.tighten_sl is not None
            else break_even_sl(str(trade.get("side") or "BUY"), float(trade.get("entry") or 0))
        )
        if target and should_apply_be_tighten(
            str(trade.get("side") or ""),
            float(trade.get("entry") or 0),
            float(position["sl"]),
            float(target),
        ):
            position["sl"] = float(target)
            trade["sl"] = float(target)
        return False
    return verdict.action in DEAD_FLATTEN_ACTIONS


def _is_boundary(ts: Any, minutes: int) -> bool:
    t = pd.Timestamp(ts)
    if t.second or t.microsecond or getattr(t, "nanosecond", 0):
        return False
    if minutes <= 0:
        return True
    if minutes % (24 * 60) == 0:
        return t.hour == 0 and t.minute == 0
    total = t.hour * 60 + t.minute
    return total % int(minutes) == 0


def advance_position(
    position: Dict[str, Any],
    until: Any,
    frames: Mapping[str, pd.DataFrame],
    strategy,
    spec: StrategySpec,
    funding: Optional[pd.DataFrame],
    *,
    taker: float,
    slip: float,
    context_bars: int,
) -> Optional[ClosedTrade]:
    """Walk exit bars that have closed by ``until``. Stop updates apply to the next bar."""
    interval = interval_td(position["exit_tf"])
    chunk = closed_bars_between(
        position["exit_df"],
        position["entry_time"],
        until,
        interval,
        after_open=position.get("last_open"),
    )
    thesis_minutes = INTERVAL_MS[spec.thesis_tf] // 60_000
    for ts, row in chunk.iterrows():
        position["bars_held"] = int(position["bars_held"]) + 1
        position["last_open"] = ts
        hit = bar_bracket_exit(
            position["side"],
            row["open"],
            row["high"],
            row["low"],
            position["sl"],
            position["initial_tp"],
        )
        close_t = ts + interval
        if hit is not None:
            price, reason = hit
            return _close_trade(
                position, price, close_t, reason, funding, taker=taker, slip=slip
            )
        flat = _manage_close(
            strategy,
            position,
            float(row["close"]),
            close_t,
            frames,
            spec,
            context_bars=context_bars,
            thesis_minutes=thesis_minutes,
        )
        if flat:
            return _close_trade(
                position,
                float(row["close"]),
                close_t,
                "thesis",
                funding,
                taker=taker,
                slip=slip,
            )
    return None


def _signal_at(
    strategy,
    spec: StrategySpec,
    frames: Mapping[str, pd.DataFrame],
    t: Any,
    *,
    symbol: str,
    config: Mapping[str, Any],
    regime_table: Optional[pd.DataFrame],
    context_bars: int,
    trigger_bars: int,
    diag: Dict[str, int],
    take_trade: bool,
) -> Optional[Dict[str, Any]]:
    windows = _windows(frames, t, context_bars=context_bars, trigger_bars=trigger_bars)
    primary = windows.get(spec.primary)
    if primary is None or len(primary) < 2:
        return None
    if spec.name in ("spark", "ember"):
        df = windows.get("15m")
        if df is None or df.empty:
            df = primary
    else:
        df = primary
    regime, regime_adx = lookup_regime(regime_table, t) if regime_table is not None else ("UNKNOWN", "UNKNOWN")
    if spec.regime_gate:
        if regime not in ("TREND", "TREND_BULL_STRONG", "TREND_BEAR_STRONG"):
            if take_trade:
                diag["regime_skips"] += 1
            return None
    extra = dict(windows)
    extra["symbol"] = symbol
    extra["regime"] = regime
    extra["regime_adx"] = regime_adx if regime_adx in ("TREND", "RANGE") else "RANGE"
    try:
        extra["regime_adx_threshold"] = float(
            regime_threshold(config)
        )
    except (TypeError, ValueError):
        extra["regime_adx_threshold"] = 22.0
    try:
        sig = strategy.generate_signal(df, extra_data=extra)
    except Exception:
        diag["errors"] += 1
        return None
    if not isinstance(sig, dict):
        return None
    side = str(sig.get("signal") or "")
    if side not in ("BUY", "SELL"):
        return None
    if not take_trade:
        diag["state_updates"] += 1
        return None
    diag["signals"] += 1
    if not _allows(strategy, side):
        diag["direction_block"] += 1
        return None
    try:
        price = float(sig["price"])
        sl = float(sig["sl"])
        tp = float(sig["tp"])
    except (KeyError, TypeError, ValueError):
        diag["invalid_bracket"] += 1
        return None
    geo_df = primary
    if hasattr(strategy, "pre_ai_geometry_veto"):
        try:
            ctx = strategy.geometry_context_from_df(geo_df) if hasattr(strategy, "geometry_context_from_df") else {}
            adjusted, reason = strategy.pre_ai_geometry_veto(dict(sig), ctx)
        except Exception:
            diag["errors"] += 1
            return None
        if reason:
            diag["geometry_veto"] += 1
            return None
        if isinstance(adjusted, dict):
            for key in ("price", "sl", "tp"):
                if adjusted.get(key) is not None:
                    sig[key] = adjusted[key]
            try:
                price = float(sig["price"])
                sl = float(sig["sl"])
                tp = float(sig["tp"])
            except (KeyError, TypeError, ValueError):
                diag["invalid_bracket"] += 1
                return None
    if not valid_bracket(side, price, sl, tp):
        diag["invalid_bracket"] += 1
        return None
    if spec.bb_filter and bb_blocks(frames.get("_bb"), side, t):
        diag["bb_block"] += 1
        return None
    veto_ctx = _indicator_context(geo_df)
    veto_ctx["strong_trend"] = bool(sig.get("strong_trend"))
    rate = _funding_asof(frames.get("funding") if isinstance(frames.get("funding"), pd.DataFrame) else None, t)
    if rate is not None:
        veto_ctx["funding_rate"] = rate
        veto_ctx["funding"] = rate
    if spec.mtf:
        line_1h = _mtf_line(windows.get("1h"), "1h")
        line_4h = _mtf_line(windows.get("4h"), "4h")
        veto_ctx["mtf_sentiment"] = f"{line_1h} | {line_4h}"
    if hasattr(strategy, "check_hard_veto"):
        try:
            veto = strategy.check_hard_veto(side, veto_ctx)
        except Exception:
            diag["errors"] += 1
            return None
        if veto:
            diag["hard_veto"] += 1
            return None
    sig["price"] = price
    sig["sl"] = sl
    sig["tp"] = tp
    sig["signal"] = side
    return sig


def replay_symbol(
    strategy,
    spec: StrategySpec,
    symbol: str,
    frames: Mapping[str, pd.DataFrame],
    config: Mapping[str, Any],
    *,
    funding: Optional[pd.DataFrame] = None,
    regime_table: Optional[pd.DataFrame] = None,
    bb_table: Optional[pd.DataFrame] = None,
    primary_adx: Optional[pd.Series] = None,
    context_bars: int = 300,
    trigger_bars: int = 120,
    taker: float = TAKER_FEE,
    slip: float = DEFAULT_SLIP_FRAC,
    verbose: bool = False,
    warmup: Optional[int] = None,
) -> Tuple[List[ClosedTrade], Dict[str, int], Optional[pd.Timestamp], Optional[pd.Timestamp]]:
    """
    Replay one strategy on one symbol.

    Returns trades, diagnostic counters, and the decision span actually scanned.
    """
    diag = _empty_diag()
    missing = [
        tf
        for tf in spec.required
        if frames.get(tf) is None or getattr(frames.get(tf), "empty", True)
    ]
    if missing:
        diag["errors"] += 1
        return [], diag, None, None
    warmup = warmup_bars(spec.name, strategy) if warmup is None else int(warmup)
    need = max(int(context_bars), warmup + 2)
    decisions = build_decisions(frames, spec, warmup)
    if len(decisions) == 0:
        return [], diag, None, None
    bundled = dict(frames)
    if bb_table is not None:
        bundled["_bb"] = bb_table
    if funding is not None:
        bundled["funding"] = funding
    position: Optional[Dict[str, Any]] = None
    trades: List[ClosedTrade] = []
    cooldown_until: Optional[pd.Timestamp] = None
    cool = cooldown_delta(strategy)
    span_start = pd.Timestamp(decisions[0])
    span_end = pd.Timestamp(decisions[-1])

    def _open(sig: Mapping[str, Any], t: pd.Timestamp) -> Optional[Dict[str, Any]]:
        try:
            exit_tf, exit_df = choose_exit_frame(frames, t, spec.primary)
        except KeyError:
            diag["unresolved"] += 1
            return None
        interval = interval_td(exit_tf)
        forward = closed_bars_between(exit_df, t, exit_df.index[-1] + interval, interval)
        if forward.empty:
            diag["unresolved"] += 1
            return None
        side = str(sig["signal"])
        price = float(sig["price"])
        sl = float(sig["sl"])
        tp = float(sig["tp"])
        meta = {}
        for key in PLAN_META_KEYS:
            if sig.get(key) is not None:
                meta[key] = sig[key]
        trade = {
            "side": side,
            "entry": price,
            "entry_price": price,
            "sl": sl,
            "tp": tp,
            "initial_sl": sl,
            "strategy": spec.name,
            "symbol": symbol,
            "metadata": meta,
            "strong_trend": bool(sig.get("strong_trend")),
        }
        freeze_initial_sl(trade, sl)
        regime_15, _adx_reg = lookup_regime(regime_table, t)
        adx_now = _adx_value(primary_adx, t, spec.primary)
        return {
            "strategy": spec.name,
            "symbol": symbol,
            "side": side,
            "entry": price,
            "sl": sl,
            "initial_sl": sl,
            "initial_tp": tp,
            "entry_time": t,
            "trade": trade,
            "regime": entry_regime(spec, strategy, regime_15, adx_now),
            "bars_held": 0,
            "exit_tf": exit_tf,
            "exit_df": exit_df,
            "last_open": None,
        }

    for raw_t in decisions:
        t = pd.Timestamp(raw_t)
        diag["decisions"] += 1
        if verbose and diag["decisions"] % 500 == 0:
            print(f"[bt] {spec.name} {symbol} decisions={diag['decisions']} trades={len(trades)}")
        if position is not None:
            closed = advance_position(
                position,
                t,
                frames,
                strategy,
                spec,
                funding,
                taker=taker,
                slip=slip,
                context_bars=need,
            )
            if closed is not None:
                trades.append(closed)
                position = None
        paused = _weekend(spec.name, config, t)
        regime_open = True
        if spec.regime_gate:
            regime_now, _ = lookup_regime(regime_table, t)
            regime_open = regime_now in ("TREND", "TREND_BULL_STRONG", "TREND_BEAR_STRONG")
        if position is not None:
            if not paused and regime_open:
                _signal_at(
                    strategy,
                    spec,
                    bundled,
                    t,
                    symbol=symbol,
                    config=config,
                    regime_table=regime_table,
                    context_bars=need,
                    trigger_bars=trigger_bars,
                    diag=diag,
                    take_trade=False,
                )
            continue
        if paused:
            diag["weekend_skips"] += 1
            continue
        if cooldown_until is not None and t < cooldown_until:
            diag["cooldown_skips"] += 1
            continue
        sig = _signal_at(
            strategy,
            spec,
            bundled,
            t,
            symbol=symbol,
            config=config,
            regime_table=regime_table,
            context_bars=need,
            trigger_bars=trigger_bars,
            diag=diag,
            take_trade=True,
        )
        if not sig:
            continue
        opened = _open(sig, t)
        if opened is None:
            continue
        position = opened
        if cool > pd.Timedelta(0):
            cooldown_until = t + cool

    if position is not None:
        interval = interval_td(position["exit_tf"])
        end = position["exit_df"].index[-1] + interval
        closed = advance_position(
            position,
            end,
            frames,
            strategy,
            spec,
            funding,
            taker=taker,
            slip=slip,
            context_bars=need,
        )
        if closed is not None:
            trades.append(closed)
        else:
            last = position["exit_df"].iloc[-1]
            last_open = position["exit_df"].index[-1]
            if _align_ts(last_open, position["exit_df"].index) >= _align_ts(
                position["entry_time"], position["exit_df"].index
            ):
                if position.get("last_open") is None or _align_ts(
                    position["last_open"], position["exit_df"].index
                ) < _align_ts(last_open, position["exit_df"].index):
                    position["bars_held"] = int(position["bars_held"]) + 1
                trades.append(
                    _close_trade(
                        position,
                        float(last["close"]),
                        last_open + interval,
                        "eod",
                        funding,
                        taker=taker,
                        slip=slip,
                    )
                )
    return trades, diag, span_start, span_end


@dataclass
class StrategyReport:
    name: str
    enabled: bool
    optional: bool
    trades: List[ClosedTrade] = field(default_factory=list)
    diagnostics: Dict[str, int] = field(default_factory=_empty_diag)
    span_start: Optional[pd.Timestamp] = None
    span_end: Optional[pd.Timestamp] = None
    blockers: List[str] = field(default_factory=list)
    frame_notes: List[str] = field(default_factory=list)


def _fmt_r(value: Optional[float]) -> str:
    if value is None:
        return "—"
    return f"{value:.3f}"


def _fmt_pct(value: Optional[float]) -> str:
    if value is None:
        return "—"
    return f"{100.0 * value:.1f}%"


def _fmt_pf(stats: TradeStats) -> str:
    if stats.n < 5:
        return "n/a (n<5)"
    if stats.profit_factor is None:
        return "inf (no losses)"
    return f"{stats.profit_factor:.2f}"


def _fmt_days(value: Optional[float]) -> str:
    if value is None:
        return "—"
    return f"{value:.1f}d"


def _stats_row(label: str, stats: TradeStats) -> str:
    return (
        f"| {label} | {stats.n} | {_fmt_pct(stats.hit_rate)} | {_fmt_r(stats.avg_gross_r)} | "
        f"{_fmt_r(stats.avg_net_r)} | {_fmt_r(stats.sum_net_r)} | {_fmt_pf(stats)} | "
        f"{_fmt_r(stats.max_dd_r)} | {_fmt_days(stats.max_tuw_days)} |"
    )


_TABLE_HEADER = (
    "| slice | n | hit rate (net R>0) | avg gross R | avg net R | sum net R | "
    "profit factor | max DD (R) | max time under water |\n"
    "|---|---:|---:|---:|---:|---:|---:|---:|---:|"
)


def render_report(
    reports: Sequence[StrategyReport],
    *,
    symbols: Sequence[str],
    config_path: str,
    taker: float,
    slip: float,
) -> str:
    lines: List[str] = []
    lines.append("# NovaBot per-strategy causal backtest")
    lines.append("")
    lines.append("Params are `data/config/strategies.json` on this branch (based on `main`).")
    lines.append("AI is not replayed. A signal that passes mechanical geometry and `check_hard_veto` is taken.")
    lines.append("")
    lines.append("## Method")
    lines.append("")
    lines.append(
        "- Confirmed bars only. At decision time t the strategy sees bars with open time ≤ t; "
        "the last row is the forming bar and entries use `iloc[-2]`."
    )
    lines.append(
        f"- Costs: taker {taker * 10000:.2f} bp per side + slip {slip * 10000:.2f} bp per fill "
        "(round trip), subtracted in R via `net_r` "
        "(same constants as `app/core/causal_backtest.py`). The fill price is the strategy signal price."
    )
    lines.append(
        "- Funding: hourly Hyperliquid `fundingHistory` when the cache covers the hold, "
        "as an extra R drag (`net_r_funding`). Positive funding is paid by longs."
    )
    lines.append(
        "- Exits: walk the finest candle interval that exists at the entry. "
        "Same-bar SL and TP counts as a stop. A gap through the stop fills at the open. "
        "R-ladder trailing and thesis tightens update the stop for the *next* bar, using the bar close. "
        "Thesis `CLOSE` flattens at that close. Still-open trades at the last bar are marked `eod`."
    )
    lines.append(
        "- One open trade per strategy per symbol. Books are independent across strategies "
        "(no shared `max_positions`, no scanner top-K). This is not a portfolio equity curve."
    )
    lines.append(
        "- `type: trend` plans are idle unless the 15m regime is TREND or a confirmed cascade, "
        "matching `StrategyEngine`. Weekend pause uses the bar time in Europe/Paris."
    )
    lines.append(
        "- Context depth defaults to 300 primary bars and 120 one-minute bars, "
        "in line with the live fetch in `_analyze_symbol_market`."
    )
    lines.append(
        "- Hard veto sees RSI, ADX, MACD histogram, confirmed volume ratio, and funding when present. "
        "Trend LT also gets a 1h/4h MTF line built like `_fetch_mtf_sentiment`. "
        "Missing funding or MTF does not veto (same fallback as live)."
    )
    lines.append(
        "- Official `candleSnapshot` retains only the most recent 5000 candles per interval. "
        "That caps 1m near 3.5 days, 15m near 52 days, and 1h near 208 days. "
        "There is no multi-year OOS sample in this run."
    )
    lines.append("")
    lines.append(f"Symbols (example scanner whitelist, not the live top-K): {', '.join(symbols)}.")
    lines.append(f"Config file: `{config_path}`.")
    lines.append("")
    lines.append("## PR #28")
    lines.append("")
    lines.append(
        "These numbers use **main** params. Draft PR #28 "
        "(`cursor/lt-cascade-trigger-refine-adab`) softens Trend LT / Range LT geometry "
        "and cascade 1m timing. It is not merged here. Re-run this command after that PR lands "
        "if you want the comparison; do not read this report as a test of #28."
    )
    lines.append("")
    lines.append("## Results")
    lines.append("")
    lines.append(_TABLE_HEADER)
    for report in reports:
        label = report.name + ("" if report.enabled else " (disabled)")
        lines.append(_stats_row(label, summarize_trades(report.trades)))
    lines.append("")
    for report in reports:
        stats = summarize_trades(report.trades)
        lines.append(f"### {report.name}")
        lines.append("")
        state = "enabled in strategies.json" if report.enabled else "disabled in strategies.json"
        if report.optional:
            state += "; optional rider"
        lines.append(f"Status: {state}.")
        if report.span_start is not None and report.span_end is not None:
            lines.append(
                f"Decisions scanned: {report.span_start.isoformat()} → {report.span_end.isoformat()}."
            )
        for note in report.frame_notes:
            lines.append(f"- {note}")
        for blocker in report.blockers:
            lines.append(f"- Blocker: {blocker}")
        lines.append("")
        lines.append(sample_size_note(stats.n))
        lines.append("")
        if stats.n:
            lines.append(
                f"Funding covered {stats.n_funding}/{stats.n} trades. "
                f"Avg net R after funding: {_fmt_r(stats.avg_net_r_funding)}. "
                f"EOD marks: {stats.n_eod}."
            )
            exit_counts: Dict[str, int] = {}
            tf_counts: Dict[str, int] = {}
            for trade in report.trades:
                exit_counts[trade.exit_reason] = exit_counts.get(trade.exit_reason, 0) + 1
                tf_counts[trade.exit_tf] = tf_counts.get(trade.exit_tf, 0) + 1
            lines.append(
                "Exit reasons: "
                + ", ".join(f"{k}={v}" for k, v in sorted(exit_counts.items()))
                + ". Exit candles: "
                + ", ".join(f"{k}={v}" for k, v in sorted(tf_counts.items()))
                + "."
            )
            lines.append("")
            lines.append("By symbol")
            lines.append("")
            lines.append(_TABLE_HEADER)
            for key, row in group_stats(report.trades, lambda t: t.symbol):
                lines.append(_stats_row(key, row))
            lines.append("")
            lines.append("By regime at entry")
            lines.append("")
            lines.append(_TABLE_HEADER)
            for key, row in group_stats(report.trades, lambda t: t.regime or "UNKNOWN"):
                lines.append(_stats_row(key, row))
            lines.append("")
            if report.span_start is not None and report.span_end is not None:
                earlier, later, cut = chronological_holdout(
                    report.trades,
                    span_start=report.span_start,
                    span_end=report.span_end,
                )
                lines.append(
                    "Chronological holdout (no refit). "
                    f"Cut at {pd.Timestamp(cut).isoformat()} — last third of the scanned span is the holdout."
                )
                lines.append("")
                lines.append(_TABLE_HEADER)
                lines.append(_stats_row("earlier", earlier))
                lines.append(_stats_row("holdout", later))
                lines.append("")
            lines.append("By entry month")
            lines.append("")
            lines.append(_TABLE_HEADER)
            for key, row in group_stats(
                report.trades,
                lambda t: pd.Timestamp(t.entry_time).strftime("%Y-%m"),
            ):
                lines.append(_stats_row(key, row))
            lines.append("")
        diag = report.diagnostics
        lines.append(
            "Diagnostics: "
            f"decisions={diag.get('decisions', 0)}, signals={diag.get('signals', 0)}, "
            f"hard_veto={diag.get('hard_veto', 0)}, geometry_veto={diag.get('geometry_veto', 0)}, "
            f"bb_block={diag.get('bb_block', 0)}, regime_skips={diag.get('regime_skips', 0)}, "
            f"weekend_skips={diag.get('weekend_skips', 0)}, cooldown_skips={diag.get('cooldown_skips', 0)}, "
            f"direction_block={diag.get('direction_block', 0)}, invalid_bracket={diag.get('invalid_bracket', 0)}, "
            f"unresolved={diag.get('unresolved', 0)}, errors={diag.get('errors', 0)}."
        )
        lines.append("")
    lines.append("## What this does not say")
    lines.append("")
    lines.append(
        "A positive average on a short window is not an edge. "
        "The audit kill lines (profit factor under 1.1 after costs, n under 200, "
        "hit rate under 40% for a 2R trend plan or under 58% for a 1R cascade) "
        "are only meaningful once n is large. Max drawdown here is in R units "
        "assuming 1R risk per trade added when each trade closes, not a percent of account equity."
    )
    lines.append("")
    return "\n".join(lines)


def trades_frame(trades: Sequence[ClosedTrade]) -> pd.DataFrame:
    rows = []
    for trade in trades:
        rows.append(
            {
                "strategy": trade.strategy,
                "symbol": trade.symbol,
                "side": trade.side,
                "entry_time": pd.Timestamp(trade.entry_time).isoformat(),
                "exit_time": pd.Timestamp(trade.exit_time).isoformat(),
                "entry": trade.entry,
                "exit": trade.exit,
                "initial_sl": trade.initial_sl,
                "initial_tp": trade.initial_tp,
                "gross_r": trade.gross_r,
                "net_r": trade.net_r,
                "net_r_funding": trade.net_r_funding,
                "funding_r": trade.funding_r,
                "funding_covered": trade.funding_covered,
                "sl_frac": trade.sl_frac,
                "exit_reason": trade.exit_reason,
                "regime": trade.regime,
                "bars_held": trade.bars_held,
                "exit_tf": trade.exit_tf,
            }
        )
    return pd.DataFrame(rows)


def load_config(path: Path) -> dict:
    with path.open() as handle:
        return json.load(handle)


def select_strategies(
    config: Mapping[str, Any],
    requested: Optional[Sequence[str]],
    *,
    include_disabled: bool,
) -> List[str]:
    if requested:
        unknown = [name for name in requested if name not in SPECS]
        if unknown:
            raise SystemExit(f"unknown strategies: {', '.join(unknown)}")
        return list(requested)
    names = [name for name in FOCUS if (config.get(name) or {}).get("enabled", True)]
    if include_disabled:
        names.extend(OPTIONAL)
    return names


def intervals_for(names: Sequence[str]) -> List[str]:
    needed = set()
    for name in names:
        spec = SPECS[name]
        needed.update(spec.required)
        if spec.regime_gate or spec.bb_filter:
            needed.add("15m")
        if spec.mtf:
            needed.add("1h")
            needed.add("4h")
    order = ["1m", "3m", "5m", "15m", "1h", "4h"]
    return [iv for iv in order if iv in needed]


def run_backtest(
    *,
    symbols: Sequence[str],
    strategies: Sequence[str],
    config: Mapping[str, Any],
    cache_dir: Path,
    fetch: bool,
    days: Optional[float],
    context_bars: int,
    trigger_bars: int,
    taker: float,
    slip: float,
    verbose: bool = True,
) -> List[StrategyReport]:
    intervals = intervals_for(strategies)
    loaded: Dict[str, Dict[str, pd.DataFrame]] = {}
    for symbol in symbols:
        if verbose:
            print(f"[bt] data {symbol} intervals={','.join(intervals)}")
        frames = ensure_symbol_cache(
            symbol,
            intervals,
            cache_dir,
            fetch=fetch,
            days=days,
        )
        loaded[symbol] = frames
    reports: List[StrategyReport] = []
    threshold = regime_threshold(config)
    for name in strategies:
        spec = SPECS[name]
        enabled = bool((config.get(name) or {}).get("enabled", True))
        report = StrategyReport(name=name, enabled=enabled, optional=spec.optional)
        report.diagnostics = _empty_diag()
        for symbol, frames in loaded.items():
            bits = []
            for iv in intervals:
                bits.append(f"{symbol} {iv}: {describe_span(frames.get(iv))}")
            if symbol == symbols[0]:
                report.frame_notes.extend(bits[: len(intervals)])
            missing = [
                tf
                for tf in spec.required
                if frames.get(tf) is None or getattr(frames.get(tf), "empty", True)
            ]
            if missing:
                report.blockers.append(f"{symbol} missing {', '.join(missing)}")
                continue
            regime_table = None
            bb_table = None
            if frames.get("15m") is not None and not frames["15m"].empty and (spec.regime_gate or spec.bb_filter):
                regime_table = build_regime_table(frames["15m"], threshold)
                if spec.bb_filter:
                    bb_table = build_bb_table(frames["15m"])
            primary = frames.get(spec.primary)
            primary_adx = build_adx_series(primary) if primary is not None and not primary.empty else None
            strategy = make_strategy(name, config)
            if verbose:
                print(f"[bt] replay {name} {symbol}")
            trades, diag, span_start, span_end = replay_symbol(
                strategy,
                spec,
                symbol,
                frames,
                config,
                funding=frames.get("funding"),
                regime_table=regime_table,
                bb_table=bb_table,
                primary_adx=primary_adx,
                context_bars=context_bars,
                trigger_bars=trigger_bars,
                taker=taker,
                slip=slip,
                verbose=verbose,
            )
            report.trades.extend(trades)
            _add_diag(report.diagnostics, diag)
            if span_start is not None and (report.span_start is None or span_start < report.span_start):
                report.span_start = span_start
            if span_end is not None and (report.span_end is None or span_end > report.span_end):
                report.span_end = span_end
            if span_start is None:
                report.blockers.append(f"{symbol} produced no decision timestamps (warmup or empty overlap)")
        reports.append(report)
    return reports


def main(argv: Optional[Sequence[str]] = None) -> None:
    parser = argparse.ArgumentParser(description="Causal per-strategy Hyperliquid backtest")
    parser.add_argument("--symbols", nargs="+", default=list(DEFAULT_SYMBOLS))
    parser.add_argument("--strategies", nargs="*", default=None)
    parser.add_argument("--include-disabled", action="store_true")
    parser.add_argument("--config", default="data/config/strategies.json")
    parser.add_argument("--cache-dir", default="data/ohlcv")
    parser.add_argument("--out", default="reports/strategy_backtest.md")
    parser.add_argument("--trades-out", default="reports/strategy_backtest_trades.csv")
    parser.add_argument("--no-fetch", action="store_true")
    parser.add_argument("--days", type=float, default=0.0)
    parser.add_argument("--context-bars", type=int, default=300)
    parser.add_argument("--trigger-bars", type=int, default=120)
    parser.add_argument("--taker", type=float, default=TAKER_FEE)
    parser.add_argument("--slip", type=float, default=DEFAULT_SLIP_FRAC)
    args = parser.parse_args(argv)
    config_path = Path(args.config)
    config = load_config(config_path)
    names = select_strategies(config, args.strategies, include_disabled=args.include_disabled)
    days = args.days if args.days and args.days > 0 else None
    symbols = [s.upper() for s in args.symbols]
    reports = run_backtest(
        symbols=symbols,
        strategies=names,
        config=config,
        cache_dir=Path(args.cache_dir),
        fetch=not args.no_fetch,
        days=days,
        context_bars=args.context_bars,
        trigger_bars=args.trigger_bars,
        taker=args.taker,
        slip=args.slip,
        verbose=True,
    )
    text = render_report(
        reports,
        symbols=symbols,
        config_path=str(config_path),
        taker=args.taker,
        slip=args.slip,
    )
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text)
    trades = trades_frame([trade for report in reports for trade in report.trades])
    trades_path = Path(args.trades_out)
    trades_path.parent.mkdir(parents=True, exist_ok=True)
    trades.to_csv(trades_path, index=False)
    print(text)
    print(f"[bt] wrote {out} and {trades_path}")


if __name__ == "__main__":
    main()
