from app.services.indicators import ta
import pandas as pd
from strategies.base import BaseStrategy

class TripleEMA(BaseStrategy):
    """
    Triple EMA Crossover Strategy
    Uses 3 EMAs to filter false signals and catch strong trends
    """
    def add_indicators(self, df):
        # Triple EMAs
        df['EMA_8'] = ta.ema(df['close'], length=8)
        df['EMA_21'] = ta.ema(df['close'], length=21)
        df['EMA_55'] = ta.ema(df['close'], length=55)
        
        # Volume for confirmation
        df['volume_sma'] = df['volume'].rolling(window=20).mean()
        
        # ATR
        df['ATRr_14'] = ta.atr(df['high'], df['low'], df['close'], length=14)
        return df
    
    def generate_signal(self, df, extra_data=None):
        if df.empty or len(df) < 60:
            return None
        
        self.add_indicators(df)
        
        params = self.config.get("params", {})
        require_volume = params.get("require_volume", True)
        
        # Current and previous values
        close = df['close'].iloc[-1]
        ema_8 = df['EMA_8'].iloc[-1]
        prev_ema_8 = df['EMA_8'].iloc[-2]
        ema_21 = df['EMA_21'].iloc[-1]
        prev_ema_21 = df['EMA_21'].iloc[-2]
        ema_55 = df['EMA_55'].iloc[-1]
        
        volume = df['volume'].iloc[-1]
        volume_sma = df['volume_sma'].iloc[-1]
        atr = df['ATRr_14'].iloc[-1]
        
        # LONG: EMA 8 crosses above EMA 21, both above EMA 55
        if prev_ema_8 <= prev_ema_21 and ema_8 > ema_21:  # Crossover
            if ema_21 > ema_55 and close > ema_55:  # Trend confirmed
                if not require_volume or volume > volume_sma:  # Volume confirmation
                    return {
                        "signal": "BUY",
                        "sl": ema_55 - (1.5 * atr),  # SL below EMA 55
                        "tp": close + (3.0 * atr),  # 2:1 R:R
                        "comment": "Triple EMA Bullish Cross"
                    }
        
        # SHORT: EMA 8 crosses below EMA 21, both below EMA 55
        if prev_ema_8 >= prev_ema_21 and ema_8 < ema_21:  # Crossover
            if ema_21 < ema_55 and close < ema_55:  # Trend confirmed
                if not require_volume or volume > volume_sma:
                    return {
                        "signal": "SELL",
                        "sl": ema_55 + (1.5 * atr),
                        "tp": close - (3.0 * atr),
                        "comment": "Triple EMA Bearish Cross"
                    }
        
        return None
    
    def calculate_progress(self, df, extra_data=None):
        """Calculate progress based on EMA proximity to crossover"""
        if df.empty or len(df) < 60:
            return 0
        
        try:
            self.add_indicators(df)
            
            ema_8 = df['EMA_8'].iloc[-1]
            ema_21 = df['EMA_21'].iloc[-1]
            ema_55 = df['EMA_55'].iloc[-1]
            close = df['close'].iloc[-1]
            
            progress = 0
            
            # Trend alignment (40 points)
            if (ema_21 > ema_55 and close > ema_55) or (ema_21 < ema_55 and close < ema_55):
                progress += 40
            
            # Proximity to crossover (60 points)
            ema_diff = abs(ema_8 - ema_21)
            ema_avg = (ema_8 + ema_21) / 2
            if ema_avg > 0:
                proximity = 1 - min(1, ema_diff / (ema_avg * 0.01))  # Within 1%
                progress += int(60 * proximity)
            
            return min(100, max(0, progress))
        except:
            return 0
