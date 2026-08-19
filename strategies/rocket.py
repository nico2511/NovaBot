"""
Rocket — long-only bullish cascade rider (15m detection / 1m entry).

Mirror of waterfall: price > EMA9 > EMA20, consecutive green candles,
higher highs. Enter on the pump, exit when the cascade breaks.
"""
from __future__ import annotations

from typing import Any, Dict, Optional, Tuple

import pandas as pd

from app.services.indicators import ta
from strategies.base import BaseStrategy


def detect_rocket(
    df: pd.DataFrame,
    *,
    use_live: bool = True,
) -> Tuple[bool, Dict[str, float]]:
    """
    Bullish cascade on 15m (mirror of detect_waterfall): live bar by default.

    Returns (active, snapshot) with ema9/ema20/close/prev_high when active.
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


class StrategyRocket(BaseStrategy):
    """
    Rocket long plan (inverse waterfall):
    - Detect bullish cascade on 15m
    - Enter on confirmed 1m green + higher high
    - SL below recent swing / EMA9 buffer; TP via min_rr
    - Thesis: exit when price loses EMA9 or cascade stalls
    """

    AI_PERSONA = """
    CODENAME: "ROCKET RIDER"

    ROLE:
    You validate FAST bullish cascade longs only. Speed matters — do not overthink.

    PRIME DIRECTIVE:
    Approve BUY when the strategy confirmed an active 15m rocket (price > EMA9 > EMA20,
    double green, higher high) with acceptable volume. Momentum continuation, NOT a fade.

    RULES OF ENGAGEMENT:
    1. LONG ONLY — never approve SELL.
    2. APPROVE when cascade is live and R:R meets the risk-profile minimum.
    3. Do NOT reject because price is near the upper Bollinger band — we ride the pump.
    4. Do NOT reject because RSI is high — rockets are overbought by design.
    5. Do NOT reject because SL is below entry (normal for longs).
    6. REJECT if volume_ratio < 40% (WEAK_VOLUME) unless a clear volume spike on the cascade.
    7. REJECT if higher-TF (1h/4h) is strongly bearish AND price lost 1h EMA20.
    8. When cascade evidence is weak or mixed, REJECT — do not rubber-stamp.
    """

    AI_VALIDATION_CRITERIA = """=== VALIDATION CRITERIA (ROCKET) ===
The strategy already confirmed: 15m bullish cascade + 1m entry trigger.
Fast sanity check only — latency-sensitive setup.

APPROVE when ALL of:
1. Signal is BUY (long-only strategy)
2. R:R meets capital risk-profile minimum (after any TP trim)
3. Volume ratio >= 40% OR clear cascade volume spike (> 120%)
4. No obvious 1h bearish breakdown (price below 1h EMA20 with red momentum)

REJECT when ANY of:
- Signal is SELL (wrong direction)
- volume_ratio < 40% without spike (WEAK_VOLUME)
- Computed R:R below profile minimum (BAD_RR)
- Clear 1h counter-trend breakdown against the long

Do NOT reject solely because:
- RSI is overbought (expected on rockets)
- Price is at upper BB (we buy into the pump)
- SL is wider than scalp norms (ATR stops are normal)
- Entry has no pullback (rocket = immediate momentum entry)
"""

    def __init__(self, config=None):
        super().__init__(config)
        self._last_entry_time = None
        self._last_signal_bar = None

    def get_ai_validation_criteria(self) -> Optional[str]:
        return self.AI_VALIDATION_CRITERIA

    def get_min_volume_ratio_pct(self) -> Optional[float]:
        return self._float_param("min_volume_ratio_pct", 40.0)

    def get_rr_epsilon(self) -> float:
        return 0.05

    def _float_param(self, key: str, default: float) -> float:
        raw = self.get_param(key, default)
        if raw is None:
            return float(default)
        try:
            return float(raw)
        except (TypeError, ValueError):
            return float(default)

    def _params_snapshot(self) -> Dict[str, Any]:
        return {
            "min_rr": self._float_param("min_rr", 1.0),
            "sl_atr_mult": self._float_param("sl_atr_mult", 0.5),
            "min_sl_pct": self._float_param("min_sl_pct", 0.4),
            "sl_swing_lookback": int(self.get_param("sl_swing_lookback", 8) or 8),
            "min_volume_ratio_pct": self._float_param("min_volume_ratio_pct", 40.0),
            "cooldown_minutes": int(self.get_param("cooldown_minutes", 10) or 10),
            "require_1m_confirm": bool(self.get_param("require_1m_confirm", True)),
            "veto_rsi_overbought": self._float_param("veto_rsi_overbought", 82.0),
            "volume_spike_pct": self._float_param("volume_spike_pct", 120.0),
        }

    def check_hard_veto(self, signal: str, market_context: dict) -> Optional[str]:
        ctx = market_context or {}
        side = str(signal or "").upper()
        if side == "SELL":
            return "Rocket is long-only (SELL blocked)"

        try:
            rsi = float(ctx.get("rsi_val", ctx.get("rsi")) or 50)
        except (TypeError, ValueError):
            rsi = 50.0
        ceiling = self._float_param("veto_rsi_overbought", 82.0)
        if rsi > ceiling:
            return f"RSI {rsi:.1f} > {ceiling:.0f} — cascade may be exhausted (blow-off top)"

        try:
            vol = float(ctx.get("volume_ratio") or 100)
        except (TypeError, ValueError):
            vol = 100.0
        min_vol = self._float_param("min_volume_ratio_pct", 40.0)
        spike = self._float_param("volume_spike_pct", 120.0)
        if vol < min_vol and vol < spike:
            return f"Volume {vol:.0f}% < {min_vol:.0f}% (no cascade spike)"

        return None

    def get_scan_timeframe(self) -> str:
        return "15m"

    def get_scan_interval_minutes(self) -> float:
        try:
            raw = self.get_param("scan_interval_minutes", None)
            if raw is not None:
                return max(1.0, float(raw))
        except (TypeError, ValueError):
            pass
        return 5.0

    def score_scan_candidate(self, df, *, symbol: str, meta=None):
        active, snap = detect_rocket(df, use_live=True)
        if not active:
            return None

        p = self._params_snapshot()
        work = df.copy()
        if "RSI_14" not in work.columns:
            work["RSI_14"] = ta.rsi(work["close"], length=14)

        rsi = float(work["RSI_14"].iloc[-1]) if len(work) else 50.0
        if rsi > float(p["veto_rsi_overbought"]):
            return None

        vol_ratio_pct = None
        if "volume" in work.columns and len(work) >= 3:
            try:
                vol_now = float(work["volume"].iloc[-1])
                vol_ma = float(work["volume"].iloc[:-1].rolling(50).mean().iloc[-1])
                if vol_ma > 0:
                    vol_ratio_pct = (vol_now / vol_ma) * 100.0
            except Exception:
                vol_ratio_pct = None

        min_vol = float(p["min_volume_ratio_pct"])
        spike = float(p["volume_spike_pct"])
        if vol_ratio_pct is not None and vol_ratio_pct < min_vol and vol_ratio_pct < spike:
            return None

        score = 70.0
        reasons = ["15m rocket cascade live"]
        if vol_ratio_pct is not None:
            score += min(20.0, max(0.0, (vol_ratio_pct - min_vol) * 0.15))
            reasons.append(f"Vol {vol_ratio_pct:.0f}%")
        score += min(10.0, max(0.0, (rsi - 65.0) * 0.2))
        reasons.append(f"RSI {rsi:.1f}")

        return {
            "score": min(100.0, score),
            "bias": "LONG",
            "symbol": symbol,
            "rsi": round(rsi, 1),
            "reasons": reasons,
            "armed": True,
            "timeframe": "15m",
            "rocket_close": snap.get("close"),
            "rocket_ema9": snap.get("ema9"),
        }

    def post_ai_adjust(
        self,
        signal: Dict[str, Any],
        ai_result: Dict[str, Any],
        market_context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        ctx = market_context or {}
        side = str((signal or {}).get("signal") or "").upper()
        if side != "BUY":
            return ai_result

        try:
            entry = float((signal or {}).get("price") or 0)
            swing_high = float(ctx.get("swing_high") or 0)
            adj = (ai_result or {}).get("suggested_adjustments") or {}
            if not isinstance(adj, dict):
                adj = {}
            tp = float(adj.get("tp") or (signal or {}).get("tp") or 0)
            if entry > 0 and tp > 0 and swing_high > entry and tp > swing_high:
                trimmed = swing_high * (1.0 - 0.0005)
                adj = {**adj, "tp": float(trimmed)}
                ai_result = dict(ai_result or {})
                ai_result["suggested_adjustments"] = adj
        except (TypeError, ValueError):
            pass
        return ai_result

    def add_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        if df is None or getattr(df, "empty", True):
            return df
        work = df.copy()
        if "EMA_9" not in work.columns:
            work["EMA_9"] = ta.ema(work["close"], length=9)
        if "EMA_20" not in work.columns:
            work["EMA_20"] = ta.ema(work["close"], length=20)
        if "ATR_14" not in work.columns:
            work["ATR_14"] = ta.atr(work["high"], work["low"], work["close"], length=14)
        if "RSI_14" not in work.columns:
            work["RSI_14"] = ta.rsi(work["close"], length=14)
        return work

    def _build_sl_tp(
        self,
        entry: float,
        df_15m: pd.DataFrame,
        cascade: Dict[str, float],
        p: Dict[str, Any],
    ) -> Tuple[Optional[float], Optional[float]]:
        if entry <= 0:
            return None, None

        lookback = max(3, int(p["sl_swing_lookback"]))
        try:
            swing_low = float(df_15m["low"].iloc[-lookback:].min())
        except Exception:
            swing_low = entry

        atr = float(df_15m["ATR_14"].iloc[-1]) if "ATR_14" in df_15m.columns else 0.0
        ema9 = float(cascade.get("ema9") or df_15m["EMA_9"].iloc[-1])
        atr_buf = atr * float(p["sl_atr_mult"]) if atr > 0 else 0.0
        sl_candidate = min(swing_low, ema9 - atr_buf)

        min_sl_dist = entry * float(p["min_sl_pct"]) / 100.0
        if entry - sl_candidate < min_sl_dist:
            sl_candidate = entry - min_sl_dist

        if sl_candidate >= entry:
            sl_candidate = entry - min_sl_dist

        risk = entry - sl_candidate
        if risk <= 0:
            return None, None

        tp = entry + risk * float(p["min_rr"])
        if tp <= entry:
            return None, None

        return float(sl_candidate), float(tp)

    def _confirm_1m(self, df_1m: pd.DataFrame) -> Tuple[bool, Optional[float]]:
        if df_1m is None or getattr(df_1m, "empty", True) or len(df_1m) < 3:
            return False, None
        last = df_1m.iloc[-2]
        prev = df_1m.iloc[-3]
        try:
            close = float(last["close"])
            open_ = float(last["open"])
            prev_high = float(prev["high"])
        except (TypeError, ValueError):
            return False, None
        if close <= open_ or close <= prev_high:
            return False, None
        return True, close

    def generate_signal(self, df, extra_data=None):
        p = self._params_snapshot()
        extra = extra_data or {}

        if df is None or getattr(df, "empty", True) or len(df) < 50:
            return self._reject("Not enough 15m data for rocket detection")

        df_15m = self.add_indicators(df)
        active, cascade = detect_rocket(df_15m, use_live=True)
        if not active:
            return self._reject("No active 15m rocket cascade")

        try:
            rsi_15m = float(df_15m["RSI_14"].iloc[-1])
        except Exception:
            rsi_15m = 50.0
        if rsi_15m > float(p["veto_rsi_overbought"]):
            return self._reject(
                f"15m RSI {rsi_15m:.1f} > {p['veto_rsi_overbought']:.0f} — cascade exhausted"
            )

        df_1m = extra.get("1m")
        if df_1m is None or getattr(df_1m, "empty", True):
            return self._reject("Missing 1m data for rocket entry")

        if p["require_1m_confirm"]:
            ok_1m, entry = self._confirm_1m(df_1m)
            if not ok_1m or entry is None:
                return self._reject("1m confirm failed — need green candle + higher high")
        else:
            entry = float(df_1m["close"].iloc[-2])

        now_ts = df_1m.index[-2] if len(df_1m) >= 2 else None
        if now_ts is not None and self._same_bar_already_signaled(now_ts):
            return self._reject("Same 1m bar already signaled")

        if not self._cooldown_ok(now_ts, int(p["cooldown_minutes"])):
            return self._reject(f"Fill cooldown {p['cooldown_minutes']}m not elapsed")

        sl, tp = self._build_sl_tp(entry, df_15m, cascade, p)
        if sl is None or tp is None:
            return self._reject("Failed to calculate valid SL/TP for rocket long")

        self._mark_signal_bar(now_ts)
        sl_pct = (entry - sl) / entry * 100.0
        rr = abs(tp - entry) / abs(entry - sl)

        try:
            swing_low = float(df_15m["low"].iloc[-int(p["sl_swing_lookback"]) :].min())
        except Exception:
            swing_low = sl

        return {
            "signal": "BUY",
            "price": float(entry),
            "sl": float(sl),
            "tp": float(tp),
            "cascade_ema9": float(cascade.get("ema9") or 0),
            "cascade_low": float(swing_low),
            "comment": (
                f"Rocket: 15m cascade (price > EMA9 > EMA20, double green, HH). "
                f"1m entry {entry:.6g}, SL {sl_pct:.2f}% below swing, R:R {rr:.2f}"
            ),
        }

    def supports_trade_thesis(self) -> bool:
        return True

    def get_thesis_timeframe(self) -> str:
        return "15m"

    def evaluate_trade_thesis(self, trade, current_price, *, df, extra_data=None):
        from app.core.trade_thesis import evaluate_rocket_thesis

        if df is None or getattr(df, "empty", True) or len(df) < 5:
            return None

        work = self.add_indicators(df)
        meta = trade.get("metadata") or {}
        cascade_low = meta.get("cascade_low")

        last = work.iloc[-1]
        try:
            close = float(last["close"])
            ema9 = float(last["EMA_9"])
            rsi = float(last["RSI_14"])
        except (TypeError, ValueError):
            return None

        try:
            prev = work.iloc[-2]
            prev_low = float(prev["low"])
            prev_close = float(prev["close"])
            prev_open = float(prev["open"])
        except (IndexError, TypeError, ValueError):
            prev_low = prev_close = prev_open = close

        side = str(trade.get("side") or "BUY").upper()
        entry = float(trade.get("entry") or trade.get("entry_price") or 0)

        return evaluate_rocket_thesis(
            side=side,
            entry=entry,
            current_price=float(current_price),
            close_15m=close,
            ema9=ema9,
            rsi=rsi,
            prev_open=prev_open,
            prev_close=prev_close,
            prev_low=prev_low,
            cascade_low=float(cascade_low) if cascade_low is not None else None,
        )
