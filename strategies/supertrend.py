from app.services.indicators import ta
import pandas as pd
import numpy as np
from strategies.base import BaseStrategy

class StrategySupertrend(BaseStrategy):
    """
    Supertrend Strategy with MTF Funnel (15m Context / 1m Trigger)

    Setup (15m):
    - Trend Filter: Price > EMA filter (Long) or Price < EMA filter (Short)
    - Supertrend Filter: Supertrend must be BULLISH for Long, BEARISH for Short.
    - ADX Filter: ADX > threshold (Trend presence) and slope not dying
    - Location: not already extended from 15m SuperTrend (avoid late chase)

    Trigger (1m) — pullback then resume:
    - Price must have tagged the 15m SuperTrend band recently (pullback)
    - THEN price must reclaim the 15m ST (resume). Optional: require a fresh 1m ST flip.
    - Pure mid-impulse entries without a pullback are rejected

    Risk:
    - SL: 15m SuperTrend line, widened by ATR floor / min_sl_pct (not noisy 1m ST).
    - TP: Risk-Reward from min_rr, preferably capped at local swing (AI/code may trim).
    """

    AI_PERSONA = """
    CODENAME: "SUPERTREND SURFER"

    ROLE:
    You are a TREND RIDER. You don't try to predict reversals; you follow the momentum until it breaks.

    PRIME DIRECTIVE:
    Ride the wave only when confluence is clean. Protect capital.
    Approve when the strategy confirmed a 15m bias + pullback-to-ST reclaim/resume
    with healthy ADX, acceptable R:R, AND healthy volume. Do not apply scalping SL width rules (0.5%-1.2%).

    RULES OF ENGAGEMENT:
    1. TREND IS KING: Only trade in the direction of the 15m trend (EMA filter).
    2. ATR STOPS ARE NORMAL: SuperTrend SL may be 1.5%-6% on volatile perps — that is expected, not a reject reason.
    3. LOCATION FIRST: Prefer pullback-to-15m-ST then reclaim (price back on trend side of ST). Reject mid-impulse chase.
    4. TP MUST RESPECT STRUCTURE: For BUY, Proposed TP should be <= Swing High (trim below it if needed).
       For SELL, Proposed TP should be >= Swing Low (trim above it if needed). Prefer a realistic structural TP
       over a purely mechanical min_rr extension beyond local swing. Put the trimmed TP in suggested_adjustments.tp.
    5. REJECT if volume_ratio < 50% of average (WEAK_VOLUME) — no exceptions.
    6. REJECT chase entries: BUY with RSI > 70 or SELL with RSI < 30 unless a clear breakout with volume > 150% avg.
    7. If MTF sentiment is unavailable, do NOT invent higher-TF structure — stay neutral on HTF and judge 15m + volume only.
    8. If MTF 1h/4h clearly conflicts with the 15m signal direction, REJECT as COUNTER_TREND.
    9. When structure is only "almost ok", REJECT or ask for better location — do not default to APPROVE.
    """

    AI_VALIDATION_CRITERIA = """=== VALIDATION CRITERIA (SUPERTREND) ===
The strategy ALREADY confirmed: 15m EMA+SuperTrend bias, ADX/quality filters, pullback-to-ST,
and a 15m ST reclaim/resume trigger (1m flip is optional, not required).
Your job is a sanity check with hard reject rules — not a rubber stamp.

APPROVE when ALL of:
1. Direction aligns with market bias / 15m trend (or TREND_BEAR_STRONG for shorts)
2. Computed R:R meets the risk-profile minimum (after any TP trim below)
3. Volume ratio >= 50% of average
4. No clear fight vs available higher-TF sentiment (1h/4h). If MTF says Unavailable, ignore HTF (do not invent it)
5. TP is structurally realistic vs Key Levels:
   - BUY: Proposed TP must be <= Swing High. If Proposed TP > Swing High, TRIM TP slightly below Swing High
     via suggested_adjustments.tp (do not keep an optimistic breakout TP by default).
   - SELL: Proposed TP must be >= Swing Low. If Proposed TP < Swing Low, TRIM TP slightly above Swing Low.
   - If after a required trim the R:R falls below profile minimum, REJECT as BAD_RR (do not approve an undersized target).

REJECT when ANY of:
- volume_ratio < 50% (WEAK_VOLUME)
- BUY with RSI > 70 or SELL with RSI < 30 without volume > 150% (OVEREXTENDED chase)
- 1h/4h MTF clearly opposite to signal direction (COUNTER_TREND)
- Computed R:R below profile minimum (BAD_RR)
- TP requires a breakout beyond Swing High/Low and you did not trim (OPTIMISTIC_TP)

Do NOT reject solely because:
- SL width is wider than scalp norms (ATR/SuperTrend stops of ~1.5%-6% are normal on perps)
- RSI is moderately extended (50-70 long / 30-50 short) in a trending regime
- Price is not sitting exactly on a Fib level
- Entry used ST reclaim instead of a fresh 1m SuperTrend flip

If confluence is weak or mixed, prefer approved=false over forcing a trade."""

    def __init__(self, config=None):
        super().__init__(config)
        # Stateful attributes (not tunable params — kept across ticks)
        self.looking_for_entry = False
        self.entry_direction = None
        self._last_entry_time = None
        self._last_signal_bar = None
        # NOTE: tunable params are read dynamically via self.get_param()
        # so that API edits take effect immediately without engine rebuild.

    def get_ai_validation_criteria(self):
        return self.AI_VALIDATION_CRITERIA

    def get_min_volume_ratio_pct(self):
        try:
            return float(self.get_param("min_volume_ratio_pct", 50.0) or 50.0)
        except (TypeError, ValueError):
            return 50.0

    def check_hard_veto(self, signal: str, market_context: dict):
        """Strategy-owned hard veto — SuperTrend 15m thresholds via shared helper."""
        from app.core.veto_checker import check_hard_veto as _helper

        return _helper(signal, market_context or {})

    def get_scan_timeframe(self) -> str:
        return "15m"

    def get_scan_interval_minutes(self) -> float:
        try:
            raw = self.get_param("scan_interval_minutes", None)
            if raw is not None:
                return max(1.0, float(raw))
        except (TypeError, ValueError):
            pass
        return 15.0

    def score_scan_candidate(self, df, *, symbol: str, meta=None):
        """
        Rank a 15m OHLCV frame for SuperTrend context quality (no 1m trigger).
        """
        import numpy as np
        import pandas as pd
        from app.services.indicators import ta

        p = self._params_snapshot()
        period = int(p["st_period"])
        multiplier = float(p["st_multiplier"])
        ema_len = int(p["ema_filter"])
        adx_threshold = float(p["adx_threshold"])
        min_vol_pct = float(p["min_volume_ratio_pct"])
        rsi_lo = float(p["rsi_neutral_low"])
        rsi_hi = float(p["rsi_neutral_high"])
        max_ext = float(p["max_extension_atr"])

        min_bars = max(ema_len + 10, period + 30, 60)
        if df is None or getattr(df, "empty", True) or len(df) < min_bars:
            return None

        work = df.copy()
        work["EMA_FILTER"] = ta.ema(work["close"], length=ema_len)
        work["ADX_14"] = ta.adx(work["high"], work["low"], work["close"])["ADX"]
        st = ta.supertrend(
            work["high"], work["low"], work["close"], period=period, multiplier=multiplier
        )
        work["Supertrend"] = st["Supertrend"]
        work["ST_Direction"] = np.where(work["close"] >= work["Supertrend"], 1, -1)
        work["RSI_14"] = ta.rsi(work["close"], length=14)
        work["ATR_14"] = ta.atr(work["high"], work["low"], work["close"], length=14)

        last = work.iloc[-2]
        close = float(last["close"])
        ema = float(last["EMA_FILTER"])
        adx = float(last["ADX_14"])
        st_dir = int(last["ST_Direction"])
        st_line = float(last["Supertrend"])
        atr = float(last["ATR_14"]) if not pd.isna(last["ATR_14"]) else 0.0
        rsi = float(last["RSI_14"]) if not pd.isna(last["RSI_14"]) else 50.0

        if any(np.isnan(x) for x in (close, ema, adx, st_line)):
            return None
        if adx < adx_threshold:
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

        if (
            vol_ratio_pct is not None
            and vol_ratio_pct < min_vol_pct
            and rsi_lo <= rsi <= rsi_hi
        ):
            return None

        reasons = []
        score = 0.0
        adx_edge = max(0.0, adx - adx_threshold)
        score += min(40.0, 20.0 + adx_edge * 2.0)
        reasons.append(f"ADX {adx:.1f} (≥{adx_threshold:.0f})")
        score += 30.0
        reasons.append(f"15m {bias}: price vs EMA{ema_len} + ST")

        if vol_ratio_pct is None:
            score += 5.0
        elif vol_ratio_pct >= min_vol_pct:
            score += min(15.0, 8.0 + (vol_ratio_pct - min_vol_pct) * 0.05)
            reasons.append(f"Vol {vol_ratio_pct:.0f}% of MA50")
        else:
            score += 3.0
            reasons.append(f"Vol thin ({vol_ratio_pct:.0f}%) but RSI not neutral")

        if rsi < rsi_lo or rsi > rsi_hi:
            score += 10.0
            reasons.append(f"RSI {rsi:.0f} outside neutral band")
        else:
            score += 3.0

        dist_pct = abs(close - st_line) / close * 100.0 if close else 99.0
        if extension_atr <= 0.8:
            score += 15.0
            reasons.append(f"Pullback zone ({extension_atr:.2f}x ATR / {dist_pct:.2f}%)")
        elif extension_atr <= 1.2:
            score += 10.0
            reasons.append(f"Near ST ({extension_atr:.2f}x ATR)")
        else:
            score += 4.0
            reasons.append(f"Acceptable extension ({extension_atr:.2f}x ATR)")

        score = float(min(100.0, round(score, 1)))
        market = meta or {}
        armed = bool(getattr(self, "looking_for_entry", False))
        return {
            "symbol": symbol or market.get("symbol"),
            "strategy": getattr(self, "name", "supertrend"),
            "score": score,
            "bias": bias,
            "trend": trend,
            "adx": round(adx, 2),
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
            "armed": armed,
            "timeframe": "15m",
            "st_params": {
                "period": period,
                "multiplier": multiplier,
                "ema_filter_period": ema_len,
                "adx_threshold": adx_threshold,
            },
        }

    def post_ai_adjust(self, signal, ai_result, market_context=None):
        """Trim optimistic SuperTrend TP to local swing before R:R hard gate."""
        import logging

        logger = logging.getLogger(__name__)
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
            # 0.05% buffer inside the swing so TP sits on structure, not through it
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
                logger.info(
                    "[STRATEGY] Trimmed SuperTrend TP %s -> %s (swing structure)",
                    tp,
                    trimmed,
                )
        except (TypeError, ValueError) as trim_err:
            logger.debug("TP swing trim skipped: %s", trim_err)
        return ai_result

    def _params_snapshot(self):
        return {
            "st_period":             int(self.get_param("period", 10)),
            "st_multiplier":         float(self.get_param("multiplier", 3.0)),
            "ema_filter":            int(self.get_param("ema_filter_period", 200)),
            "adx_threshold":         float(self.get_param("adx_threshold", 22)),
            "rr_ratio":              float(self.get_param("min_rr", 2.0)),
            "sl_atr_mult":           float(self.get_param("sl_atr_mult", 2.0)),
            "trigger_flip_lookback": int(self.get_param("trigger_flip_lookback", 30)),
            "cooldown_minutes":      int(self.get_param("cooldown_minutes", 15)),
            # Anti stop-hunt guard: skip signals in thin liquidity + neutral momentum
            "min_volume_ratio_pct":  float(self.get_param("min_volume_ratio_pct", 50.0)),
            "rsi_neutral_low":       float(self.get_param("rsi_neutral_low", 45.0)),
            "rsi_neutral_high":      float(self.get_param("rsi_neutral_high", 55.0)),
            # Quality filters (reduce mid-trend chase / dying ADX / tiny SL noise)
            "min_adx_slope":         float(self.get_param("min_adx_slope", -0.35)),
            "max_rsi_long":          float(self.get_param("max_rsi_long", 60.0)),
            "min_rsi_short":         float(self.get_param("min_rsi_short", 40.0)),
            "max_extension_atr":     float(self.get_param("max_extension_atr", 1.4)),
            "min_sl_pct":            float(self.get_param("min_sl_pct", 0.8)),
            # Pullback-then-resume (fixes late 1m flip entries)
            "require_pullback":      bool(self.get_param("require_pullback", True)),
            "pullback_lookback_1m":  int(self.get_param("pullback_lookback_1m", 30)),
            "pullback_touch_atr":    float(self.get_param("pullback_touch_atr", 1.0)),
            # Fresh 1m ST flip is optional — reclaim of 15m ST is the default resume trigger
            "require_recent_flip":   bool(self.get_param("require_recent_flip", False)),
        }

    def _build_sl_tp(self, side: str, entry: float, st_15m: float, atr_val: float, p: dict):
        """
        Anchor SL on 15m SuperTrend (stable), widen with ATR and min_sl_pct.
        Previously SL used 1m ST which hugs price and gets noise-stopped (ETH ~0.6%).
        """
        atr_val = float(atr_val or 0)
        st_15m = float(st_15m or 0)
        entry = float(entry)
        if entry <= 0 or atr_val <= 0 or np.isnan(atr_val) or np.isnan(st_15m):
            return None, None

        min_dist = entry * (float(p["min_sl_pct"]) / 100.0)
        atr_dist = float(p["sl_atr_mult"]) * atr_val

        if side == "LONG":
            # Wider stop = lower price among candidates that are below entry
            atr_sl = entry - atr_dist
            st_sl = st_15m if st_15m < entry else atr_sl
            sl = min(st_sl, atr_sl, entry - min_dist)
            if sl >= entry:
                sl = entry - max(atr_dist, min_dist)
            risk = entry - sl
            tp = entry + (float(p["rr_ratio"]) * risk)
        else:
            atr_sl = entry + atr_dist
            st_sl = st_15m if st_15m > entry else atr_sl
            sl = max(st_sl, atr_sl, entry + min_dist)
            if sl <= entry:
                sl = entry + max(atr_dist, min_dist)
            risk = sl - entry
            tp = entry - (float(p["rr_ratio"]) * risk)

        if risk <= 0 or np.isnan(sl) or np.isnan(tp):
            return None, None
        return float(sl), float(tp)

    def _get_timestamp(self, df, iloc_idx: int):
        """Best-effort timestamp extraction for cooldown logic."""
        try:
            ts = df.index[iloc_idx]
            if isinstance(ts, (pd.Timestamp,)):
                return ts
            # try coercion for string / datetime / numpy types
            return pd.to_datetime(ts, errors="coerce")
        except Exception:
            return None

    def _recent_flip_ok(self, dir_series: pd.Series, desired_dir: int, lookback: int) -> bool:
        """
        Require last confirmed 1m direction == desired_dir AND
        the most recent flip happened within `lookback` confirmed candles.
        """
        if dir_series is None or dir_series.empty:
            return False

        # Exclude live candle direction (last element corresponds to iloc[-1] in df_1m)
        confirmed = dir_series.iloc[:-1] if len(dir_series) >= 2 else dir_series
        if confirmed.empty:
            return False

        last_dir = int(confirmed.iloc[-1])
        if last_dir != int(desired_dir):
            return False

        # Find flip points (where direction changes)
        changes = confirmed != confirmed.shift(1)
        change_positions = np.where(changes.fillna(False).to_numpy())[0]
        if change_positions.size == 0:
            return False

        last_change_pos = int(change_positions[-1])
        # If last change is the first element, it's not reliable (no prior context)
        if last_change_pos <= 0:
            return False

        # Lookback window measured in confirmed candles from the end
        min_allowed_pos = max(0, len(confirmed) - 1 - lookback)
        return last_change_pos >= min_allowed_pos

    def _pullback_to_st_ok(
        self,
        df_1m: pd.DataFrame,
        side: str,
        st_15m: float,
        atr_15m: float,
        lookback: int,
        touch_atr: float,
    ) -> bool:
        """
        True if, within recent confirmed 1m bars, price tagged the 15m ST band.
        LONG: a low came down to ST + touch_atr*ATR
        SHORT: a high came up to ST - touch_atr*ATR
        """
        if df_1m is None or df_1m.empty or atr_15m <= 0 or st_15m <= 0:
            return False
        lookback = max(3, int(lookback))
        confirmed = df_1m.iloc[:-1]
        if len(confirmed) < lookback:
            return False
        window = confirmed.iloc[-lookback:]
        band = float(touch_atr) * float(atr_15m)
        try:
            if side == "LONG":
                return float(window["low"].min()) <= (float(st_15m) + band)
            return float(window["high"].max()) >= (float(st_15m) - band)
        except Exception:
            return False

    def add_indicators(self, df, p=None):
        """Add indicators to 15m dataframe"""
        p = p or self._params_snapshot()
        # Param is named ema_filter_period — use EMA (not SMA) so docs/UI match behavior.
        # Column kept as EMA_200 for display_conditions compatibility.
        df["EMA_200"] = ta.ema(df["close"], length=p["ema_filter"])
        df['ADX_14'] = ta.adx(df['high'], df['low'], df['close'])['ADX']
        st_data = ta.supertrend(df['high'], df['low'], df['close'], period=p["st_period"], multiplier=p["st_multiplier"])
        df['Supertrend'] = st_data['Supertrend']
        # Normalize direction from price vs ST line to avoid convention drift
        # across Supertrend implementations (some invert +1/-1 labels).
        df['ST_Direction'] = np.where(df['close'] >= df['Supertrend'], 1, -1)
        df['ATR_14'] = ta.atr(df['high'], df['low'], df['close'], length=14)
        # Alias for bot AI/SL-floor paths that historically looked for pandas_ta's ATRr_14
        df['ATRr_14'] = df['ATR_14']
        # RSI used as a lightweight momentum sanity check (anti stop-hunt in ranges)
        df['RSI_14'] = ta.rsi(df['close'], length=14)
        return df

    def generate_signal(self, df, extra_data=None):
        """
        Args:
            df: 15m context
            extra_data: {"1m": df_1m} trigger
        """
        p = self._params_snapshot()
        if df.empty or len(df) < (p["ema_filter"] + 10):
            return self._reject("Not enough 15m candles for supertrend context")

        if not extra_data or "1m" not in extra_data:
            return self._reject("Missing 1m trigger data for MTF supertrend")

        df_1m = extra_data["1m"]
        if df_1m.empty or len(df_1m) < 20:
            return self._reject("Insufficient 1m candles for trigger")

        # 1. Add 15m indicators
        self.add_indicators(df, p)

        # Latest 15m values (completed candle)
        last_15m = df.iloc[-2]
        close_15m = last_15m['close']
        ema_filter_15m = last_15m['EMA_200']
        st_dir_15m = last_15m['ST_Direction']
        adx_15m = last_15m['ADX_14']
        rsi_15m = float(last_15m.get("RSI_14", np.nan))
        now_ts = self._get_timestamp(df, -2)

        if not self._cooldown_ok(now_ts, p["cooldown_minutes"]):
            return self._reject(f"Cooldown active ({p['cooldown_minutes']}m) — skipping entry")

        if self._same_bar_already_signaled(now_ts):
            return self._reject("Already evaluated this bar — waiting for next close")

        # --- ANTI STOP-HUNT GUARD (Thin liquidity + neutral RSI) ---
        # In thin markets, stop-hunts are common; avoid taking trend entries with no momentum edge.
        try:
            vol_now = float(df["volume"].iloc[-2]) if "volume" in df.columns else None
            vol_ma = float(df["volume"].iloc[:-1].rolling(50).mean().iloc[-2]) if "volume" in df.columns else None
            vol_ratio_pct = (vol_now / vol_ma) * 100.0 if vol_now is not None and vol_ma and vol_ma > 0 else None

            if (
                vol_ratio_pct is not None
                and vol_ratio_pct < float(p["min_volume_ratio_pct"])
                and not np.isnan(rsi_15m)
                and float(p["rsi_neutral_low"]) <= rsi_15m <= float(p["rsi_neutral_high"])
            ):
                return self._reject(
                    f"Thin liquidity + RSI neutral (vol={vol_ratio_pct:.1f}% < {p['min_volume_ratio_pct']:.0f}%, "
                    f"RSI={rsi_15m:.1f}) — stop-hunt risk"
                )
        except Exception:
            # If we can't compute the guard reliably, stay permissive (do not block).
            pass

        # --- 15m SETUP ---
        if adx_15m < p["adx_threshold"]:
            self.looking_for_entry = False
            return self._reject(f"ADX below threshold ({adx_15m:.1f} < {p['adx_threshold']})")

        # Reject dying trends (AAVE/UNI style: ADX still high but slope negative)
        try:
            adx_prev = float(df["ADX_14"].iloc[-3])
            adx_slope = float(adx_15m) - adx_prev
            if adx_slope < float(p["min_adx_slope"]):
                self.looking_for_entry = False
                return self._reject(
                    f"ADX slope dying ({adx_slope:+.2f} < {p['min_adx_slope']:+.2f}) — skip late trend entry"
                )
        except Exception:
            adx_slope = 0.0

        atr_15m = float(last_15m.get("ATR_14", 0) or 0)
        st_15m = float(last_15m.get("Supertrend", 0) or 0)

        if close_15m > ema_filter_15m and st_dir_15m == 1:
            self.entry_direction = "LONG"
            self.looking_for_entry = True
        elif close_15m < ema_filter_15m and st_dir_15m == -1:
            self.entry_direction = "SHORT"
            self.looking_for_entry = True
        else:
            self.looking_for_entry = False
            return self._reject(
                f"15m trend filter not aligned (EMA{p['ema_filter']}/Supertrend)"
            )

        # Chase / extension filters on 15m context (before spending 1m trigger work)
        if not np.isnan(rsi_15m):
            if self.entry_direction == "LONG" and rsi_15m > float(p["max_rsi_long"]):
                self.looking_for_entry = False
                return self._reject(
                    f"Chase filter: 15m RSI {rsi_15m:.1f} > {p['max_rsi_long']:.0f} — wait pullback"
                )
            if self.entry_direction == "SHORT" and rsi_15m < float(p["min_rsi_short"]):
                self.looking_for_entry = False
                return self._reject(
                    f"Chase filter: 15m RSI {rsi_15m:.1f} < {p['min_rsi_short']:.0f} — wait bounce"
                )

        if atr_15m > 0 and st_15m > 0:
            extension = abs(close_15m - st_15m) / atr_15m
            if extension > float(p["max_extension_atr"]):
                self.looking_for_entry = False
                return self._reject(
                    f"Extended from 15m ST ({extension:.2f}x ATR > {p['max_extension_atr']:.1f}x) — late entry"
                )

        # --- 1m TRIGGER ---
        if self.looking_for_entry:
            st_data_1m = ta.supertrend(df_1m['high'], df_1m['low'], df_1m['close'], period=p["st_period"], multiplier=p["st_multiplier"])
            df_1m = df_1m.copy()
            df_1m['Supertrend'] = st_data_1m['Supertrend']
            # Same normalization on trigger timeframe for consistent flip logic.
            df_1m['ST_Direction'] = np.where(df_1m['close'] >= df_1m['Supertrend'], 1, -1)

            last_1m = df_1m.iloc[-2]
            entry = float(last_1m["close"])

            # Entry must still be near 15m ST (1m impulse can extend past 15m close)
            if atr_15m > 0 and st_15m > 0:
                entry_ext = abs(entry - st_15m) / atr_15m
                if entry_ext > float(p["max_extension_atr"]):
                    return self._reject(
                        f"1m entry already extended ({entry_ext:.2f}x ATR from 15m ST) — late"
                    )

            if p["require_pullback"]:
                if not self._pullback_to_st_ok(
                    df_1m,
                    self.entry_direction,
                    st_15m,
                    atr_15m,
                    p["pullback_lookback_1m"],
                    p["pullback_touch_atr"],
                ):
                    return self._reject(
                        f"No pullback to 15m ST within {p['pullback_lookback_1m']}m "
                        f"(need tag within {p['pullback_touch_atr']:.1f}x ATR) — wait for retrace"
                    )

            # Resume confirmation: price back on the trend side of 15m ST
            if self.entry_direction == "LONG" and entry < st_15m:
                return self._reject("Pullback not resumed — 1m still below 15m ST")
            if self.entry_direction == "SHORT" and entry > st_15m:
                return self._reject("Pullback not resumed — 1m still above 15m ST")

            desired = 1 if self.entry_direction == "LONG" else -1
            last_1m_dir = int(df_1m["ST_Direction"].iloc[-2])
            # Optional lagging confirm: fresh 1m SuperTrend flip (often blocks near ST)
            if p["require_recent_flip"]:
                if last_1m_dir != desired:
                    return self._reject(
                        f"1m ST still against bias ({last_1m_dir:+d} vs {desired:+d}) — wait resume flip"
                    )
                if not self._recent_flip_ok(
                    df_1m["ST_Direction"], desired_dir=desired, lookback=p["trigger_flip_lookback"]
                ):
                    return self._reject(
                        f"1m supertrend flip not detected within lookback={p['trigger_flip_lookback']} "
                        f"for 15m {self.entry_direction} bias (after pullback)"
                    )

            sl, tp = self._build_sl_tp(self.entry_direction, entry, st_15m, atr_15m, p)
            if sl is None or tp is None:
                return self._reject("Failed to calculate valid SL/TP (15m ST / ATR)")

            self.looking_for_entry = False
            self._mark_signal_bar(now_ts)

            side = "BUY" if self.entry_direction == "LONG" else "SELL"
            sl_pct = abs(entry - sl) / entry * 100.0
            trigger_note = (
                f"1m flip (lb={p['trigger_flip_lookback']})"
                if p["require_recent_flip"]
                else "15m ST reclaim"
            )
            return {
                "signal": side,
                "sl": float(sl),
                "tp": float(tp),
                "price": float(entry),
                "comment": (
                    f"Supertrend: 15m {self.entry_direction} + pullback-to-ST + {trigger_note}. "
                    f"ADX: {adx_15m:.1f} (slope {adx_slope:+.2f}), SL {sl_pct:.2f}% via 15m ST/ATR"
                ),
            }

        return self._reject("No entry setup")

    def supports_trade_thesis(self) -> bool:
        return True

    def get_thesis_timeframe(self) -> str:
        return "15m"

    def evaluate_trade_thesis(self, trade, current_price, *, df, extra_data=None):
        from app.core.trade_thesis import evaluate_supertrend_thesis, thesis_indicators_ready

        if df is None or getattr(df, "empty", True) or len(df) < 50:
            return None

        p = self._params_snapshot()
        ema_need = int(p.get("ema_filter", 200) or 200) + 10
        if len(df) < ema_need:
            return None

        self.add_indicators(df, p)

        last_15m = df.iloc[-2]
        adx = float(last_15m.get("ADX_14", 0) or 0)
        try:
            adx_slope = adx - float(df["ADX_14"].iloc[-3])
        except Exception:
            adx_slope = 0.0

        close_15m = float(last_15m.get("close", 0) or 0)
        ema_filter = float(last_15m.get("EMA_200", 0) or 0)
        st_direction = int(last_15m.get("ST_Direction", 0) or 0)
        supertrend = float(last_15m.get("Supertrend", 0) or 0)
        if not thesis_indicators_ready(
            close_15m=close_15m,
            ema_filter=ema_filter,
            st_direction=st_direction,
            supertrend=supertrend,
            adx=adx,
        ):
            return None

        side = str(trade.get("side") or "BUY").upper()
        entry = float(trade.get("entry") or trade.get("entry_price") or 0)
        raw_entry_slope = p.get("min_adx_slope", -0.35)
        try:
            weak_adx_slope = (
                float(raw_entry_slope) if raw_entry_slope is not None else -0.35
            )
        except (TypeError, ValueError):
            weak_adx_slope = -0.35
        dead_adx_slope = min(-1.0, weak_adx_slope - 0.65)

        return evaluate_supertrend_thesis(
            side=side,
            entry=entry,
            current_price=float(current_price),
            close_15m=close_15m,
            ema_filter=ema_filter,
            st_direction=st_direction,
            supertrend=supertrend,
            adx=adx,
            adx_slope=adx_slope,
            adx_threshold=float(p.get("adx_threshold", 22) or 22),
            min_adx_slope=dead_adx_slope,
            weak_adx_slope=weak_adx_slope,
        )
