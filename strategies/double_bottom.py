"""
Double Bottom Pattern Recognition Strategy

Detects and trades double bottom reversal patterns with rigorous validation.

Pattern Characteristics:
- Two swing lows at similar price levels (within 2% tolerance)
- Neckline formed by peak between the lows
- Breakout above neckline with volume confirmation
- Bullish reversal signal

Entry Rules:
- Close > Neckline
- Volume > SMA(Volume, 20)
- R:R ratio > 1.5

Author: NovaBot Team
Date: 2026-01-04
"""

import pandas as pd
import numpy as np
from typing import Optional, Dict, List
from strategies.chart_patterns_base import ChartPatternBase


class DoubleBottomStrategy(ChartPatternBase):
    """
    Double Bottom pattern detection and trading strategy.
    
    Identifies two swing lows at similar levels, waits for neckline breakout,
    and enters long position with proper risk management.
    """
    
    def __init__(self, config=None):
        super().__init__(config)
        self.tolerance = self.params.get("tolerance", 0.02)  # 2% tolerance for matching lows
        self.min_distance = self.params.get("min_distance", 10)  # Min candles between lows
        self.max_distance = self.params.get("max_distance", 50)  # Max candles between lows
        
        # Cache for detected pattern
        self._cached_pattern = None
        self._cache_time = None
    
    def _detect_pattern(self, df: pd.DataFrame) -> Optional[Dict]:
        """
        Detect double bottom pattern in the DataFrame.
        
        Returns:
            Dict with pattern info if found, None otherwise
        """
        # Find all pivot lows
        pivots = self._find_pivots(df, order=self.pivot_order)
        lows = [p for p in pivots if p['type'] == 'low']
        
        if len(lows) < 2:
            return None
        
        # Scan for matching lows (most recent first)
        for i in range(len(lows) - 1, 0, -1):
            low2 = lows[i]  # More recent low
            
            for j in range(i - 1, -1, -1):
                low1 = lows[j]  # Earlier low
                
                # Check distance constraints
                distance = low2['idx'] - low1['idx']
                if distance < self.min_distance or distance > self.max_distance:
                    continue
                
                # Check if lows are at similar levels
                if not self._check_tolerance(low1['price'], low2['price'], self.tolerance):
                    continue
                
                # Calculate neckline (highest high between the two lows)
                neckline = self._calculate_neckline(low1, low2, df)
                
                # Pattern found!
                pattern_height = neckline - min(low1['price'], low2['price'])
                
                return {
                    'type': 'double_bottom',
                    'low1': low1,
                    'low2': low2,
                    'neckline': neckline,
                    'pattern_height': pattern_height,
                    'distance': distance
                }
        
        return None
    
    def generate_signal(self, df: pd.DataFrame, extra_data=None) -> Optional[Dict]:
        """
        Generate trading signal if double bottom breakout is confirmed.
        
        Args:
            df: OHLCV DataFrame
            extra_data: Additional market data
            
        Returns:
            Signal dict with entry, SL, TP if valid, None otherwise
        """
        if df is None or df.empty or len(df) < 30:
            return None
        
        try:
            # GUARD CLAUSE: Reversal patterns require minimum volatility (ADX > 15)
            # Avoid trading reversals in dead/zero-volatility markets
            if 'ADX_14' in df.columns:
                current_adx = df['ADX_14'].iloc[-2]
                if current_adx < 15:
                    return None  # Market too dead, reversal unreliable
            
            # Add volume indicator
            self.add_indicators(df)
            
            # Detect pattern
            pattern = self._detect_pattern(df)
            if not pattern:
                return None
            
            # Cache pattern for progress/conditions
            self._cached_pattern = pattern
            
            # Validate breakout
            breakout = self._validate_breakout(
                df, 
                pattern['neckline'], 
                direction='up',
                volume_filter=self.volume_filter
            )
            
            if not breakout:
                return None
            
            # Calculate entry, SL, TP
            entry = breakout['price']
            
            # SL: Below the lowest of the two bottoms - 0.5% margin
            lowest_low = min(pattern['low1']['price'], pattern['low2']['price'])
            sl = lowest_low * 0.995
            
            # TP: Pattern projection (Entry + Pattern Height)
            tp, risk, rr_ratio = self._calculate_pattern_rr(
                entry, 
                sl, 
                pattern['pattern_height']
            )
            
            # Check minimum R:R
            if rr_ratio < self.min_rr:
                return None
            
            return {
                "signal": "BUY",
                "sl": sl,
                "tp": tp,
                "comment": f"Double Bottom Breakout (R:R {rr_ratio:.2f})"
            }
        
        except Exception as e:
            print(f"Error in DoubleBottom signal generation: {e}")
            return None
    
    def calculate_progress(self, df: pd.DataFrame, extra_data=None) -> int:
        """
        Calculate how close we are to a double bottom signal (0-100%).
        
        Progress breakdown:
        - 40% if pattern is detected
        - 30% if price is approaching neckline
        - 30% if volume is building
        
        Returns:
            Progress percentage (0-100)
        """
        if df is None or df.empty or len(df) < 30:
            return 0
        
        try:
            self.add_indicators(df)
            
            # Detect pattern
            pattern = self._detect_pattern(df)
            if not pattern:
                return 0
            
            progress = 0
            
            # 1. Pattern detected (40 points)
            progress += 40
            
            # 2. Price proximity to neckline (30 points)
            current_price = df['close'].iloc[-2]
            neckline = pattern['neckline']
            distance_to_neckline = (neckline - current_price) / current_price
            
            if current_price >= neckline:
                # Already broken out
                progress += 30
            elif distance_to_neckline < 0.02:  # Within 2%
                # Very close
                progress += int(30 * (1 - distance_to_neckline / 0.02))
            
            # 3. Volume building (30 points)
            if 'volume_sma_20' in df.columns:
                current_volume = df['volume'].iloc[-1]
                avg_volume = df['volume_sma_20'].iloc[-1]
                
                if current_volume > avg_volume:
                    volume_ratio = current_volume / avg_volume
                    progress += min(30, int(30 * volume_ratio))
            
            return min(100, progress)
        
        except:
            return 0
    
    def check_conditions(self, df: pd.DataFrame, extra_data=None) -> List[Dict]:
        """Check detailed conditions for UI - Diagnostic Card"""
        if df is None or df.empty or len(df) < 30:
            return []
        
        try:
            self.add_indicators(df)
            
            # Detect pattern
            pattern = self._detect_pattern(df)
            
            conditions = []
            
            # 1. Pattern Detection
            pattern_detected = pattern is not None
            conditions.append({
                "name": "Double Bottom Pattern Detected",
                "status": pattern_detected,
                "value": "Yes" if pattern_detected else "No"
            })
            
            if not pattern:
                return conditions
            
            # 2. Neckline Breakout
            current_price = df['close'].iloc[-1]
            neckline = pattern['neckline']
            breakout_ok = current_price > neckline
            
            conditions.append({
                "name": "Breakout Above Neckline",
                "status": breakout_ok,
                "value": f"Price: {current_price:.2f} vs Neckline: {neckline:.2f}"
            })
            
            # 3. Volume Confirmation
            if 'volume_sma_20' in df.columns:
                current_volume = df['volume'].iloc[-1]
                avg_volume = df['volume_sma_20'].iloc[-1]
                volume_ok = current_volume > avg_volume
                
                vol_ratio = (current_volume / avg_volume) * 100 if avg_volume > 0 else 0
                conditions.append({
                    "name": "Volume Confirmation",
                    "status": volume_ok,
                    "value": f"{vol_ratio:.0f}% vs Req: >100%"
                })
            
            # 4. R:R Ratio
            rr_val = 0
            if breakout_ok:
                lowest_low = min(pattern['low1']['price'], pattern['low2']['price'])
                sl = lowest_low * 0.995
                tp, risk, rr_ratio = self._calculate_pattern_rr(
                    current_price, 
                    sl, 
                    pattern['pattern_height']
                )
                rr_val = rr_ratio
                
            rr_ok = rr_val >= self.min_rr
            conditions.append({
                "name": "Risk:Reward Ratio",
                "status": rr_ok,
                "value": f"{rr_val:.2f} vs Min: {self.min_rr}"
            })
            
            return conditions
        
        except Exception as e:
            return [{"name": "Error", "status": False, "value": str(e)}]
