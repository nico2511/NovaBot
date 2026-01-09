"""
Head and Shoulders Pattern Recognition Strategy

Detects and trades head and shoulders reversal patterns.

Pattern Characteristics:
- Three peaks: Left Shoulder, Head (highest), Right Shoulder
- Head > Left Shoulder and Head > Right Shoulder
- Left Shoulder ≈ Right Shoulder (within 3% tolerance)
- Neckline connects the two troughs
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


class HeadShouldersStrategy(ChartPatternBase):
    """Head and Shoulders pattern detection and trading strategy."""
    
    def __init__(self, config=None):
        super().__init__(config)
        self.shoulder_tolerance = self.params.get("shoulder_tolerance", 0.03)  # 3%
        self.min_candles = self.params.get("min_candles", 20)
        
        self._cached_pattern = None
    
    def _detect_pattern(self, df: pd.DataFrame) -> Optional[Dict]:
        """Detect head and shoulders pattern."""
        pivots = self._find_pivots(df, order=7)  # Larger window for H&S
        peaks = [p for p in pivots if p['type'] == 'high']
        troughs = [p for p in pivots if p['type'] == 'low']
        
        if len(peaks) < 3 or len(troughs) < 2:
            return None
        
        # Scan for H&S pattern (3 consecutive peaks)
        for i in range(len(peaks) - 2):
            ls = peaks[i]      # Left Shoulder
            h = peaks[i + 1]   # Head
            rs = peaks[i + 2]  # Right Shoulder
            
            # Check distance
            total_distance = rs['idx'] - ls['idx']
            if total_distance < self.min_candles:
                continue
            
            # Validate H&S structure
            # 1. Head must be highest
            if not (h['price'] > ls['price'] and h['price'] > rs['price']):
                continue
            
            # 2. Shoulders should be similar height
            if not self._check_tolerance(ls['price'], rs['price'], self.shoulder_tolerance):
                continue
            
            # 3. Find troughs between peaks for neckline
            trough1 = None
            trough2 = None
            
            for t in troughs:
                if ls['idx'] < t['idx'] < h['idx'] and trough1 is None:
                    trough1 = t
                elif h['idx'] < t['idx'] < rs['idx'] and trough2 is None:
                    trough2 = t
            
            if not trough1 or not trough2:
                continue
            
            # Calculate neckline (simple: average of two troughs)
            neckline = (trough1['price'] + trough2['price']) / 2
            pattern_height = h['price'] - neckline
            
            return {
                'type': 'head_shoulders',
                'left_shoulder': ls,
                'head': h,
                'right_shoulder': rs,
                'trough1': trough1,
                'trough2': trough2,
                'neckline': neckline,
                'pattern_height': pattern_height
            }
        
        return None
    
    def generate_signal(self, df: pd.DataFrame, extra_data=None) -> Optional[Dict]:
        """Generate SELL signal if H&S neckline is broken."""
        if df is None or df.empty or len(df) < 60:
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
            
            # Validate breakout below neckline
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
            sl = pattern['right_shoulder']['price'] * 1.01  # Above RS + 1%
            
            # TP: Entry - Pattern Height
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
                "comment": f"Head & Shoulders Breakout (R:R {rr_ratio:.2f})"
            }
        
        except Exception as e:
            print(f"Error in HeadShoulders signal generation: {e}")
            return None
    
    def calculate_progress(self, df: pd.DataFrame, extra_data=None) -> int:
        """Calculate proximity to H&S signal (0-100%)."""
        if df is None or df.empty or len(df) < 60:
            return 0
        
        try:
            self.add_indicators(df)
            pattern = self._detect_pattern(df)
            
            if not pattern:
                return 0
            
            progress = 50  # Pattern detected
            
            # Price proximity to neckline
            current_price = df['close'].iloc[-1]
            neckline = pattern['neckline']
            
            if current_price <= neckline:
                progress += 30
            else:
                distance_pct = (current_price - neckline) / current_price
                if distance_pct < 0.03:
                    progress += int(30 * (1 - distance_pct / 0.03))
            
            # Volume
            if 'volume_sma_20' in df.columns:
                current_volume = df['volume'].iloc[-1]
                avg_volume = df['volume_sma_20'].iloc[-1]
                if current_volume > avg_volume:
                    progress += min(20, int(20 * (current_volume / avg_volume)))
            
            return min(100, progress)
        
        except:
            return 0
    
    def check_conditions(self, df: pd.DataFrame, extra_data=None) -> List[Dict]:
        """Check detailed conditions for UI - Diagnostic Card"""
        if df is None or df.empty or len(df) < 60:
            return []
        
        try:
            self.add_indicators(df)
            pattern = self._detect_pattern(df)
            
            conditions = []
            
            # 1. Pattern Detection
            pattern_detected = pattern is not None
            conditions.append({
                "name": "Head & Shoulders Pattern",
                "status": pattern_detected,
                "value": ""
            })
            
            if not pattern:
                return conditions
            
            # 2. Pattern structure
            head_price = pattern['head']['price']
            ls_price = pattern['left_shoulder']['price']
            rs_price = pattern['right_shoulder']['price']
            
            conditions.append({
                "name": "Pattern Structure",
                "status": True,
                "value": ""
            })
            
            # 3. Neckline breakout
            current_price = df['close'].iloc[-1]
            neckline = pattern['neckline']
            breakout_ok = current_price < neckline
            
            conditions.append({
                "name": "Breakout Below Neckline",
                "status": breakout_ok,
                "value": ""
            })
            
            # 4. Volume
            if 'volume_sma_20' in df.columns:
                current_volume = df['volume'].iloc[-1]
                avg_volume = df['volume_sma_20'].iloc[-1]
                volume_ok = current_volume > avg_volume
                
                vol_ratio = (current_volume / avg_volume) * 100 if avg_volume > 0 else 0
                conditions.append({
                    "name": "Volume Confirmation",
                    "status": volume_ok,
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
            pattern = self._detect_pattern(df)
            current_price = df['close'].iloc[-1]
            
            pat_str = "None"
            neck_str = "None"
            if pattern:
                pat_str = f"L-S:{pattern['left_shoulder']['price']:.2f} H:{pattern['head']['price']:.2f} R-S:{pattern['right_shoulder']['price']:.2f}"
                neck_str = f"{current_price:.2f} vs {pattern['neckline']:.2f}"
            
            vol_ratio = 0
            if 'volume_sma_20' in df.columns:
                curr = df['volume'].iloc[-1]
                avg = df['volume_sma_20'].iloc[-1]
                vol_ratio = curr / avg if avg > 0 else 0

            return {
                "Pattern": pat_str,
                "Breakout": neck_str,
                "Volume": f"{vol_ratio:.2f}x vs Req: >1.0x"
            }
        except Exception as e: return {"Error": str(e)}

