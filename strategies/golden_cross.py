from app.services.indicators import ta
import pandas as pd
from strategies.base import BaseStrategy

# ============================================
# STRATEGY: Golden Cross (Trend Following)
# ============================================
class StrategyGoldenCross(BaseStrategy):
    """
    Classic Trend Following strategy using SMA crossovers.
    
    Entry:
    - LONG: SMA 50 crosses above SMA 200 (Golden Cross)
    - SHORT: SMA 50 crosses below SMA 200 (Death Cross)
    
    Exit:
    - Close LONG if price closes below SMA 50
    - Close SHORT if price closes above SMA 50
    """
    
    def add_indicators(self, df):
        df['SMA_50'] = ta.sma(df['close'], length=50)
        df['SMA_200'] = ta.sma(df['close'], length=200)
        return df
    
    def generate_signal(self, df, extra_data=None):
        df = self.add_indicators(df)
        
        if len(df) < 201:  # Need at least 201 candles for SMA 200
            return None
        
        # Current and previous values
        sma_50_curr = df['SMA_50'].iloc[-1]
        sma_50_prev = df['SMA_50'].iloc[-2]
        sma_200_curr = df['SMA_200'].iloc[-1]
        sma_200_prev = df['SMA_200'].iloc[-2]
        close = df['close'].iloc[-1]
        
        # Golden Cross: SMA 50 crosses above SMA 200
        if sma_50_prev <= sma_200_prev and sma_50_curr > sma_200_curr:
            return {
                'signal': 'BUY',
                'price': close,
                'sl': sma_50_curr * 0.97,  # 3% below SMA 50
                'tp': close * 1.10,  # 10% profit target
                'comment': 'Golden Cross detected - SMA 50 crossed above SMA 200'
            }
        
        # Death Cross: SMA 50 crosses below SMA 200
        if sma_50_prev >= sma_200_prev and sma_50_curr < sma_200_curr:
            return {
                'signal': 'SELL',
                'price': close,
                'sl': sma_50_curr * 1.03,  # 3% above SMA 50
                'tp': close * 0.90,  # 10% profit target
                'comment': 'Death Cross detected - SMA 50 crossed below SMA 200'
            }
        
        return None
    
    def calculate_progress(self, df, extra_data=None):
        """Calculate proximity to Golden/Death Cross"""
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
