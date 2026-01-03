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
        
        allow_longs = params.get("allow_longs", True)
        allow_shorts = params.get("allow_shorts", True)

        
        current = df.iloc[-1]
        close = current['close']
        high = current['high']
        low = current['low']
        atr = current[atr_col]
        
        recent = df.tail(lookback + 1)
        recent_high = recent['high'].iloc[:-1].max()
        recent_low = recent['low'].iloc[:-1].min()
        
        sl_mult = params.get("sl_atr_mult", 0.5)
        tp_mult = params.get("tp_atr_mult", 2.0)
        
        # BULLISH LIQUIDITY GRAB
        if allow_longs and low < recent_low and close > recent_low:
            candle_range = high - low
            if candle_range > 0 and (close - low) / candle_range > 0.5:
                return {
                    "signal": "BUY",
                    "sl": low - (sl_mult * atr),
                    "tp": close + (tp_mult * atr),
                    "comment": "Bullish Liquidity Grab"
                }
        
        # BEARISH LIQUIDITY GRAB
        if allow_shorts and high > recent_high and close < recent_high:
            candle_range = high - low
            if candle_range > 0 and (high - close) / candle_range > 0.5:
                return {
                    "signal": "SELL",
                    "sl": high + (sl_mult * atr),
                    "tp": close - (tp_mult * atr),
                    "comment": "Bearish Liquidity Grab"
                }
        return None
