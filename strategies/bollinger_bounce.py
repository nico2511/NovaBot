"""
Bollinger Bounce - AGGRESSIVE RANGE VERSION (Consolidated 2026)
Trades volatility within "Choppy" markets, not just perfect flats.
"""

import pandas as pd
import numpy as np
from typing import Optional, Dict, List
from strategies.base import BaseStrategy
from app.services.indicators import ta

class BollingerBounceStrategy(BaseStrategy):
    """
    Bollinger Bounce strategy logic.
    """
    
    AI_PERSONA = """
    CODENAME: "SHIELD - MEAN REVERSION SNIPER"
    
    ROLE:
    You are a PATIENT COUNTER-TREND SPECIALIST. You hunt for exhaustion, not just movement.
    
    PRIME DIRECTIVE:
    "Don't catch a falling knife, catch the bounce." We need statistical extremes to enter.
    
    RULES OF ENGAGEMENT:
    1. STRICT RANGE ONLY: ADX must be LOW. If ADX is rising above 30, the beast is waking up -> ABORT TRADES.
    2. EXHAUSTION IS KEY: We do not trade every touch of the Bollinger Band. We trade when the price shows exhaustion "Oversold" (RSI < 40) or "Overbought" (RSI > 60).
    3. FADE THE SPIKES: We love vertical moves into resistance. Moving slowly to the band is risky (trend grinding). We want a violent rejection.
    4. PROTECT THE CAPITAL: If the price closes OUTSIDE the band and stays there, it's a breakout. DO NOT FADE. We need a "Wick" rejection.
    
    RESPONSE STYLE:
    Protective, skeptical.
    "RSI not extreme enough - Pass.", "ADX rising - Risk of breakout - Pass."
    """
    
    def __init__(self, config=None):
        super().__init__(config)
        self.bb_period = self.params.get("bb_period", 20)
        self.bb_std = self.params.get("bb_std", 2.15)  # Match strategies.json
        
        # --- Config Params ---
        self.adx_threshold = self.params.get("adx_threshold", 22)  # CHANGED 2026-02: 25 -> 22 (More strict range)
        self.adx_period = self.params.get("adx_period", 14)
        
        self.ema50_slope_threshold = self.params.get("ema50_slope_threshold", 0.008)  # Match strategies.json 
        
        self.atr_period = self.params.get("atr_period", 14)
        self.min_rr = self.params.get("min_rr", 1.3)  # CHANGED 2026-02: 1.5 -> 1.3
        
        # New Params
        self.kill_zone_percent = self.params.get("kill_zone_percent", 0.16)
        # Reduced candle size requirement slightly
        self.min_candle_atr_multiple = self.params.get("min_candle_atr_multiple", 1.0) # CHANGED 2026-02: 1.1 -> 1.0
        self.volume_multiplier = self.params.get("volume_multiplier", 1.2)
        self.sl_atr_mult = self.params.get("sl_atr_mult", 0.8) # Relaxed SL
    
    def is_ranging(self, df: pd.DataFrame) -> tuple[bool, str]:
        """
        Detect if market is tradable as a range (relaxed criteria).
        """
        try:
            # ADX Check
            adx_res = ta.adx(df['high'], df['low'], df['close'], length=self.adx_period)
            current_adx = adx_res['ADX'].iloc[-2]
            
            if current_adx >= self.adx_threshold:
                return False, f"Trend too strong (ADX {current_adx:.1f})"
            
            # EMA Slope Check
            ema_50 = ta.ema(df['close'], length=50)
            ema_slope = (ema_50.iloc[-1] - ema_50.iloc[-5]) / ema_50.iloc[-5]
            
            if abs(ema_slope) > self.ema50_slope_threshold:
                return False, f"Slope too steep ({ema_slope:.4f})"
            
            return True, f"Choppy/Range confirmed (ADX={current_adx:.1f})"
        
        except Exception as e:
            return False, f"Error detection: {e}"
    
    def generate_signal(self, df: pd.DataFrame, extra_data=None) -> Optional[Dict]:
        """
        Generate signal with RELAXED proximity checks + Candle Size Filter.
        """
        if df is None or df.empty or len(df) < 60:
            return None
        
        try:
            # 1. Regime Check
            is_range, reason = self.is_ranging(df)
            if not is_range:
                return None
            
            # 2. Indicators
            bb = ta.bbands(df['close'], length=self.bb_period, std=self.bb_std)
            atr = ta.atr(df['high'], df['low'], df['close'], length=self.atr_period)
            
            current_price = df['close'].iloc[-1] # Close of current forming candle? or completed? Usually use completed for Backtest, but Live allows current. Wait, user said "Last Close: 0.36" implies completed. For safety with spikes, we can check current.
            # Using -1 (current closing price) for check
            
            current_high = df['high'].iloc[-1]
            current_low = df['low'].iloc[-1]
            current_open = df['open'].iloc[-1]
            
            bb_upper = bb['BBU'].iloc[-1]
            bb_lower = bb['BBL'].iloc[-1]
            bb_basis = bb['BBM'].iloc[-1] # Middle Band
            current_atr = atr.iloc[-1]
            
            # RSI Filter (Added for Safety)
            rsi = ta.rsi(df['close'], length=14)
            current_rsi = rsi.iloc[-1]
            
            # Calcul de la largeur du range
            bb_width = bb_upper - bb_lower
            
            # FILTRE DE VOLATILITÉ MINIMALE
            if bb_width / current_price < 0.003: 
                return None

            # Kill Zone
            kill_zone_size = bb_width * self.kill_zone_percent
            
            upper_trigger_zone = bb_upper - kill_zone_size
            lower_trigger_zone = bb_lower + kill_zone_size
            
            # Dynamic TP 
            tp_padding = bb_width * 0.05 
            
            # Candle Size Check (Is the candle significant?)
            candle_body = abs(current_price - current_open)
            candle_range = current_high - current_low
            is_significant = candle_range >= (current_atr * self.min_candle_atr_multiple) # Request: Candle >= 1.0 * ATR
            
            # === SIGNAL LONG ===
            if current_low <= lower_trigger_zone:
                
                # RSI Safety Check: Must be oversold (or close) to buy bounce
                # CHANGED 2026-02: 40 -> 35 (Wider neutral zone)
                if current_rsi > 35: 
                     return None

                
                if self.min_candle_atr_multiple > 0 and not is_significant:
                    # Weak candle, ignore
                    return None
                
                # Volume Filter
                if 'volume' in df.columns:
                    current_vol = df['volume'].iloc[-2]
                    avg_vol = df['volume'].iloc[-22:-2].mean()
                    if avg_vol > 0 and current_vol < avg_vol * self.volume_multiplier:
                        return None

                entry = current_price
                tp = bb_basis + tp_padding
                sl = bb_lower - (current_atr * self.sl_atr_mult)  # SL from config
                
                risk = entry - sl
                reward = tp - entry
                
                if risk > 0 and (reward / risk) >= self.min_rr: 
                    return {
                        "signal": "BUY",
                        "sl": sl,
                        "tp": tp,
                        "comment": f"Range Dip Buying (Zone: {lower_trigger_zone:.4f}, Vol: {candle_range/current_atr:.1f}xATR)"
                    }
            
            # === SIGNAL SHORT ===
            if current_high >= upper_trigger_zone:
                
                # RSI Safety Check: Must be overbought to short bounce
                # CHANGED 2026-02: 60 -> 65 (Wider neutral zone)
                if current_rsi < 65: 
                    return None

                
                if self.min_candle_atr_multiple > 0 and not is_significant:
                    return None
                
                # Volume Filter
                if 'volume' in df.columns:
                    current_vol = df['volume'].iloc[-2]
                    avg_vol = df['volume'].iloc[-22:-2].mean()
                    if avg_vol > 0 and current_vol < avg_vol * self.volume_multiplier:
                        return None

                entry = current_price
                tp = bb_basis - tp_padding
                sl = bb_upper + (current_atr * self.sl_atr_mult)  # SL from config
                
                risk = sl - entry
                reward = entry - tp
                
                if risk > 0 and (reward / risk) >= self.min_rr:
                    return {
                        "signal": "SELL",
                        "sl": sl,
                        "tp": tp,
                        "comment": f"Range Top Shorting (Zone: {upper_trigger_zone:.4f}, Vol: {candle_range/current_atr:.1f}xATR)"
                    }
            
            return None
        
        except Exception as e:
            return None
    
    def calculate_progress(self, df: pd.DataFrame, extra_data=None):
        """
        Returns detailed progress stages for monitoring.
        Stages:
        1. Context (Regime Check)
        2. Filter (Kill Zone & RSI)
        3. Trigger (Candle & Vol)
        """
        if df is None or df.empty or len(df) < 60:
             return {
                "strategy": "Bollinger Bounce",
                "score": 0,
                "stages": [{"name": "Data Check", "status": "FAIL", "details": "Not enough data"}]
            }
        
        try:
            # 1. Regime Check
            is_range, reason = self.is_ranging(df)
            
            # ADX for metrics
            adx_res = ta.adx(df['high'], df['low'], df['close'], length=self.adx_period)
            current_adx = adx_res['ADX'].iloc[-2]
            
            s1_status = "PASS" if is_range else "WAIT"
            s1_details = reason
            
            stages = []
            stages.append({
                "name": "1. Regime (Range)",
                "status": s1_status,
                "details": s1_details,
                "metrics": {
                    "adx": {"value": round(current_adx, 1), "threshold": self.adx_threshold, "op": "<"}
                }
            })
            
            # 2. Filter (Kill Zone)
            bb = ta.bbands(df['close'], length=self.bb_period, std=self.bb_std)
            current_price = df['close'].iloc[-1]
            bb_upper = bb['BBU'].iloc[-1]
            bb_lower = bb['BBL'].iloc[-1]
            bb_width = bb_upper - bb_lower
            
            kill_zone_size = bb_width * self.kill_zone_percent
            upper_trigger_zone = bb_upper - kill_zone_size
            lower_trigger_zone = bb_lower + kill_zone_size
            
            # Check RSI
            rsi = ta.rsi(df['close'], length=14)
            current_rsi = rsi.iloc[-1]
            
            in_buy_zone = current_price <= lower_trigger_zone
            in_sell_zone = current_price >= upper_trigger_zone
            
            s2_status = "WAIT"
            s2_details = "Mid-Range: No Zone"
            
            if in_buy_zone:
                if current_rsi <= 45: # Relaxed check for monitoring visual
                    s2_status = "READY (BUY)"
                    s2_details = f"In Buy Zone (RSI {current_rsi:.1f})"
                else: 
                     s2_details = f"In Buy Zone but RSI High ({current_rsi:.1f})"
            elif in_sell_zone:
                 if current_rsi >= 55:
                    s2_status = "READY (SELL)"
                    s2_details = f"In Sell Zone (RSI {current_rsi:.1f})"
                 else:
                    s2_details = f"In Sell Zone but RSI Low ({current_rsi:.1f})"

            stages.append({
                "name": "2. Kill Zone",
                "status": s2_status,
                "details": s2_details,
                 "metrics": {
                    "dist_lower": {"value": round(current_price - lower_trigger_zone, 4), "threshold": 0, "op": "<"},
                    "dist_upper": {"value": round(upper_trigger_zone - current_price, 4), "threshold": 0, "op": "<"}
                }
            })
            
            # 3. Trigger
            # We need a rejection candle (wick or reversal)
            # This is hard to predict on the *forming* candle, but we monitor the *potential*
            
            atr = ta.atr(df['high'], df['low'], df['close'], length=self.atr_period)
            current_atr = atr.iloc[-1]
            current_range = df['high'].iloc[-1] - df['low'].iloc[-1]
            
            is_significant = current_range >= (current_atr * self.min_candle_atr_multiple)
            
            s3_status = "WAIT"
            s3_details = "Waiting for volatility..."
            
            if s2_status.startswith("READY"):
                if is_significant:
                    s3_status = "POTENTIAL"
                    s3_details = f"Volatile Candle ({current_range/current_atr:.1f}x ATR)"
                else:
                    s3_details = f"Low Volatility ({current_range/current_atr:.1f}x ATR)"
            
            stages.append({
                "name": "3. Rejection Trigger",
                "status": s3_status,
                "details": s3_details
            })
            
            # Score
            score = 0
            if s1_status == "PASS": score += 30
            if "READY" in s2_status: score += 40
            if s3_status == "POTENTIAL": score += 30
            
            return {
                "strategy": "Bollinger Bounce",
                "score": score,
                "stages": stages
            }
            
        except Exception as e:
             return {
                "strategy": "Bollinger Bounce",
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
            adx_res = ta.adx(df['high'], df['low'], df['close'], length=self.adx_period)
            adx = adx_res['ADX'].iloc[-1]
            
            bb = ta.bbands(df['close'], length=self.bb_period, std=self.bb_std)
            price = df['close'].iloc[-1]
            width = bb['BBU'].iloc[-1] - bb['BBL'].iloc[-1]
            
            dist_lower = price - bb['BBL'].iloc[-1]
            dist_upper = bb['BBU'].iloc[-1] - price
            min_dist = min(dist_lower, dist_upper)
            
            return {
                "ADX": f"{adx:.1f} (Max: {self.adx_threshold})",
                "Band Dist": f"{min_dist/width*100:.1f}% (Zone: {self.kill_zone_percent*100:.0f}%)",
            }
        except Exception as e:
            return {"Error": str(e)}
