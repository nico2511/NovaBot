from app.services.indicators import ta
import pandas as pd
from strategies.base import BaseStrategy

class SMCFVG(BaseStrategy):
    def add_indicators(self, df):
        df['ATRr_14'] = ta.atr(df['high'], df['low'], df['close'], length=14)
        return df

    def generate_signal(self, df, extra_data=None):
        if df.empty or len(df) < 10: return None
        
        self.add_indicators(df)
        
        params = self.config.get("params", {})
        fvg_threshold = params.get("fvg_threshold", 0.005)
        atr_col = "ATRr_14"
        if atr_col not in df.columns: return None
        
        if len(df) < 3: return None
        
        candle_1 = df.iloc[-3]
        candle_3 = df.iloc[-1]
        close = candle_3['close']
        atr = candle_3[atr_col]
        
        # Bullish FVG
        bullish_fvg_top = candle_3['low']
        bullish_fvg_bottom = candle_1['high']
        
        if bullish_fvg_top > bullish_fvg_bottom:
            gap_size = bullish_fvg_top - bullish_fvg_bottom
            gap_percent = gap_size / bullish_fvg_bottom
            if gap_percent >= fvg_threshold:
                if close <= bullish_fvg_top and close >= bullish_fvg_bottom * 0.998:
                    return {
                        "signal": "BUY",
                        "sl": bullish_fvg_bottom - (0.5 * atr),
                        "tp": close + (2.5 * atr),
                        "comment": f"Bullish FVG Fill"
                    }
        
        # Bearish FVG
        bearish_fvg_bottom = candle_3['high']
        bearish_fvg_top = candle_1['low']
        
        if bearish_fvg_top > bearish_fvg_bottom:
            gap_size = bearish_fvg_top - bearish_fvg_bottom
            gap_percent = gap_size / bearish_fvg_top
            if gap_percent >= fvg_threshold:
                if close >= bearish_fvg_bottom and close <= bearish_fvg_top * 1.002:
                    return {
                        "signal": "SELL",
                        "sl": bearish_fvg_top + (0.5 * atr),
                        "tp": close - (2.5 * atr),
                        "comment": f"Bearish FVG Fill"
                    }
        return None
