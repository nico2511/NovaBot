"""
Trend LT — longer-horizon trend rider (1h EMA200 + SuperTrend + pullback/reclaim).

Complements SuperTrend 15m (unchanged). Same-symbol concurrency is blocked by
the trade book (HL nets one position per coin).
"""
from __future__ import annotations

import logging

import numpy as np
import pandas as pd

from app.services.indicators import ta
from strategies.base import BaseStrategy

logger = logging.getLogger(__name__)


class StrategyTrendLT(BaseStrategy):
    """
    1h trend setup:
    - Filter: price vs EMA200 + SuperTrend direction on 1h
    - ADX / slope quality on 1h
    - Location: pullback toward 1h ST then reclaim (no mid-impulse chase)
    - SL: 1h SuperTrend widened by ATR / min_sl_pct; TP via min_rr
    """

    AI_PERSONA = """
    CODENAME: "TREND LT SWINGER"

    ROLE:
    You judge LONGER-HORIZON trend continuations on the 1h timeframe.
    Prefer progressive swings over scalp-speed reclaim entries.

    PRIME DIRECTIVE:
    Approve when 1h EMA+SuperTrend bias is clean, ADX is healthy, a pullback
    to the 1h SuperTrend has reclaimed, volume is acceptable, and R:R works.
    Do NOT apply scalping SL width rules.

    RULES OF ENGAGEMENT:
    1. TRADE WITH 1h TREND ONLY (EMA filter + SuperTrend).
    2. ATR/SuperTrend stops of ~2%-8% on 1h perps can be normal — not auto-reject.
    3. Prefer pullback-to-1h-ST then reclaim. Reject mid-impulse chase.
    4. TP should respect local structure (trim to swing when proposed TP is optimistic).
    5. REJECT if volume_ratio < 50% of average (WEAK_VOLUME).
    6. REJECT chase: BUY RSI > 65 or SELL RSI < 35 without volume > 150%.
    7. If MTF 4h clearly fights the 1h signal, REJECT as COUNTER_TREND.
    8. When confluence is mixed, REJECT — do not rubber-stamp.
    """

    AI_VALIDATION_CRITERIA = """=== VALIDATION CRITERIA (TREND LT / 1h) ===
The strategy already confirmed: 1h EMA+SuperTrend bias, ADX/quality filters,
and a 1h pullback-to-ST reclaim. Sanity-check only.

APPROVE when ALL of:
1. Direction aligns with 1h trend / available higher-TF bias
2. R:R meets the capital risk-profile minimum (after any TP trim)
3. Volume ratio >= 50%
4. No clear 4h fight vs signal (if MTF unavailable, ignore HTF)
5. TP is structurally realistic vs Key Levels (trim optimistic breakout TPs)

REJECT when ANY of:
- volume_ratio < 50% (WEAK_VOLUME)
- BUY RSI > 65 or SELL RSI < 35 without volume > 150% (OVEREXTENDED)
- Clear 4h counter-trend
- Computed R:R below profile minimum (BAD_RR)

Do NOT reject solely because SL is wider than scalp norms on a 1h swing."""

    def __init__(self, config=None):
        super().__init__(config)
        self.looking_for_entry = False
        self.entry_direction = None
        self._last_entry_time = None
        self._last_signal_bar = None

    def get_ai_validation_criteria(self):
        return self.AI_VALIDATION_CRITERIA

    def get_min_volume_ratio_pct(self):
        try:
            return float(self.get_param("min_volume_ratio_pct", 50.0) or 50.0)
        except (TypeError, ValueError):
            return 50.0

    def check_hard_veto(self, signal: str, market_context: dict):
        """
        Trend LT 1h hard veto — swing-calibrated (not a blind copy of ST 15m helpers).
        """
        ctx = market_context or {}
        try:
            price = float(ctx.get("current_price") or 0)
            side = str(signal or "").upper()
            rsi = ctx.get("rsi_val", ctx.get("rsi"))
            adx = ctx.get("adx_val", ctx.get("adx"))
            # Wider RSI extremes on 1h swings vs scalp
            rsi_ob = float(self.get_param("veto_rsi_overbought", 85.0) or 85.0)
            rsi_os = float(self.get_param("veto_rsi_oversold", 20.0) or 20.0)
            adx_runaway = float(self.get_param("veto_adx_runaway", 85.0) or 85.0)
            vol_floor = float(self.get_min_volume_ratio_pct() or 50.0)

            if rsi is not None:
                rsi_f = float(rsi)
                if side in ("BUY", "LONG") and rsi_f > rsi_ob:
                    return f"HARD VETO (LT): RSI Overbought ({rsi_f:.1f} > {rsi_ob:.0f}) @ {price:.4f}"
                if side in ("SELL", "SHORT") and rsi_f < rsi_os:
                    return f"HARD VETO (LT): RSI Oversold ({rsi_f:.1f} < {rsi_os:.0f}) @ {price:.4f}"

            if adx is not None and float(adx) > adx_runaway:
                return (
                    f"HARD VETO (LT): ADX Extreme ({float(adx):.1f} > {adx_runaway:.0f}) "
                    f"- 1h runaway @ {price:.4f}"
                )

            vol_ratio = ctx.get("volume_ratio")
            if vol_ratio is None:
                cur = ctx.get("current_volume")
                avg = ctx.get("avg_volume")
                if cur and avg and float(avg) > 0:
                    vol_ratio = (float(cur) / float(avg)) * 100.0
            try:
                vol_f = float(vol_ratio) if vol_ratio is not None else None
            except (TypeError, ValueError):
                vol_f = None
            if vol_f is not None and vol_f > 0.5 and vol_f < vol_floor:
                return f"HARD VETO (LT): Low Volume ({vol_f:.1f}% < {vol_floor:.0f}%) @ {price:.4f}"
            return None
        except Exception as e:
            logger.warning("Trend LT veto error: %s", e)
            return None

    def get_scan_timeframe(self) -> str:
        return "1h"

    def get_scan_interval_minutes(self) -> float:
        try:
            raw = self.get_param("scan_interval_minutes", None)
            if raw is not None:
                return max(1.0, float(raw))
        except (TypeError, ValueError):
            pass
        return 60.0

    def score_scan_candidate(self, df, *, symbol: str, meta=None):
        """
        Rank a 1h OHLCV frame for Trend LT context quality (no full entry trigger).
        """
        p = self._params_snapshot()
        period = int(p["st_period"])
        multiplier = float(p["st_multiplier"])
        ema_len = int(p["ema_filter"])
        adx_threshold = float(p["adx_threshold"])
        min_vol_pct = float(p["min_volume_ratio_pct"])
        max_ext = float(p["max_extension_atr"])
        min_slope = float(p["min_adx_slope"])

        min_bars = max(ema_len + 10, period + 30, 60)
        if df is None or getattr(df, "empty", True) or len(df) < min_bars:
            return None

        work = self.add_indicators(df, p)
        last = work.iloc[-2]
        close = float(last["close"])
        ema = float(last["EMA_200"])
        adx = float(last["ADX_14"])
        st_dir = int(last["ST_Direction"])
        st_line = float(last["Supertrend"])
        atr = float(last["ATR_14"]) if not np.isnan(last["ATR_14"]) else 0.0
        rsi = float(last["RSI_14"]) if not np.isnan(float(last["RSI_14"])) else 50.0

        if any(np.isnan(x) for x in (close, ema, adx, st_line)):
            return None
        if adx < adx_threshold:
            return None

        try:
            adx_prev = float(work["ADX_14"].iloc[-3])
            adx_slope = adx - adx_prev
        except Exception:
            adx_slope = 0.0
        if adx_slope < min_slope:
            return None

        if close > ema and st_dir == 1:
            bias = "LONG"
            trend = "UP"
        elif close < ema and st_dir == -1:
            bias = "SHORT"
            trend = "DOWN"
        else:
            return None

        if atr > 0:
            extension_atr = abs(close - st_line) / atr
            if extension_atr > max_ext:
                return None
        else:
            extension_atr = 99.0

        vol_ratio_pct = None
        if "volume" in work.columns:
            try:
                vol_now = float(work["volume"].iloc[-2])
                vol_ma = float(work["volume"].iloc[:-1].rolling(50).mean().iloc[-2])
                if vol_ma > 0:
                    vol_ratio_pct = (vol_now / vol_ma) * 100.0
            except Exception:
                vol_ratio_pct = None

        if vol_ratio_pct is not None and vol_ratio_pct < min_vol_pct:
            return None

        reasons = []
        score = 0.0
        adx_edge = max(0.0, adx - adx_threshold)
        score += min(40.0, 20.0 + adx_edge * 2.0)
        reasons.append(f"1h ADX {adx:.1f} (slope {adx_slope:+.2f})")
        score += 30.0
        reasons.append(f"1h {bias}: EMA{ema_len} + ST")

        if vol_ratio_pct is None:
            score += 5.0
        else:
            score += min(15.0, 8.0 + (vol_ratio_pct - min_vol_pct) * 0.05)
            reasons.append(f"Vol {vol_ratio_pct:.0f}% of MA50")

        # Prefer progressive RSI (not chase extremes on 1h scan)
        max_rsi_long = float(p["max_rsi_long"])
        min_rsi_short = float(p["min_rsi_short"])
        if bias == "LONG" and rsi <= max_rsi_long:
            score += 10.0
            reasons.append(f"RSI {rsi:.0f} ≤ chase cap {max_rsi_long:.0f}")
        elif bias == "SHORT" and rsi >= min_rsi_short:
            score += 10.0
            reasons.append(f"RSI {rsi:.0f} ≥ chase floor {min_rsi_short:.0f}")
        else:
            score += 2.0
            reasons.append(f"RSI {rsi:.0f} near chase edge")

        if extension_atr <= 1.0:
            score += 15.0
            reasons.append(f"Pullback zone ({extension_atr:.2f}x ATR)")
        elif extension_atr <= 1.5:
            score += 10.0
            reasons.append(f"Near 1h ST ({extension_atr:.2f}x ATR)")
        else:
            score += 4.0
            reasons.append(f"Acceptable extension ({extension_atr:.2f}x ATR)")

        score = float(min(100.0, round(score, 1)))
        market = meta or {}
        return {
            "symbol": symbol or market.get("symbol"),
            "strategy": getattr(self, "name", "trend_lt"),
            "score": score,
            "bias": bias,
            "trend": trend,
            "adx": round(adx, 2),
            "adx_slope": round(adx_slope, 2),
            "rsi": round(rsi, 2),
            "st_direction": st_dir,
            "ema_filter": round(ema, 8),
            "supertrend": round(st_line, 8),
            "current_price": round(close, 8),
            "volume_ratio_pct": round(vol_ratio_pct, 1) if vol_ratio_pct is not None else None,
            "volume_24h": market.get("volume_24h", 0),
            "open_interest": market.get("open_interest", 0),
            "funding": market.get("funding", 0),
            "momentum_24h": market.get("momentum_24h", 0),
            "reasons": reasons,
            "armed": bool(getattr(self, "looking_for_entry", False)),
            "timeframe": "1h",
        }

    def post_ai_adjust(self, signal, ai_result, market_context=None):
        ctx = market_context or {}
        side = str((signal or {}).get("signal") or "").upper()
        try:
            entry = float((signal or {}).get("price") or 0)
            swing_high = float(ctx.get("swing_high") or 0)
            swing_low = float(ctx.get("swing_low") or 0)
            adj = (ai_result or {}).get("suggested_adjustments") or {}
            if not isinstance(adj, dict):
                adj = {}
            tp = float(adj.get("tp") or (signal or {}).get("tp") or 0)
            trimmed = None
            if side == "BUY" and entry > 0 and tp > 0 and swing_high > entry and tp > swing_high:
                trimmed = swing_high * (1.0 - 0.0005)
            elif side == "SELL" and entry > 0 and tp > 0 and 0 < swing_low < entry and tp < swing_low:
                trimmed = swing_low * (1.0 + 0.0005)
            if trimmed is not None and trimmed > 0:
                adj = {**adj, "tp": float(trimmed)}
                ai_result = dict(ai_result or {})
                ai_result["suggested_adjustments"] = adj
                prev = ai_result.get("reasoning") or ""
                note = (
                    f" TP trimmed to structural swing ({trimmed:.6g}) "
                    f"from mechanical target ({tp:.6g})."
                )
                if "trimmed to structural swing" not in prev:
                    ai_result["reasoning"] = (prev + note).strip()
        except (TypeError, ValueError) as trim_err:
            logger.debug("Trend LT TP trim skipped: %s", trim_err)
        return ai_result

    def _params_snapshot(self):
        return {
            "st_period": int(self.get_param("period", 10)),
            "st_multiplier": float(self.get_param("multiplier", 3.0)),
            "ema_filter": int(self.get_param("ema_filter_period", 200)),
            "adx_threshold": float(self.get_param("adx_threshold", 20)),
            "rr_ratio": float(self.get_param("min_rr", 2.0)),
            "sl_atr_mult": float(self.get_param("sl_atr_mult", 2.0)),
            "cooldown_minutes": int(self.get_param("cooldown_minutes", 60)),
            "min_volume_ratio_pct": float(self.get_param("min_volume_ratio_pct", 50.0)),
            "min_adx_slope": float(self.get_param("min_adx_slope", -0.5)),
            "max_rsi_long": float(self.get_param("max_rsi_long", 65.0)),
            "min_rsi_short": float(self.get_param("min_rsi_short", 35.0)),
            "max_extension_atr": float(self.get_param("max_extension_atr", 2.0)),
            "min_sl_pct": float(self.get_param("min_sl_pct", 1.2)),
            "require_pullback": bool(self.get_param("require_pullback", True)),
            "pullback_lookback": int(self.get_param("pullback_lookback", 12)),
            "pullback_touch_atr": float(self.get_param("pullback_touch_atr", 1.2)),
        }

    def _build_sl_tp(self, side: str, entry: float, st_line: float, atr_val: float, p: dict):
        atr_val = float(atr_val or 0)
        st_line = float(st_line or 0)
        entry = float(entry)
        if entry <= 0 or atr_val <= 0 or np.isnan(atr_val) or np.isnan(st_line):
            return None, None
        min_dist = entry * (float(p["min_sl_pct"]) / 100.0)
        atr_dist = float(p["sl_atr_mult"]) * atr_val
        if side == "LONG":
            atr_sl = entry - atr_dist
            st_sl = st_line if st_line < entry else atr_sl
            sl = min(st_sl, atr_sl, entry - min_dist)
            if sl >= entry:
                sl = entry - max(atr_dist, min_dist)
            risk = entry - sl
            tp = entry + (float(p["rr_ratio"]) * risk)
        else:
            atr_sl = entry + atr_dist
            st_sl = st_line if st_line > entry else atr_sl
            sl = max(st_sl, atr_sl, entry + min_dist)
            if sl <= entry:
                sl = entry + max(atr_dist, min_dist)
            risk = sl - entry
            tp = entry - (float(p["rr_ratio"]) * risk)
        if risk <= 0 or np.isnan(sl) or np.isnan(tp):
            return None, None
        return float(sl), float(tp)

    def _get_timestamp(self, df, iloc_idx: int):
        try:
            ts = df.index[iloc_idx]
            if isinstance(ts, pd.Timestamp):
                return ts
            return pd.to_datetime(ts, errors="coerce")
        except Exception:
            return None

    def _pullback_to_st_ok(
        self,
        df: pd.DataFrame,
        direction: str,
        st_line: float,
        atr: float,
        lookback: int,
        touch_atr: float,
    ) -> bool:
        if atr <= 0 or st_line <= 0 or lookback <= 0:
            return False
        window = df.iloc[-(lookback + 2) : -1]
        if window.empty:
            return False
        band = float(touch_atr) * atr
        if direction == "LONG":
            return bool((window["low"] <= (st_line + band)).any())
        return bool((window["high"] >= (st_line - band)).any())

    def add_indicators(self, df, p=None):
        p = p or self._params_snapshot()
        df = df.copy()
        df["EMA_200"] = ta.ema(df["close"], length=p["ema_filter"])
        df["ADX_14"] = ta.adx(df["high"], df["low"], df["close"])["ADX"]
        st_data = ta.supertrend(
            df["high"], df["low"], df["close"], period=p["st_period"], multiplier=p["st_multiplier"]
        )
        df["Supertrend"] = st_data["Supertrend"]
        df["ST_Direction"] = np.where(df["close"] >= df["Supertrend"], 1, -1)
        df["ATR_14"] = ta.atr(df["high"], df["low"], df["close"], length=14)
        df["RSI_14"] = ta.rsi(df["close"], length=14)
        return df

    def generate_signal(self, df, extra_data=None):
        """
        Primary context is 1h (extra_data['1h']). The engine still passes 15m as `df`
        for regime — LT ignores 15m bars for setup geometry.
        """
        p = self._params_snapshot()
        df_1h = None
        if extra_data and isinstance(extra_data.get("1h"), pd.DataFrame):
            df_1h = extra_data["1h"]
        if df_1h is None or getattr(df_1h, "empty", True):
            return self._reject("Missing 1h data for trend_lt")

        if len(df_1h) < (p["ema_filter"] + 10):
            return self._reject("Not enough 1h candles for trend_lt context")

        df_1h = self.add_indicators(df_1h, p)
        last = df_1h.iloc[-2]
        close = float(last["close"])
        ema_filter = float(last["EMA_200"])
        st_dir = int(last["ST_Direction"])
        adx = float(last["ADX_14"])
        rsi = float(last.get("RSI_14", np.nan))
        atr = float(last.get("ATR_14", 0) or 0)
        st_line = float(last.get("Supertrend", 0) or 0)
        now_ts = self._get_timestamp(df_1h, -2)

        if not self._cooldown_ok(now_ts, p["cooldown_minutes"]):
            return self._reject(f"Cooldown active ({p['cooldown_minutes']}m) — skipping LT entry")

        if self._same_bar_already_signaled(now_ts):
            return self._reject("Already evaluated this bar — waiting for next close")

        if adx < p["adx_threshold"]:
            self.looking_for_entry = False
            return self._reject(f"1h ADX below threshold ({adx:.1f} < {p['adx_threshold']})")

        try:
            adx_prev = float(df_1h["ADX_14"].iloc[-3])
            adx_slope = adx - adx_prev
            if adx_slope < float(p["min_adx_slope"]):
                self.looking_for_entry = False
                return self._reject(
                    f"1h ADX slope dying ({adx_slope:+.2f} < {p['min_adx_slope']:+.2f})"
                )
        except Exception:
            adx_slope = 0.0

        if close > ema_filter and st_dir == 1:
            self.entry_direction = "LONG"
            self.looking_for_entry = True
        elif close < ema_filter and st_dir == -1:
            self.entry_direction = "SHORT"
            self.looking_for_entry = True
        else:
            self.looking_for_entry = False
            return self._reject("1h trend filter not aligned (EMA200 vs 1h SuperTrend line)")

        if not np.isnan(rsi):
            if self.entry_direction == "LONG" and rsi > float(p["max_rsi_long"]):
                self.looking_for_entry = False
                return self._reject(f"Chase filter: 1h RSI {rsi:.1f} > {p['max_rsi_long']:.0f}")
            if self.entry_direction == "SHORT" and rsi < float(p["min_rsi_short"]):
                self.looking_for_entry = False
                return self._reject(f"Chase filter: 1h RSI {rsi:.1f} < {p['min_rsi_short']:.0f}")

        if atr > 0 and st_line > 0:
            extension = abs(close - st_line) / atr
            if extension > float(p["max_extension_atr"]):
                self.looking_for_entry = False
                return self._reject(
                    f"Extended from 1h ST ({extension:.2f}x ATR > {p['max_extension_atr']:.1f}x)"
                )

        if not self.looking_for_entry:
            return self._reject("Not armed for LT entry")

        if p["require_pullback"]:
            if not self._pullback_to_st_ok(
                df_1h,
                self.entry_direction,
                st_line,
                atr,
                p["pullback_lookback"],
                p["pullback_touch_atr"],
            ):
                return self._reject(
                    f"No 1h pullback to ST within {p['pullback_lookback']} bars"
                )

        # Reclaim: confirmed close back on trend side of ST
        if self.entry_direction == "LONG" and close < st_line:
            return self._reject("Pullback not resumed — 1h still below ST")
        if self.entry_direction == "SHORT" and close > st_line:
            return self._reject("Pullback not resumed — 1h still above ST")

        entry = close
        sl, tp = self._build_sl_tp(self.entry_direction, entry, st_line, atr, p)
        if sl is None or tp is None:
            return self._reject("Failed to calculate valid LT SL/TP")

        self.looking_for_entry = False
        self._mark_signal_bar(now_ts)

        side = "BUY" if self.entry_direction == "LONG" else "SELL"
        sl_pct = abs(entry - sl) / entry * 100.0
        return {
            "signal": side,
            "sl": float(sl),
            "tp": float(tp),
            "price": float(entry),
            "comment": (
                f"Trend LT: 1h {self.entry_direction} + pullback-to-ST reclaim. "
                f"ADX: {adx:.1f} (slope {adx_slope:+.2f}), SL {sl_pct:.2f}% via 1h ST/ATR"
            ),
        }

    def supports_trade_thesis(self) -> bool:
        return True

    def get_thesis_timeframe(self) -> str:
        return "1h"

    def evaluate_trade_thesis(self, trade, current_price, *, df, extra_data=None):
        from app.core.trade_thesis import evaluate_supertrend_thesis, thesis_indicators_ready

        if df is None or getattr(df, "empty", True) or len(df) < 50:
            return None

        p = self._params_snapshot()
        ema_need = int(p.get("ema_filter", 200) or 200) + 10
        if len(df) < ema_need:
            return None

        work = self.add_indicators(df, p)

        last_1h = work.iloc[-2]
        adx = float(last_1h.get("ADX_14", 0) or 0)
        try:
            adx_slope = adx - float(work["ADX_14"].iloc[-3])
        except Exception:
            adx_slope = 0.0

        close_1h = float(last_1h.get("close", 0) or 0)
        ema_filter = float(last_1h.get("EMA_200", 0) or 0)
        st_direction = int(last_1h.get("ST_Direction", 0) or 0)
        supertrend = float(last_1h.get("Supertrend", 0) or 0)
        if not thesis_indicators_ready(
            close_15m=close_1h,
            ema_filter=ema_filter,
            st_direction=st_direction,
            supertrend=supertrend,
            adx=adx,
        ):
            return None

        side = str(trade.get("side") or "BUY").upper()
        entry = float(trade.get("entry") or trade.get("entry_price") or 0)
        raw_entry_slope = p.get("min_adx_slope", -0.5)
        try:
            weak_adx_slope = (
                float(raw_entry_slope) if raw_entry_slope is not None else -0.5
            )
        except (TypeError, ValueError):
            weak_adx_slope = -0.5
        dead_adx_slope = min(-1.0, weak_adx_slope - 0.65)

        return evaluate_supertrend_thesis(
            side=side,
            entry=entry,
            current_price=float(current_price),
            close_15m=close_1h,
            ema_filter=ema_filter,
            st_direction=st_direction,
            supertrend=supertrend,
            adx=adx,
            adx_slope=adx_slope,
            adx_threshold=float(p.get("adx_threshold", 20) or 20),
            min_adx_slope=dead_adx_slope,
            weak_adx_slope=weak_adx_slope,
        )
