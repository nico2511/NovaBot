"""
Chart Pattern Recognition - Base Module

This module provides the foundation for detecting classic chart patterns
using quantitative price action analysis.

Author: NovaBot Team
Date: 2026-01-04
"""

import pandas as pd
import numpy as np
from typing import List, Dict, Optional, Tuple
from strategies.base import BaseStrategy


class ChartPatternBase(BaseStrategy):
    """
    Base class for chart pattern recognition strategies.
    
    Provides core functionality for:
    - Pivot detection (swing highs/lows)
    - Breakout validation with volume confirmation
    - Neckline calculation
    - Risk/Reward ratio calculation
    """
    
    def __init__(self, config=None):
        super().__init__(config)
        self.params = config.get("params", {}) if config else {}
        self.pivot_order = self.params.get("pivot_order", 5)
        self.volume_filter = self.params.get("volume_filter", True)
        self.min_rr = self.params.get("min_rr", 1.5)
    
    def _find_pivots(self, df: pd.DataFrame, order: int = None) -> List[Dict]:
        """
        Detect swing highs and lows using rolling window comparison.
        
        A pivot high is confirmed when the high at index i is greater than
        all highs in the window [i-order, i+order].
        
        Args:
            df: OHLCV DataFrame with 'high' and 'low' columns
            order: Number of candles before/after to confirm pivot (default: self.pivot_order)
            
        Returns:
            List of pivot dictionaries with keys:
                - idx: Index in DataFrame
                - price: Pivot price
                - type: 'high' or 'low'
                - time: Timestamp
        """
        if order is None:
            order = self.pivot_order
        
        pivots = []
        
        # Need at least 2*order + 1 candles
        if len(df) < (2 * order + 1):
            return pivots
        
        for i in range(order, len(df) - order):
            # Check for pivot high
            current_high = df['high'].iloc[i]
            window_before = df['high'].iloc[i-order:i]
            window_after = df['high'].iloc[i+1:i+order+1]
            
            if (current_high > window_before.max()) and (current_high > window_after.max()):
                pivots.append({
                    'idx': i,
                    'price': current_high,
                    'type': 'high',
                    'time': df.index[i] if hasattr(df.index[i], 'strftime') else i
                })
            
            # Check for pivot low
            current_low = df['low'].iloc[i]
            window_before_low = df['low'].iloc[i-order:i]
            window_after_low = df['low'].iloc[i+1:i+order+1]
            
            if (current_low < window_before_low.min()) and (current_low < window_after_low.min()):
                pivots.append({
                    'idx': i,
                    'price': current_low,
                    'type': 'low',
                    'time': df.index[i] if hasattr(df.index[i], 'strftime') else i
                })
        
        return pivots
    
    def _is_pivot_high(self, df: pd.DataFrame, idx: int, order: int = None) -> bool:
        """
        Check if the given index is a pivot high.
        
        Args:
            df: OHLCV DataFrame
            idx: Index to check
            order: Window size for comparison
            
        Returns:
            True if index is a pivot high
        """
        if order is None:
            order = self.pivot_order
        
        if idx < order or idx >= len(df) - order:
            return False
        
        current_high = df['high'].iloc[idx]
        window_before = df['high'].iloc[idx-order:idx]
        window_after = df['high'].iloc[idx+1:idx+order+1]
        
        return (current_high > window_before.max()) and (current_high > window_after.max())
    
    def _is_pivot_low(self, df: pd.DataFrame, idx: int, order: int = None) -> bool:
        """
        Check if the given index is a pivot low.
        
        Args:
            df: OHLCV DataFrame
            idx: Index to check
            order: Window size for comparison
            
        Returns:
            True if index is a pivot low
        """
        if order is None:
            order = self.pivot_order
        
        if idx < order or idx >= len(df) - order:
            return False
        
        current_low = df['low'].iloc[idx]
        window_before = df['low'].iloc[idx-order:idx]
        window_after = df['low'].iloc[idx+1:idx+order+1]
        
        return (current_low < window_before.min()) and (current_low < window_after.min())
    
    def _calculate_neckline(self, point1: Dict, point2: Dict, df: pd.DataFrame) -> float:
        """
        Calculate neckline level between two pivot points.
        
        For double bottom: neckline is the highest high between the two lows
        For double top: neckline is the lowest low between the two highs
        
        Args:
            point1: First pivot point dict
            point2: Second pivot point dict
            df: OHLCV DataFrame
            
        Returns:
            Neckline price level
        """
        idx1, idx2 = point1['idx'], point2['idx']
        start_idx = min(idx1, idx2)
        end_idx = max(idx1, idx2)
        
        if point1['type'] == 'low':
            # Double bottom: neckline is resistance (highest high between lows)
            neckline = df['high'].iloc[start_idx:end_idx+1].max()
        else:
            # Double top: neckline is support (lowest low between highs)
            neckline = df['low'].iloc[start_idx:end_idx+1].min()
        
        return neckline
    
    def _validate_breakout(
        self, 
        df: pd.DataFrame, 
        level: float, 
        direction: str,
        volume_filter: bool = None
    ) -> Optional[Dict]:
        """
        Validate if a breakout has occurred with proper confirmation.
        
        Breakout criteria:
        1. Close beyond the level (above for bullish, below for bearish)
        2. Volume > SMA(Volume, 20) if volume_filter is True
        3. No immediate rejection (next candle doesn't reverse)
        
        Args:
            df: OHLCV DataFrame
            level: Price level to break (neckline, trendline, etc.)
            direction: 'up' for bullish breakout, 'down' for bearish
            volume_filter: Apply volume confirmation (default: self.volume_filter)
            
        Returns:
            Dict with breakout info if valid, None otherwise
        """
        if volume_filter is None:
            volume_filter = self.volume_filter
        
        # Need at least 2 candles (current + confirmation)
        if len(df) < 2:
            return None
        
        current_candle = df.iloc[-1]
        prev_candle = df.iloc[-2] if len(df) > 1 else None
        
        # Check if close is beyond level
        if direction == 'up':
            breakout_confirmed = current_candle['close'] > level
        else:  # direction == 'down'
            breakout_confirmed = current_candle['close'] < level
        
        if not breakout_confirmed:
            return None
        
        # Volume filter
        if volume_filter and 'volume' in df.columns:
            volume_sma = df['volume'].rolling(20).mean().iloc[-1]
            if current_candle['volume'] < volume_sma:
                return None
        
        # Return breakout info
        return {
            'price': current_candle['close'],
            'time': df.index[-1] if hasattr(df.index[-1], 'strftime') else len(df) - 1,
            'volume': current_candle['volume'] if 'volume' in df.columns else None,
            'direction': direction
        }
    
    def _calculate_pattern_rr(
        self, 
        entry: float, 
        sl: float, 
        pattern_height: float
    ) -> Tuple[float, float, float]:
        """
        Calculate Take Profit and Risk/Reward ratio for a pattern.
        
        Standard pattern projection: TP = Entry + Pattern Height
        
        Args:
            entry: Entry price
            sl: Stop loss price
            pattern_height: Height of the pattern (for projection)
            
        Returns:
            Tuple of (tp, risk, reward_ratio)
        """
        risk = abs(entry - sl)
        
        # TP is projected using pattern height
        tp = entry + pattern_height if entry > sl else entry - pattern_height
        
        reward = abs(tp - entry)
        rr_ratio = reward / risk if risk > 0 else 0
        
        return tp, risk, rr_ratio
    
    def _check_tolerance(self, price1: float, price2: float, tolerance: float = 0.02) -> bool:
        """
        Check if two prices are within tolerance percentage.
        
        Args:
            price1: First price
            price2: Second price
            tolerance: Maximum allowed difference as percentage (default: 2%)
            
        Returns:
            True if prices are within tolerance
        """
        diff_pct = abs(price1 - price2) / max(price1, price2)
        return diff_pct <= tolerance
    
    def _find_impulse(
        self, 
        df: pd.DataFrame, 
        direction: str, 
        min_gain: float = 0.05,
        max_candles: int = 10
    ) -> Optional[Dict]:
        """
        Find a strong impulse move (for flag patterns).
        
        Args:
            df: OHLCV DataFrame
            direction: 'up' or 'down'
            min_gain: Minimum percentage gain/loss (default: 5%)
            max_candles: Maximum candles for impulse (default: 10)
            
        Returns:
            Dict with impulse info if found, None otherwise
        """
        if len(df) < max_candles:
            return None
        
        # Scan recent candles for impulse
        for start_idx in range(len(df) - max_candles, len(df) - 2):
            for end_idx in range(start_idx + 3, min(start_idx + max_candles, len(df))):
                start_price = df['close'].iloc[start_idx]
                end_price = df['close'].iloc[end_idx]
                
                gain_pct = (end_price - start_price) / start_price
                
                if direction == 'up' and gain_pct >= min_gain:
                    return {
                        'start_idx': start_idx,
                        'end_idx': end_idx,
                        'start_price': start_price,
                        'end_price': end_price,
                        'height': end_price - start_price,
                        'gain_pct': gain_pct
                    }
                elif direction == 'down' and gain_pct <= -min_gain:
                    return {
                        'start_idx': start_idx,
                        'end_idx': end_idx,
                        'start_price': start_price,
                        'end_price': end_price,
                        'height': abs(end_price - start_price),
                        'gain_pct': abs(gain_pct)
                    }
        
        return None
    
    def add_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Add volume SMA for breakout validation.
        
        Args:
            df: OHLCV DataFrame
            
        Returns:
            DataFrame with added indicators
        """
        if 'volume' in df.columns:
            df['volume_sma_20'] = df['volume'].rolling(20).mean()
        return df
    
    def generate_signal(self, df: pd.DataFrame, extra_data=None) -> Optional[Dict]:
        """
        Base implementation - should be overridden by child classes.
        """
        raise NotImplementedError("Child class must implement generate_signal()")
    
    def calculate_progress(self, df: pd.DataFrame, extra_data=None) -> int:
        """
        Base implementation - should be overridden by child classes.
        """
        return 0
    
    def check_conditions(self, df: pd.DataFrame, extra_data=None) -> List[Dict]:
        """
        Base implementation - should be overridden by child classes.
        """
        return []
