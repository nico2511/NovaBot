"""
Shared helpers for rocket / waterfall / spark / ember cascade riders.

Centralises extension filters, cascade age, and hybrid scan scoring so bull/bear
and 15m/5m strategies stay symmetric without duplicating métier logic.
"""
from __future__ import annotations

from typing import Any, Callable, Dict, Optional, Tuple

import pandas as pd

from app.services.indicators import ta
from app.core.veto_checker import check_funding_veto, check_macd_momentum_veto
from app.utils.market_metrics import (
    is_missing_volume_ratio,
    volume_ratio_for_gate,
)
from strategies.cascade_exhaustion import (
    DEFAULT_RANGE_ADX_MAX,
    DEFAULT_RANGE_RSI_LONG_MIN,
    DEFAULT_RANGE_RSI_SHORT_MAX,
    check_range_exhaustion_veto,
)

# Entry / regime / SL use the last *closed* bar. Scan may still arm on live.
CASCADE_ENTRY_USE_LIVE = False

DEFAULT_MAX_EXTENSION_ATR = 1.5
DEFAULT_SPARK_MAX_EXTENSION_ATR = 1.5
DEFAULT_EMBER_MAX_EXTENSION_ATR = 1.5
DEFAULT_CASCADE_FRESH_BARS_MAX = 4
DEFAULT_SPARK_CASCADE_FRESH_BARS_MAX = 3
DEFAULT_EMBER_CASCADE_FRESH_BARS_MAX = 3
DEFAULT_CASCADE_FRESH_BONUS = 10.0
# Idle lane: notice a just-closed 15m cascade within ~2 minutes.
# Armed lane: re-check the 1m with-trend guard every minute while waiting.
DEFAULT_SCAN_INTERVAL_MINUTES = 2.0
DEFAULT_SCAN_INTERVAL_ACTIVE_MINUTES = 1.0
# 1m may confirm the micro bar is still with the move, but must not run
# this far past the confirmed 15m close (that was the late-chase fill).
DEFAULT_MAX_1M_CHASE_ATR = 0.35
DEFAULT_SPARK_SCAN_INTERVAL_ACTIVE_MINUTES = 1.5
DEFAULT_EMBER_SCAN_INTERVAL_ACTIVE_MINUTES = 1.5


def detect_bull_cascade(
    df: pd.DataFrame,
    *,
    use_live: bool = True,
) -> Tuple[bool, Dict[str, float]]:
    """
    Bullish cascade: price > EMA9 > EMA20, double green, higher high.

    Shared by rocket (15m) and spark (5m).
    """
    empty: Dict[str, float] = {}
    if df is None or getattr(df, "empty", True) or len(df) < 3:
        return False, empty

    work = df
    if "EMA_9" not in work.columns or "EMA_20" not in work.columns:
        work = work.copy()
        work["EMA_9"] = ta.ema(work["close"], length=9)
        work["EMA_20"] = ta.ema(work["close"], length=20)

    curr_i = -1 if use_live else -2
    prev_i = -2 if use_live else -3

    try:
        curr_close = float(work["close"].iloc[curr_i])
        curr_open = float(work["open"].iloc[curr_i])
        curr_ema9 = float(work["EMA_9"].iloc[curr_i])
        curr_ema20 = float(work["EMA_20"].iloc[curr_i])
        prev_close = float(work["close"].iloc[prev_i])
        prev_open = float(work["open"].iloc[prev_i])
        prev_high = float(work["high"].iloc[prev_i])
    except (IndexError, TypeError, ValueError):
        return False, empty

    is_curr_green = curr_close > curr_open
    is_prev_green = prev_close > prev_open
    active = (
        curr_close > curr_ema9 > curr_ema20
        and is_curr_green
        and is_prev_green
        and curr_close > prev_high
    )
    if not active:
        return False, empty

    return True, {
        "close": curr_close,
        "ema9": curr_ema9,
        "ema20": curr_ema20,
        "prev_high": prev_high,
    }


def detect_bear_cascade(
    df: pd.DataFrame,
    *,
    use_live: bool = True,
) -> Tuple[bool, Dict[str, float]]:
    """
    Bearish cascade: price < EMA9 < EMA20, double red, lower low.

    Shared by waterfall (15m) and ember (5m).
    """
    empty: Dict[str, float] = {}
    if df is None or getattr(df, "empty", True) or len(df) < 3:
        return False, empty

    work = df
    if "EMA_9" not in work.columns or "EMA_20" not in work.columns:
        work = work.copy()
        work["EMA_9"] = ta.ema(work["close"], length=9)
        work["EMA_20"] = ta.ema(work["close"], length=20)

    curr_i = -1 if use_live else -2
    prev_i = -2 if use_live else -3

    try:
        curr_close = float(work["close"].iloc[curr_i])
        curr_open = float(work["open"].iloc[curr_i])
        curr_ema9 = float(work["EMA_9"].iloc[curr_i])
        curr_ema20 = float(work["EMA_20"].iloc[curr_i])
        prev_close = float(work["close"].iloc[prev_i])
        prev_open = float(work["open"].iloc[prev_i])
        prev_low = float(work["low"].iloc[prev_i])
    except (IndexError, TypeError, ValueError):
        return False, empty

    is_curr_red = curr_close < curr_open
    is_prev_red = prev_close < prev_open
    active = (
        curr_close < curr_ema9 < curr_ema20
        and is_curr_red
        and is_prev_red
        and curr_close < prev_low
    )
    if not active:
        return False, empty

    return True, {
        "close": curr_close,
        "ema9": curr_ema9,
        "ema20": curr_ema20,
        "prev_low": prev_low,
    }


def bar_index(*, use_live: bool) -> int:
    return -1 if use_live else -2


def minute_entry_decision(
    df_1m: Optional[pd.DataFrame],
    *,
    side: str,
    confirmed_close: float,
    atr: float,
    max_chase_atr: float,
    require_1m: bool,
) -> Tuple[str, Optional[float], Optional[str]]:
    """
    Entry after a *confirmed* higher-TF cascade (``use_live=False`` stays on).

    Returns ``(status, entry, reason)``:

    - ``enter`` — last closed 1m is still with the cascade and has not run
      more than ``max_chase_atr`` past the confirmed close. Entry is that
      1m close (or the confirmed close when 1m is not required).
    - ``wait`` — 1m missing or against the cascade. Keep the setup armed.
    - ``late`` — 1m already extended past the cap. Disarm; do not chase.

    A 1m higher-high / lower-low is **not** required. That extra break waited
    for the next push and filled late. Both bars are closed; the forming
    candle is never the trigger.
    """
    side_u = str(side or "").upper()
    if side_u not in ("LONG", "SHORT"):
        return "late", None, "Cascade entry side missing"
    if not require_1m:
        if confirmed_close <= 0:
            return "late", None, "Confirmed cascade close missing"
        return "enter", float(confirmed_close), None

    if df_1m is None or getattr(df_1m, "empty", True) or len(df_1m) < 3:
        return "wait", None, "Missing 1m data for cascade entry"

    last = df_1m.iloc[-2]
    try:
        close = float(last["close"])
        open_ = float(last["open"])
    except (TypeError, ValueError):
        return "wait", None, "1m confirm unreadable — waiting for a closed bar"

    with_trend = close > open_ if side_u == "LONG" else close < open_
    if not with_trend:
        color = "green" if side_u == "LONG" else "red"
        return (
            "wait",
            None,
            f"1m confirm failed — need a {color} candle (higher-high not required)",
        )

    chase_cap = float(max_chase_atr)
    if atr > 0 and confirmed_close > 0 and chase_cap >= 0:
        if side_u == "LONG":
            chase = (close - float(confirmed_close)) / float(atr)
        else:
            chase = (float(confirmed_close) - close) / float(atr)
        if chase > chase_cap:
            return (
                "late",
                None,
                (
                    f"1m chased {chase:.2f}x ATR past confirmed close "
                    f"(>{chase_cap:.2f}x) — late cascade"
                ),
            )
    return "enter", close, None


def closed_bars(df: pd.DataFrame) -> pd.DataFrame:
    """OHLCV excluding the forming candle (iloc[:-1])."""
    if df is None or getattr(df, "empty", True):
        return df
    if len(df) >= 2:
        return df.iloc[:-1]
    return df


def thesis_confirmed_rows(work: pd.DataFrame):
    """Last two *closed* rows for in-trade thesis, or (None, None)."""
    if work is None or getattr(work, "empty", True) or len(work) < 3:
        return None, None
    return work.iloc[-2], work.iloc[-3]


def ensure_ema_atr_rsi(work: pd.DataFrame) -> pd.DataFrame:
    """Return a copy with EMA_9/20, ATR_14, RSI_14 when missing."""
    if work is None or getattr(work, "empty", True):
        return work
    out = work
    need_copy = False
    for col, fn in (
        ("EMA_9", lambda w: ta.ema(w["close"], length=9)),
        ("EMA_20", lambda w: ta.ema(w["close"], length=20)),
        ("ATR_14", lambda w: ta.atr(w["high"], w["low"], w["close"], length=14)),
        ("RSI_14", lambda w: ta.rsi(w["close"], length=14)),
    ):
        if col not in out.columns:
            if not need_copy:
                out = work.copy()
                need_copy = True
            out[col] = fn(out)
    return out


def extension_vs_ema_anchor(
    work: pd.DataFrame,
    side: str,
    *,
    ema_period: int = 9,
    use_live: bool = True,
) -> Optional[float]:
    """
    Extension from the cascade anchor EMA in ATR units (default EMA9).

    Rocket: (close - EMA9) / ATR — waterfall: (EMA9 - close) / ATR.
    """
    side_u = str(side or "").upper()
    if work is None or getattr(work, "empty", True):
        return None
    col = "EMA_9" if int(ema_period) == 9 else f"EMA_{int(ema_period)}"
    if col not in work.columns and int(ema_period) == 20 and "EMA_20" in work.columns:
        col = "EMA_20"
    idx = bar_index(use_live=use_live)
    try:
        close = float(work["close"].iloc[idx])
        ema = float(work[col].iloc[idx])
        atr = float(work["ATR_14"].iloc[idx])
    except (IndexError, TypeError, ValueError, KeyError):
        return None
    if atr <= 0:
        return None
    if side_u == "LONG":
        return (close - ema) / atr
    if side_u == "SHORT":
        return (ema - close) / atr
    return None


def extension_vs_ema20(
    work: pd.DataFrame,
    side: str,
    *,
    use_live: bool = True,
) -> Optional[float]:
    """Backward-compatible alias — cascade riders anchor on EMA9."""
    return extension_vs_ema_anchor(work, side, ema_period=9, use_live=use_live)


def extension_within_limit(
    work: pd.DataFrame,
    side: str,
    max_extension_atr: float,
    *,
    ema_period: int = 9,
    use_live: bool = True,
) -> Tuple[bool, Optional[float]]:
    ext = extension_vs_ema_anchor(
        work, side, ema_period=ema_period, use_live=use_live
    )
    if ext is None:
        return True, None
    return ext <= float(max_extension_atr), ext


def cascade_age_bars(
    work: pd.DataFrame,
    side: str,
    *,
    use_live: bool = True,
) -> int:
    """Count consecutive same-color candles ending at the evaluation bar."""
    side_u = str(side or "").upper()
    if work is None or getattr(work, "empty", True) or len(work) < 1:
        return 0
    end = bar_index(use_live=use_live)
    end_abs = len(work) + end if end < 0 else end
    streak = 0
    for i in range(end_abs, -1, -1):
        try:
            close = float(work["close"].iloc[i])
            open_ = float(work["open"].iloc[i])
        except (TypeError, ValueError, IndexError):
            break
        if side_u == "LONG":
            if close > open_:
                streak += 1
            else:
                break
        elif side_u == "SHORT":
            if close < open_:
                streak += 1
            else:
                break
        else:
            break
    return streak


def active_scan_interval_minutes(
    base_interval: float,
    *,
    sticky_armed: bool,
    scan_interval_active_minutes: float,
) -> float:
    """Accelerate lane refresh when a symbol is sticky-armed for 1m entry."""
    if sticky_armed:
        return max(1.0, min(float(base_interval), float(scan_interval_active_minutes)))
    return float(base_interval)


def compare_detection_timeframes(
    df_15m: pd.DataFrame,
    detect_fn: Callable[..., Tuple[bool, Dict[str, float]]],
    *,
    resample_rule: str = "5min",
) -> Dict[str, Any]:
    """
  Lightweight comparison helper for 15m vs resampled detection TF.

  Returns counts of live-bar detections on 15m and on a resampled series.
  Intended for offline analysis / unit tests — not used in the live bot loop.
    """
    if df_15m is None or getattr(df_15m, "empty", True):
        return {
            "bars_15m": 0,
            "bars_resampled": 0,
            "detections_15m_live": 0,
            "detections_resampled_live": 0,
            "resample_rule": resample_rule,
        }

    work = ensure_ema_atr_rsi(df_15m)
    det_15m = 0
    min_bars = 3
    for i in range(min_bars, len(work) + 1):
        slice_df = work.iloc[:i]
        active, _ = detect_fn(slice_df, use_live=True)
        if active:
            det_15m += 1

    resampled = (
        df_15m.resample(resample_rule)
        .agg({"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"})
        .dropna()
    )
    resampled = ensure_ema_atr_rsi(resampled)
    det_rs = 0
    for i in range(min_bars, len(resampled) + 1):
        slice_df = resampled.iloc[:i]
        active, _ = detect_fn(slice_df, use_live=True)
        if active:
            det_rs += 1

    return {
        "bars_15m": len(work),
        "bars_resampled": len(resampled),
        "detections_15m_live": det_15m,
        "detections_resampled_live": det_rs,
        "resample_rule": resample_rule,
    }


def score_cascade_scan(
    df: pd.DataFrame,
    *,
    side: str,
    symbol: str,
    detect_fn: Callable[..., Tuple[bool, Dict[str, float]]],
    params: Dict[str, Any],
    vol_slope_from_df: Callable[[pd.DataFrame], Optional[float]],
    prior_structure_level: Callable[[pd.DataFrame, Dict[str, Any]], Optional[float]],
    at_prior_level: Callable[[float, float, Dict[str, Any]], bool],
    wick_trap_reason: Callable[..., Optional[str]],
    rsi_veto: Callable[[float, Dict[str, Any]], bool],
    rsi_score_bonus: Callable[[float], float],
    meta: Optional[Dict[str, Any]],
    close_key: str,
    ema_key: str,
    timeframe: str = "15m",
) -> Optional[Dict[str, float]]:
    """
    Hybrid scan scorer: live bar arms, confirmed bar gates board score.

    Returns None when the candidate should not appear on the merge board.
    """
    if df is None or getattr(df, "empty", True):
        return None

    sticky_armed = bool(meta and meta.get("sticky_armed"))
    hybrid = bool(params.get("scan_score_use_confirmed_bar", True))

    live_active, live_snap = detect_fn(df, use_live=True)
    confirmed_active, confirmed_snap = (
        detect_fn(df, use_live=False) if hybrid else (live_active, live_snap)
    )

    if not live_active and not sticky_armed:
        return None
    if hybrid and not confirmed_active and not sticky_armed:
        return None

    work = ensure_ema_atr_rsi(df.copy())
    use_confirmed_filters = hybrid and (confirmed_active or sticky_armed)
    filter_live = not use_confirmed_filters

    rsi_idx = bar_index(use_live=filter_live)
    try:
        rsi = float(work["RSI_14"].iloc[rsi_idx])
    except (TypeError, ValueError, IndexError):
        rsi = 50.0
    if rsi_veto(rsi, params):
        return None

    vol_slope = vol_slope_from_df(work)
    if vol_slope is not None and vol_slope < float(params["veto_vol_slope_min"]):
        return None

    vol_ratio_pct = volume_ratio_for_gate(work, live_cascade=bool(live_active))
    min_vol = float(params["min_volume_ratio_pct"])
    spike = float(params["volume_spike_pct"])
    if (
        vol_ratio_pct is not None
        and not is_missing_volume_ratio(vol_ratio_pct)
        and vol_ratio_pct < min_vol
        and vol_ratio_pct < spike
    ):
        return None

    try:
        px = float(work["close"].iloc[bar_index(use_live=filter_live)])
    except Exception:
        px = 0.0

    prior = prior_structure_level(work, params)
    # Volume at a prior shelf is often absorption — it does not override structure.
    if prior is not None and px > 0 and at_prior_level(px, prior, params):
        return None

    wick_idx = bar_index(use_live=filter_live)
    wick_reason = wick_trap_reason(
        work,
        bar_index=wick_idx,
        min_wick_ratio=float(params["wick_trap_min_ratio"]),
        close_extreme_pct=float(params["wick_trap_close_extreme_pct"]),
    )
    if wick_reason:
        return None

    ext_ok, ext_atr = extension_within_limit(
        work,
        side,
        float(params.get("max_extension_atr", DEFAULT_MAX_EXTENSION_ATR)),
        ema_period=int(params.get("extension_ema_period", 9) or 9),
        use_live=filter_live,
    )
    if not ext_ok:
        return None

    snap = confirmed_snap if hybrid and confirmed_active else live_snap
    age = cascade_age_bars(work, side, use_live=filter_live)
    fresh_max = int(params.get("cascade_fresh_bars_max", DEFAULT_CASCADE_FRESH_BARS_MAX))

    score = 70.0
    tf = str(timeframe or "15m")
    reasons = [f"{tf} {side.lower()} cascade" + (" confirmed" if hybrid and confirmed_active else " live")]
    if vol_ratio_pct is not None:
        score += min(20.0, max(0.0, (vol_ratio_pct - min_vol) * 0.15))
        reasons.append(f"Vol {vol_ratio_pct:.0f}%")
    score += rsi_score_bonus(rsi)
    reasons.append(f"RSI {rsi:.1f}")
    if ext_atr is not None:
        reasons.append(f"Ext {ext_atr:.2f}x ATR")
    if age > 0 and age <= fresh_max:
        bonus = float(params.get("cascade_fresh_bonus", DEFAULT_CASCADE_FRESH_BONUS))
        score += bonus
        reasons.append(f"Fresh cascade ({age} bars)")

    if sticky_armed:
        score += 15.0
        reasons.append("Sticky armed near-entry")

    armed = sticky_armed or (live_active and not confirmed_active)

    bias = "LONG" if str(side).upper() == "LONG" else "SHORT"
    return {
        "score": min(100.0, score),
        "bias": bias,
        "symbol": symbol,
        "rsi": round(rsi, 1),
        "reasons": reasons,
        "armed": armed,
        "timeframe": tf,
        close_key: snap.get("close"),
        ema_key: snap.get("ema9"),
        "cascade_age_bars": age,
        "extension_atr": round(ext_atr, 3) if ext_atr is not None else None,
    }


def _resolve_volume_ratio_pct(ctx: Dict[str, Any]) -> Optional[float]:
    """Confirmed volume ratio from context; None when data is incomplete (permissive)."""
    vol_ratio = ctx.get("volume_ratio")
    if vol_ratio is not None:
        try:
            return float(vol_ratio)
        except (TypeError, ValueError):
            pass
    cur = ctx.get("current_volume")
    avg = ctx.get("avg_volume")
    if cur is not None and avg and float(avg) > 0:
        try:
            return (float(cur) / float(avg)) * 100.0
        except (TypeError, ValueError):
            pass
    return None


def cascade_volume_reject_reason(
    df,
    params: Dict[str, Any],
    *,
    live_cascade: bool = True,
) -> Optional[str]:
    """
    Same volume floor as scan + hard veto, evaluated before 1m arm.

    Uses max(confirmed, live) when the cascade is live so a forming spike
    can qualify; a dead confirmed tape cannot arm.
    """
    vol_ratio = volume_ratio_for_gate(df, live_cascade=live_cascade)
    if is_missing_volume_ratio(vol_ratio):
        return None
    min_vol = float(params.get("min_volume_ratio_pct") or 0)
    spike = float(params.get("volume_spike_pct") or min_vol)
    if vol_ratio < min_vol and vol_ratio < spike:
        return f"Volume {vol_ratio:.0f}% < {min_vol:.0f}% (no cascade spike)"
    return None


def check_cascade_hard_veto(
    signal: str,
    market_context: Optional[Dict[str, Any]],
    *,
    direction: str,
    blocked_side_message: str,
    rsi_threshold: float,
    rsi_mode: str,
    exhaustion_message: str,
    min_volume_ratio_pct: float,
    volume_spike_pct: float,
    veto_vol_slope_min: float,
    continuation_label: str,
    range_exhaustion_enabled: bool = True,
    range_adx_max: float = DEFAULT_RANGE_ADX_MAX,
    range_rsi_long_min: float = DEFAULT_RANGE_RSI_LONG_MIN,
    range_rsi_short_max: float = DEFAULT_RANGE_RSI_SHORT_MAX,
    veto_macd_momentum: bool = True,
) -> Optional[str]:
    """
    Shared pre-AI hard veto for rocket / waterfall / spark / ember cascade riders.

    ``direction`` is ``long`` or ``short`` (strategy-owned side filter).
    ``rsi_mode`` is ``above`` (block long when RSI too high) or ``below`` (block short).
    """
    ctx = market_context or {}
    side = str(signal or "").upper()
    direction = str(direction or "").lower()

    if direction == "long" and side == "SELL":
        return blocked_side_message
    if direction == "short" and side == "BUY":
        return blocked_side_message

    try:
        rsi = float(ctx.get("rsi_val", ctx.get("rsi")) or 50)
    except (TypeError, ValueError):
        rsi = 50.0

    if rsi_mode == "above" and rsi > float(rsi_threshold):
        return f"RSI {rsi:.1f} > {rsi_threshold:.0f} — {exhaustion_message}"
    if rsi_mode == "below" and rsi < float(rsi_threshold):
        return f"RSI {rsi:.1f} < {rsi_threshold:.0f} — {exhaustion_message}"

    vol_ratio = _resolve_volume_ratio_pct(ctx)
    min_vol = float(min_volume_ratio_pct)
    spike = float(volume_spike_pct)
    if (
        not is_missing_volume_ratio(vol_ratio)
        and vol_ratio < min_vol
        and vol_ratio < spike
    ):
        return f"Volume {vol_ratio:.0f}% < {min_vol:.0f}% (no cascade spike)"

    slope_floor = float(veto_vol_slope_min)
    try:
        raw_slope = ctx.get("vol_slope")
        if raw_slope is not None:
            vol_slope = float(raw_slope)
            if vol_slope < slope_floor:
                return (
                    f"Volume dying (slope {vol_slope:+.1f}% < {slope_floor:.0f}%) "
                    f"— no fuel for {continuation_label} continuation"
                )
    except (TypeError, ValueError):
        pass

    if range_exhaustion_enabled:
        range_kwargs: Dict[str, Any] = {"adx_max": float(range_adx_max)}
        if direction == "long":
            range_kwargs["rsi_long_min"] = float(range_rsi_long_min)
        else:
            range_kwargs["rsi_short_max"] = float(range_rsi_short_max)
        reason = check_range_exhaustion_veto(side, ctx, **range_kwargs)
        if reason:
            return reason

    if veto_macd_momentum:
        macd_reason = check_macd_momentum_veto(side, ctx)
        if macd_reason:
            return macd_reason

    fund_reason = check_funding_veto(side, ctx)
    if fund_reason:
        return fund_reason

    return None
