"""
Range LT — 1h box fade (mean reversion at range extremes).

Complements Trend LT: when 1h ADX is low and EMA50 is flat, fade a defined
box (rejection at the edge, TP toward the opposite bound). SuperTrend 15m
and Trend LT stay unchanged. Same-symbol concurrency is blocked by the
trade book (HL nets one position per coin).
"""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional, Tuple

import numpy as np
import pandas as pd

from app.services.indicators import ta
from strategies.base import BaseStrategy

logger = logging.getLogger(__name__)


class StrategyRangeLT(BaseStrategy):
    """
    1h range fade:
    - Filter: 1h ADX below ceiling, EMA50 slope flat, Donchian box with touches
    - Location: tag range high/low then close back inside (rejection, not breakout)
    - SL: beyond the box (ATR / min_sl_pct / range-fraction floor)
    - TP: opposite bound (AI may trim toward mid; never beyond the box)
    """

    AI_PERSONA = """
    CODENAME: "RANGE LT BOX FADE"

    ROLE:
    You judge 1h MEAN-REVERSION inside a defined range. You fade extremes
    back toward the opposite bound. You do NOT ride breakouts or trends.

    PRIME DIRECTIVE:
    Approve when a real 1h box is intact (low ADX, flat EMA50, multiple
    touches), price rejected the edge (wick tag + close back inside), volume
    is acceptable, and R:R to the opposite bound works.
    Do NOT apply trend-following SuperTrend/EMA200 continuation rules.
    Do NOT apply scalping SL width rules.

    RULES OF ENGAGEMENT:
    1. FADE THE BOX ONLY. BUY near range low, SELL near range high.
    2. REJECT breakouts: a close outside the box is a failed range, not a fade.
    3. REJECT if 1h ADX is expanding into a trend, or 4h drift clearly fights the fade.
    4. TP must stay inside the box (trim to opposite bound / mid — never a breakout TP).
    5. SL beyond the box is expected (~0.4%-3% on 1h perps) — not auto-reject.
    6. REJECT if volume_ratio < 50% of average (WEAK_VOLUME).
    7. When confluence is mixed, REJECT — do not rubber-stamp a mid-range chase.
    """

    AI_VALIDATION_CRITERIA = """=== VALIDATION CRITERIA (RANGE LT / 1h BOX FADE) ===
The strategy already confirmed: 1h ADX is subdued, EMA50 is flat, a Donchian
box has touches, and the last closed 1h bar rejected an extreme back inside.
Sanity-check only.

APPROVE when ALL of:
1. Direction is a fade (BUY at/near range low, SELL at/near range high)
2. R:R meets the capital risk-profile minimum (after any TP trim)
3. Volume ratio >= 50%
4. No clear 4h fight vs the fade (if MTF unavailable, ignore HTF)
5. TP stays inside the box (trim optimistic breakout TPs to the opposite bound)

REJECT when ANY of:
- volume_ratio < 50% (WEAK_VOLUME)
- Close already outside the box / range clearly broken (BREAKOUT)
- BUY from the upper half or SELL from the lower half (WRONG_SIDE)
- Computed R:R below profile minimum (BAD_RR)
- 1h ADX expanding into a trend (RANGE_DEAD)

Do NOT reject solely because:
- SL is beyond the box (that is the plan)
- RSI is oversold on a BUY fade or overbought on a SELL fade
- SuperTrend / EMA200 do not agree with a trend continuation
"""

    def __init__(self, config=None):
        super().__init__(config)
        self.looking_for_entry = False
        self.entry_direction = None
        self._last_entry_time = None
        self._last_signal_bar = None
        self.last_veto_report = None

    def get_ai_validation_criteria(self):
        return self.AI_VALIDATION_CRITERIA

    def get_min_volume_ratio_pct(self):
        try:
            return float(self.get_param("min_volume_ratio_pct", 50.0) or 50.0)
        except (TypeError, ValueError):
            return 50.0

    def check_hard_veto(self, signal: str, market_context: dict) -> Optional[str]:
        """
        Range LT 1h hard veto — inverted vs trend: do not block oversold BUY
        / overbought SELL fades. Block mid-range chase, ADX expansion, dead volume.

        Always evaluates every check so logs can show PASS vs BLOCK (first tests).
        """
        ctx = market_context or {}
        self.last_veto_report = []
        blocking: list[str] = []
        try:
            price = float(ctx.get("current_price") or 0)
            side = str(signal or "").upper()
            rsi = ctx.get("rsi_val", ctx.get("rsi"))
            adx = ctx.get("adx_val", ctx.get("adx"))
            rsi_long_max = float(self.get_param("veto_rsi_long_max", 58.0) or 58.0)
            rsi_short_min = float(self.get_param("veto_rsi_short_min", 42.0) or 42.0)
            adx_trend = float(self.get_param("veto_adx_trend", 28.0) or 28.0)
            vol_floor = float(self.get_min_volume_ratio_pct() or 50.0)

            if adx is None:
                self.last_veto_report.append({"name": "ADX", "blocked": False, "detail": "n/a"})
            else:
                adx_f = float(adx)
                blocked = adx_f > adx_trend
                self.last_veto_report.append(
                    {
                        "name": "ADX",
                        "blocked": blocked,
                        "detail": f"{adx_f:.1f} {'>' if blocked else '<='} {adx_trend:.0f}",
                    }
                )
                if blocked:
                    blocking.append(
                        f"HARD VETO (RANGE LT): ADX expanding ({adx_f:.1f} > {adx_trend:.0f}) "
                        f"- range likely dead @ {price:.4f}"
                    )

            if rsi is None:
                self.last_veto_report.append({"name": "RSI", "blocked": False, "detail": "n/a"})
            else:
                rsi_f = float(rsi)
                if side in ("BUY", "LONG"):
                    blocked = rsi_f > rsi_long_max
                    detail = f"{rsi_f:.1f} {'>' if blocked else '<='} {rsi_long_max:.0f} (BUY fade)"
                    if blocked:
                        blocking.append(
                            f"HARD VETO (RANGE LT): BUY not at range low "
                            f"(RSI {rsi_f:.1f} > {rsi_long_max:.0f}) @ {price:.4f}"
                        )
                elif side in ("SELL", "SHORT"):
                    blocked = rsi_f < rsi_short_min
                    detail = f"{rsi_f:.1f} {'<' if blocked else '>='} {rsi_short_min:.0f} (SELL fade)"
                    if blocked:
                        blocking.append(
                            f"HARD VETO (RANGE LT): SELL not at range high "
                            f"(RSI {rsi_f:.1f} < {rsi_short_min:.0f}) @ {price:.4f}"
                        )
                else:
                    blocked = False
                    detail = f"{rsi_f:.1f} (side {side or '?'})"
                self.last_veto_report.append({"name": "RSI", "blocked": blocked, "detail": detail})

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
            if vol_f is None:
                self.last_veto_report.append({"name": "VOL", "blocked": False, "detail": "n/a"})
            elif vol_f <= 0.5:
                self.last_veto_report.append(
                    {"name": "VOL", "blocked": False, "detail": f"{vol_f:.1f}% skip (incomplete bar)"}
                )
            else:
                blocked = vol_f < vol_floor
                self.last_veto_report.append(
                    {
                        "name": "VOL",
                        "blocked": blocked,
                        "detail": f"{vol_f:.1f}% {'<' if blocked else '>='} {vol_floor:.0f}%",
                    }
                )
                if blocked:
                    blocking.append(
                        f"HARD VETO (RANGE LT): Low Volume ({vol_f:.1f}% < {vol_floor:.0f}%) @ {price:.4f}"
                    )

            if not bool(self.get_param("log_veto_report", True)):
                self.last_veto_report = None
            return blocking[0] if blocking else None
        except Exception as e:
            logger.warning("Range LT veto error: %s", e)
            self.last_veto_report = None
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
        """Rank a 1h OHLCV frame for range-fade context (no rejection trigger)."""
        p = self._params_snapshot()
        setup = self._evaluate_setup(df, p, require_rejection=False)
        if setup is None:
            return None
        if setup.get("breakout"):
            return None
        bias = setup.get("bias")
        if bias not in ("LONG", "SHORT"):
            return None

        adx = float(setup["adx"])
        loc = float(setup["loc"])
        width_pct = float(setup["width_pct"])
        upper_t = int(setup["upper_touches"])
        lower_t = int(setup["lower_touches"])
        vol_ratio_pct = setup.get("volume_ratio_pct")
        reasons = []
        score = 0.0

        adx_room = max(0.0, float(p["adx_max"]) - adx)
        score += min(30.0, 12.0 + adx_room * 1.5)
        reasons.append(f"1h ADX {adx:.1f} (range ≤ {p['adx_max']:.0f})")

        score += min(25.0, 10.0 + (upper_t + lower_t) * 2.0)
        reasons.append(f"Box touches {lower_t}L/{upper_t}H width {width_pct:.1f}%")

        edge_dist = loc if bias == "LONG" else (1.0 - loc)
        score += min(25.0, 8.0 + (1.0 - edge_dist) * 20.0)
        reasons.append(f"Near {'low' if bias == 'LONG' else 'high'} (loc {loc:.2f})")

        if vol_ratio_pct is None:
            score += 5.0
        else:
            score += min(15.0, 6.0 + (float(vol_ratio_pct) - float(p["min_volume_ratio_pct"])) * 0.05)
            reasons.append(f"Vol {float(vol_ratio_pct):.0f}% of MA50")

        if abs(float(setup.get("ema_slope") or 0)) <= float(p["ema_slope_flat_max"]):
            score += 10.0
            reasons.append("EMA50 flat")
        else:
            score += 2.0

        score = float(min(100.0, round(score, 1)))
        market = meta or {}
        return {
            "symbol": symbol or market.get("symbol"),
            "strategy": getattr(self, "name", "range_lt"),
            "score": score,
            "bias": bias,
            "trend": "RANGE",
            "adx": round(adx, 2),
            "adx_slope": round(float(setup.get("adx_slope") or 0), 2),
            "rsi": round(float(setup.get("rsi") or 50.0), 2),
            "range_high": round(float(setup["range_high"]), 8),
            "range_low": round(float(setup["range_low"]), 8),
            "current_price": round(float(setup["close"]), 8),
            "volume_ratio_pct": round(float(vol_ratio_pct), 1) if vol_ratio_pct is not None else None,
            "volume_24h": market.get("volume_24h", 0),
            "open_interest": market.get("open_interest", 0),
            "funding": market.get("funding", 0),
            "momentum_24h": market.get("momentum_24h", 0),
            "reasons": reasons,
            "armed": bool(getattr(self, "looking_for_entry", False)),
            "timeframe": "1h",
        }

    def post_ai_adjust(self, signal, ai_result, market_context=None):
        """Cap TP at the opposite box bound — never a breakout target."""
        ctx = market_context or {}
        side = str((signal or {}).get("signal") or "").upper()
        try:
            entry = float((signal or {}).get("price") or 0)
            range_high = float((signal or {}).get("range_high") or ctx.get("swing_high") or 0)
            range_low = float((signal or {}).get("range_low") or ctx.get("swing_low") or 0)
            adj = (ai_result or {}).get("suggested_adjustments") or {}
            if not isinstance(adj, dict):
                adj = {}
            tp = float(adj.get("tp") or (signal or {}).get("tp") or 0)
            trimmed = None
            if side == "BUY" and entry > 0 and tp > 0 and range_high > entry and tp > range_high:
                trimmed = range_high * (1.0 - 0.0005)
            elif side == "SELL" and entry > 0 and tp > 0 and 0 < range_low < entry and tp < range_low:
                trimmed = range_low * (1.0 + 0.0005)
            if trimmed is not None and trimmed > 0:
                adj = {**adj, "tp": float(trimmed)}
                ai_result = dict(ai_result or {})
                ai_result["suggested_adjustments"] = adj
                prev = ai_result.get("reasoning") or ""
                note = (
                    f" TP trimmed to opposite range bound ({trimmed:.6g}) "
                    f"from mechanical/breakout target ({tp:.6g})."
                )
                if "opposite range bound" not in prev:
                    ai_result["reasoning"] = (prev + note).strip()
        except (TypeError, ValueError) as trim_err:
            logger.debug("Range LT TP trim skipped: %s", trim_err)
        return ai_result

    def _params_snapshot(self):
        return {
            "lookback": int(self.get_param("lookback", 48)),
            "structure_lookback": int(self.get_param("structure_lookback", 72)),
            "ceiling_expansion_bars": int(self.get_param("ceiling_expansion_bars", 6)),
            "min_touches": int(self.get_param("min_touches", 2)),
            "adx_max": float(self.get_param("adx_max", 18.0)),
            "max_adx_slope": float(self.get_param("max_adx_slope", 0.4)),
            "ema_period": int(self.get_param("ema_period", 50)),
            "ema_slope_flat_max": float(self.get_param("ema_slope_flat_max", 0.0004)),
            "min_range_pct": float(self.get_param("min_range_pct", 2.0)),
            "max_range_pct": float(self.get_param("max_range_pct", 12.0)),
            "touch_atr": float(self.get_param("touch_atr", 0.35)),
            "touch_width_frac": float(self.get_param("touch_width_frac", 0.15)),
            "edge_frac": float(self.get_param("edge_frac", 0.28)),
            "rr_ratio": float(self.get_param("min_rr", 2.0)),
            "sl_atr_mult": float(self.get_param("sl_atr_mult", 0.4)),
            "sl_range_frac": float(self.get_param("sl_range_frac", 0.12)),
            "min_sl_pct": float(self.get_param("min_sl_pct", 0.4)),
            "cooldown_minutes": int(self.get_param("cooldown_minutes", 60)),
            "min_volume_ratio_pct": float(self.get_param("min_volume_ratio_pct", 50.0)),
            "htf_slope_max": float(self.get_param("htf_slope_max", 0.001)),
            "allow_longs": bool(self.get_param("allow_longs", True)),
            "allow_shorts": bool(self.get_param("allow_shorts", True)),
        }

    def add_indicators(self, df, p=None):
        p = p or self._params_snapshot()
        df = df.copy()
        ema_len = int(p["ema_period"])
        df["EMA_50"] = ta.ema(df["close"], length=ema_len)
        df["ADX_14"] = ta.adx(df["high"], df["low"], df["close"])["ADX"]
        df["ATR_14"] = ta.atr(df["high"], df["low"], df["close"], length=14)
        df["RSI_14"] = ta.rsi(df["close"], length=14)
        return df

    def _get_timestamp(self, df, iloc_idx: int):
        try:
            ts = df.index[iloc_idx]
            if isinstance(ts, pd.Timestamp):
                return ts
            return pd.to_datetime(ts, errors="coerce")
        except Exception:
            return None

    def _volume_ratio_pct(self, df) -> Optional[float]:
        if "volume" not in df.columns:
            return None
        try:
            vol_now = float(df["volume"].iloc[-2])
            vol_ma = float(df["volume"].iloc[:-1].rolling(50).mean().iloc[-2])
            if vol_ma > 0:
                return (vol_now / vol_ma) * 100.0
        except Exception:
            return None
        return None

    def _ema_slope(self, series: pd.Series, idx: int = -2) -> float:
        try:
            now = float(series.iloc[idx])
            prev = float(series.iloc[idx - 1])
            if prev > 0 and not np.isnan(now) and not np.isnan(prev):
                return (now - prev) / prev
        except Exception:
            return 0.0
        return 0.0

    def _resample_4h(self, df_1h: pd.DataFrame) -> Optional[pd.DataFrame]:
        if df_1h is None or getattr(df_1h, "empty", True):
            return None
        if not isinstance(df_1h.index, pd.DatetimeIndex):
            return None
        try:
            work = df_1h.copy()
            if work.index.tz is not None:
                work = work.tz_convert("UTC")
            agg = (
                work.resample("4h")
                .agg(
                    {
                        "open": "first",
                        "high": "max",
                        "low": "min",
                        "close": "last",
                        "volume": "sum",
                    }
                )
                .dropna()
            )
            return agg if len(agg) >= 20 else None
        except Exception:
            return None

    def _htf_blocks_fade(self, df_1h: pd.DataFrame, direction: str, p: dict) -> Optional[str]:
        df4 = self._resample_4h(df_1h)
        if df4 is None or len(df4) < 30:
            return None
        try:
            ema = ta.ema(df4["close"], length=int(p["ema_period"]))
            slope = self._ema_slope(ema, -2)
        except Exception:
            return None
        cap = float(p["htf_slope_max"])
        if direction == "SHORT" and slope > cap:
            return f"4h EMA{p['ema_period']} rising ({slope:.5f} > {cap:.5f}) — don't fade highs"
        if direction == "LONG" and slope < -cap:
            return f"4h EMA{p['ema_period']} falling ({slope:.5f} < {-cap:.5f}) — don't fade lows"
        return None

    def _evaluate_setup(
        self, df, p: dict, require_rejection: bool
    ) -> Optional[Dict[str, Any]]:
        lookback = int(p["lookback"])
        struct_lb = max(lookback, int(p.get("structure_lookback", lookback)))
        min_bars = max(struct_lb + 8, int(p["ema_period"]) + 10, 60)
        if df is None or getattr(df, "empty", True) or len(df) < min_bars:
            return None

        work = self.add_indicators(df, p)
        # Drop forming candle; box is built on bars *before* the last confirmed close.
        confirmed = work.iloc[:-1]
        if len(confirmed) < struct_lb + 2:
            return None
        prior = confirmed.iloc[-(struct_lb + 1) : -1]
        last = confirmed.iloc[-1]
        close = float(last["close"])
        bar_high = float(last["high"])
        bar_low = float(last["low"])
        adx = float(last["ADX_14"])
        atr = float(last["ATR_14"]) if not np.isnan(float(last["ATR_14"])) else 0.0
        rsi = float(last["RSI_14"]) if not np.isnan(float(last.get("RSI_14", np.nan))) else 50.0
        ema = float(last["EMA_50"])
        if any(np.isnan(x) for x in (close, adx, ema)) or atr <= 0:
            return None

        try:
            adx_prev = float(confirmed["ADX_14"].iloc[-2])
            adx_slope = adx - adx_prev
        except Exception:
            adx_slope = 0.0
        ema_slope = self._ema_slope(confirmed["EMA_50"], -1)

        range_high = float(prior["high"].max())
        range_low = float(prior["low"].min())
        width = range_high - range_low
        if width <= 0 or range_low <= 0:
            return None
        mid = (range_high + range_low) / 2.0
        width_pct = (width / mid) * 100.0

        if adx > float(p["adx_max"]):
            return None
        if adx_slope > float(p["max_adx_slope"]):
            return None
        if abs(ema_slope) > float(p["ema_slope_flat_max"]):
            return None
        if width_pct < float(p["min_range_pct"]) or width_pct > float(p["max_range_pct"]):
            return None

        band = max(float(p["touch_atr"]) * atr, width * float(p["touch_width_frac"]))
        upper_touches = int((prior["high"] >= (range_high - band)).sum())
        lower_touches = int((prior["low"] <= (range_low + band)).sum())
        if upper_touches < int(p["min_touches"]) or lower_touches < int(p["min_touches"]):
            return None

        loc = (close - range_low) / width
        breakout = close > range_high or close < range_low
        edge = float(p["edge_frac"])
        # Hourly location only — no arming on wick-only LTF-style tags without close at the edge.
        near_high = loc >= (1.0 - edge)
        near_low = loc <= edge

        exp_n = max(2, int(p.get("ceiling_expansion_bars", 6)))
        recent = confirmed.iloc[-exp_n:]
        recent_high = float(recent["high"].max())
        recent_low = float(recent["low"].min())
        tol = band * 0.05
        ceiling_expanding = recent_high > (range_high + tol)
        floor_expanding = recent_low < (range_low - tol)

        inner = 0.08 * width
        tagged_high = bar_high >= (range_high - band)
        tagged_low = bar_low <= (range_low + band)
        # SHORT: H1 high must not pierce the hourly box top (breakout wick ≠ fade).
        h1_top_intact = bar_high <= range_high
        h1_bottom_intact = bar_low >= range_low
        reject_high = (
            tagged_high
            and h1_top_intact
            and close < (range_high - inner)
            and close <= float(last["open"])
            and close > range_low
            and near_high
        )
        reject_low = (
            tagged_low
            and h1_bottom_intact
            and close > (range_low + inner)
            and close >= float(last["open"])
            and close < range_high
            and near_low
        )

        bias = None
        if not breakout:
            if require_rejection:
                if reject_low and loc <= 0.5:
                    bias = "LONG"
                elif reject_high and loc >= 0.5 and not ceiling_expanding:
                    bias = "SHORT"
            else:
                if near_low and not near_high and not floor_expanding:
                    bias = "LONG"
                elif near_high and not near_low and not ceiling_expanding:
                    bias = "SHORT"
                elif near_low and loc <= 0.5 and not floor_expanding:
                    bias = "LONG"
                elif near_high and loc >= 0.5 and not ceiling_expanding:
                    bias = "SHORT"

        vol_ratio_pct = self._volume_ratio_pct(work)
        if vol_ratio_pct is not None and vol_ratio_pct < float(p["min_volume_ratio_pct"]):
            return None

        return {
            "work": work,
            "confirmed": confirmed,
            "last": last,
            "close": close,
            "adx": adx,
            "adx_slope": adx_slope,
            "atr": atr,
            "rsi": rsi,
            "ema": ema,
            "ema_slope": ema_slope,
            "range_high": range_high,
            "range_low": range_low,
            "mid": mid,
            "width": width,
            "width_pct": width_pct,
            "upper_touches": upper_touches,
            "lower_touches": lower_touches,
            "loc": loc,
            "breakout": breakout,
            "near_high": near_high,
            "near_low": near_low,
            "reject_high": reject_high,
            "reject_low": reject_low,
            "ceiling_expanding": ceiling_expanding,
            "floor_expanding": floor_expanding,
            "h1_top_intact": h1_top_intact,
            "h1_bottom_intact": h1_bottom_intact,
            "bias": bias,
            "volume_ratio_pct": vol_ratio_pct,
            "now_ts": self._get_timestamp(confirmed, -1),
        }

    def _build_sl_tp(
        self, side: str, entry: float, range_high: float, range_low: float, atr_val: float, p: dict
    ) -> Tuple[Optional[float], Optional[float]]:
        entry = float(entry)
        atr_val = float(atr_val or 0)
        width = float(range_high) - float(range_low)
        if entry <= 0 or atr_val <= 0 or width <= 0:
            return None, None
        min_dist = entry * (float(p["min_sl_pct"]) / 100.0)
        buffer = max(float(p["sl_atr_mult"]) * atr_val, width * float(p["sl_range_frac"]), min_dist)
        if side == "LONG":
            sl = float(range_low) - buffer
            if sl >= entry:
                sl = entry - buffer
            tp = float(range_high) * (1.0 - 0.0005)
            if tp <= entry:
                return None, None
            risk = entry - sl
        else:
            sl = float(range_high) + buffer
            if sl <= entry:
                sl = entry + buffer
            tp = float(range_low) * (1.0 + 0.0005)
            if tp >= entry:
                return None, None
            risk = sl - entry
        if risk <= 0 or np.isnan(sl) or np.isnan(tp):
            return None, None
        reward = abs(tp - entry)
        if reward / risk < float(p["rr_ratio"]):
            return None, None
        return float(sl), float(tp)

    def generate_signal(self, df, extra_data=None):
        """
        Primary context is 1h (extra_data['1h']). Engine still passes 15m as `df`
        for regime — Range LT ignores 15m bars for setup geometry.
        """
        p = self._params_snapshot()
        df_1h = None
        if extra_data and isinstance(extra_data.get("1h"), pd.DataFrame):
            df_1h = extra_data["1h"]
        if df_1h is None or getattr(df_1h, "empty", True):
            return self._reject("Missing 1h data for range_lt")

        lookback = int(p["lookback"])
        struct_lb = max(lookback, int(p.get("structure_lookback", lookback)))
        if len(df_1h) < max(struct_lb + 8, int(p["ema_period"]) + 10):
            return self._reject("Not enough 1h candles for range_lt context")

        setup = self._evaluate_setup(df_1h, p, require_rejection=False)
        if setup is None:
            self.looking_for_entry = False
            self.entry_direction = None
            return self._reject("1h range filters not met (ADX/EMA slope/box quality)")

        now_ts = setup["now_ts"]
        if not self._cooldown_ok(now_ts, p["cooldown_minutes"]):
            return self._reject(f"Cooldown active ({p['cooldown_minutes']}m) — skipping range_lt entry")
        if self._same_bar_already_signaled(now_ts):
            return self._reject("Already evaluated this bar — waiting for next close")

        if setup["breakout"]:
            self.looking_for_entry = False
            self.entry_direction = None
            return self._reject("1h box broken (close outside range) — no fade")

        loc = float(setup.get("loc") or 0.5)
        if setup["near_low"] and setup["near_high"]:
            # Wide bar spanning both edges: pick the side of the close.
            self.entry_direction = "LONG" if loc <= 0.5 else "SHORT"
            self.looking_for_entry = True
        elif setup["near_low"]:
            self.entry_direction = "LONG"
            self.looking_for_entry = True
        elif setup["near_high"]:
            if setup.get("ceiling_expanding"):
                self.looking_for_entry = False
                self.entry_direction = None
                return self._reject(
                    "H1 range ceiling expanding above box top — not a confirmed hourly top"
                )
            self.entry_direction = "SHORT"
            self.looking_for_entry = True
        elif not self.looking_for_entry:
            return self._reject("Price mid-range — waiting for an extreme")

        if not self.looking_for_entry:
            return self._reject("Not armed for range_lt entry")

        rejected = (
            (self.entry_direction == "LONG" and setup.get("reject_low") and loc <= 0.5)
            or (self.entry_direction == "SHORT" and setup.get("reject_high") and loc >= 0.5)
        )
        if not rejected:
            if self.entry_direction == "SHORT":
                if setup.get("ceiling_expanding"):
                    return self._reject(
                        "H1 ceiling expanding — wait for a stable hourly range top"
                    )
                if not setup.get("h1_top_intact", True):
                    return self._reject(
                        "1h high pierced box top (breakout wick) — not an hourly fade entry"
                    )
            if self.entry_direction == "LONG" and setup.get("floor_expanding"):
                return self._reject(
                    "H1 floor expanding below box — wait for a stable hourly range low"
                )
            return self._reject(
                f"Armed {self.entry_direction} — waiting for 1h rejection close at hourly extreme"
            )

        htf_block = self._htf_blocks_fade(df_1h, self.entry_direction, p)
        if htf_block:
            return self._reject(htf_block)

        entry = float(setup["close"])
        sl, tp = self._build_sl_tp(
            self.entry_direction, entry, setup["range_high"], setup["range_low"], setup["atr"], p
        )
        if sl is None or tp is None:
            return self._reject("Failed to calculate valid range_lt SL/TP (R:R vs box width)")

        self.looking_for_entry = False
        self._mark_signal_bar(now_ts)

        side = "BUY" if self.entry_direction == "LONG" else "SELL"
        sl_pct = abs(entry - sl) / entry * 100.0
        return {
            "signal": side,
            "sl": float(sl),
            "tp": float(tp),
            "price": float(entry),
            "range_high": float(setup["range_high"]),
            "range_low": float(setup["range_low"]),
            "range_mid": float(setup["mid"]),
            "comment": (
                f"Range LT: 1h {self.entry_direction} fade at box "
                f"[{setup['range_low']:.6g}-{setup['range_high']:.6g}] "
                f"({setup['width_pct']:.1f}%). ADX {setup['adx']:.1f} "
                f"(slope {setup['adx_slope']:+.2f}), SL {sl_pct:.2f}% beyond box"
            ),
        }

    def supports_trade_thesis(self) -> bool:
        return True

    def get_thesis_timeframe(self) -> str:
        return "1h"

    def _plan_bounds_from_trade(self, trade: dict) -> Tuple[Optional[float], Optional[float]]:
        meta = trade.get("metadata") or {}
        rh = meta.get("range_high", trade.get("range_high"))
        rl = meta.get("range_low", trade.get("range_low"))
        try:
            return (
                float(rh) if rh is not None else None,
                float(rl) if rl is not None else None,
            )
        except (TypeError, ValueError):
            return None, None

    def evaluate_trade_thesis(self, trade, current_price, *, df, extra_data=None):
        from app.core.trade_thesis import evaluate_range_lt_thesis

        range_high, range_low = self._plan_bounds_from_trade(trade)
        if range_high is None or range_low is None or range_high <= range_low:
            return None
        if df is None or getattr(df, "empty", True) or len(df) < 20:
            return None

        p = self._params_snapshot()
        self.add_indicators(df, p)

        last_1h = df.iloc[-2]
        close_1h = float(last_1h.get("close", 0) or 0)
        if close_1h <= 0:
            return None

        adx = float(last_1h.get("ADX_14", 0) or 0)
        try:
            adx_slope = adx - float(df["ADX_14"].iloc[-3])
        except Exception:
            adx_slope = 0.0

        side = str(trade.get("side") or "BUY").upper()
        entry = float(trade.get("entry") or trade.get("entry_price") or 0)
        adx_trend = float(p.get("adx_trend_veto", 22) or 22)

        return evaluate_range_lt_thesis(
            side=side,
            entry=entry,
            current_price=float(current_price),
            close_1h=close_1h,
            range_high=range_high,
            range_low=range_low,
            adx=adx,
            adx_slope=adx_slope,
            adx_trend_threshold=adx_trend,
            weak_adx_slope=float(p.get("thesis_weak_adx_slope", 0.4) or 0.4),
        )
