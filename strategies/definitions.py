from abc import ABC, abstractmethod
from app.services.indicators import ta
import pandas as pd

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
        
        # Indicators (Pure Pandas implementation)
        df[f'EMA_{ema_fast_len}'] = ta.ema(df['close'], length=ema_fast_len)
        df[f'EMA_{ema_slow_len}'] = ta.ema(df['close'], length=ema_slow_len)
        df['EMA_200'] = ta.ema(df['close'], length=200)
        df[f'RSI_{rsi_len}'] = ta.rsi(df['close'], length=rsi_len)
        df['ATRr_14'] = ta.atr(df['high'], df['low'], df['close'], length=14)
        
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
            if close > current_trend:
                if 50 < current_rsi < 70:
                    return {
                        "signal": "BUY",
                        "sl": close - (1.5 * atr),
                        "tp": close + (2.5 * atr),
                        "comment": "EMA Cross + Trend + RSI Momentum"
                    }
                
        # SELL: Cross DOWN + Trend Bearish
        if prev_fast >= prev_slow and current_fast < current_slow:
            if close < current_trend:
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
        if df.empty or len(df) < 30: return None
        
        params = self.config.get("params", {})
        lookback = params.get("liq_grab_lookback", 20)
        
        # Indicators
        df['ATRr_14'] = ta.atr(df['high'], df['low'], df['close'], length=14)
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

class SwingTrendPullback(BaseStrategy):
    def generate_signal(self, df):
        if df.empty or len(df) < 200: return None
        
        params = self.config.get("params", {})
        ema_trend_len = params.get("ema_trend", 200)
        ema_fast_len = params.get("ema_pullback_fast", 20)
        ema_slow_len = params.get("ema_pullback_slow", 50)
        
        # Indicators
        df[f'EMA_{ema_trend_len}'] = ta.ema(df['close'], length=ema_trend_len)
        df[f'EMA_{ema_fast_len}'] = ta.ema(df['close'], length=ema_fast_len)
        df[f'EMA_{ema_slow_len}'] = ta.ema(df['close'], length=ema_slow_len)
        df['RSI_14'] = ta.rsi(df['close'], length=14)
        df['ATRr_14'] = ta.atr(df['high'], df['low'], df['close'], length=14)
        
        trend_col = f"EMA_{ema_trend_len}"
        fast_col = f"EMA_{ema_fast_len}"
        rsi_col = "RSI_14"
        atr_col = "ATRr_14"
        
        if trend_col not in df.columns: return None
        
        close = df['close'].iloc[-1]
        low = df['low'].iloc[-1]
        high = df['high'].iloc[-1]
        trend = df[trend_col].iloc[-1]
        ema_fast = df[fast_col].iloc[-1]
        rsi = df[rsi_col].iloc[-1]
        atr = df[atr_col].iloc[-1] if atr_col in df.columns else (close * 0.01)
        
        if close > trend:
            if low <= ema_fast and rsi > params.get("rsi_min_long", 40):
                 if atr > (close * 0.002):
                     return {
                        "signal": "BUY",
                        "sl": close - (1.5 * atr),
                        "tp": close + (3.0 * atr),
                        "comment": "Trend Pullback"
                    }

        if close < trend:
            if high >= ema_fast and rsi < params.get("rsi_max_short", 60):
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
        return None

class MeanReversion(BaseStrategy):
    def generate_signal(self, df):
        if df.empty or len(df) < 50: return None
        
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

class SMCFVG(BaseStrategy):
    def generate_signal(self, df):
        if df.empty or len(df) < 10: return None
        
        params = self.config.get("params", {})
        fvg_threshold = params.get("fvg_threshold", 0.005)
        
        df['ATRr_14'] = ta.atr(df['high'], df['low'], df['close'], length=14)
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
