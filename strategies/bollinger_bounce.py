"""
Bollinger Bounce Range Trading Strategy

Trades bounces off Bollinger Bands in confirmed ranging markets.
Includes ADX kill switch to exit on trend breakouts.

Strategy Logic:
- LONG: Price touches lower band and bounces back
- SHORT: Price touches upper band and bounces back
- TP: Middle band (mean reversion)
- SL: Band ± ATR
- Kill Switch: Exit if ADX > 25 (trend breakout)

Author: NovaBot Team
Date: 2026-01-04
"""

import pandas as pd
import numpy as np
from typing import Optional, Dict, List
from strategies.base import BaseStrategy
from app.services.indicators import ta


class BollingerBounceStrategy(BaseStrategy):
    """
    Bollinger Bounce strategy for range-bound markets.
    
    Only activates when market is confirmed ranging (ADX < 25).
    Exits immediately if ADX breaks above threshold (kill switch).
    """
    
AI_PERSONA = """
    CODENAME: "APEX RANGER - BOUNDARY GUARDIAN"
    
    ROLE:
    You are the MASTER OF CONTAINMENT. You do not fear volatility; you trap it.
    
    PRIME DIRECTIVE:
    "The Bands are Electric Fences." Nothing escapes the range without a fight. We short the highs and buy the lows.
    
    RULES OF ENGAGEMENT (OVERRIDES):
    1. RANGE IS RELATIVE: Do not demand a perfectly flat dead market. If ADX is under 30, the trend is weak enough to fade. ENGAGE.
    2. THE "TOUCH" IS ENOUGH: If price slams into the band, don't wait for a perfect rejection candle if the extension is extreme. Front-run the reversal.
    3. IGNORE THE NOISE: Small breakouts (wicks) are fake-outs. Use them as better entry prices. We do not panic exit on a wick.
    4. VOLATILITY IS PROFIT: Expanding bands are not a warning; they are a bigger target. A wider range means more profit potential.
    
    RESPONSE STYLE:
    Confident, territorial, aggressive.
    "Intruder at the upper band - SHIELD UP (Short)", "Price floor tested - HOLD THE LINE (Buy)".
    """
    
    def __init__(self, config=None):
        super().__init__(config)
        self.bb_period = self.params.get("bb_period", 20)
        self.bb_std = self.params.get("bb_std", 2.0)
        self.adx_threshold = self.params.get("adx_threshold", 30)
        self.adx_period = self.params.get("adx_period", 14)
        self.bandwidth_expansion_limit = self.params.get("bandwidth_expansion_limit", 1.2)
        self.ema50_slope_threshold = self.params.get("ema50_slope_threshold", 0.001)
        self.atr_period = self.params.get("atr_period", 14)
        self.atr_sl_multiplier = self.params.get("atr_sl_multiplier", 1.0)
        self.min_rr = self.params.get("min_rr", 1.0)
    
    def is_ranging(self, df: pd.DataFrame) -> tuple[bool, str]:
        """
        Detect if market is in range (sideways).
        
        Criteria:
        1. ADX < threshold (no strong trend)
        2. EMA 50 slope near zero (flat market)
        3. Bollinger Bandwidth stable (not expanding)
        
        Returns:
            (is_range, reason)
        """
        try:
            # Calculate ADX
            adx_res = ta.adx(df['high'], df['low'], df['close'], length=self.adx_period)
            current_adx = adx_res['ADX'].iloc[-2]
            
            if current_adx >= self.adx_threshold:
                return False, f"ADX too high ({current_adx:.1f} >= {self.adx_threshold})"
            
            # Calculate EMA 50 slope
            ema_50 = ta.ema(df['close'], length=50)
            ema_slope = (ema_50.iloc[-1] - ema_50.iloc[-5]) / ema_50.iloc[-5]
            
            if abs(ema_slope) > self.ema50_slope_threshold:
                return False, f"EMA50 slope too steep ({ema_slope:.4f})"
            
            # Calculate Bollinger Bandwidth
            bb = ta.bbands(df['close'], length=self.bb_period, std=self.bb_std)
            bb_width = (bb['BBU'].iloc[-1] - bb['BBL'].iloc[-1]) / bb['BBM'].iloc[-1]
            bb_width_sma = pd.Series([
                (bb['BBU'].iloc[i] - bb['BBL'].iloc[i]) / bb['BBM'].iloc[i]
                for i in range(len(bb) - 20, len(bb))
            ]).mean()
            
            if bb_width > bb_width_sma * self.bandwidth_expansion_limit:
                return False, f"Bandwidth expanding ({bb_width:.4f} > {bb_width_sma * self.bandwidth_expansion_limit:.4f})"
            
            return True, f"Range confirmed (ADX={current_adx:.1f}, Slope={ema_slope:.4f})"
        
        except Exception as e:
            return False, f"Error in range detection: {e}"
    
    def generate_signal(self, df: pd.DataFrame, extra_data=None) -> Optional[Dict]:
        """
        Generate trading signal if Bollinger bounce conditions are met.
        
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
            bb = ta.bbands(df['close'], length=self.bb_period, std=self.bb_std)
            atr = ta.atr(df['high'], df['low'], df['close'], length=self.atr_period)
            
            current_price = df['close'].iloc[-1]
            current_low = df['low'].iloc[-1]
            current_high = df['high'].iloc[-1]
            
            bb_upper = bb['BBU'].iloc[-1]
            bb_lower = bb['BBL'].iloc[-1]
            bb_basis = bb['BBM'].iloc[-1]
            current_atr = atr.iloc[-1]
            
            # Check Volatility Filter (Bandwidth Percentile)
            # Avoid trading dead markets
            min_bandwidth_percentile = self.params.get("min_bandwidth_percentile", 20)
            if min_bandwidth_percentile > 0:
                current_bb_width = (bb['BBU'].iloc[-1] - bb['BBL'].iloc[-1]) / bb['BBM'].iloc[-1]
                
                # Calculate rolling percentile
                hist_width = (bb['BBU'] - bb['BBL']) / bb['BBM']
                percentile = hist_width.rolling(100).rank(pct=True).iloc[-1] * 100
                
                if percentile < min_bandwidth_percentile:
                    return None # Market too dead
            
            # Dynamic TP Calculation (Target Opposite Band + Boost)
            bb_width = bb_upper - bb_lower
            tp_boost = bb_width * 0.2
            
            # 3. Check for LONG signal (bounce off lower band)
            touched_lower = current_low <= bb_lower
            bounced_up = current_price > bb_lower
            
            if touched_lower and bounced_up:
                entry = current_price
                tp = bb_upper + tp_boost  # Dynamic TP: Upper Band + Boost
                sl = bb_lower - (current_atr * self.atr_sl_multiplier)
                
                # Check R:R
                risk = entry - sl
                reward = tp - entry
                rr_ratio = reward / risk if risk > 0 else 0
                
                if rr_ratio >= self.min_rr:
                    return {
                        "signal": "BUY",
                        "sl": sl,
                        "tp": tp,
                        "comment": f"Bollinger Bounce Long (R:R {rr_ratio:.2f}, Vol {percentile:.0f}%)"
                    }
            
            # 4. Check for SHORT signal (bounce off upper band)
            touched_upper = current_high >= bb_upper
            bounced_down = current_price < bb_upper
            
            if touched_upper and bounced_down:
                entry = current_price
                tp = bb_lower - tp_boost  # Dynamic TP: Lower Band - Boost
                sl = bb_upper + (current_atr * self.atr_sl_multiplier)
                
                # Check R:R
                risk = sl - entry
                reward = entry - tp
                rr_ratio = reward / risk if risk > 0 else 0
                
                if rr_ratio >= self.min_rr:
                    return {
                        "signal": "SELL",
                        "sl": sl,
                        "tp": tp,
                        "comment": f"Bollinger Bounce Short (R:R {rr_ratio:.2f}, Vol {percentile:.0f}%)"
                    }
            
            return None
        
        except Exception as e:
            print(f"Error in BollingerBounce signal generation: {e}")
            return None
    
    def calculate_progress(self, df: pd.DataFrame, extra_data=None) -> int:
        """
        Calculate how close we are to a Bollinger bounce signal (0-100%).
        
        Progress breakdown:
        - 30% if in range regime
        - 30% if price near band
        - 20% if bandwidth stable
        - 20% if EMA slope flat
        """
        if df is None or df.empty or len(df) < 60:
            return 0
        
        try:
            progress = 0
            
            # 1. Range regime (30 points)
            is_range, _ = self.is_ranging(df)
            if is_range:
                progress += 30
            
            # 2. Price proximity to bands (30 points)
            bb = ta.bbands(df['close'], length=self.bb_period, std=self.bb_std)
            current_price = df['close'].iloc[-1]
            bb_upper = bb['BBU'].iloc[-1]
            bb_lower = bb['BBL'].iloc[-1]
            bb_range = bb_upper - bb_lower
            
            distance_to_lower = abs(current_price - bb_lower) / bb_range
            distance_to_upper = abs(current_price - bb_upper) / bb_range
            min_distance = min(distance_to_lower, distance_to_upper)
            
            if min_distance < 0.05:  # Within 5% of band
                progress += 30
            elif min_distance < 0.15:  # Within 15%
                progress += int(30 * (1 - min_distance / 0.15))
            
            # 3. Bandwidth stable (20 points)
            bb_width = (bb_upper - bb_lower) / bb['BBM'].iloc[-1]
            bb_width_sma = pd.Series([
                (bb['BBU'].iloc[i] - bb['BBL'].iloc[i]) / bb['BBM'].iloc[i]
                for i in range(len(bb) - 20, len(bb))
            ]).mean()
            
            if bb_width < bb_width_sma * self.bandwidth_expansion_limit:
                progress += 20
            
            # 4. EMA slope flat (20 points)
            ema_50 = ta.ema(df['close'], length=50)
            ema_slope = abs((ema_50.iloc[-1] - ema_50.iloc[-5]) / ema_50.iloc[-5])
            
            if ema_slope < self.ema50_slope_threshold:
                progress += 20
            
            return min(100, progress)
        
        except:
            return 0
    
    def check_conditions(self, df: pd.DataFrame, extra_data=None) -> List[Dict]:
        """
        Check detailed conditions for UI display.
        
        Returns:
            List of condition dicts with name, status, and value
        """
        if df is None or df.empty or len(df) < 60:
            return []
        
        try:
            conditions = []
            
            # 1. Range Regime
            is_range, reason = self.is_ranging(df)
            adx_res = ta.adx(df['high'], df['low'], df['close'], length=self.adx_period)
            current_adx = adx_res['ADX'].iloc[-2]
            
            conditions.append({
                "name": f"Range Regime (ADX < {self.adx_threshold})",
                "status": is_range,
                "value": f"ADX: {current_adx:.1f}"
            })
            
            # 2. Price at Band
            bb = ta.bbands(df['close'], length=self.bb_period, std=self.bb_std)
            current_price = df['close'].iloc[-1]
            bb_upper = bb['BBU'].iloc[-1]
            bb_lower = bb['BBL'].iloc[-1]
            
            at_lower = abs(current_price - bb_lower) / current_price < 0.01
            at_upper = abs(current_price - bb_upper) / current_price < 0.01
            at_band = at_lower or at_upper
            
            band_name = "Lower" if at_lower else "Upper" if at_upper else "None"
            conditions.append({
                "name": "Price at Band",
                "status": at_band,
                "value": f"{band_name} (${current_price:.4f})"
            })
            
            # 3. Bandwidth Stable
            bb_width = (bb_upper - bb_lower) / bb['BBM'].iloc[-1]
            bb_width_sma = pd.Series([
                (bb['BBU'].iloc[i] - bb['BBL'].iloc[i]) / bb['BBM'].iloc[i]
                for i in range(len(bb) - 20, len(bb))
            ]).mean()
            
            bandwidth_ok = bb_width < bb_width_sma * self.bandwidth_expansion_limit
            conditions.append({
                "name": "Bandwidth Stable",
                "status": bandwidth_ok,
                "value": f"{(bb_width / bb_width_sma):.2f}x avg"
            })
            
            # 4. R:R Ratio
            atr = ta.atr(df['high'], df['low'], df['close'], length=self.atr_period)
            current_atr = atr.iloc[-1]
            
            # Estimate R:R for potential long
            entry = current_price
            tp = bb['BBM'].iloc[-1]
            sl = bb_lower - (current_atr * self.atr_sl_multiplier)
            risk = entry - sl
            reward = tp - entry
            rr_ratio = reward / risk if risk > 0 else 0
            
            conditions.append({
                "name": f"R:R Ratio (Min {self.min_rr})",
                "status": rr_ratio >= self.min_rr,
                "value": f"{rr_ratio:.2f}"
            })
            
            return conditions
        
        except Exception as e:
            return [{"name": "Error", "status": False, "value": str(e)}]
