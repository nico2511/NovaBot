from app.services.indicators import ta
import pandas as pd
from strategies.base import BaseStrategy

class EMABounce(BaseStrategy):
    """
    EMA 9/21 Bounce Strategy
    Simple scalping strategy that buys pullbacks to EMA 21 in trending markets
    """
    def add_indicators(self, df):
        # EMAs
        df['EMA_9'] = ta.ema(df['close'], length=9)
        df['EMA_21'] = ta.ema(df['close'], length=21)
        df['EMA_200'] = ta.ema(df['close'], length=200)
        
        # RSI for momentum filter
        df['RSI_14'] = ta.rsi(df['close'], length=14)
        
        # ATR for SL/TP
        df['ATRr_14'] = ta.atr(df['high'], df['low'], df['close'], length=14)
        return df
    
    def generate_signal(self, df, extra_data=None):
        if df.empty or len(df) < 200:
            return None
        
        self.add_indicators(df)
        
        params = self.config.get("params", {})
        rsi_min = params.get("rsi_min", 40)
        rsi_max = params.get("rsi_max", 60)
        
        # Current and previous values
        close = df['close'].iloc[-1]
        prev_close = df['close'].iloc[-2]
        low = df['low'].iloc[-1]
        prev_low = df['low'].iloc[-2]
        high = df['high'].iloc[-1]
        prev_high = df['high'].iloc[-2]
        
        ema_9 = df['EMA_9'].iloc[-1]
        ema_21 = df['EMA_21'].iloc[-1]
        ema_200 = df['EMA_200'].iloc[-1]
        rsi = df['RSI_14'].iloc[-1]
        atr = df['ATRr_14'].iloc[-1]
        
        # LONG: Bullish trend + bounce off EMA 21
        if close > ema_200 and ema_9 > ema_21:  # Uptrend
            # Previous candle touched EMA 21, current bouncing
            if prev_low <= ema_21 and close > ema_21:
                if rsi_min < rsi < rsi_max:  # Not too weak, not overbought
                    return {
                        "signal": "BUY",
                        "sl": ema_21 - (0.5 * atr),  # Tight SL below EMA
                        "tp": close + (1.5 * atr),  # 3:1 R:R
                        "comment": "EMA 21 Bounce (Bullish)"
                    }
        
        # SHORT: Bearish trend + bounce off EMA 21
        if close < ema_200 and ema_9 < ema_21:  # Downtrend
            # Previous candle touched EMA 21, current bouncing
            if prev_high >= ema_21 and close < ema_21:
                if (100 - rsi_max) < rsi < (100 - rsi_min):  # Inverse for shorts
                    return {
                        "signal": "SELL",
                        "sl": ema_21 + (0.5 * atr),
                        "tp": close - (1.5 * atr),
                        "comment": "EMA 21 Bounce (Bearish)"
                    }
        
        return None
    
    def calculate_progress(self, df, extra_data=None):
        """Calculate progress based on proximity to EMA 21 and trend strength"""
        if df.empty or len(df) < 200:
            return 0
        
        try:
            self.add_indicators(df)
            
            close = df['close'].iloc[-1]
            ema_9 = df['EMA_9'].iloc[-1]
            ema_21 = df['EMA_21'].iloc[-1]
            ema_200 = df['EMA_200'].iloc[-1]
            rsi = df['RSI_14'].iloc[-1]
            
            progress = 0
            
            # Trend alignment (40 points)
            if (close > ema_200 and ema_9 > ema_21) or (close < ema_200 and ema_9 < ema_21):
                progress += 40
            
            # Proximity to EMA 21 (40 points)
            dist_to_ema = abs(close - ema_21) / ema_21
            if dist_to_ema < 0.002:  # Within 0.2%
                progress += 40
            elif dist_to_ema < 0.005:  # Within 0.5%
                progress += 20
            
            # RSI in range (20 points)
            if 40 < rsi < 60:
                progress += 20
            
            return min(100, max(0, progress))
        except:
            return 0
