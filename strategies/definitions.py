from abc import ABC, abstractmethod

import pandas_ta as ta

class BaseStrategy(ABC):
    def __init__(self, config=None):
        self.name = self.__class__.__name__
        self.config = config or {}

    @abstractmethod
    def generate_signal(self, df):
        pass

class ScalpEmaRsi(BaseStrategy):
    def generate_signal(self, df):
        if df.empty or len(df) < 200: return None
            
        params = self.config.get("params", {})
        ema_fast_len = params.get("ema_fast", 9)
        ema_slow_len = params.get("ema_slow", 21)
        rsi_len = params.get("rsi_period", 14)
        
        # Indicators
        df.ta.ema(length=ema_fast_len, append=True)
        df.ta.ema(length=ema_slow_len, append=True)
        df.ta.ema(length=200, append=True) # Trend Filter
        df.ta.rsi(length=rsi_len, append=True)
        df.ta.atr(length=14, append=True)
        
        fast_col = f"EMA_{ema_fast_len}"
        slow_col = f"EMA_{ema_slow_len}"
        trend_col = "EMA_200"
        rsi_col = f"RSI_{rsi_len}"
        atr_col = "ATRr_14"
        
        if trend_col not in df.columns or atr_col not in df.columns: return None

        # Values
        current_fast = df[fast_col].iloc[-1]
        prev_fast = df[fast_col].iloc[-2]
        current_slow = df[slow_col].iloc[-1]
        prev_slow = df[slow_col].iloc[-2]
        
        current_trend = df[trend_col].iloc[-1]
        current_rsi = df[rsi_col].iloc[-1]
        close = df['close'].iloc[-1]
        atr = df[atr_col].iloc[-1]
        
        # BUY: Cross UP + Trend Bullish
        if prev_fast <= prev_slow and current_fast > current_slow:
            if close > current_trend: # EMA 200 Filter
                # RSI must be showing Momentum, but not Overbought (Ex: >50 but <70)
                if 50 < current_rsi < 70:
                    return {
                        "signal": "BUY",
                        "sl": close - (1.5 * atr),
                        "tp": close + (2.5 * atr),
                        "comment": "EMA Cross + Trend + RSI Momentum"
                    }
                
        # SELL: Cross DOWN + Trend Bearish
        if prev_fast >= prev_slow and current_fast < current_slow:
            if close < current_trend: # EMA 200 Filter
                # RSI Bearish Momentum (Ex: <50 but >30)
                if 30 < current_rsi < 50:
                    return {
                        "signal": "SELL",
                        "sl": close + (1.5 * atr),
                        "tp": close - (2.5 * atr),
                        "comment": "EMA Cross + Trend + RSI Momentum"
                    }
        return None


class InstitutionalScalp(BaseStrategy):
    def generate_signal(self, df):
        return None

class SwingTrendPullback(BaseStrategy):
    def generate_signal(self, df):
        if df.empty or len(df) < 200: return None
        
        params = self.config.get("params", {})
        ema_trend_len = params.get("ema_trend", 200)
        ema_fast_len = params.get("ema_pullback_fast", 20)
        ema_slow_len = params.get("ema_pullback_slow", 50)
        
        # 1. Indicators
        df.ta.ema(length=ema_trend_len, append=True)
        df.ta.ema(length=ema_fast_len, append=True)
        df.ta.ema(length=ema_slow_len, append=True)
        df.ta.rsi(length=14, append=True)
        df.ta.atr(length=14, append=True)
        
        trend_col = f"EMA_{ema_trend_len}"
        fast_col = f"EMA_{ema_fast_len}"
        slow_col = f"EMA_{ema_slow_len}"
        rsi_col = "RSI_14"
        atr_col = "ATRr_14"
        
        if trend_col not in df.columns: return None
        
        close = df['close'].iloc[-1]
        low = df['low'].iloc[-1]
        high = df['high'].iloc[-1]
        trend = df[trend_col].iloc[-1]
        ema_fast = df[fast_col].iloc[-1]
        ema_slow = df[slow_col].iloc[-1]
        rsi = df[rsi_col].iloc[-1]
        atr = df[atr_col].iloc[-1] if atr_col in df.columns else (close * 0.01)
        
        if close > trend:
            if low <= ema_fast and rsi > params.get("rsi_min_long", 40):
                 # Volatility Filter: Avoid flat markets
                 if atr > (close * 0.002):
                     return {
                        "signal": "BUY",
                        "sl": close - (1.5 * atr),
                        "tp": close + (3.0 * atr),
                        "comment": "Trend Pullback"
                    }

        # SHORT: Overall Trend Bearish (Price < EMA200)
        if close < trend:
            if high >= ema_fast and rsi < params.get("rsi_max_short", 60):
                # Volatility Filter
                if atr > (close * 0.002):
                    return {
                        "signal": "SELL",
                        "sl": close + (1.5 * atr),
                        "tp": close - (3.0 * atr),
                        "comment": "Trend Pullback"
                    }
        return None

class DayTradingORB(BaseStrategy):
    def generate_signal(self, df):
        # DISABLED FOR OPTIMIZATION
        return None
        
        # Original Logic Backup:
        # if df.empty or len(df) < 200: return None
        # ... logic ...

class MeanReversion(BaseStrategy):
    def generate_signal(self, df):
        return None

class SMCFVG(BaseStrategy):
    def generate_signal(self, df):
        return None
