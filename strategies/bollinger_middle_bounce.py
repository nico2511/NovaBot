
"""
Bollinger Middle Band Bounce - Trend Following Strategy
"""

import pandas as pd
import numpy as np
from typing import Optional, Dict, List
from strategies.base import BaseStrategy
from app.services.indicators import ta

class BollingerMiddleBounceStrategy(BaseStrategy):
    """
    Bollinger Middle Band Bounce strategy logic.
    Logic:
    1. Trend Filter: EMA20 > EMA50, ADX > 25
    2. Setup: Price interacts with Bollinger Middle Band (Pullback)
    3. Trigger: Confirmation candle (Green/Red) + Volume validation
    """
    
    # ==========================================
    # 🧠 PERSONA : LE SNIPER DE TENDANCE
    # ==========================================
    AI_PERSONA = """
    CODENAME: "TREND SURFER - MIDDLE BAND SNIPER"
    
    ROLE:
    You are a TREND FOLLOWER. You ignore the noise and wait for the perfect pullback.
    
    PRIME DIRECTIVE:
    "The trend is your friend until the bend." We buy the dips in uptrends and sell the rips in downtrends.
    
    RULES OF ENGAGEMENT:
    1. TREND IS KING: Never trade against the EMA hierarchy (20 > 50 for Long, 20 < 50 for Short).
    2. THE MIDDLE PATH: The Bollinger Middle Band (SMA 20) is your value zone. Wait for price to touch or pierce it.
    3. NO WEAKNESS: We need MOMENTUM. ADX must be > 25. If the trend is dying, we stand down.
    4. CONFIRMATION: Don't just buy the touch. Wait for the market to prove it wants to resume the trend (Green candle closing above Middle Band).
    5. VOLUME SPEAKS: A volume spike on the reversal candle is the golden seal of approval.
    
    RESPONSE STYLE:
    Professional, precise, disciplined.
    "Trend intact. Pullback validated. Engaging.", "Momentum fading. Aborting mission."
    """
    
    def __init__(self, config=None):
        super().__init__(config)
        self.bb_period = self.params.get("bb_period", 20)
        self.bb_std = self.params.get("bb_std", 2.0)
        
        self.ema_trend_short = self.params.get("ema_trend_short", 20)
        self.ema_trend_long = self.params.get("ema_trend_long", 50)
        
        self.adx_threshold = self.params.get("adx_threshold", 20)
        self.rsi_min = self.params.get("rsi_min", 50)
        
        self.min_rr = self.params.get("min_rr", 2.0)
        
        # SL and Volume Confirmation
        self.sl_buffer_pct = self.params.get("sl_buffer_pct", 0.012)
        self.volume_multiplier = self.params.get("volume_multiplier", 1.3)

    
    def check_trend(self, df: pd.DataFrame) -> tuple[int, str]:
        """
        Check trend direction: 1 (Long), -1 (Short), 0 (Neutral)
        """
        try:
            # ADX Momentum Filter: ADX must be above threshold AND not crashing
            adx_res = ta.adx(df['high'], df['low'], df['close'], length=14)
            current_adx = adx_res['ADX'].iloc[-1]
            adx_prev = adx_res['ADX'].iloc[-2]
            
            if current_adx < self.adx_threshold:
                return 0, f"ADX too low ({current_adx:.1f})"
            
            if current_adx < adx_prev - 0.5: # Allow very minor dips, but reject sharp trend exhaustion
                return 0, f"ADX dying ({adx_prev:.1f} -> {current_adx:.1f})"
            
            # EMA Trend Check
            ema_short = ta.ema(df['close'], length=self.ema_trend_short)
            ema_long = ta.ema(df['close'], length=self.ema_trend_long)
            
            curr_short = ema_short.iloc[-1]
            curr_long = ema_long.iloc[-1]
            price = df['close'].iloc[-1]
            
            if curr_short > curr_long and price > curr_long:
                return 1, "Uptrend (EMA20 > EMA50)"
            elif curr_short < curr_long and price < curr_long:
                return -1, "Downtrend (EMA20 < EMA50)"
            
            return 0, "No clear trend structure"

            
        except Exception as e:
            return 0, f"Error trend: {e}"

    def generate_signal(self, df: pd.DataFrame, extra_data=None) -> Optional[Dict]:
        """
        Generate signal based on Pullback to Middle Band
        """
        if df is None or df.empty or len(df) < 60:
            return None
        
        try:
            # 1. Trend Filter
            trend_dir, reason = self.check_trend(df)
            if trend_dir == 0:
                return None
            
            # 2. Bollinger Bands
            bb = ta.bbands(df['close'], length=self.bb_period, std=self.bb_std)
            middle_band = bb['BBM']
            upper_band = bb['BBU']
            lower_band = bb['BBL']
            
            current_price = df['close'].iloc[-1]
            current_mb = middle_band.iloc[-1]
            
            prev_price = df['close'].iloc[-2]
            prev_low = df['low'].iloc[-2]
            prev_high = df['high'].iloc[-2]
            prev_mb = middle_band.iloc[-2]
            
            # RSI Check
            rsi = ta.rsi(df['close'], length=14).iloc[-1]
            
            atr = ta.atr(df['high'], df['low'], df['close'], length=14).iloc[-1]
            
            # Volume Check (NEW: use volume_multiplier from config)
            avg_volume = df['volume'].rolling(20).mean().iloc[-1]
            current_volume = df['volume'].iloc[-1]
            volume_ok = current_volume >= (avg_volume * self.volume_multiplier)
            
            # === LONG SETUP ===
            if trend_dir == 1:
                # GUARD: Reject if price is already at lower band extreme (not a middle band pullback!)
                current_lb = lower_band.iloc[-1]
                if current_price < current_lb * 1.005:  # Within 0.5% of lower band
                    return None  # Price crashed to lower band, this is NOT a middle band bounce
                
                # Check confirmation candle: Green and closed above Middle Band
                is_green = df['close'].iloc[-1] > df['open'].iloc[-1]
                closes_above_mb = current_price > current_mb
                
                # Interaction Check (Pullback): 
                # 1. Proximity Check
                recent_touch = (df['low'].iloc[-1] <= current_mb * 1.004) or (prev_low <= prev_mb * 1.004)
                
                # 2. Deep Pullback Guard: Reject if price is too close to EMA50 (failed trend)
                ema_50 = ta.ema(df['close'], length=self.ema_trend_long).iloc[-1]
                if current_price < ema_50 * 1.003: # Within 0.3% of EMA50 is too deep
                    return None
                
                # 3. Wick Rejection: Ideally candle low was below MB but close is above
                # This proves the level was defended
                has_rejection_wick = df['low'].iloc[-1] < (current_mb * 1.001) and closes_above_mb
                
                if is_green and closes_above_mb and recent_touch and volume_ok:
                     if rsi > self.rsi_min and (has_rejection_wick or volume_ok):


                        # Use sl_buffer_pct from config instead of hardcoded ATR
                        sl = df['low'].iloc[-1] * (1 - self.sl_buffer_pct)  # Dynamic SL with buffer
                        tp = upper_band.iloc[-1] # Target 1: Upper Band
                        
                        # Calculate Risk/Reward to Upper Band to determine viability
                        # Or use fixed RR
                        
                        risk = current_price - sl
                        reward_to_band = tp - current_price
                        
                        # Ideally target a bit higher if trend is strong, so let's stick to standard RR logic 
                        # but check if Upper Band offers decent initial reward
                        
                        min_target = current_price + (risk * self.min_rr)
                        
                        return {
                            "signal": "BUY",
                            "sl": sl,
                            "tp": min_target,
                            "comment": f"Trend Pullback Bounce (RSI: {rsi:.1f})"
                        }

            # === SHORT SETUP ===
            elif trend_dir == -1:
                # GUARD: Reject if price is already at upper band extreme (not a middle band pullback!)
                current_ub = upper_band.iloc[-1]
                current_lb = lower_band.iloc[-1]
                
                # CRITICAL FIX: Also reject if price is already at/below lower band
                # This prevents the bug where we SHORT when price has already crashed
                if current_price > current_ub * 0.995:  # Within 0.5% of upper band
                    return None  # Price spiked to upper band, not a middle band rejection
                if current_price < current_lb * 1.005:  # Within 0.5% of lower band  
                    return None  # Price already at lower band - NO MORE ROOM TO SHORT!
                
                # Confirmation: Red and closed below MB
                is_red = df['close'].iloc[-1] < df['open'].iloc[-1]
                closes_below_mb = current_price < current_mb
                
                recent_touch = (df['high'].iloc[-1] >= current_mb * 0.999) or (prev_high >= prev_mb * 0.999)
                
                if is_red and closes_below_mb and recent_touch and volume_ok:
                    if rsi < (100 - self.rsi_min): # e.g. < 60
                        # Use sl_buffer_pct from config
                        sl = df['high'].iloc[-1] * (1 + self.sl_buffer_pct)  # Dynamic SL with buffer
                        tp = lower_band.iloc[-1]
                        
                        risk = sl - current_price
                        min_target = current_price - (risk * self.min_rr)
                        
                        return {
                            "signal": "SELL",
                            "sl": sl,
                            "tp": min_target,
                            "comment": f"Trend Pullback Rejection (RSI: {rsi:.1f})"
                        }

            return None

        except Exception as e:
            return None

    def calculate_progress(self, df: pd.DataFrame, extra_data=None):
        """
        Returns detailed progress stages for monitoring.
        Stages:
        1. Context (Trend & ADX)
        2. Setup (Middle Band Pullback)
        3. Trigger (Confirmation Candle)
        """
        if df is None or df.empty or len(df) < 60:
             return {
                "strategy": "Bollinger Middle",
                "score": 0,
                "stages": [{"name": "Data Check", "status": "FAIL", "details": "Not enough data"}]
            }
        
        try:
            # 1. Trend Presence
            trend_dir, reason = self.check_trend(df)
            
            s1_status = "WAIT"
            s1_details = reason
            if trend_dir == 1:
                s1_status = "pass_bull" # Custom status for internal logic if needed, or just "PASS"
                s1_details = "Uptrend (EMA20 > EMA50)"
            elif trend_dir == -1:
                s1_status = "pass_bear"
                s1_details = "Downtrend (EMA20 < EMA50)"
                
            stages = []
            stages.append({
                "name": "1. Trend Context",
                "status": "PASS" if trend_dir != 0 else "WAIT",
                "details": s1_details
            })
            
            # 2. Middle Band Interaction
            bb = ta.bbands(df['close'], length=self.bb_period, std=self.bb_std)
            mb = bb['BBM'].iloc[-1]
            price = df['close'].iloc[-1]
            
            # Check proximity (0.5% default for "close")
            dist_pct = (price - mb) / mb
            is_close = abs(dist_pct) < 0.005
            
            s2_status = "WAIT"
            s2_details = f"Distance: {dist_pct*100:+.2f}%"
            
            if trend_dir != 0:
                if is_close:
                    s2_status = "READY"
                    s2_details = f"Touching Middle Band ({dist_pct*100:+.2f}%)"
                else:
                    # Provide directional hint
                    if trend_dir == 1 and dist_pct > 0:
                         s2_details = f"Above MB (+{dist_pct*100:.2f}%) - Waiting for dip"
                    elif trend_dir == -1 and dist_pct < 0:
                         s2_details = f"Below MB ({dist_pct*100:.2f}%) - Waiting for rally"

            stages.append({
                "name": "2. Pullback Setup",
                "status": s2_status,
                "details": s2_details,
                "metrics": {
                    "dist": {"value": round(dist_pct*100, 2), "threshold": 0.5, "op": "abs <"}
                }
            })
            
            # 3. Trigger (Confirmation)
            # Need volume and correct candle color
            
            avg_volume = df['volume'].rolling(20).mean().iloc[-1]
            current_volume = df['volume'].iloc[-1]
            volume_ok = current_volume >= (avg_volume * self.volume_multiplier)
            
            rsi = ta.rsi(df['close'], length=14).iloc[-1]
            
            s3_status = "WAIT"
            s3_details = "Waiting for bounce..."
            
            if s2_status == "READY":
                if trend_dir == 1:
                    # Need Green Candle + Volume + RSI
                    is_green = df['close'].iloc[-1] > df['open'].iloc[-1]
                    if is_green:
                        if volume_ok:
                             s3_status = "TRIGGER!"
                             s3_details = f"Green Candle + Vol ({current_volume/avg_volume:.1f}x)"
                        else:
                             s3_details = "Green Candle, Low Vol"
                    else:
                        s3_details = "Waiting for Green Candle"
                elif trend_dir == -1:
                    # Need Red Candle + Volume + RSI
                    is_red = df['close'].iloc[-1] < df['open'].iloc[-1]
                    if is_red:
                         if volume_ok:
                             s3_status = "TRIGGER!"
                             s3_details = f"Red Candle + Vol ({current_volume/avg_volume:.1f}x)"
                         else:
                             s3_details = "Red Candle, Low Vol"
                    else:
                         s3_details = "Waiting for Red Candle"
                         
            stages.append({
                "name": "3. Confirmation",
                "status": s3_status,
                "details": s3_details
            })
            
            # Score
            score = 0
            if trend_dir != 0: score += 30
            if s2_status == "READY": score += 40
            if s3_status == "TRIGGER!": score += 30
            
            # Determine Bias
            bias = "NEUTRAL"
            if trend_dir == 1: bias = "LONG"
            elif trend_dir == -1: bias = "SHORT"

            return {
                "strategy": "Bollinger Middle",
                "score": score,
                "bias": bias,
                "stages": stages
            }
            
        except Exception as e:
            return {
                "strategy": "Bollinger Middle",
                "score": 0,
                "error": str(e),
                "stages": []
            }

    def check_conditions(self, df: pd.DataFrame, extra_data=None) -> List[Dict]:
        return []

    def get_threshold_comparisons(self, df: pd.DataFrame, extra_data=None) -> Dict:
        """Get detailed threshold comparisons for Parameters section"""
        if df is None or df.empty: return {}
        try:
            adx_res = ta.adx(df['high'], df['low'], df['close'], length=14)
            adx = adx_res['ADX'].iloc[-1]
            
            bb = ta.bbands(df['close'], length=self.bb_period, std=self.bb_std)
            mb = bb['BBM'].iloc[-1]
            price = df['close'].iloc[-1]
            dist_pct = (price - mb) / mb * 100
            
            return {
                "ADX": f"{adx:.1f} (Min: {self.adx_threshold})",
                "MB Dist": f"{dist_pct:+.2f}% (Target: ~0.0%)",
                "RSI": f"{ta.rsi(df['close']).iloc[-1]:.1f} (Min: {self.rsi_min})"
            }
        except Exception as e:
            return {"Error": str(e)}

