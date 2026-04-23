from app.services.indicators import ta
import pandas as pd
import numpy as np
from strategies.base import BaseStrategy

class StrategySupertrend(BaseStrategy):
    """
    Supertrend Strategy with MTF Funnel (15m Context / 1m Trigger)

    Setup (15m):
    - Trend Filter: Price > SMA 200 (Long) or Price < SMA 200 (Short)
    - Supertrend Filter: Supertrend must be BULLISH for Long, BEARISH for Short.
    - ADX Filter: ADX > threshold (Trend presence)

    Trigger (1m):
    - Supertrend Flip: Enter when 1m Supertrend flips to match 15m bias.
    - OR: Pullback to 1m Supertrend line if 15m is strong.

    Risk:
    - SL: Fixed at Supertrend line or ATR swing.
    - TP: Risk-Reward 1.5 - 2.0.
    """

    AI_PERSONA = """
    CODENAME: "SUPERTREND SURFER"

    ROLE:
    You are a TREND RIDER. You don't try to predict reversals; you follow the momentum until it breaks.

    PRIME DIRECTIVE:
    Ride the wave. Protect capital by trailing stops precisely at the trend line.

    RULES OF ENGAGEMENT:
    1. TREND IS KING: Only trade in the direction of the 15m trend (EMA 200).
    2. VOLATILITY PROTECTION: Ensure ATR is healthy. If the market is dead (low volatility), avoid entry.
    3. MOMENTUM CONFIRMATION: Enter when the 1m chart aligns with the 15m tide.
    """

    def __init__(self, config=None):
        super().__init__(config)
        self.looking_for_entry = False
        self.entry_direction = None
        self._last_entry_time = None

        params = self.config.get("params", {})
        self.st_period = params.get("period", 10)
        self.st_multiplier = params.get("multiplier", 3.0)
        self.ema_filter = params.get("ema_filter_period", 200)
        self.adx_threshold = params.get("adx_threshold", 15)
        self.vol_mult = params.get("volume_multiplier", 1.2)
        self.rr_ratio = params.get("min_rr", 1.5)
        self.sl_atr_mult = params.get("sl_atr_mult", 1.0)
        self.trigger_flip_lookback = int(params.get("trigger_flip_lookback", 3))
        self.cooldown_minutes = int(params.get("cooldown_minutes", 0))

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

    def _cooldown_ok(self, now_ts):
        if self.cooldown_minutes <= 0:
            return True
        if now_ts is None or pd.isna(now_ts):
            return True  # can't enforce without time
        if self._last_entry_time is None or pd.isna(self._last_entry_time):
            return True
        try:
            elapsed = now_ts - self._last_entry_time
            return elapsed >= pd.Timedelta(minutes=self.cooldown_minutes)
        except Exception:
            return True

    def _recent_flip_ok(self, dir_series: pd.Series, desired_dir: int) -> bool:
        """
        Require last confirmed 1m direction == desired_dir AND
        the most recent flip happened within trigger_flip_lookback confirmed candles.
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
        min_allowed_pos = max(0, len(confirmed) - 1 - self.trigger_flip_lookback)
        return last_change_pos >= min_allowed_pos

    def add_indicators(self, df):
        """Add indicators to 15m dataframe"""
        df['SMA_200'] = ta.sma(df['close'], length=self.ema_filter)
        df['ADX_14'] = ta.adx(df['high'], df['low'], df['close'])['ADX']
        st_data = ta.supertrend(df['high'], df['low'], df['close'], period=self.st_period, multiplier=self.st_multiplier)
        df['Supertrend'] = st_data['Supertrend']
        df['ST_Direction'] = st_data['Direction']
        df['ATR_14'] = ta.atr(df['high'], df['low'], df['close'], length=14)
        return df

    def generate_signal(self, df, extra_data=None):
        """
        Args:
            df: 15m context
            extra_data: {"1m": df_1m} trigger
        """
        if df.empty or len(df) < (self.ema_filter + 10):
            return self._reject("Not enough 15m candles for supertrend context")

        if not extra_data or "1m" not in extra_data:
            return self._reject("Missing 1m trigger data for MTF supertrend")

        df_1m = extra_data["1m"]
        if df_1m.empty or len(df_1m) < 20:
            return self._reject("Insufficient 1m candles for trigger")

        # 1. Add 15m indicators
        self.add_indicators(df)

        # Latest 15m values (completed candle)
        last_15m = df.iloc[-2]
        close_15m = last_15m['close']
        sma_200_15m = last_15m['SMA_200']
        st_dir_15m = last_15m['ST_Direction']
        adx_15m = last_15m['ADX_14']
        now_ts = self._get_timestamp(df, -2)

        if not self._cooldown_ok(now_ts):
            return self._reject(f"Cooldown active ({self.cooldown_minutes}m) — skipping entry")

        # --- 15m SETUP ---
        if adx_15m < self.adx_threshold:
            self.looking_for_entry = False
            return self._reject(f"ADX below threshold ({adx_15m:.1f} < {self.adx_threshold})")

        if close_15m > sma_200_15m and st_dir_15m == 1:
            self.entry_direction = "LONG"
            self.looking_for_entry = True
        elif close_15m < sma_200_15m and st_dir_15m == -1:
            self.entry_direction = "SHORT"
            self.looking_for_entry = True
        else:
            self.looking_for_entry = False
            return self._reject("15m trend filter not aligned (SMA200/Supertrend)")

        # --- 1m TRIGGER ---
        if self.looking_for_entry:
            st_data_1m = ta.supertrend(df_1m['high'], df_1m['low'], df_1m['close'], period=self.st_period, multiplier=self.st_multiplier)
            df_1m = df_1m.copy()
            df_1m['ST_Direction'] = st_data_1m['Direction']
            df_1m['Supertrend'] = st_data_1m['Supertrend']

            last_1m = df_1m.iloc[-2]

            # TRIGGER: require a RECENT 1m flip into the 15m direction (prevents spam on mere alignment)
            if self.entry_direction == "LONG":
                if self._recent_flip_ok(df_1m["ST_Direction"], desired_dir=1):
                    atr_val = last_15m.get('ATR_14', 0)
                    st_val = last_1m.get('Supertrend', 0)
                    
                    if np.isnan(atr_val) or np.isnan(st_val):
                        return self._reject(f"NaN indicators detected (ATR: {atr_val}, ST: {st_val})")
                        
                    sl = min(st_val, last_1m['close'] - (self.sl_atr_mult * atr_val))
                    risk = last_1m['close'] - sl
                    tp = last_1m['close'] + (self.rr_ratio * risk)
                    
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
                        "comment": f"Supertrend: 15m {self.entry_direction} + 1m Flip (lookback={self.trigger_flip_lookback}). ADX: {adx_15m:.1f}"
                    }

            elif self.entry_direction == "SHORT":
                if self._recent_flip_ok(df_1m["ST_Direction"], desired_dir=-1):
                    atr_val = last_15m.get('ATR_14', 0)
                    st_val = last_1m.get('Supertrend', 0)
                    
                    if np.isnan(atr_val) or np.isnan(st_val):
                        return self._reject(f"NaN indicators detected (ATR: {atr_val}, ST: {st_val})")
                        
                    sl = max(st_val, last_1m['close'] + (self.sl_atr_mult * atr_val))
                    risk = sl - last_1m['close']
                    tp = last_1m['close'] - (self.rr_ratio * risk)
                    
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
                        "comment": f"Supertrend: 15m {self.entry_direction} + 1m Flip (lookback={self.trigger_flip_lookback}). ADX: {adx_15m:.1f}"
                    }

        return self._reject(f"1m supertrend flip not detected within lookback={self.trigger_flip_lookback} for 15m {self.entry_direction} bias")

    def calculate_progress(self, df, extra_data=None):
        """UI Progress calculation with structured stages"""
        if df.empty or len(df) < self.ema_filter:
            return {
                "strategy": "Supertrend",
                "score": 0,
                "bias": "NEUTRAL",
                "stages": [{"name": "Data Check", "status": "WAIT", "details": "Waiting for indicators..."}]
            }

        try:
            self.add_indicators(df)
            last_15m = df.iloc[-1]

            stages = []
            score = 0

            # --- Stage 1: Trend Filter (SMA 200) ---
            is_bullish = last_15m['close'] > last_15m['SMA_200']
            is_bearish = last_15m['close'] < last_15m['SMA_200']
            st_align = (is_bullish and last_15m['ST_Direction'] == 1) or \
                       (is_bearish and last_15m['ST_Direction'] == -1)

            s1_status = "PASS" if st_align else "WAIT"
            bias_text = "BULL" if is_bullish else "BEAR"
            s1_details = f"15m {bias_text} Bias (Price vs SMA200)" if st_align else "Waiting for Trend Alignment"

            stages.append({
                "name": "1. Trend Regime",
                "status": s1_status,
                "details": s1_details,
                "metrics": {
                    "bias": {"value": bias_text, "align": "YES" if st_align else "NO"}
                }
            })
            if st_align: score += 40

            # --- Stage 2: ADX Filter ---
            adx_val = last_15m['ADX_14']
            adx_ok = adx_val >= self.adx_threshold

            s2_status = "PASS" if adx_ok else "WAIT"
            s2_details = f"ADX {adx_val:.1f} (Trend Active)" if adx_ok else f"ADX Low ({adx_val:.1f} < {self.adx_threshold})"

            stages.append({
                "name": "2. Trend Strength",
                "status": s2_status,
                "details": s2_details,
                "metrics": {
                    "adx": {"value": round(adx_val, 1), "threshold": self.adx_threshold, "op": ">"}
                }
            })
            if adx_ok: score += 30
            else: score += int((adx_val / self.adx_threshold) * 20)

            # --- Stage 3: 1m Alignment ---
            s3_status = "WAIT"
            s3_details = "Waiting for 1m sync..."

            if extra_data and "1m" in extra_data:
                df_1m = extra_data["1m"]
                if not df_1m.empty and len(df_1m) > 2:
                    st_data_1m = ta.supertrend(df_1m['high'], df_1m['low'], df_1m['close'], period=self.st_period, multiplier=self.st_multiplier)
                    curr_st_1m = st_data_1m['Direction'].iloc[-1]
                    prev_st_1m = st_data_1m['Direction'].iloc[-2]

                    if curr_st_1m == last_15m['ST_Direction']:
                        if prev_st_1m != curr_st_1m:
                            s3_status = "TRIGGER!"
                            s3_details = "1m Supertrend JUST Flipped!"
                            score += 30
                        else:
                            s3_status = "PASS"
                            s3_details = "1m Aligned (Waiting for new Flip)"
                            score += 20
                    else:
                        s3_details = "1m Counter-trend"

            stages.append({
                "name": "3. Execution Sync",
                "status": s3_status,
                "details": s3_details
            })

            # Determine Bias
            bias = "NEUTRAL"
            if is_bullish: bias = "LONG"
            elif is_bearish: bias = "SHORT"

            return {
                "strategy": "Supertrend",
                "score": min(100, score),
                "bias": bias,
                "stages": stages
            }
        except Exception as e:
            return {
                "strategy": "Supertrend",
                "score": 0,
                "error": str(e),
                "bias": "NEUTRAL",
                "stages": []
            }
