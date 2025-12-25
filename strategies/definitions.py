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
        """
        Detects liquidity grabs (stop hunts) - institutional patterns
        Looks for wicks that exceed recent highs/lows followed by reversal
        """
        if df.empty or len(df) < 30:
            return None
        
        params = self.config.get("params", {})
        lookback = params.get("liq_grab_lookback", 20)
        
        # Calculate ATR for stops
        df.ta.atr(length=14, append=True)
        atr_col = "ATRr_14"
        
        if atr_col not in df.columns:
            return None
        
        # Get recent data
        recent = df.tail(lookback + 1)
        current = df.iloc[-1]
        prev = df.iloc[-2]
        
        close = current['close']
        high = current['high']
        low = current['low']
        atr = current[atr_col]
        
        # Find recent swing high/low (excluding current candle)
        recent_high = recent['high'].iloc[:-1].max()
        recent_low = recent['low'].iloc[:-1].min()
        
        # BULLISH LIQUIDITY GRAB:
        # - Current candle wick goes below recent low (liquidity grab)
        # - But closes back above recent low (rejection/reversal)
        if low < recent_low and close > recent_low:
            # Confirm it's a strong reversal (close in upper half of candle)
            candle_range = high - low
            if candle_range > 0 and (close - low) / candle_range > 0.5:
                return {
                    "signal": "BUY",
                    "sl": low - (0.5 * atr),  # Below the liquidity grab wick
                    "tp": close + (2.0 * atr),
                    "comment": "Bullish Liquidity Grab (Stop Hunt Reversal)"
                }
        
        # BEARISH LIQUIDITY GRAB:
        # - Current candle wick goes above recent high (liquidity grab)
        # - But closes back below recent high (rejection/reversal)
        if high > recent_high and close < recent_high:
            # Confirm it's a strong reversal (close in lower half of candle)
            candle_range = high - low
            if candle_range > 0 and (high - close) / candle_range > 0.5:
                return {
                    "signal": "SELL",
                    "sl": high + (0.5 * atr),  # Above the liquidity grab wick
                    "tp": close - (2.0 * atr),
                    "comment": "Bearish Liquidity Grab (Stop Hunt Reversal)"
                }
        
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
        """
        Mean Reversion using Bollinger Bands + RSI
        Trades when price touches outer bands with RSI confirmation
        Best in ranging/choppy markets
        """
        if df.empty or len(df) < 50:
            return None
        
        params = self.config.get("params", {})
        bb_length = params.get("bb_length", 20)
        bb_std = params.get("bb_std", 2.0)
        rsi_period = params.get("rsi_period", 14)
        
        # Calculate indicators
        df.ta.bbands(length=bb_length, std=bb_std, append=True)
        df.ta.rsi(length=rsi_period, append=True)
        df.ta.atr(length=14, append=True)
        
        # Column names
        bb_upper = f"BBU_{bb_length}_{bb_std}"
        bb_middle = f"BBM_{bb_length}_{bb_std}"
        bb_lower = f"BBL_{bb_length}_{bb_std}"
        rsi_col = f"RSI_{rsi_period}"
        atr_col = "ATRr_14"
        
        # Check if all columns exist
        required_cols = [bb_upper, bb_middle, bb_lower, rsi_col, atr_col]
        if not all(col in df.columns for col in required_cols):
            return None
        
        # Current values
        close = df['close'].iloc[-1]
        upper = df[bb_upper].iloc[-1]
        middle = df[bb_middle].iloc[-1]
        lower = df[bb_lower].iloc[-1]
        rsi = df[rsi_col].iloc[-1]
        atr = df[atr_col].iloc[-1]
        
        # BULLISH MEAN REVERSION:
        # - Price touches or goes below lower band
        # - RSI oversold (< 30)
        # - Expect bounce back to middle band
        if close <= lower and rsi < 30:
            return {
                "signal": "BUY",
                "sl": close - (1.5 * atr),  # Below entry
                "tp": middle,  # Target middle band (mean)
                "comment": "Mean Reversion - Oversold Bounce"
            }
        
        # BEARISH MEAN REVERSION:
        # - Price touches or goes above upper band
        # - RSI overbought (> 70)
        # - Expect pullback to middle band
        if close >= upper and rsi > 70:
            return {
                "signal": "SELL",
                "sl": close + (1.5 * atr),  # Above entry
                "tp": middle,  # Target middle band (mean)
                "comment": "Mean Reversion - Overbought Pullback"
            }
        
        return None

class SMCFVG(BaseStrategy):
    def generate_signal(self, df):
        """
        Smart Money Concepts - Fair Value Gap (FVG) Detection
        Identifies imbalances (gaps) in price action that often get filled
        FVG = Gap between candle 1 high and candle 3 low (or vice versa)
        """
        if df.empty or len(df) < 10:
            return None
        
        params = self.config.get("params", {})
        fvg_threshold = params.get("fvg_threshold", 0.005)  # 0.5% minimum gap
        
        # Calculate ATR for stops
        df.ta.atr(length=14, append=True)
        atr_col = "ATRr_14"
        
        if atr_col not in df.columns:
            return None
        
        # Get last 3 candles
        if len(df) < 3:
            return None
        
        candle_1 = df.iloc[-3]  # 2 candles ago
        candle_2 = df.iloc[-2]  # 1 candle ago
        candle_3 = df.iloc[-1]  # Current candle
        
        close = candle_3['close']
        atr = candle_3[atr_col]
        
        # BULLISH FVG:
        # Gap between candle_1 high and candle_3 low
        # Candle 2 creates the imbalance (big move up)
        bullish_fvg_top = candle_3['low']
        bullish_fvg_bottom = candle_1['high']
        
        if bullish_fvg_top > bullish_fvg_bottom:
            gap_size = bullish_fvg_top - bullish_fvg_bottom
            gap_percent = gap_size / bullish_fvg_bottom
            
            # Check if gap is significant enough
            if gap_percent >= fvg_threshold:
                # Price should be near or in the FVG zone
                fvg_middle = (bullish_fvg_top + bullish_fvg_bottom) / 2
                
                # Entry when price is within or just above the FVG
                if close <= bullish_fvg_top and close >= bullish_fvg_bottom * 0.998:
                    return {
                        "signal": "BUY",
                        "sl": bullish_fvg_bottom - (0.5 * atr),  # Below FVG
                        "tp": close + (2.5 * atr),  # Target continuation
                        "comment": f"Bullish FVG Fill ({gap_percent*100:.2f}% gap)"
                    }
        
        # BEARISH FVG:
        # Gap between candle_1 low and candle_3 high
        # Candle 2 creates the imbalance (big move down)
        bearish_fvg_bottom = candle_3['high']
        bearish_fvg_top = candle_1['low']
        
        if bearish_fvg_top > bearish_fvg_bottom:
            gap_size = bearish_fvg_top - bearish_fvg_bottom
            gap_percent = gap_size / bearish_fvg_top
            
            # Check if gap is significant enough
            if gap_percent >= fvg_threshold:
                # Price should be near or in the FVG zone
                fvg_middle = (bearish_fvg_top + bearish_fvg_bottom) / 2
                
                # Entry when price is within or just below the FVG
                if close >= bearish_fvg_bottom and close <= bearish_fvg_top * 1.002:
                    return {
                        "signal": "SELL",
                        "sl": bearish_fvg_top + (0.5 * atr),  # Above FVG
                        "tp": close - (2.5 * atr),  # Target continuation
                        "comment": f"Bearish FVG Fill ({gap_percent*100:.2f}% gap)"
                    }
        
        return None

