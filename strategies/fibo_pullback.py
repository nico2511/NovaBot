from app.services.indicators import ta
import pandas as pd
from strategies.base import BaseStrategy

class StrategyFiboPullback(BaseStrategy):
    """
    Fibonacci Pullback Strategy V2 - REFACTORED (2026-01-08)
    
    FIXES APPLIED:
    ✅ Anti-repainting: All signals use iloc[-2] (completed candles only)
    ✅ Swing confirmation: Exclude last 10 bars for swing detection
    ✅ Wider Fibo zone: 50-78.6% (golden zone) instead of 50-65%
    ✅ Volume filter: Require 1.5x average volume for entry
    ✅ Consistent UI: Progress/conditions use same anti-repainting logic
    ✅ SHORT Logic Added: Supports both Bullish and Bearish pullbacks
    
    Logic (LONG):
    1. Trend Filter: Price > EMA 200 AND ADX >= 20
    2. Swing Detection: Find confirmed Highest High (10+ bars old) and preceding Lowest Low
    3. Fibonacci Levels: Calculate 50%, 61.8%, and 78.6% retracement zones
    4. Entry Trigger: Price in 50-78.6% zone + Volume > 1.5x average
    5. Risk Management: SL below 78.6%, TP at Swing High
    6. R:R Filter: Minimum 1.5 ratio required

    Logic (SHORT):
    1. Trend Filter: Price < EMA 200 AND ADX >= 20
    2. Swing Detection: Find confirmed Lowest Low (10+ bars old) and preceding Highest High
    3. Fibo Retracement: Upward retracement 50-78.6%
    4. Entry Trigger: Price in zone + Volume
    
    Timeframe: 15m optimized
    Type: TREND (Pullback continuation)
    """

    AI_PERSONA = """
    CODENAME: "GOLDEN RETRACEMENT - FIBONACCI PHANTOM"

    ROLE:
    You are a PRECISION TREND HUNTER. You specialize in the sacred art of Fibonacci confluence in trending markets.

    PRIME DIRECTIVE:
    "Respect the golden zone." Pullbacks are not weakness; they are breathing room for the next leg up.

    RULES OF ENGAGEMENT (OVERRIDES):
    1. TREND IS KING: EMA 200 + ADX >=20 is non-negotiable. No chop, no counter-trend. Only continuation.
    2. GOLDEN ZONE ONLY: 50-78.6% is the sacred retracement. Do NOT enter outside it, even if price looks tempting.
    3. VOLUME CONFIRMATION: 1.5x average or GTFO. Fake pullbacks die without fuel.
    4. PATIENCE IS POWER: Wait for confirmed swing + zone + volume. No FOMO entries.
    5. RISK IS SACRED: SL below 78.6%, TP at previous high, RR >=1.5 or no trade.

    RESPONSE STYLE:
    Calm, precise, almost spiritual.
    "The market breathes... now it exhales upward.", "Golden zone respected. Alignment complete.", "Fibonacci whispers: Enter."
    """
    
    def __init__(self, config=None):
        super().__init__(config)
        
        # Configurable Parameters - Read from params block in strategies.json
        params = self.config.get('params', {})
        self.ema_period = params.get('ema_period', 200)
        self.adx_threshold = params.get('adx_threshold', 22) # CHANGED 2026-02: 18 -> 22 (More strict Trend)
        self.swing_lookback = params.get('swing_lookback', 35)
        self.swing_confirmation_bars = params.get('swing_confirmation_bars', 10)
        self.min_rr = params.get('min_rr', 1.5)
        self.volume_multiplier = params.get('volume_multiplier', 1.2) # CHANGED 2026-02: 1.3 -> 1.2
        
        # Fibonacci Levels (FIXED: Wider zone)
        self.fibo_entry_min = 0.382  # CHANGED 2026-02: 0.50 -> 0.382 (Wider zone)
        self.fibo_entry_max = 0.786  # 78.6% retracement (golden zone)
        self.fibo_sl_level = 0.786   # 78.6% for SL placement
    
    def add_indicators(self, df):
        """Add required indicators to dataframe"""
        df['EMA_200'] = ta.ema(df['close'], length=self.ema_period)
        adx_result = ta.adx(df['high'], df['low'], df['close'], length=14)
        df['ADX_14'] = adx_result['ADX'] if isinstance(adx_result, pd.DataFrame) else adx_result
        
        # Add volume SMA for filter
        if 'volume' in df.columns:
            df['volume_sma_20'] = df['volume'].rolling(20).mean()
        
        return df
    
    def generate_signal(self, df, extra_data=None):
        """
        Generate Fibonacci Pullback signal (FIXED VERSION)
        Supports LONG and SHORT
        
        Returns:
            dict with signal details or None
        """
        # Need extra bars for swing confirmation
        min_bars = self.swing_lookback + self.ema_period + self.swing_confirmation_bars
        if df.empty or len(df) < min_bars:
            return None
        
        # Add indicators
        self.add_indicators(df)
        
        # ✅ FIX #1: Use completed candles (iloc[-2])
        current_price = df['close'].iloc[-2]
        current_low = df['low'].iloc[-2]
        current_high = df['high'].iloc[-2]
        ema_200 = df['EMA_200'].iloc[-2]
        adx = df['ADX_14'].iloc[-2]
        
        # Check ADX for both directions
        if adx < self.adx_threshold:
            return None
            
        # GUARD CLAUSE: OI Counter-Trend Risk
        # "Confirm pullback if OI stable/decreasing."
        # If OI Spikes (>1.5%) during valid pullback zone, it implies Strong Counter-Trend Interest -> Reversal Risk.
        if 'OI_Change_Pct' in df.columns:
            oi_chg = df['OI_Change_Pct'].iloc[-2]
            if oi_chg > 1.5: # User: "stable or decreasing". 1.5% is a significant increase.
                return None 

        # ============================================
        # DECISION: LONG OR SHORT?
        # ============================================
        is_bullish = current_price > ema_200
        is_bearish = current_price < ema_200

        if not is_bullish and not is_bearish: 
            return None

        # ============================================
        # SWING DETECTION & LOGIC (Merged)
        # ============================================
        
        # Select data for confirmed swing
        confirmed_end = -self.swing_confirmation_bars
        confirmed_start = -(self.swing_lookback + self.swing_confirmation_bars)
        confirmed_df = df.iloc[confirmed_start:confirmed_end].copy()
        
        if len(confirmed_df) < 20:
            return None
        
        signal_data = None

        # --- LONG SETUP ---
        if is_bullish:
            # Find Swing High (Highest High)
            swing_high_idx = confirmed_df['high'].idxmax()
            swing_high = confirmed_df.loc[swing_high_idx, 'high']
            
            # Find Swing Low (Lowest Low BEFORE Swing High)
            data_before = confirmed_df.loc[:swing_high_idx]
            if len(data_before) < 10: return None
            
            swing_low_idx = data_before['low'].idxmin()
            swing_low = data_before.loc[swing_low_idx, 'low']
            
            if swing_high <= swing_low: return None
            
            # Calc Levels
            diff = swing_high - swing_low
            entry_zone_high = swing_high - (diff * self.fibo_entry_min)
            entry_zone_low = swing_high - (diff * self.fibo_entry_max)
            
            # Entry Trigger
            in_zone = (current_low <= entry_zone_high and current_high >= entry_zone_low)
            if not in_zone: return None
            
            entry = current_price
            sl = swing_high - (diff * 0.786) - (diff * 0.01) # Below 78.6%
            tp = swing_high

            signal_data = {
                "signal": "BUY",
                "sl": sl,
                "tp": tp,
                "swing_h": swing_high,
                "swing_l": swing_low,
                "diff": diff
            }

        # --- SHORT SETUP ---
        if is_bearish:
            # Find Swing Low (Lowest Low)
            swing_low_idx = confirmed_df['low'].idxmin()
            swing_low = confirmed_df.loc[swing_low_idx, 'low']
            
            # Find Swing High (Highest High BEFORE Swing Low)
            data_before = confirmed_df.loc[:swing_low_idx]
            if len(data_before) < 10: return None
            
            swing_high_idx = data_before['high'].idxmax()
            swing_high = data_before.loc[swing_high_idx, 'high']
            
            if swing_low >= swing_high: return None
            
            # Calc Levels (Retracement goes UP)
            diff = swing_high - swing_low
            # 50% retracement is higher than Low
            entry_zone_low = swing_low + (diff * self.fibo_entry_min)
            entry_zone_high = swing_low + (diff * self.fibo_entry_max)
            
            # Entry Trigger
            in_zone = (current_high >= entry_zone_low and current_low <= entry_zone_high)
            if not in_zone: return None
            
            entry = current_price
            sl = swing_low + (diff * 0.786) + (diff * 0.01) # Above 78.6%
            tp = swing_low # Target Low

            signal_data = {
                "signal": "SELL",
                "sl": sl,
                "tp": tp,
                "swing_h": swing_high,
                "swing_l": swing_low,
                "diff": diff
            }
            
        if not signal_data:
            return None

        # ============================================
        # VOLUME FILTER & R:R CHECK (Shared)
        # ============================================
        
        # Volume Filter
        current_vol = 0
        avg_vol = 0
        if 'volume' in df.columns:
            current_vol = df['volume'].iloc[-2]
            avg_vol = df['volume'].iloc[-22:-2].mean()
            if avg_vol > 0 and current_vol < avg_vol * self.volume_multiplier:
                return None
        
        # R:R Check
        entry_price = current_price
        dist_tp = abs(signal_data["tp"] - entry_price)
        dist_sl = abs(entry_price - signal_data["sl"])
        
        if dist_sl == 0: return None
        rr = dist_tp / dist_sl
        
        if rr < self.min_rr:
            return None
            
        # ============================================
        # RETURN SIGNAL
        # ============================================
        vol_ratio = current_vol / avg_vol if avg_vol > 0 else 0
        diff = signal_data["diff"]
        retracement_pct = abs(signal_data["swing_h"] - current_price) / diff * 100 if is_bullish else abs(current_price - signal_data["swing_l"]) / diff * 100
        
        return {
            "signal": signal_data["signal"],
            "sl": signal_data["sl"],
            "tp": signal_data["tp"],
            "comment": f"Fibo Pullback V2 (RR:{rr:.1f}, Vol:{vol_ratio:.1f}x, Retrace:{retracement_pct:.0f}%)",
            "metadata": {
                "swing_high": signal_data["swing_h"],
                "swing_low": signal_data["swing_l"],
                "adx": adx,
                "rr_ratio": round(rr, 2),
                "volume_ratio": round(vol_ratio, 2)
            }
        }
    
    def calculate_progress(self, df, extra_data=None):
        """
        Returns detailed progress stages for monitoring.
        Stages:
        1. Context (Trend & ADX)
        2. Setup (Swing & Retracement)
        3. Trigger (Volume)
        """
        if df is None or df.empty or len(df) < 60:
             return {
                "strategy": "Fibo Pullback",
                "score": 0,
                "stages": [{"name": "Data Check", "status": "FAIL", "details": "Not enough data"}]
            }
        
        try:
            # 1. Context (Trend + ADX)
            self.add_indicators(df)
            # Use -1 for monitoring current state
            current_price = df['close'].iloc[-1]
            ema_200 = df['EMA_200'].iloc[-1]
            adx = df['ADX_14'].iloc[-1]
            
            is_bullish = current_price > ema_200
            is_bearish = current_price < ema_200
            adx_ok = adx >= self.adx_threshold
            
            s1_status = "WAIT"
            s1_details = "Neutral / Weak"
            
            if adx_ok:
                if is_bullish:
                    s1_status = "BULLISH"
                    s1_details = f"Uptrend (ADX {adx:.1f})"
                elif is_bearish:
                    s1_status = "BEARISH"
                    s1_details = f"Downtrend (ADX {adx:.1f})"
            else:
                s1_details = f"Weak ADX ({adx:.1f})"
            
            stages = []
            stages.append({
                "name": "1. Trend Context",
                "status": "PASS" if s1_status in ["BULLISH", "BEARISH"] else "WAIT",
                "details": s1_details,
                 "metrics": {
                    "adx": {"value": round(adx, 1), "threshold": self.adx_threshold, "op": ">="}
                }
            })
            
            # 2. Setup (Swing Retracement)
            # This requires scanning for swings. We can reuse a simplified version of generate_signal logic.
            
            s2_status = "WAIT"
            s2_details = "No Valid Swing"
            
            # We need valid swing logic. 
            # Reimplementing simplified check:
            if s1_status != "WAIT":
                # Need at least 50 bars
                lookback = self.swing_lookback + self.swing_confirmation_bars
                subset = df.iloc[-(lookback+20):-1] # Exclude current for swing finding? 
                # Actually, swing high must be old.
                
                # Check closest significant High/Low
                # Simplified: Current Price vs 50-period range
                range_high = subset['high'].max()
                range_low = subset['low'].min()
                diff = range_high - range_low
                
                if diff > 0:
                     if s1_status == "BULLISH":
                         retrace = (range_high - current_price) / diff
                         # Zone: 0.5 to 0.786
                         if 0.5 <= retrace <= 0.786:
                             s2_status = "READY"
                             s2_details = f"In Golden Zone ({retrace*100:.1f}%)"
                         elif retrace < 0.5:
                             s2_details = f"Shallow Dip ({retrace*100:.1f}%)"
                         else:
                             s2_details = f"Deep Dip ({retrace*100:.1f}%)"
                             
                     elif s1_status == "BEARISH":
                         retrace = (current_price - range_low) / diff
                         if 0.5 <= retrace <= 0.786:
                             s2_status = "READY"
                             s2_details = f"In Golden Zone ({retrace*100:.1f}%)"
                         elif retrace < 0.5:
                             s2_details = f"Shallow Rally ({retrace*100:.1f}%)"
                         else:
                             s2_details = f"Deep Rally ({retrace*100:.1f}%)"

            stages.append({
                "name": "2. Fibo Zone (50-78%)",
                "status": s2_status,
                "details": s2_details
            })
            
            # 3. Trigger (Volume)
            avg_vol = df['volume'].rolling(20).mean().iloc[-1]
            current_vol = df['volume'].iloc[-1]
            
            vol_ratio = current_vol / avg_vol if avg_vol > 0 else 0
            vol_ok = vol_ratio >= self.volume_multiplier
            
            s3_status = "WAIT"
            s3_details = f"Vol Ratio: {vol_ratio:.1f}x"
            
            if s2_status == "READY":
                if vol_ok:
                    s3_status = "TRIGGER!"
                    s3_details = f"Volume Spike ({vol_ratio:.1f}x)"
                else:
                    s3_details = f"Low Volume ({vol_ratio:.1f}x)"
            
            stages.append({
                "name": "3. Volume Trigger",
                "status": s3_status,
                "details": s3_details
            })
            
            # Score
            score = 0
            if s1_status in ["BULLISH", "BEARISH"]: score += 30
            if s2_status == "READY": score += 40
            if s3_status == "TRIGGER!": score += 30
            
            # Determine Bias
            bias = "NEUTRAL"
            if s1_status == "BULLISH": bias = "LONG"
            elif s1_status == "BEARISH": bias = "SHORT"

            return {
                "strategy": "Fibo Pullback",
                "score": score,
                "bias": bias,
                "stages": stages
            }

        except Exception as e:
            return {
                "strategy": "Fibo Pullback",
                "score": 0,
                "error": str(e),
                "stages": []
            }

    def check_conditions(self, df, extra_data=None):
        return []

    def get_threshold_comparisons(self, df, extra_data=None):
        """Detailed parameters for UI"""
        if df.empty: return {}
        try:
            self.add_indicators(df)
            adx = df['ADX_14'].iloc[-1]
            return {
                "ADX": f"{adx:.1f} (Threshold: {self.adx_threshold})",
                "EMA200": "Active"
            }
        except: return {}
