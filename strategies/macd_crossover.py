from app.services.indicators import ta
import pandas as pd
from strategies.base import BaseStrategy

class MACDCrossover(BaseStrategy):
    """
    MACD + EMA Crossover Strategy
    Popular trend-following strategy combining MACD momentum with EMA trend filter
    """
    def add_indicators(self, df):
        import pandas_ta as pta
        
        # MACD (12, 26, 9)
        macd_df = pta.macd(df['close'], fast=12, slow=26, signal=9)
        df['MACD'] = macd_df[f'MACD_12_26_9']
        df['MACD_signal'] = macd_df[f'MACDs_12_26_9']
        df['MACD_hist'] = macd_df[f'MACDh_12_26_9']
        
        # EMAs for trend filter
        df['EMA_50'] = ta.ema(df['close'], length=50)
        df['EMA_200'] = ta.ema(df['close'], length=200)
        
        # ATR for SL/TP
        df['ATRr_14'] = ta.atr(df['high'], df['low'], df['close'], length=14)
        return df
    
    def generate_signal(self, df, extra_data=None):
        if df.empty or len(df) < 200:
            return None
        
        self.add_indicators(df)
        
        # Current values
        macd = df['MACD'].iloc[-1]
        macd_signal = df['MACD_signal'].iloc[-1]
        macd_hist = df['MACD_hist'].iloc[-1]
        prev_hist = df['MACD_hist'].iloc[-2]
        
        close = df['close'].iloc[-1]
        ema_50 = df['EMA_50'].iloc[-1]
        ema_200 = df['EMA_200'].iloc[-1]
        atr = df['ATRr_14'].iloc[-1]
        
        # LONG: Bullish trend + MACD crossover
        if close > ema_200 and ema_50 > ema_200:  # Strong uptrend
            if macd > macd_signal and macd_hist > 0:  # MACD bullish
                if macd_hist > prev_hist:  # Histogram growing (momentum increasing)
                    return {
                        "signal": "BUY",
                        "sl": close - (1.5 * atr),
                        "tp": close + (2.5 * atr),
                        "comment": "MACD Bullish Crossover"
                    }
        
        # SHORT: Bearish trend + MACD crossover
        if close < ema_200 and ema_50 < ema_200:  # Strong downtrend
            if macd < macd_signal and macd_hist < 0:  # MACD bearish
                if macd_hist < prev_hist:  # Histogram declining (momentum increasing)
                    return {
                        "signal": "SELL",
                        "sl": close + (1.5 * atr),
                        "tp": close - (2.5 * atr),
                        "comment": "MACD Bearish Crossover"
                    }
        
        return None
    
    def calculate_progress(self, df, extra_data=None):
        """Calculate progress based on MACD proximity to crossover"""
        if df.empty or len(df) < 200:
            return 0
        
        try:
            self.add_indicators(df)
            
            macd = df['MACD'].iloc[-1]
            macd_signal = df['MACD_signal'].iloc[-1]
            macd_hist = df['MACD_hist'].iloc[-1]
            close = df['close'].iloc[-1]
            ema_50 = df['EMA_50'].iloc[-1]
            ema_200 = df['EMA_200'].iloc[-1]
            
            progress = 0
            
            # Trend alignment (40 points)
            if (close > ema_200 and ema_50 > ema_200) or (close < ema_200 and ema_50 < ema_200):
                progress += 40
            
            # MACD proximity to crossover (60 points)
            macd_diff = abs(macd - macd_signal)
            macd_avg = (abs(macd) + abs(macd_signal)) / 2
            if macd_avg > 0:
                proximity = 1 - min(1, macd_diff / macd_avg)
                progress += int(60 * proximity)
            
            # Bonus if already crossed and histogram growing
            if abs(macd_hist) > 0:
                prev_hist = df['MACD_hist'].iloc[-2]
                if (macd_hist > 0 and macd_hist > prev_hist) or (macd_hist < 0 and macd_hist < prev_hist):
                    progress = min(100, progress + 20)
            
            return min(100, max(0, progress))
        except:
            return 0
