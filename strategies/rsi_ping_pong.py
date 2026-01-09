"""
RSI Ping Pong Range Trading Strategy

Trades RSI extremes in confirmed ranging markets with pivot confirmation.
Uses fast RSI (7) for better reactivity in sideways markets.

Strategy Logic:
- LONG: RSI < 30 + crosses up + price near recent pivot low
- SHORT: RSI > 70 + crosses down + price near recent pivot high
- TP: EMA 20 (mean reversion)
- SL: Pivot ± ATR
- Kill Switch: Exit if ADX > 25 (trend breakout)

Author: NovaBot Team
Date: 2026-01-04
"""

import pandas as pd
import numpy as np
from typing import Optional, Dict, List
from strategies.base import BaseStrategy
from app.services.indicators import ta


class RSIPingPongStrategy(BaseStrategy):
    """
    RSI Ping Pong strategy for range-bound markets.
    
    Uses fast RSI with pivot confirmation for high-probability reversals.
    Only activates when market is confirmed ranging (ADX < 25).
    """
    
    def __init__(self, config=None):
        super().__init__(config)
        self.rsi_period = self.params.get("rsi_period", 7)  # Fast RSI for range
        self.rsi_oversold = self.params.get("rsi_oversold", 30)
        self.rsi_overbought = self.params.get("rsi_overbought", 70)
        self.adx_threshold = self.params.get("adx_threshold", 25)
        self.pivot_order = self.params.get("pivot_order", 5)
        self.pivot_lookback = self.params.get("pivot_lookback", 20)
        self.pivot_tolerance = self.params.get("pivot_tolerance", 0.02)  # 2%
        self.atr_period = self.params.get("atr_period", 14)
        self.atr_sl_multiplier = self.params.get("atr_sl_multiplier", 1.5)
        self.min_rr = self.params.get("min_rr", 1.0)
    
    def _find_recent_pivots(self, df: pd.DataFrame) -> Dict[str, float]:
        """
        Find most recent pivot high and low.
        
        Returns:
            {'pivot_low': price, 'pivot_high': price}
        """
        try:
            pivots = {'pivot_low': None, 'pivot_high': None}
            
            # Search for pivots in lookback window
            start_idx = max(0, len(df) - self.pivot_lookback - self.pivot_order)
            end_idx = len(df) - self.pivot_order
            
            for i in range(end_idx - 1, start_idx, -1):
                # Check for pivot low
                if pivots['pivot_low'] is None:
                    window_before = df['low'].iloc[i-self.pivot_order:i]
                    window_after = df['low'].iloc[i+1:i+self.pivot_order+1]
                    
                    if len(window_before) > 0 and len(window_after) > 0:
                        if (df['low'].iloc[i] < window_before.min()) and \
                           (df['low'].iloc[i] < window_after.min()):
                            pivots['pivot_low'] = df['low'].iloc[i]
                
                # Check for pivot high
                if pivots['pivot_high'] is None:
                    window_before = df['high'].iloc[i-self.pivot_order:i]
                    window_after = df['high'].iloc[i+1:i+self.pivot_order+1]
                    
                    if len(window_before) > 0 and len(window_after) > 0:
                        if (df['high'].iloc[i] > window_before.max()) and \
                           (df['high'].iloc[i] > window_after.max()):
                            pivots['pivot_high'] = df['high'].iloc[i]
                
                # Stop if both found
                if pivots['pivot_low'] and pivots['pivot_high']:
                    break
            
            return pivots
        
        except Exception as e:
            print(f"Error finding pivots: {e}")
            return {'pivot_low': None, 'pivot_high': None}
    
    def is_ranging(self, df: pd.DataFrame) -> tuple[bool, str]:
        """
        Detect if market is in range (sideways).
        
        Criteria:
        - ADX < threshold (no strong trend)
        
        Returns:
            (is_range, reason)
        """
        try:
            adx_res = ta.adx(df['high'], df['low'], df['close'], length=14)
            current_adx = adx_res['ADX'].iloc[-1]
            
            if current_adx >= self.adx_threshold:
                return False, f"ADX too high ({current_adx:.1f} >= {self.adx_threshold})"
            
            return True, f"Range confirmed (ADX={current_adx:.1f})"
        
        except Exception as e:
            return False, f"Error in range detection: {e}"
    
    def generate_signal(self, df: pd.DataFrame, extra_data=None) -> Optional[Dict]:
        """
        Generate trading signal if RSI ping pong conditions are met.
        
        Returns:
            Signal dict with entry, SL, TP if valid, None otherwise
        """
        if df is None or df.empty or len(df) < 60:
            return None
        
        try:
            # 1. Check if market is ranging
            is_range, reason = self.is_ranging(df)
            if not is_range:
                return None
            
            # 2. Calculate indicators
            rsi = ta.rsi(df['close'], length=self.rsi_period)
            ema_20 = ta.ema(df['close'], length=20)
            atr = ta.atr(df['high'], df['low'], df['close'], length=self.atr_period)
            
            # ANTI-REPAINTING: Use completed candles only
            # Current = iloc[-2] (last completed candle)
            # Previous = iloc[-3] (candle before that)
            current_rsi = rsi.iloc[-2]
            prev_rsi = rsi.iloc[-3]
            current_price = df['close'].iloc[-2]
            current_ema20 = ema_20.iloc[-2]
            current_atr = atr.iloc[-2]
            
            # 3. Find recent pivots
            pivots = self._find_recent_pivots(df)
            
            # 4. Check for LONG signal (RSI oversold + pivot low)
            rsi_oversold = current_rsi < self.rsi_oversold
            rsi_crossing_up = current_rsi > prev_rsi
            
            if rsi_oversold and rsi_crossing_up and pivots['pivot_low']:
                # Check if price is near pivot low
                distance_to_pivot = abs(current_price - pivots['pivot_low']) / current_price
                
                if distance_to_pivot < self.pivot_tolerance:
                    entry = current_price
                    tp = current_ema20  # Mean reversion target
                    sl = pivots['pivot_low'] - (current_atr * self.atr_sl_multiplier)
                    
                    # Check R:R
                    risk = entry - sl
                    reward = tp - entry
                    rr_ratio = reward / risk if risk > 0 else 0
                    
                    if rr_ratio >= self.min_rr:
                        return {
                            "signal": "BUY",
                            "sl": sl,
                            "tp": tp,
                            "comment": f"RSI Ping Pong Long (RSI:{current_rsi:.1f}, R:R {rr_ratio:.2f})"
                        }
            
            # 5. Check for SHORT signal (RSI overbought + pivot high)
            rsi_overbought = current_rsi > self.rsi_overbought
            rsi_crossing_down = current_rsi < prev_rsi
            
            if rsi_overbought and rsi_crossing_down and pivots['pivot_high']:
                # Check if price is near pivot high
                distance_to_pivot = abs(current_price - pivots['pivot_high']) / current_price
                
                if distance_to_pivot < self.pivot_tolerance:
                    entry = current_price
                    tp = current_ema20  # Mean reversion target
                    sl = pivots['pivot_high'] + (current_atr * self.atr_sl_multiplier)
                    
                    # Check R:R
                    risk = sl - entry
                    reward = entry - tp
                    rr_ratio = reward / risk if risk > 0 else 0
                    
                    if rr_ratio >= self.min_rr:
                        return {
                            "signal": "SELL",
                            "sl": sl,
                            "tp": tp,
                            "comment": f"RSI Ping Pong Short (RSI:{current_rsi:.1f}, R:R {rr_ratio:.2f})"
                        }
            
            return None
        
        except Exception as e:
            print(f"Error in RSIPingPong signal generation: {e}")
            return None
    
    def calculate_progress(self, df: pd.DataFrame, extra_data=None) -> int:
        """
        Calculate how close we are to an RSI ping pong signal (0-100%).
        
        Progress breakdown:
        - 30% if in range regime
        - 30% if RSI in extreme zone
        - 20% if near pivot
        - 20% if RSI showing reversal momentum
        """
        if df is None or df.empty or len(df) < 60:
            return 0
        
        try:
            progress = 0
            
            # 1. Range regime (30 points)
            is_range, _ = self.is_ranging(df)
            if is_range:
                progress += 30
            
            # 2. RSI in extreme zone (30 points)
            rsi = ta.rsi(df['close'], length=self.rsi_period)
            current_rsi = rsi.iloc[-1]
            
            if current_rsi < 35 or current_rsi > 65:
                # In extreme zone
                if current_rsi < self.rsi_oversold or current_rsi > self.rsi_overbought:
                    progress += 30
                else:
                    progress += 15
            
            # 3. Near pivot (20 points)
            pivots = self._find_recent_pivots(df)
            current_price = df['close'].iloc[-1]
            
            if pivots['pivot_low']:
                distance_to_low = abs(current_price - pivots['pivot_low']) / current_price
                if distance_to_low < self.pivot_tolerance:
                    progress += 20
            
            if pivots['pivot_high']:
                distance_to_high = abs(current_price - pivots['pivot_high']) / current_price
                if distance_to_high < self.pivot_tolerance:
                    progress += 20
            
            # 4. RSI reversal momentum (20 points)
            prev_rsi = rsi.iloc[-2]
            rsi_delta = current_rsi - prev_rsi
            
            if (current_rsi < self.rsi_oversold and rsi_delta > 0) or \
               (current_rsi > self.rsi_overbought and rsi_delta < 0):
                progress += 20
            
            return min(100, progress)
        
        except:
            return 0
    
    def check_conditions(self, df: pd.DataFrame, extra_data=None) -> List[Dict]:
        """
        Check detailed conditions for UI - Diagnostic Card
        
        Returns:
            List of condition dicts with name, status, and value
        """
        if df is None or df.empty or len(df) < 60:
            return []
        
        try:
            conditions = []
            
            # 1. Range Regime
            is_range, reason = self.is_ranging(df)
            adx_res = ta.adx(df['high'], df['low'], df['close'], length=14)
            current_adx = adx_res['ADX'].iloc[-1]
            
            conditions.append({
                "name": f"Range Regime",
                "status": is_range,
                "value": ""
            })
            
            # 2. RSI Extreme
            rsi = ta.rsi(df['close'], length=self.rsi_period)
            current_rsi = rsi.iloc[-1]
            prev_rsi = rsi.iloc[-2]
            
            in_extreme = current_rsi < self.rsi_oversold or current_rsi > self.rsi_overbought
            
            conditions.append({
                "name": "RSI Extreme Zone",
                "status": in_extreme,
                "value": ""
            })
            
            # 3. Near Pivot
            pivots = self._find_recent_pivots(df)
            current_price = df['close'].iloc[-1]
            
            near_pivot = False
            pivot_info = "None"
            dist_pct = 0.0
            
            if pivots['pivot_low']:
                distance = abs(current_price - pivots['pivot_low']) / current_price
                if distance < self.pivot_tolerance:
                    near_pivot = True
                    pivot_info = f"Low ${pivots['pivot_low']:.2f}"
                    dist_pct = distance * 100
            
            if pivots['pivot_high']:
                distance = abs(current_price - pivots['pivot_high']) / current_price
                if distance < self.pivot_tolerance:
                    near_pivot = True
                    pivot_info = f"High ${pivots['pivot_high']:.2f}"
                    dist_pct = distance * 100
            
            conditions.append({
                "name": "Pivot Proximity",
                "status": near_pivot,
                "value": ""
            })
            
            # 4. RSI Reversal
            rsi_delta = current_rsi - prev_rsi
            reversing = (current_rsi < self.rsi_oversold and rsi_delta > 0) or \
                       (current_rsi > self.rsi_overbought and rsi_delta < 0)
            
            conditions.append({
                "name": "RSI Reversal Momentum",
                "status": reversing,
                "value": ""
            })
            
            return conditions
        
        except Exception as e:
            return [{"name": "Error", "status": False, "value": str(e)}]
    
    def get_threshold_comparisons(self, df, extra_data=None):
        """Get detailed threshold comparisons for Parameters section"""
        if df is None or df.empty: return {}
        try:
            self.add_indicators(df)
            adx_res = ta.adx(df['high'], df['low'], df['close'], length=14)
            current_adx = adx_res['ADX'].iloc[-1]
            rsi = ta.rsi(df['close'], length=self.rsi_period)
            current_rsi = rsi.iloc[-1]
            pivots = self._find_recent_pivots(df)
            current_price = df['close'].iloc[-1]
            
            p_text = "None"
            if pivots['pivot_low']:
                d = abs(current_price - pivots['pivot_low']) / current_price
                if d < 0.05: p_text = f"Low ({d*100:.2f}%)"
            if pivots['pivot_high']:
                d = abs(current_price - pivots['pivot_high']) / current_price
                if d < 0.05: p_text = f"High ({d*100:.2f}%)"
            
            return {
                "Range (ADX)": f"{current_adx:.1f} vs Max: {self.adx_threshold}",
                "RSI": f"{current_rsi:.1f} (L: {self.rsi_oversold}, H: {self.rsi_overbought})",
                "Pivot": p_text
            }
        except Exception as e: return {"Error": str(e)}

