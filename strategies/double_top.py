"""
Double Top Pattern Recognition Strategy

Detects and trades double top reversal patterns with rigorous validation.

Pattern Characteristics:
- Two swing highs at similar price levels (within 2% tolerance)
- Neckline formed by trough between the peaks
- Breakout below neckline with volume confirmation
- Bearish reversal signal

Entry Rules:
- Close < Neckline
- Volume > SMA(Volume, 20)
- R:R ratio > 1.5

Author: NovaBot Team
Date: 2026-01-04
"""

import pandas as pd
import numpy as np
from typing import Optional, Dict, List
from strategies.chart_patterns_base import ChartPatternBase


class DoubleTopStrategy(ChartPatternBase):
    """
    Double Top pattern detection and trading strategy.
    
    Identifies two swing highs at similar levels, waits for neckline breakout,
    and enters short position with proper risk management.
    """
    
    def __init__(self, config=None):
        super().__init__(config)
        self.tolerance = self.params.get("tolerance", 0.02)
        self.min_distance = self.params.get("min_distance", 10)
        self.max_distance = self.params.get("max_distance", 50)
        
        self._cached_pattern = None
    
    def _detect_pattern(self, df: pd.DataFrame) -> Optional[Dict]:
        """Detect double top pattern in the DataFrame."""
        pivots = self._find_pivots(df, order=self.pivot_order)
        highs = [p for p in pivots if p['type'] == 'high']
        
        if len(highs) < 2:
            return None
        
        # Scan for matching highs (most recent first)
        for i in range(len(highs) - 1, 0, -1):
            high2 = highs[i]
            
            for j in range(i - 1, -1, -1):
                high1 = highs[j]
                
                distance = high2['idx'] - high1['idx']
                if distance < self.min_distance or distance > self.max_distance:
                    continue
                
                if not self._check_tolerance(high1['price'], high2['price'], self.tolerance):
                    continue
                
                # Neckline is lowest low between the two highs
                neckline = self._calculate_neckline(high1, high2, df)
                pattern_height = max(high1['price'], high2['price']) - neckline
                
                return {
                    'type': 'double_top',
                    'high1': high1,
                    'high2': high2,
                    'neckline': neckline,
                    'pattern_height': pattern_height,
                    'distance': distance
                }
        
        return None
    
    def generate_signal(self, df: pd.DataFrame, extra_data=None) -> Optional[Dict]:
        """Generate SHORT signal if double top breakout is confirmed."""
        if df is None or df.empty or len(df) < 30:
            return None
        
        try:
            # GUARD CLAUSE: Reversal patterns require minimum volatility (ADX > 15)
            # Avoid trading reversals in dead/zero-volatility markets
            if 'ADX_14' in df.columns:
                current_adx = df['ADX_14'].iloc[-2]
                if current_adx < 15:
                    return None  # Market too dead, reversal unreliable
            
            self.add_indicators(df)
            pattern = self._detect_pattern(df)
            
            if not pattern:
                return None
            
            self._cached_pattern = pattern
            
            # Validate breakout (downward)
            breakout = self._validate_breakout(
                df, 
                pattern['neckline'], 
                direction='down',
                volume_filter=self.volume_filter
            )
            
            if not breakout:
                return None
            
            # Calculate entry, SL, TP
            entry = breakout['price']
            
            # SL: Above the highest of the two tops + 0.5% margin
            highest_high = max(pattern['high1']['price'], pattern['high2']['price'])
            sl = highest_high * 1.005
            
            # TP: Pattern projection (Entry - Pattern Height)
            tp, risk, rr_ratio = self._calculate_pattern_rr(
                entry, 
                sl, 
                pattern['pattern_height']
            )
            
            if rr_ratio < self.min_rr:
                return None
            
            return {
                "signal": "SELL",
                "sl": sl,
                "tp": tp,
                "comment": f"Double Top Breakout (R:R {rr_ratio:.2f})"
            }
        
        except Exception as e:
            print(f"Error in DoubleTop signal generation: {e}")
            return None
    
    def calculate_progress(self, df: pd.DataFrame, extra_data=None) -> int:
        """Calculate proximity to double top signal (0-100%)."""
        if df is None or df.empty or len(df) < 30:
            return 0
        
        try:
            self.add_indicators(df)
            pattern = self._detect_pattern(df)
            
            if not pattern:
                return 0
            
            progress = 40  # Pattern detected
            
            # Price proximity to neckline
            current_price = df['close'].iloc[-1]
            neckline = pattern['neckline']
            distance_to_neckline = (current_price - neckline) / current_price
            
            if current_price <= neckline:
                progress += 30
            elif distance_to_neckline < 0.02:
                progress += int(30 * (1 - distance_to_neckline / 0.02))
            
            # Volume building
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
            pattern = self._detect_pattern(df)
            
            conditions = []
            
            # 1. Pattern Detection
            pattern_detected = pattern is not None
            conditions.append({
                "name": "Double Top Pattern Detected",
                "status": pattern_detected,
                "value": "Yes" if pattern_detected else "No"
            })
            
            if not pattern:
                return conditions
            
            # 2. Neckline Breakout
            current_price = df['close'].iloc[-1]
            neckline = pattern['neckline']
            breakout_ok = current_price < neckline
            
            conditions.append({
                "name": "Breakout Below Neckline",
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
                highest_high = max(pattern['high1']['price'], pattern['high2']['price'])
                sl = highest_high * 1.005
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
