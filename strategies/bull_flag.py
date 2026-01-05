"""
Bull Flag Pattern Recognition Strategy

Detects and trades bull flag continuation patterns.

Pattern Characteristics:
- Strong upward impulse (flagpole): +5% minimum in < 10 candles
- Downward consolidation (flag): channeled, lower volume
- Breakout above upper trendline with volume spike
- Bullish continuation signal

Entry Rules:
- Close > Upper trendline of flag
- Volume > 1.5x SMA(Volume, 20)
- R:R ratio > 1.5

Author: NovaBot Team
Date: 2026-01-04
"""

import pandas as pd
import numpy as np
from typing import Optional, Dict, List
from strategies.chart_patterns_base import ChartPatternBase


class BullFlagStrategy(ChartPatternBase):
    """Bull Flag pattern detection and trading strategy."""
    
    def __init__(self, config=None):
        super().__init__(config)
        self.min_impulse_pct = self.params.get("min_impulse_pct", 0.05)  # 5% minimum gain
        self.max_impulse_candles = self.params.get("max_impulse_candles", 10)
        self.flag_duration_min = self.params.get("flag_duration_min", 5)
        self.flag_duration_max = self.params.get("flag_duration_max", 20)
        self.volume_multiplier = self.params.get("volume_multiplier", 1.5)
        
        self._cached_pattern = None
    
    def _detect_pattern(self, df: pd.DataFrame) -> Optional[Dict]:
        """Detect bull flag pattern."""
        if len(df) < 30:
            return None
        
        # 1. Find impulse (flagpole)
        impulse = self._find_impulse(
            df, 
            direction='up', 
            min_gain=self.min_impulse_pct,
            max_candles=self.max_impulse_candles
        )
        
        if not impulse:
            return None
        
        # 2. Check for consolidation after impulse
        flag_start = impulse['end_idx']
        flag_end = min(flag_start + self.flag_duration_max, len(df) - 1)
        
        if flag_end - flag_start < self.flag_duration_min:
            return None
        
        flag_zone = df.iloc[flag_start:flag_end]
        
        # 3. Flag should be descending/sideways with lower volume
        flag_high = flag_zone['high'].max()
        flag_low = flag_zone['low'].min()
        
        # Simple check: flag should not exceed flagpole height
        if (flag_high - impulse['end_price']) > impulse['height'] * 0.3:
            return None
        
        return {
            'type': 'bull_flag',
            'impulse': impulse,
            'flag_start': flag_start,
            'flag_end': flag_end,
            'flag_high': flag_high,
            'flag_low': flag_low,
            'flagpole_height': impulse['height']
        }
    
    def generate_signal(self, df: pd.DataFrame, extra_data=None) -> Optional[Dict]:
        """Generate BUY signal if bull flag breakout is confirmed."""
        if df is None or df.empty or len(df) < 30:
            return None
        
        try:
            # GUARD CLAUSE: Trend Continuation requires active trend (ADX > 20)
            # Bull Flag is a continuation pattern - avoid trading in flat/choppy markets
            if 'ADX_14' in df.columns:
                current_adx = df['ADX_14'].iloc[-2]
                if current_adx < 20:
                    return None  # Market too flat, pattern unreliable
            
            self.add_indicators(df)
            pattern = self._detect_pattern(df)
            
            if not pattern:
                return None
            
            self._cached_pattern = pattern
            
            # Validate breakout above flag high
            breakout = self._validate_breakout(
                df, 
                pattern['flag_high'], 
                direction='up',
                volume_filter=self.volume_filter
            )
            
            if not breakout:
                return None
            
            # Check volume spike
            if 'volume_sma_20' in df.columns:
                current_volume = df['volume'].iloc[-1]
                avg_volume = df['volume_sma_20'].iloc[-1]
                if current_volume < avg_volume * self.volume_multiplier:
                    return None
            
            # Calculate entry, SL, TP
            entry = breakout['price']
            sl = pattern['flag_low'] * 0.995  # Below flag low
            
            # TP: Entry + Flagpole height
            tp, risk, rr_ratio = self._calculate_pattern_rr(
                entry, 
                sl, 
                pattern['flagpole_height']
            )
            
            if rr_ratio < self.min_rr:
                return None
            
            return {
                "signal": "BUY",
                "sl": sl,
                "tp": tp,
                "comment": f"Bull Flag Breakout (R:R {rr_ratio:.2f})"
            }
        
        except Exception as e:
            print(f"Error in BullFlag signal generation: {e}")
            return None
    
    def calculate_progress(self, df: pd.DataFrame, extra_data=None) -> int:
        """Calculate proximity to bull flag signal (0-100%)."""
        if df is None or df.empty or len(df) < 30:
            return 0
        
        try:
            self.add_indicators(df)
            pattern = self._detect_pattern(df)
            
            if not pattern:
                return 0
            
            progress = 50  # Pattern detected
            
            # Price proximity to flag high
            current_price = df['close'].iloc[-1]
            flag_high = pattern['flag_high']
            
            if current_price >= flag_high:
                progress += 30
            else:
                distance_pct = (flag_high - current_price) / current_price
                if distance_pct < 0.02:
                    progress += int(30 * (1 - distance_pct / 0.02))
            
            # Volume building
            if 'volume_sma_20' in df.columns:
                current_volume = df['volume'].iloc[-1]
                avg_volume = df['volume_sma_20'].iloc[-1]
                volume_ratio = current_volume / avg_volume
                progress += min(20, int(20 * volume_ratio))
            
            return min(100, progress)
        
        except:
            return 0
    
    def check_conditions(self, df: pd.DataFrame, extra_data=None) -> List[Dict]:
        """Check detailed conditions for UI display."""
        if df is None or df.empty or len(df) < 30:
            return []
        
        try:
            self.add_indicators(df)
            pattern = self._detect_pattern(df)
            
            conditions = []
            
            pattern_detected = pattern is not None
            conditions.append({
                "name": "Bull Flag Pattern Detected",
                "status": pattern_detected,
                "value": "Yes" if pattern_detected else "No"
            })
            
            if not pattern:
                return conditions
            
            # Impulse strength
            impulse_pct = pattern['impulse']['gain_pct'] * 100
            conditions.append({
                "name": f"Flagpole Strength (Min {self.min_impulse_pct*100:.0f}%)",
                "status": True,
                "value": f"+{impulse_pct:.1f}%"
            })
            
            # Breakout
            current_price = df['close'].iloc[-1]
            flag_high = pattern['flag_high']
            breakout_ok = current_price > flag_high
            
            conditions.append({
                "name": f"Breakout Above Flag (${flag_high:.4f})",
                "status": breakout_ok,
                "value": f"${current_price:.4f}"
            })
            
            # Volume spike
            if 'volume_sma_20' in df.columns:
                current_volume = df['volume'].iloc[-1]
                avg_volume = df['volume_sma_20'].iloc[-1]
                volume_ratio = current_volume / avg_volume
                volume_ok = volume_ratio >= self.volume_multiplier
                
                conditions.append({
                    "name": f"Volume Spike (>{self.volume_multiplier}x)",
                    "status": volume_ok,
                    "value": f"{volume_ratio:.2f}x"
                })
            
            return conditions
        
        except Exception as e:
            return [{"name": "Error", "status": False, "value": str(e)}]
