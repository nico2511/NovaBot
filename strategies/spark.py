"""
Spark — long-only fast bullish cascade rider (5m detection / 1m entry).

Faster sibling of rocket for alt pumps that ignite on 5m before a clean 15m
cascade forms. Same cascade geometry, tighter extension and SL defaults.
"""
from __future__ import annotations

from typing import Any, Dict, Optional, Tuple

import pandas as pd

from app.services.indicators import ta
from strategies.base import BaseStrategy
from strategies.cascade_exhaustion import (
    DEFAULT_RANGE_ADX_MAX,
    DEFAULT_RANGE_RSI_LONG_MIN,
    DEFAULT_STRUCTURE_CLEAR_PCT,
    DEFAULT_WICK_TRAP_CLOSE_EXTREME_PCT,
    DEFAULT_WICK_TRAP_MIN_RATIO,
    at_prior_ceiling,
    check_range_exhaustion_veto,
    unbroken_structure_reason,
    wick_trap_reason_long,
)
from strategies.cascade_rider import (
    DEFAULT_CASCADE_FRESH_BONUS,
    DEFAULT_SPARK_CASCADE_FRESH_BARS_MAX,
    DEFAULT_SPARK_MAX_EXTENSION_ATR,
    DEFAULT_SPARK_SCAN_INTERVAL_ACTIVE_MINUTES,
    active_scan_interval_minutes,
    detect_bull_cascade,
    extension_within_limit,
    score_cascade_scan,
)

detect_spark = detect_bull_cascade


class StrategySpark(BaseStrategy):
    """
    Spark long plan:
    - Detect bullish cascade on 5m
    - Enter on confirmed 1m green + higher high
    - Tighter SL / extension vs rocket — fast alt ignition
    - Thesis: exit when price loses EMA9 or cascade stalls (5m)
    """

    AI_PERSONA = """
    CODENAME: "SPARK RIDER"

    ROLE:
    You validate ULTRA-FAST bullish cascade longs on 5m. Latency is critical.

    PRIME DIRECTIVE:
    Approve BUY when the strategy confirmed an active 5m spark (price > EMA9 > EMA20,
    double green, higher high) with acceptable volume. Early ignition, NOT a 15m rocket fade.

    RULES OF ENGAGEMENT:
    1. LONG ONLY — never approve SELL.
    2. APPROVE when 5m cascade is live and R:R meets the risk-profile minimum.
    3. Do NOT reject because RSI is high in a **trend** — sparks run hot by design.
    4. REJECT range blow-offs: RANGE + weak ADX + (upper BB OR RSI>74) = climax trap.
    5. REJECT if volume_ratio < 120% without a clear cascade spike.
    6. REJECT if volume is dying (vol_slope DROP).
    7. REJECT if entry is into prior swing-high resistance without a clear 5m CLOSE through that level.
       A volume spike at the ceiling is often absorption, not cascade fuel.
    8. REJECT if 1h is strongly bearish AND price lost 1h EMA20.
    9. When evidence is weak, REJECT — do not rubber-stamp a late chase.
    """

    AI_VALIDATION_CRITERIA = """=== VALIDATION CRITERIA (SPARK) ===
The strategy already confirmed: 5m bullish cascade + 1m entry trigger.
Ultra-fast sanity check — latency-sensitive early pump setup.

APPROVE when ALL of:
1. Signal is BUY (long-only strategy)
2. R:R meets capital risk-profile minimum (after any TP trim)
3. Volume ratio >= 120% OR clear cascade volume spike (> 120%)
4. Volume is NOT dying (vol_slope not in hard DROP)
5. Entry is NOT sitting on prior swing resistance — require a clear 5m close-through (volume spike does NOT override)
6. No obvious 1h bearish breakdown (price below 1h EMA20 with red momentum)

REJECT when ANY of:
- Signal is SELL (wrong direction)
- volume_ratio < 120% without spike (WEAK_VOLUME)
- vol_slope strongly negative / volume dying into the move
- Entry pressed into prior swing-high resistance without a clear 5m close breakout
  (volume spike at the ceiling does NOT override)
- Computed R:R below profile minimum (BAD_RR)
- Clear 1h counter-trend breakdown against the long

Do NOT reject solely because:
- RSI is overbought **when regime is TREND and ADX supports momentum**
- Price is at upper BB **in a trending market**
- SL is wider than scalp norms (ATR stops are normal)
- Entry has no pullback (spark = immediate momentum entry)

REJECT range climax traps:
- Regime RANGE + ADX weak + (ABOVE_UPPER BB or RSI > 74) = blow-off top
"""

    def __init__(self, config=None):
        super().__init__(config)
        self.looking_for_entry = False
        self.entry_direction = None
        self._last_entry_time = None
        self._last_signal_bar = None

    def get_ai_validation_criteria(self) -> Optional[str]:
        return self.AI_VALIDATION_CRITERIA

    def get_min_volume_ratio_pct(self) -> Optional[float]:
        return self._float_param("min_volume_ratio_pct", 120.0)

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
            "sl_atr_mult": self._float_param("sl_atr_mult", 0.45),
            "min_sl_pct": self._float_param("min_sl_pct", 0.35),
            "sl_swing_lookback": int(self.get_param("sl_swing_lookback", 6) or 6),
            "min_volume_ratio_pct": self._float_param("min_volume_ratio_pct", 120.0),
            "volume_spike_pct": self._float_param("volume_spike_pct", 120.0),
            "cooldown_minutes": int(self.get_param("cooldown_minutes", 7) or 7),
            "require_1m_confirm": bool(self.get_param("require_1m_confirm", True)),
            "veto_rsi_overbought": self._float_param("veto_rsi_overbought", 74.0),
            "veto_vol_slope_min": self._float_param("veto_vol_slope_min", -30.0),
            "ceiling_proximity_pct": self._float_param("ceiling_proximity_pct", 0.35),
            "breakout_clear_pct": self._float_param("breakout_clear_pct", DEFAULT_STRUCTURE_CLEAR_PCT),
            "struct_lookback": int(self.get_param("struct_lookback", 48) or 48),
            "struct_exclude_bars": int(self.get_param("struct_exclude_bars", 3) or 3),
            "range_exhaustion_enabled": bool(self.get_param("range_exhaustion_enabled", True)),
            "range_adx_max": self._float_param("range_adx_max", DEFAULT_RANGE_ADX_MAX),
            "range_rsi_long_min": self._float_param("range_rsi_long_min", DEFAULT_RANGE_RSI_LONG_MIN),
            "wick_trap_min_ratio": self._float_param("wick_trap_min_ratio", DEFAULT_WICK_TRAP_MIN_RATIO),
            "wick_trap_close_extreme_pct": self._float_param(
                "wick_trap_close_extreme_pct", DEFAULT_WICK_TRAP_CLOSE_EXTREME_PCT
            ),
            "max_extension_atr": self._float_param("max_extension_atr", DEFAULT_SPARK_MAX_EXTENSION_ATR),
            "extension_ema_period": int(self.get_param("extension_ema_period", 9) or 9),
            "cascade_fresh_bars_max": int(
                self.get_param("cascade_fresh_bars_max", DEFAULT_SPARK_CASCADE_FRESH_BARS_MAX)
                or DEFAULT_SPARK_CASCADE_FRESH_BARS_MAX
            ),
            "cascade_fresh_bonus": self._float_param("cascade_fresh_bonus", DEFAULT_CASCADE_FRESH_BONUS),
            "scan_interval_active_minutes": self._float_param(
                "scan_interval_active_minutes", DEFAULT_SPARK_SCAN_INTERVAL_ACTIVE_MINUTES
            ),
            "scan_score_use_confirmed_bar": bool(
                self.get_param("scan_score_use_confirmed_bar", True)
            ),
        }

    @staticmethod
    def _vol_slope_from_df(df: pd.DataFrame) -> Optional[float]:
        if df is None or getattr(df, "empty", True) or "volume" not in df.columns or len(df) < 3:
            return None
        try:
            curr = float(df["volume"].iloc[-2])
            prev = float(df["volume"].iloc[-3])
            if prev <= 0:
                return 0.0 if curr == 0 else 100.0
            return ((curr - prev) / prev) * 100.0
        except (TypeError, ValueError, IndexError):
            return None

    def _prior_structure_high(self, df: pd.DataFrame, p: Dict[str, Any]) -> Optional[float]:
        excl = max(1, int(p["struct_exclude_bars"]))
        look = max(excl + 2, int(p["struct_lookback"]))
        if df is None or getattr(df, "empty", True) or len(df) < look + excl:
            return None
        try:
            return float(df["high"].iloc[-(look + excl) : -excl].max())
        except (TypeError, ValueError):
            return None

    def _at_prior_ceiling(
        self, entry: float, prior_high: float, p: Dict[str, Any]
    ) -> bool:
        return at_prior_ceiling(
            entry,
            prior_high,
            float(p["ceiling_proximity_pct"]),
            float(p["breakout_clear_pct"]),
        )

    def check_hard_veto(self, signal: str, market_context: dict) -> Optional[str]:
        ctx = market_context or {}
        side = str(signal or "").upper()
        if side == "SELL":
            return "Spark is long-only (SELL blocked)"

        try:
            rsi = float(ctx.get("rsi_val", ctx.get("rsi")) or 50)
        except (TypeError, ValueError):
            rsi = 50.0
        ceiling = self._float_param("veto_rsi_overbought", 74.0)
        if rsi > ceiling:
            return f"RSI {rsi:.1f} > {ceiling:.0f} — 5m spark may be exhausted"

        try:
            vol = float(ctx.get("volume_ratio") or 100)
        except (TypeError, ValueError):
            vol = 100.0
        min_vol = self._float_param("min_volume_ratio_pct", 120.0)
        spike = self._float_param("volume_spike_pct", 120.0)
        if vol < min_vol and vol < spike:
            return f"Volume {vol:.0f}% < {min_vol:.0f}% (no cascade spike)"

        slope_floor = self._float_param("veto_vol_slope_min", -30.0)
        try:
            raw_slope = ctx.get("vol_slope")
            if raw_slope is not None:
                vol_slope = float(raw_slope)
                if vol_slope < slope_floor:
                    return (
                        f"Volume dying (slope {vol_slope:+.1f}% < {slope_floor:.0f}%) "
                        "— no fuel for spark continuation"
                    )
        except (TypeError, ValueError):
            pass

        if bool(self.get_param("range_exhaustion_enabled", True)):
            reason = check_range_exhaustion_veto(
                side,
                ctx,
                adx_max=self._float_param("range_adx_max", DEFAULT_RANGE_ADX_MAX),
                rsi_long_min=self._float_param("range_rsi_long_min", DEFAULT_RANGE_RSI_LONG_MIN),
            )
            if reason:
                return reason

        return None

    def get_scan_timeframe(self) -> str:
        return "5m"

    def get_scan_interval_minutes(
        self,
        *,
        scan_context: Optional[Dict[str, Any]] = None,
    ) -> float:
        p = self._params_snapshot()
        try:
            raw = self.get_param("scan_interval_minutes", None)
            base = max(1.0, float(raw)) if raw is not None else 3.0
        except (TypeError, ValueError):
            base = 3.0
        ctx = scan_context or {}
        return active_scan_interval_minutes(
            base,
            sticky_armed=bool(ctx.get("sticky_armed")),
            scan_interval_active_minutes=float(p["scan_interval_active_minutes"]),
        )

    def score_scan_candidate(self, df, *, symbol: str, meta=None):
        p = self._params_snapshot()
        return score_cascade_scan(
            df,
            side="LONG",
            symbol=symbol,
            detect_fn=detect_spark,
            params=p,
            vol_slope_from_df=self._vol_slope_from_df,
            prior_structure_level=self._prior_structure_high,
            at_prior_level=self._at_prior_ceiling,
            wick_trap_reason=wick_trap_reason_long,
            rsi_veto=lambda rsi, params: rsi > float(params["veto_rsi_overbought"]),
            rsi_score_bonus=lambda rsi: min(10.0, max(0.0, (rsi - 62.0) * 0.2)),
            meta=meta,
            close_key="spark_close",
            ema_key="spark_ema9",
            timeframe=self.get_scan_timeframe(),
        )

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
        df_ctx: pd.DataFrame,
        cascade: Dict[str, float],
        p: Dict[str, Any],
    ) -> Tuple[Optional[float], Optional[float]]:
        if entry <= 0:
            return None, None

        lookback = max(3, int(p["sl_swing_lookback"]))
        try:
            swing_low = float(df_ctx["low"].iloc[-lookback:].min())
        except Exception:
            swing_low = entry

        atr = float(df_ctx["ATR_14"].iloc[-1]) if "ATR_14" in df_ctx.columns else 0.0
        ema9 = float(cascade.get("ema9") or df_ctx["EMA_9"].iloc[-1])
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

        df_5m = extra.get("5m")
        if df_5m is None or getattr(df_5m, "empty", True) or len(df_5m) < 50:
            return self._reject("Not enough 5m data for spark detection")

        df_5m = self.add_indicators(df_5m)
        active, cascade = detect_spark(df_5m, use_live=True)
        if not active:
            self.looking_for_entry = False
            self.entry_direction = None
            return self._reject("No active 5m spark cascade")

        self.entry_direction = "LONG"

        ext_ok, ext_atr = extension_within_limit(
            df_5m,
            "LONG",
            float(p["max_extension_atr"]),
            ema_period=int(p.get("extension_ema_period", 9) or 9),
            use_live=True,
        )
        if not ext_ok:
            self.looking_for_entry = False
            return self._reject(
                f"Extended from 5m EMA{p.get('extension_ema_period', 9)} "
                f"({ext_atr:.2f}x ATR > {p['max_extension_atr']:.1f}x) — late spark"
            )

        try:
            rsi_5m = float(df_5m["RSI_14"].iloc[-1])
        except Exception:
            rsi_5m = 50.0
        if rsi_5m > float(p["veto_rsi_overbought"]):
            self.looking_for_entry = False
            return self._reject(
                f"5m RSI {rsi_5m:.1f} > {p['veto_rsi_overbought']:.0f} — cascade exhausted"
            )

        wick_reason = wick_trap_reason_long(
            df_5m,
            bar_index=-1,
            min_wick_ratio=float(p["wick_trap_min_ratio"]),
            close_extreme_pct=float(p["wick_trap_close_extreme_pct"]),
        )
        if wick_reason:
            self.looking_for_entry = False
            return self._reject(wick_reason)

        df_1m = extra.get("1m")
        if df_1m is None or getattr(df_1m, "empty", True):
            self.looking_for_entry = True
            return self._reject("Missing 1m data for spark entry")

        if p["require_1m_confirm"]:
            ok_1m, entry = self._confirm_1m(df_1m)
            if not ok_1m or entry is None:
                self.looking_for_entry = True
                return self._reject("1m confirm failed — need green candle + higher high")
        else:
            entry = float(df_1m["close"].iloc[-2])

        vol_slope = self._vol_slope_from_df(df_5m)
        if vol_slope is not None and vol_slope < float(p["veto_vol_slope_min"]):
            self.looking_for_entry = False
            return self._reject(
                f"Volume dying (slope {vol_slope:+.1f}% < {p['veto_vol_slope_min']:.0f}%) "
                "— soft cascade, skip spark"
            )

        prior_high = self._prior_structure_high(df_5m, p)
        cascade_close = float(cascade.get("close") or entry)
        structure_reason = unbroken_structure_reason(
            "LONG",
            entry=float(entry),
            cascade_close=cascade_close,
            prior_level=prior_high,
            proximity_pct=float(p["ceiling_proximity_pct"]),
            clear_pct=float(p["breakout_clear_pct"]),
            tf_label="5m",
        )
        if structure_reason:
            self.looking_for_entry = False
            return self._reject(structure_reason)

        now_ts = df_1m.index[-2] if len(df_1m) >= 2 else None
        if now_ts is not None and self._same_bar_already_signaled(now_ts):
            return self._reject("Same 1m bar already signaled")

        if not self._cooldown_ok(now_ts, int(p["cooldown_minutes"])):
            return self._reject(f"Fill cooldown {p['cooldown_minutes']}m not elapsed")

        sl, tp = self._build_sl_tp(entry, df_5m, cascade, p)
        if sl is None or tp is None:
            return self._reject("Failed to calculate valid SL/TP for spark long")

        self._mark_signal_bar(now_ts)
        self.looking_for_entry = False
        sl_pct = (entry - sl) / entry * 100.0
        rr = abs(tp - entry) / abs(entry - sl)

        try:
            swing_low = float(df_5m["low"].iloc[-int(p["sl_swing_lookback"]) :].min())
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
                f"Spark: 5m cascade (price > EMA9 > EMA20, double green, HH). "
                f"1m entry {entry:.6g}, SL {sl_pct:.2f}% below swing, R:R {rr:.2f}"
            ),
        }

    def supports_trade_thesis(self) -> bool:
        return True

    def get_thesis_timeframe(self) -> str:
        return "5m"

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
            rsi_exhaustion=self._float_param("veto_rsi_overbought", 74.0),
            timeframe_label="5m",
        )
