from app.services.indicators import ta
import pandas as pd
from strategies.base import BaseStrategy

class RBIReversion(BaseStrategy): # Renamed closer to filename or keep as RSIBollingerBands
    """
    RSI + Bollinger Bands Strategy
    Enhanced mean reversion using RSI oversold/overbought + BB touches
    """
    def add_indicators(self, df):
        # Bollinger Bands (use same method as MeanReversion)
        bb_length = 20
        bb_std = 2
        bb = ta.bbands(df['close'], length=bb_length, std=bb_std)
        df['BB_upper'] = bb['BBU']
        df['BB_middle'] = bb['BBM']
        df['BB_lower'] = bb['BBL']
        
        # RSI
        df['RSI_14'] = ta.rsi(df['close'], length=14)
        
        # Volume
        df['volume_sma'] = df['volume'].rolling(window=20).mean()
        
        # ATR
        df['ATRr_14'] = ta.atr(df['high'], df['low'], df['close'], length=14)
        return df
    
    def generate_signal(self, df, extra_data=None):
        if df.empty or len(df) < 50:
            return None
        
        self.add_indicators(df)
        
        params = self.config.get("params", {})
        rsi_oversold = params.get("rsi_oversold", 30)
        rsi_overbought = params.get("rsi_overbought", 70)
        require_volume = params.get("require_volume", True)
        
        # Current values
        close = df['close'].iloc[-1]
        low = df['low'].iloc[-1]
        high = df['high'].iloc[-1]
        
        bb_upper = df['BB_upper'].iloc[-1]
        bb_middle = df['BB_middle'].iloc[-1]
        bb_lower = df['BB_lower'].iloc[-1]
        
        rsi = df['RSI_14'].iloc[-1]
        volume = df['volume'].iloc[-1]
        volume_sma = df['volume_sma'].iloc[-1]
        atr = df['ATRr_14'].iloc[-1]
        
        # LONG: Price touches lower BB + RSI oversold
        if low <= bb_lower:
            if rsi < rsi_oversold:
                if not require_volume or volume > volume_sma:  # Volume confirmation
                    return {
                        "signal": "BUY",
                        "sl": bb_lower - (1.0 * atr),  # SL below BB
                        "tp": bb_middle,  # Target middle BB (mean reversion)
                        "comment": f"RSI+BB Oversold (RSI: {rsi:.0f})"
                    }
        
        # SHORT: Price touches upper BB + RSI overbought
        if high >= bb_upper:
            if rsi > rsi_overbought:
                if not require_volume or volume > volume_sma:
                    return {
                        "signal": "SELL",
                        "sl": bb_upper + (1.0 * atr),
                        "tp": bb_middle,
                        "comment": f"RSI+BB Overbought (RSI: {rsi:.0f})"
                    }
        
        return None
    
    def calculate_progress(self, df, extra_data=None):
        """Calculate progress based on proximity to BB and RSI levels"""
        if df.empty or len(df) < 50:
            return 0
        
        try:
            self.add_indicators(df)
            
            close = df['close'].iloc[-1]
            bb_upper = df['BB_upper'].iloc[-1]
            bb_lower = df['BB_lower'].iloc[-1]
            rsi = df['RSI_14'].iloc[-1]
            
            progress = 0
            
            # Proximity to BB (50 points)
            dist_to_upper = abs(close - bb_upper) / bb_upper
            dist_to_lower = abs(close - bb_lower) / bb_lower
            min_dist = min(dist_to_upper, dist_to_lower)
            
            if min_dist < 0.005:  # Within 0.5%
                progress += 50
            elif min_dist < 0.01:  # Within 1%
                progress += 25
            
            # RSI extreme (50 points)
            if rsi < 30:  # Oversold
                progress += int(50 * (30 - rsi) / 10)
            elif rsi > 70:  # Overbought
                progress += int(50 * (rsi - 70) / 10)
            
            return min(100, max(0, progress))
        except:
            return 0
