from app.services.indicators import ta
import pandas as pd
from strategies.base import BaseStrategy

# ============================================
# STRATEGY: Golden Cross (Trend Following - Adapted for 15m)
# ============================================
class StrategyGoldenCross(BaseStrategy):
    """
    Trend Following strategy using EMA crossovers (adapted for 15m timeframe).
    
    Entry:
    - LONG: EMA 9 crosses above EMA 21 (Mini Golden Cross)
    - SHORT: EMA 9 crosses below EMA 21 (Mini Death Cross)
    
    Exit:
    - Close LONG if price closes below EMA 9
    - Close SHORT if price closes above EMA 9
    """
    
    def add_indicators(self, df):
        # Use EMA 9/21 instead of SMA 50/200 for 15m timeframe
        df['EMA_9'] = ta.ema(df['close'], length=9)
        df['EMA_21'] = ta.ema(df['close'], length=21)
        return df
    
    def generate_signal(self, df, extra_data=None):
        df = self.add_indicators(df)
        
        if len(df) < 22:  # Need at least 22 candles for EMA 21
            return None
        
        # Current and previous values
        ema_9_curr = df['EMA_9'].iloc[-1]
        ema_9_prev = df['EMA_9'].iloc[-2]
        ema_21_curr = df['EMA_21'].iloc[-1]
        ema_21_prev = df['EMA_21'].iloc[-2]
        close = df['close'].iloc[-1]
        
        # Mini Golden Cross: EMA 9 crosses above EMA 21
        if ema_9_prev <= ema_21_prev and ema_9_curr > ema_21_curr:
            return {
                'signal': 'BUY',
                'price': close,
                'sl': ema_9_curr * 0.98,  # 2% below EMA 9
                'tp': close * 1.05,  # 5% profit target
                'comment': 'Mini Golden Cross - EMA 9 crossed above EMA 21'
            }
        
        # Mini Death Cross: EMA 9 crosses below EMA 21
        if ema_9_prev >= ema_21_prev and ema_9_curr < ema_21_curr:
            return {
                'signal': 'SELL',
                'price': close,
                'sl': ema_9_curr * 1.02,  # 2% above EMA 9
                'tp': close * 0.95,  # 5% profit target
                'comment': 'Mini Death Cross - EMA 9 crossed below EMA 21'
            }
        
        return None
    
    def calculate_progress(self, df, extra_data=None):
        """Calculate proximity to Mini Golden/Death Cross"""
        try:
            df = self.add_indicators(df)
            if len(df) < 201:
                return 0
            
            sma_50 = df['SMA_50'].iloc[-1]
            sma_200 = df['SMA_200'].iloc[-1]
            
            # Calculate distance between SMAs (as percentage)
            distance_pct = abs(sma_50 - sma_200) / sma_200 * 100
            
            # Closer = higher progress
            if distance_pct < 0.5:  # Very close
                return 90
            elif distance_pct < 1.0:
                return 70
            elif distance_pct < 2.0:
                return 50
            elif distance_pct < 5.0:
                return 30
            else:
                return 10
        except:
            return 0
