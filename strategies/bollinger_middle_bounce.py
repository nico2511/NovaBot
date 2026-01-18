
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
        
        self.adx_threshold = self.params.get("adx_threshold", 25)
        self.rsi_min = self.params.get("rsi_min", 40)
        
        self.min_rr = self.params.get("min_rr", 1.8)
        
        # NEW: sl_buffer_pct for dynamic SL calculation
        self.sl_buffer_pct = self.params.get("sl_buffer_pct", 0.008)  # 0.8% default
        # NEW: volume_multiplier for confirmation filter
        self.volume_multiplier = self.params.get("volume_multiplier", 1.2)
    
    def check_trend(self, df: pd.DataFrame) -> tuple[int, str]:
        """
        Check trend direction: 1 (Long), -1 (Short), 0 (Neutral)
        """
        try:
            # ADX Check
            adx_res = ta.adx(df['high'], df['low'], df['close'], length=14)
            current_adx = adx_res['ADX'].iloc[-1]
            
            if current_adx < self.adx_threshold:
                return 0, f"ADX too low ({current_adx:.1f})"
            
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
                # Interaction Check (Pullback): 
                # Price recently interacted with Middle Band (e.g. Low < MB or Close near MB)
                # And now confirming upward
                
                # Check confirmation candle: Green and closed above Middle Band
                is_green = df['close'].iloc[-1] > df['open'].iloc[-1]
                closes_above_mb = current_price > current_mb
                
                # Check recent touch (current or prev candle low touched MB)
                # Allow a small buffer (0.1% or similar) or strict crossover
                recent_touch = (df['low'].iloc[-1] <= current_mb * 1.001) or (prev_low <= prev_mb * 1.001)
                
                if is_green and closes_above_mb and recent_touch and volume_ok:
                     if rsi > self.rsi_min:
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

    def calculate_progress(self, df: pd.DataFrame, extra_data=None) -> int:
        """Visual progress bar logic."""
        if df is None or df.empty: return 0
        try:
            # 1. Trend Presence (50%)
            trend_dir, _ = self.check_trend(df)
            if trend_dir == 0: return 0
            progress = 50
            
            # 2. Proximity to Middle Band (50%)
            bb = ta.bbands(df['close'], length=self.bb_period, std=self.bb_std)
            mb = bb['BBM'].iloc[-1]
            price = df['close'].iloc[-1]
            
            dist_pct = abs(price - mb) / mb
            
            # Closer is better. If < 0.5% away, max score.
            if dist_pct < 0.005:
                progress += 50
            elif dist_pct < 0.015:
                progress += 30
            elif dist_pct < 0.03:
                progress += 10
            
            return min(100, progress)
        except:
            return 0

    def check_conditions(self, df: pd.DataFrame, extra_data=None) -> List[Dict]:
        """UI Conditions - Standardized Diagnostic Card"""
        if df is None or df.empty: return []
        try:
            conditions = []
            
            # 1. Trend
            trend_dir, trend_reason = self.check_trend(df)
            conditions.append({
                "name": "1. Trend Status",
                "status": trend_dir != 0,
                "value": trend_reason
            })
            
            # 2. Middle Band Interaction
            bb = ta.bbands(df['close'], length=self.bb_period, std=self.bb_std)
            msg = "No Interaction"
            status = False
            
            if trend_dir != 0:
                mb = bb['BBM'].iloc[-1]
                price = df['close'].iloc[-1]
                dist = (price - mb) / mb * 100
                
                # Check for "Touch" within 0.2%
                if abs(dist) < 0.2:
                    msg = f"Touching Middle Band ({dist:+.2f}%)"
                    status = True
                else:
                    msg = f"Distance: {dist:+.2f}%"
            
            conditions.append({
                "name": "2. Middle Band Touch",
                "status": status,
                "value": msg
            })
            
            # 3. Momentum
            rsi = ta.rsi(df['close'], length=14).iloc[-1]
            cond_name = "3. RSI Momentum"
            cond_val = f"RSI: {rsi:.1f}"
            cond_status = False
            
            if trend_dir == 1:
                cond_status = rsi > self.rsi_min
            elif trend_dir == -1:
                cond_status = rsi < (100 - self.rsi_min)
                
            conditions.append({
                "name": cond_name,
                "status": cond_status,
                "value": cond_val
            })
            
            return conditions
        except Exception as e:
            return [{"name": "Error", "status": False, "value": str(e)}]

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

