from app.services.indicators import ta
import pandas as pd
from strategies.base import BaseStrategy

class InstitutionalScalp(BaseStrategy):
    def add_indicators(self, df):
        df['ATRr_14'] = ta.atr(df['high'], df['low'], df['close'], length=14)
        return df

    def generate_signal(self, df, extra_data=None):
        if df.empty or len(df) < 30: return None
        
        self.add_indicators(df)
        
        params = self.config.get("params", {})
        lookback = params.get("liq_grab_lookback", 20)
        atr_col = "ATRr_14"
        
        if atr_col not in df.columns: return None
        
        current = df.iloc[-1]
        close = current['close']
        high = current['high']
        low = current['low']
        atr = current[atr_col]
        
        recent = df.tail(lookback + 1)
        recent_high = recent['high'].iloc[:-1].max()
        recent_low = recent['low'].iloc[:-1].min()
        
        # BULLISH LIQUIDITY GRAB
        if low < recent_low and close > recent_low:
            candle_range = high - low
            if candle_range > 0 and (close - low) / candle_range > 0.5:
                return {
                    "signal": "BUY",
                    "sl": low - (0.5 * atr),
                    "tp": close + (2.0 * atr),
                    "comment": "Bullish Liquidity Grab"
                }
        
        # BEARISH LIQUIDITY GRAB
        if high > recent_high and close < recent_high:
            candle_range = high - low
            if candle_range > 0 and (high - close) / candle_range > 0.5:
                return {
                    "signal": "SELL",
                    "sl": high + (0.5 * atr),
                    "tp": close - (2.0 * atr),
                    "comment": "Bearish Liquidity Grab"
                }
        return None
