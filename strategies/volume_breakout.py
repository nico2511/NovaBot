from app.services.indicators import ta
import pandas as pd
from strategies.base import BaseStrategy

class VolumeBreakout(BaseStrategy):
    """
    Volume Breakout Strategy
    Trades breakouts of support/resistance confirmed by volume spikes
    """
    def add_indicators(self, df):
        import pandas_ta as pta
        
        # Volume indicators
        df['volume_sma'] = df['volume'].rolling(window=20).mean()
        df['volume_ratio'] = df['volume'] / df['volume_sma']
        
        # Price indicators
        df['EMA_20'] = ta.ema(df['close'], length=20)
        df['RSI_14'] = ta.rsi(df['close'], length=14)
        df['ATRr_14'] = ta.atr(df['high'], df['low'], df['close'], length=14)
        
        # Pivot highs/lows (resistance/support)
        df['pivot_high'] = df['high'].rolling(window=10, center=True).max()
        df['pivot_low'] = df['low'].rolling(window=10, center=True).min()
        
        return df
    
    def generate_signal(self, df, extra_data=None):
        if df.empty or len(df) < 50:
            return None
        
        self.add_indicators(df)
        
        params = self.config.get("params", {})
        volume_threshold = params.get("volume_threshold", 1.5)  # 1.5x average volume
        min_rsi = params.get("min_rsi", 50)
        
        # Current values
        close = df['close'].iloc[-1]
        prev_close = df['close'].iloc[-2]
        high = df['high'].iloc[-1]
        low = df['low'].iloc[-1]
        volume_ratio = df['volume_ratio'].iloc[-1]
        rsi = df['RSI_14'].iloc[-1]
        atr = df['ATRr_14'].iloc[-1]
        
        # Recent resistance/support (last 20 candles)
        recent_high = df['high'].iloc[-20:-1].max()
        recent_low = df['low'].iloc[-20:-1].min()
        
        # LONG: Breakout above resistance with volume
        if close > recent_high and prev_close <= recent_high:
            if volume_ratio > volume_threshold:  # Volume confirmation
                if rsi > min_rsi:  # Momentum confirmation
                    return {
                        "signal": "BUY",
                        "sl": recent_high - (0.5 * atr),  # SL just below breakout level
                        "tp": close + (2.0 * atr),  # 2R target
                        "comment": f"Volume Breakout (Vol: {volume_ratio:.1f}x)"
                    }
        
        # SHORT: Breakdown below support with volume
        if close < recent_low and prev_close >= recent_low:
            if volume_ratio > volume_threshold:
                if rsi < (100 - min_rsi):  # Bearish momentum
                    return {
                        "signal": "SELL",
                        "sl": recent_low + (0.5 * atr),
                        "tp": close - (2.0 * atr),
                        "comment": f"Volume Breakdown (Vol: {volume_ratio:.1f}x)"
                    }
        
        return None
    
    def calculate_progress(self, df, extra_data=None):
        """Calculate progress based on proximity to breakout and volume buildup"""
        if df.empty or len(df) < 50:
            return 0
        
        try:
            self.add_indicators(df)
            
            close = df['close'].iloc[-1]
            volume_ratio = df['volume_ratio'].iloc[-1]
            rsi = df['RSI_14'].iloc[-1]
            
            recent_high = df['high'].iloc[-20:-1].max()
            recent_low = df['low'].iloc[-20:-1].min()
            
            progress = 0
            
            # Volume buildup (40 points)
            if volume_ratio > 1.0:
                progress += min(40, int(40 * (volume_ratio - 1.0) / 0.5))
            
            # Proximity to breakout level (40 points)
            dist_to_high = abs(close - recent_high) / recent_high
            dist_to_low = abs(close - recent_low) / recent_low
            min_dist = min(dist_to_high, dist_to_low)
            
            if min_dist < 0.01:  # Within 1%
                progress += 40
            elif min_dist < 0.02:  # Within 2%
                progress += 20
            
            # RSI momentum (20 points)
            if rsi > 50 and close > recent_high * 0.99:  # Near resistance, bullish
                progress += 20
            elif rsi < 50 and close < recent_low * 1.01:  # Near support, bearish
                progress += 20
            
            return min(100, max(0, progress))
        except:
            return 0
