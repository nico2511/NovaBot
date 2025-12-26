from abc import ABC, abstractmethod
from app.services.indicators import ta
import pandas as pd

class BaseStrategy(ABC):
    def __init__(self, config=None):
        self.name = self.__class__.__name__
        self.config = config or {}

    @abstractmethod
    def generate_signal(self, df, extra_data=None):
        """
        Generate signal from dataframe.
        
        Args:
            df: Primary dataframe (typically the strategy's main timeframe)
            extra_data: Optional dict with additional dataframes (e.g., {"1m": df_1m, "1h": df_1h})
        """
        pass

    def add_indicators(self, df):
        """Add indicators to the dataframe. Should be overridden by subclasses."""
        pass
    
    def calculate_progress(self, df, extra_data=None):
        """
        Calculate how close the strategy is to triggering a signal (0-100%).
        
        Args:
            df: Primary dataframe
            extra_data: Optional dict with additional dataframes
            
        Returns:
            int: Progress percentage (0-100)
        """
        return 0  # Default: no progress

class ScalpEmaRsi(BaseStrategy):
    def add_indicators(self, df):
        params = self.config.get("params", {})
        ema_fast_len = params.get("ema_fast", 9)
        ema_slow_len = params.get("ema_slow", 21)
        rsi_len = params.get("rsi_period", 14)
        
        # Indicators
        df[f'EMA_{ema_fast_len}'] = ta.ema(df['close'], length=ema_fast_len)
        df[f'EMA_{ema_slow_len}'] = ta.ema(df['close'], length=ema_slow_len)
        df['EMA_200'] = ta.ema(df['close'], length=200)
        df[f'RSI_{rsi_len}'] = ta.rsi(df['close'], length=rsi_len)
        df['ATRr_14'] = ta.atr(df['high'], df['low'], df['close'], length=14)
        return df

    def generate_signal(self, df, extra_data=None):
        if df.empty or len(df) < 200: return None

    def calculate_progress(self, df, extra_data=None):
        """Calculate progress based on EMA convergence"""
        if df.empty or len(df) < 200:
            return 0
        try:
            self.add_indicators(df)
            params = self.config.get("params", {})
            ema_fast = df[f"EMA_{params.get('ema_fast', 9)}"].iloc[-1]
            ema_slow = df[f"EMA_{params.get('ema_slow', 21)}"].iloc[-1]
            close = df['close'].iloc[-1]
            trend = df['EMA_200'].iloc[-1]
            rsi = df[f"RSI_{params.get('rsi_period', 14)}"].iloc[-1]
            
            # EMA distance (50 points)
            ema_diff_pct = abs(ema_fast - ema_slow) / ema_slow * 100
            ema_progress = max(0, min(50, 50 * (1 - ema_diff_pct / 0.5)))
            
            # Trend alignment (25 points)
            trend_progress = 25 if (close > trend and ema_fast > ema_slow) or (close < trend and ema_fast < ema_slow) else 0
            
            # RSI zone (25 points)
            rsi_progress = 25 if (50 < rsi < 70) or (30 < rsi < 50) else 0
            
            return min(100, int(ema_progress + trend_progress + rsi_progress))
        except:
            return 0
        
        self.add_indicators(df)
            
        params = self.config.get("params", {})
        ema_fast_len = params.get("ema_fast", 9)
        ema_slow_len = params.get("ema_slow", 21)
        rsi_len = params.get("rsi_period", 14)
        
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

class SwingTrendPullback(BaseStrategy):
    def add_indicators(self, df):
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
        return df

    def generate_signal(self, df, extra_data=None):
        if df.empty or len(df) < 200: return None
        
        self.add_indicators(df)
        
        params = self.config.get("params", {})
        ema_trend_len = params.get("ema_trend", 200)
        ema_fast_len = params.get("ema_pullback_fast", 20)
        ema_slow_len = params.get("ema_pullback_slow", 50)
        
        trend_col = f"EMA_{ema_trend_len}"
        fast_col = f"EMA_{ema_fast_len}"
        slow_col = f"EMA_{ema_slow_len}"
        rsi_col = "RSI_14"
        atr_col = "ATRr_14"
        
        if trend_col not in df.columns: return None
        
        close = df['close'].iloc[-1]
        prev_close = df['close'].iloc[-2]
        low = df['low'].iloc[-1]
        prev_low = df['low'].iloc[-2]
        high = df['high'].iloc[-1]
        prev_high = df['high'].iloc[-2]
        
        trend = df[trend_col].iloc[-1]
        ema_fast = df[fast_col].iloc[-1]
        ema_slow = df[slow_col].iloc[-1]
        rsi = df[rsi_col].iloc[-1]
        atr = df[atr_col].iloc[-1] if atr_col in df.columns else (close * 0.01)
        
        # Get ADX if available (for trend strength filter)
        adx = None
        if 'ADX_14' in df.columns:
            adx = df['ADX_14'].iloc[-1]
        
        # Require strong trend (ADX > 25)
        min_adx = params.get("min_adx", 25)
        if adx is not None and adx < min_adx:
            return None  # Weak trend, skip
        
        # LONG Setup
        if close > trend:
            # Require EMA alignment (fast > slow)
            if ema_fast <= ema_slow:
                return None
            
            # Pullback confirmation: previous candle touched EMA, current bouncing
            pullback_touched = prev_low <= ema_fast
            bouncing = close > ema_fast
            
            if pullback_touched and bouncing:
                # Check pullback depth (not too far)
                pullback_depth = abs(prev_low - ema_fast) / ema_fast
                max_depth = params.get("max_pullback_depth", 0.01)  # 1%
                if pullback_depth > max_depth:
                    return None  # Pullback too deep
                
                # Tighter RSI filter (bullish momentum)
                rsi_min = params.get("rsi_min_long", 50)
                rsi_max = params.get("rsi_max_long", 70)
                if not (rsi_min < rsi < rsi_max):
                    return None
                
                # Minimum volatility
                if atr > (close * 0.002):
                    return {
                        "signal": "BUY",
                        "sl": close - (1.5 * atr),
                        "tp": close + (3.0 * atr),
                        "comment": "Trend Pullback (Confirmed)"
                    }

        # SHORT Setup
        if close < trend:
            # Require EMA alignment (fast < slow)
            if ema_fast >= ema_slow:
                return None
            
            # Pullback confirmation: previous candle touched EMA, current bouncing
            pullback_touched = prev_high >= ema_fast
            bouncing = close < ema_fast
            
            if pullback_touched and bouncing:
                # Check pullback depth
                pullback_depth = abs(prev_high - ema_fast) / ema_fast
                max_depth = params.get("max_pullback_depth", 0.01)
                if pullback_depth > max_depth:
                    return None
                
                # Tighter RSI filter (bearish momentum)
                rsi_min = params.get("rsi_min_short", 30)
                rsi_max = params.get("rsi_max_short", 50)
                if not (rsi_min < rsi < rsi_max):
                    return None
                
                # Minimum volatility
                if atr > (close * 0.002):
                    return {
                        "signal": "SELL",
                        "sl": close + (1.5 * atr),
                        "tp": close - (3.0 * atr),
                        "comment": "Trend Pullback (Confirmed)"
                    }
        return None

class DayTradingORB(BaseStrategy):
    def generate_signal(self, df, extra_data=None):
        return None

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


class TestTriggerStrategy(BaseStrategy):
    """
    Strategy for TESTING purposes only.
    Triggers a signal almost constantly to verify engine/execution.
    """
    def add_indicators(self, df):
        df['ATRr_14'] = ta.atr(df['high'], df['low'], df['close'], length=14)
        return df

    def generate_signal(self, df, extra_data=None):
        if df.empty or len(df) < 5: return None
        
        self.add_indicators(df)
        
        atr_col = "ATRr_14"
        close = df['close'].iloc[-1]
        
        atr = df[atr_col].iloc[-1] if atr_col in df.columns else (close * 0.01)
        
        # Trigger BUY if close > 0 (always true)
        # But to avoid spamming 1000s, maybe only if not in position or simple condition
        # User asked for "strategy de test hyper light en trigger"
        # Let's signal regularly.
        return {
            "signal": "BUY",
            "sl": close * 0.99,
            "tp": close * 1.02,
            "comment": "TEST TRIGGER"
        }


class StrategySmartTrend(BaseStrategy):
    """
    Multi-Timeframe Strategy: Uses 15m for context (trend/zone) and 1m for trigger (micro-BOS).
    
    Setup (15m):
    - Trend Filter: Price above/below EMA 50
    - Zone: Price touches EMA 21 (pullback)
    
    Trigger (1m):
    - Long: Close > High of last 3 candles (Micro-BOS)
    - Short: Close < Low of last 3 candles
    
    Risk:
    - SL: Swing Low/High on 1m (tight)
    - TP: 1:2.5 RR
    """
    
    def __init__(self, config=None):
        super().__init__(config)
        self.looking_for_entry = False
        self.entry_direction = None  # "LONG" or "SHORT"
    
    def add_indicators(self, df):
        """Add indicators to 15m dataframe"""
        df['EMA_21'] = ta.ema(df['close'], length=21)
        df['EMA_50'] = ta.ema(df['close'], length=50)
        df['ATRr_14'] = ta.atr(df['high'], df['low'], df['close'], length=14)
        return df
    
    def generate_signal(self, df, extra_data=None):
        """
        Args:
            df: 15m dataframe (context)
            extra_data: dict with {"1m": df_1m} (trigger)
        """
        if df.empty or len(df) < 50:
            return None
        
        # Get 1m data
        if not extra_data or "1m" not in extra_data:
            return None
        
        df_1m = extra_data["1m"]
        if df_1m.empty or len(df_1m) < 5:
            return None
        
        # Add indicators to 15m
        self.add_indicators(df)
        
        # === STEP 1: Setup Check (15m) ===
        params = self.config.get("params", {})
        
        # Get latest 15m values
        close_15m = df['close'].iloc[-1]
        low_15m = df['low'].iloc[-1]
        high_15m = df['high'].iloc[-1]
        ema_21 = df['EMA_21'].iloc[-1]
        ema_50 = df['EMA_50'].iloc[-1]
        atr_15m = df['ATRr_14'].iloc[-1]
        
        # Check for setup
        # LONG Setup: Price above EMA 50 and touches EMA 21
        if close_15m > ema_50:
            if low_15m <= ema_21 * 1.002:  # Small tolerance for "touch"
                self.looking_for_entry = True
                self.entry_direction = "LONG"
        
        # SHORT Setup: Price below EMA 50 and touches EMA 21
        elif close_15m < ema_50:
            if high_15m >= ema_21 * 0.998:
                self.looking_for_entry = True
                self.entry_direction = "SHORT"
        
        # Cancel if trend broken
        if self.entry_direction == "LONG" and close_15m < ema_50:
            self.looking_for_entry = False
            self.entry_direction = None
        elif self.entry_direction == "SHORT" and close_15m > ema_50:
            self.looking_for_entry = False
            self.entry_direction = None
        
        # === STEP 2: Trigger Check (1m) ===
        if not self.looking_for_entry:
            return None
        
        # Get latest 1m values
        if len(df_1m) < 4:
            return None
        
        current_1m = df_1m.iloc[-1]
        last_3_1m = df_1m.iloc[-4:-1]  # Last 3 candles before current
        
        close_1m = current_1m['close']
        high_1m = current_1m['high']
        low_1m = current_1m['low']
        
        # LONG Trigger: Close > High of last 3 (Micro-BOS)
        if self.entry_direction == "LONG":
            high_of_last_3 = last_3_1m['high'].max()
            if close_1m > high_of_last_3:
                # Find swing low for SL
                swing_low = df_1m.tail(10)['low'].min()
                sl = swing_low - (0.2 * atr_15m)  # Small buffer
                tp = close_1m + (2.5 * (close_1m - sl))  # 1:2.5 RR
                
                # Reset state
                self.looking_for_entry = False
                self.entry_direction = None
                
                return {
                    "signal": "BUY",
                    "sl": sl,
                    "tp": tp,
                    "price": close_1m,
                    "comment": "Smart Trend: 15m Pullback + 1m Micro-BOS"
                }
        
        # SHORT Trigger: Close < Low of last 3
        elif self.entry_direction == "SHORT":
            low_of_last_3 = last_3_1m['low'].min()
            if close_1m < low_of_last_3:
                # Find swing high for SL
                swing_high = df_1m.tail(10)['high'].max()
                sl = swing_high + (0.2 * atr_15m)
                tp = close_1m - (2.5 * (sl - close_1m))  # 1:2.5 RR
                
                # Reset state
                self.looking_for_entry = False
                self.entry_direction = None
                
                return {
                    "signal": "SELL",
                    "sl": sl,
                    "tp": tp,
                    "price": close_1m,
                    "comment": "Smart Trend: 15m Pullback + 1m Micro-BOS"
                }
        
        return None

    def calculate_progress(self, df, extra_data=None):
        """Calculate progress: 15m setup (60%) + 1m trigger (40%)"""
        if df.empty or len(df) < 50:
            return 0
        if not extra_data or "1m" not in extra_data:
            return 0
        
        try:
            self.add_indicators(df)
            df_1m = extra_data["1m"]
            
            close_15m = df['close'].iloc[-1]
            low_15m = df['low'].iloc[-1]
            high_15m = df['high'].iloc[-1]
            ema_21 = df['EMA_21'].iloc[-1]
            ema_50 = df['EMA_50'].iloc[-1]
            
            setup_progress = 0
            
            # Trend (30 points)
            if close_15m > ema_50 or close_15m < ema_50:
                setup_progress += 30
                
                # Pullback proximity (30 points)
                if close_15m > ema_50:
                    dist = abs(low_15m - ema_21) / ema_21 * 100
                else:
                    dist = abs(high_15m - ema_21) / ema_21 * 100
                
                if dist < 0.5:
                    setup_progress += 30
                elif dist < 1.0:
                    setup_progress += 20
                elif dist < 2.0:
                    setup_progress += 10
            
            # 1m trigger (40 points)
            trigger_progress = 0
            if len(df_1m) >= 4:
                close_1m = df_1m.iloc[-1]['close']
                high_3 = df_1m.iloc[-4:-1]['high'].max()
                low_3 = df_1m.iloc[-4:-1]['low'].min()
                
                if close_15m > ema_50:
                    dist_bos = (high_3 - close_1m) / close_1m * 100
                else:
                    dist_bos = (close_1m - low_3) / close_1m * 100
                
                if dist_bos < 0:
                    trigger_progress = 40
                elif dist_bos < 0.1:
                    trigger_progress = 30
                elif dist_bos < 0.3:
                    trigger_progress = 20
            
            return min(100, int(setup_progress + trigger_progress))
        except:
            return 0

# Add calculate_progress to ScalpEmaRsi (after line 103)
# This will be inserted manually after the generate_signal method

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


class VolumeBreakout(BaseStrategy):
    """
    Volume Breakout Strategy
    Trades breakouts of support/resistance confirmed by volume spikes
    """
    def add_indicators(self, df):
        import pandas_ta as pta
        
        # Volume indicators
        df['volume_sma'] = df['volume'].rolling(window=20).mean()
        df['volume_ratio'] = df['volume'] / df['volume_sma']
        
        # Price indicators
        df['EMA_20'] = ta.ema(df['close'], length=20)
        df['RSI_14'] = ta.rsi(df['close'], length=14)
        df['ATRr_14'] = ta.atr(df['high'], df['low'], df['close'], length=14)
        
        # Pivot highs/lows (resistance/support)
        df['pivot_high'] = df['high'].rolling(window=10, center=True).max()
        df['pivot_low'] = df['low'].rolling(window=10, center=True).min()
        
        return df
    
    def generate_signal(self, df, extra_data=None):
        if df.empty or len(df) < 50:
            return None
        
        self.add_indicators(df)
        
        params = self.config.get("params", {})
        volume_threshold = params.get("volume_threshold", 1.5)  # 1.5x average volume
        min_rsi = params.get("min_rsi", 50)
        
        # Current values
        close = df['close'].iloc[-1]
        prev_close = df['close'].iloc[-2]
        high = df['high'].iloc[-1]
        low = df['low'].iloc[-1]
        volume_ratio = df['volume_ratio'].iloc[-1]
        rsi = df['RSI_14'].iloc[-1]
        atr = df['ATRr_14'].iloc[-1]
        
        # Recent resistance/support (last 20 candles)
        recent_high = df['high'].iloc[-20:-1].max()
        recent_low = df['low'].iloc[-20:-1].min()
        
        # LONG: Breakout above resistance with volume
        if close > recent_high and prev_close <= recent_high:
            if volume_ratio > volume_threshold:  # Volume confirmation
                if rsi > min_rsi:  # Momentum confirmation
                    return {
                        "signal": "BUY",
                        "sl": recent_high - (0.5 * atr),  # SL just below breakout level
                        "tp": close + (2.0 * atr),  # 2R target
                        "comment": f"Volume Breakout (Vol: {volume_ratio:.1f}x)"
                    }
        
        # SHORT: Breakdown below support with volume
        if close < recent_low and prev_close >= recent_low:
            if volume_ratio > volume_threshold:
                if rsi < (100 - min_rsi):  # Bearish momentum
                    return {
                        "signal": "SELL",
                        "sl": recent_low + (0.5 * atr),
                        "tp": close - (2.0 * atr),
                        "comment": f"Volume Breakdown (Vol: {volume_ratio:.1f}x)"
                    }
        
        return None
    
    def calculate_progress(self, df, extra_data=None):
        """Calculate progress based on proximity to breakout and volume buildup"""
        if df.empty or len(df) < 50:
            return 0
        
        try:
            self.add_indicators(df)
            
            close = df['close'].iloc[-1]
            volume_ratio = df['volume_ratio'].iloc[-1]
            rsi = df['RSI_14'].iloc[-1]
            
            recent_high = df['high'].iloc[-20:-1].max()
            recent_low = df['low'].iloc[-20:-1].min()
            
            progress = 0
            
            # Volume buildup (40 points)
            if volume_ratio > 1.0:
                progress += min(40, int(40 * (volume_ratio - 1.0) / 0.5))
            
            # Proximity to breakout level (40 points)
            dist_to_high = abs(close - recent_high) / recent_high
            dist_to_low = abs(close - recent_low) / recent_low
            min_dist = min(dist_to_high, dist_to_low)
            
            if min_dist < 0.01:  # Within 1%
                progress += 40
            elif min_dist < 0.02:  # Within 2%
                progress += 20
            
            # RSI momentum (20 points)
            if rsi > 50 and close > recent_high * 0.99:  # Near resistance, bullish
                progress += 20
            elif rsi < 50 and close < recent_low * 1.01:  # Near support, bearish
                progress += 20
            
            return min(100, max(0, progress))
        except:
            return 0

