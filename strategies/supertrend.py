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
    - ADX Filter: ADX > threshold (Trend presence)
    - Anti stop-hunt: reject thin volume + neutral RSI

    Trigger (1m):
    - Supertrend Flip: Enter when 1m Supertrend flips to match 15m bias.

    Risk:
    - SL: Fixed at Supertrend line or ATR swing.
    - TP: Risk-Reward from min_rr.
    """

    AI_PERSONA = """
    CODENAME: "SUPERTREND SURFER"

    ROLE:
    You are a TREND RIDER. You don't try to predict reversals; you follow the momentum until it breaks.

    PRIME DIRECTIVE:
    Ride the wave. Protect capital by trailing stops precisely at the trend line.
    Prefer APPROVE when the strategy already confirmed a 15m bias + recent 1m SuperTrend flip
    with healthy ADX and acceptable R:R. Do not apply scalping SL width rules (0.5%-1.2%).

    RULES OF ENGAGEMENT:
    1. TREND IS KING: Only trade in the direction of the 15m trend (EMA filter).
    2. ATR STOPS ARE NORMAL: SuperTrend SL may be 1.5%-6% on volatile perps — that is expected, not a reject reason.
    3. MOMENTUM: A recent 1m SuperTrend flip into the 15m bias is sufficient trigger confirmation.
    4. REJECT mainly for: clear counter-trend vs higher structure, dead volume, or broken R:R (< strategy min).
    5. When in doubt but structure aligns, APPROVE with MEDIUM risk rather than over-filtering.
    """

    def __init__(self, config=None):
        super().__init__(config)
        # Stateful attributes (not tunable params — kept across ticks)
        self.looking_for_entry = False
        self.entry_direction = None
        self._last_entry_time = None
        # NOTE: tunable params are read dynamically via self.get_param()
        # so that API edits take effect immediately without engine rebuild.

    def _params_snapshot(self):
        return {
            "st_period":             int(self.get_param("period", 10)),
            "st_multiplier":         float(self.get_param("multiplier", 3.0)),
            "ema_filter":            int(self.get_param("ema_filter_period", 200)),
            "adx_threshold":         float(self.get_param("adx_threshold", 15)),
            "rr_ratio":              float(self.get_param("min_rr", 1.5)),
            "sl_atr_mult":           float(self.get_param("sl_atr_mult", 1.0)),
            "trigger_flip_lookback": int(self.get_param("trigger_flip_lookback", 3)),
            "cooldown_minutes":      int(self.get_param("cooldown_minutes", 0)),
            # Anti stop-hunt guard: skip signals in thin liquidity + neutral momentum
            "min_volume_ratio_pct":  float(self.get_param("min_volume_ratio_pct", 50.0)),
            "rsi_neutral_low":       float(self.get_param("rsi_neutral_low", 45.0)),
            "rsi_neutral_high":      float(self.get_param("rsi_neutral_high", 55.0)),
        }

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

    def _cooldown_ok(self, now_ts, cooldown_minutes: int):
        if cooldown_minutes <= 0:
            return True
        if now_ts is None or pd.isna(now_ts):
            return True  # can't enforce without time
        if self._last_entry_time is None or pd.isna(self._last_entry_time):
            return True
        try:
            elapsed = now_ts - self._last_entry_time
            return elapsed >= pd.Timedelta(minutes=cooldown_minutes)
        except Exception:
            return True

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

        # --- 1m TRIGGER ---
        if self.looking_for_entry:
            st_data_1m = ta.supertrend(df_1m['high'], df_1m['low'], df_1m['close'], period=p["st_period"], multiplier=p["st_multiplier"])
            df_1m = df_1m.copy()
            df_1m['Supertrend'] = st_data_1m['Supertrend']
            # Same normalization on trigger timeframe for consistent flip logic.
            df_1m['ST_Direction'] = np.where(df_1m['close'] >= df_1m['Supertrend'], 1, -1)

            last_1m = df_1m.iloc[-2]

            # TRIGGER: require a RECENT 1m flip into the 15m direction (prevents spam on mere alignment)
            if self.entry_direction == "LONG":
                if self._recent_flip_ok(df_1m["ST_Direction"], desired_dir=1, lookback=p["trigger_flip_lookback"]):
                    atr_val = last_15m.get('ATR_14', 0)
                    st_val = last_1m.get('Supertrend', 0)

                    if np.isnan(atr_val) or np.isnan(st_val):
                        return self._reject(f"NaN indicators detected (ATR: {atr_val}, ST: {st_val})")

                    sl = min(st_val, last_1m['close'] - (p["sl_atr_mult"] * atr_val))
                    risk = last_1m['close'] - sl
                    tp = last_1m['close'] + (p["rr_ratio"] * risk)

                    if np.isnan(sl) or np.isnan(tp):
                        return self._reject("Failed to calculate valid SL/TP (NaN result)")

                    self.looking_for_entry = False
                    if now_ts is not None and not pd.isna(now_ts):
                        self._last_entry_time = now_ts
                    return {
                        "signal": "BUY",
                        "sl": float(sl),
                        "tp": float(tp),
                        "price": float(last_1m['close']),
                        "comment": f"Supertrend: 15m {self.entry_direction} + 1m Flip (lookback={p['trigger_flip_lookback']}). ADX: {adx_15m:.1f}"
                    }

            elif self.entry_direction == "SHORT":
                if self._recent_flip_ok(df_1m["ST_Direction"], desired_dir=-1, lookback=p["trigger_flip_lookback"]):
                    atr_val = last_15m.get('ATR_14', 0)
                    st_val = last_1m.get('Supertrend', 0)

                    if np.isnan(atr_val) or np.isnan(st_val):
                        return self._reject(f"NaN indicators detected (ATR: {atr_val}, ST: {st_val})")

                    sl = max(st_val, last_1m['close'] + (p["sl_atr_mult"] * atr_val))
                    risk = sl - last_1m['close']
                    tp = last_1m['close'] - (p["rr_ratio"] * risk)

                    if np.isnan(sl) or np.isnan(tp):
                        return self._reject("Failed to calculate valid SL/TP (NaN result)")

                    self.looking_for_entry = False
                    if now_ts is not None and not pd.isna(now_ts):
                        self._last_entry_time = now_ts
                    return {
                        "signal": "SELL",
                        "sl": float(sl),
                        "tp": float(tp),
                        "price": float(last_1m['close']),
                        "comment": f"Supertrend: 15m {self.entry_direction} + 1m Flip (lookback={p['trigger_flip_lookback']}). ADX: {adx_15m:.1f}"
                    }

        return self._reject(f"1m supertrend flip not detected within lookback={p['trigger_flip_lookback']} for 15m {self.entry_direction} bias")
