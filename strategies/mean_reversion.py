from app.services.indicators import ta
import pandas as pd
from strategies.base import BaseStrategy

class MeanReversion(BaseStrategy):
    def add_indicators(self, df):
        params = self.config.get("params", {})
        bb_length = params.get("bb_length", 20)
        bb_std = params.get("bb_std", 2.0)
        rsi_period = params.get("rsi_period", 14)
        
        # Indicators
        bb = ta.bbands(df['close'], length=bb_length, std=bb_std)
        df[f'BBU_{bb_length}_{bb_std}'] = bb['BBU']
        df[f'BBM_{bb_length}_{bb_std}'] = bb['BBM']
        df[f'BBL_{bb_length}_{bb_std}'] = bb['BBL']
        df[f'RSI_{rsi_period}'] = ta.rsi(df['close'], length=rsi_period)
        df['ATRr_14'] = ta.atr(df['high'], df['low'], df['close'], length=14)
        return df

    def generate_signal(self, df, extra_data=None):
        if df.empty or len(df) < 50: return None
        
        self.add_indicators(df)
        
        params = self.config.get("params", {})
        bb_length = params.get("bb_length", 20)
        bb_std = params.get("bb_std", 2.0)
        rsi_period = params.get("rsi_period", 14)
        
        bb_upper = f"BBU_{bb_length}_{bb_std}"
        bb_middle = f"BBM_{bb_length}_{bb_std}"
        bb_lower = f"BBL_{bb_length}_{bb_std}"
        rsi_col = f"RSI_{rsi_period}"
        atr_col = "ATRr_14"
        
        if bb_upper not in df.columns: return None
        
        close = df['close'].iloc[-1]
        upper = df[bb_upper].iloc[-1]
        middle = df[bb_middle].iloc[-1]
        lower = df[bb_lower].iloc[-1]
        rsi = df[rsi_col].iloc[-1]
        atr = df[atr_col].iloc[-1]
        
        if close <= lower and rsi < 30:
            return {
                "signal": "BUY",
                "sl": close - (1.5 * atr),
                "tp": middle,
                "comment": "Mean Reversion - Oversold Bounce"
            }
        
        if close >= upper and rsi > 70:
            return {
                "signal": "SELL",
                "sl": close + (1.5 * atr),
                "tp": middle,
                "comment": "Mean Reversion - Overbought Pullback"
            }
        return None
