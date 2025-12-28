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
        
        # BUY: Bullish setup (EMA alignment + Trend + RSI)
        # Trigger on: 1) Active crossover OR 2) Already aligned with all conditions met
        is_bullish_cross = prev_fast <= prev_slow and current_fast > current_slow
        is_bullish_aligned = current_fast > current_slow  # EMAs already aligned
        
        if is_bullish_cross or is_bullish_aligned:
            if close > current_trend:  # Above 200 EMA
                if 50 < current_rsi < 70:  # RSI in momentum zone
                    return {
                        "signal": "BUY",
                        "sl": close - (1.5 * atr),
                        "tp": close + (2.5 * atr),
                        "comment": "EMA Bullish + Trend + RSI" if is_bullish_aligned else "EMA Cross + Trend + RSI"
                    }
                
        # SELL: Bearish setup (EMA alignment + Trend + RSI)
        is_bearish_cross = prev_fast >= prev_slow and current_fast < current_slow
        is_bearish_aligned = current_fast < current_slow
        
        if is_bearish_cross or is_bearish_aligned:
            if close < current_trend:  # Below 200 EMA
                if 30 < current_rsi < 50:  # RSI in momentum zone
                    return {
                        "signal": "SELL",
                        "sl": close + (1.5 * atr),
                        "tp": close - (2.5 * atr),
                        "comment": "EMA Bearish + Trend + RSI" if is_bearish_aligned else "EMA Cross + Trend + RSI"
                    }
        return None

    def calculate_progress(self, df, extra_data=None):
        """Calculate progress based on EMA convergence. Capped at 95% unless signal active."""
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
            
            # EMA distance (50 points) - favors convergence
            ema_diff_pct = abs(ema_fast - ema_slow) / ema_slow * 100
            ema_progress = max(0, min(50, 50 * (1 - ema_diff_pct / 0.5)))
            
            # Trend alignment (25 points)
            trend_progress = 25 if (close > trend and ema_fast > ema_slow) or (close < trend and ema_fast < ema_slow) else 0
            
            # RSI zone (25 points)
            rsi_progress = 25 if (50 < rsi < 70) or (30 < rsi < 50) else 0
            
            total_progress = min(100, int(ema_progress + trend_progress + rsi_progress))
            
            # No cap needed - if all conditions met, show 100% and signal will trigger
            return total_progress 
        except:
            return 0


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


class EMABounce(BaseStrategy):
    """
    EMA 9/21 Bounce Strategy
    Simple scalping strategy that buys pullbacks to EMA 21 in trending markets
    """
    def add_indicators(self, df):
        # EMAs
        df['EMA_9'] = ta.ema(df['close'], length=9)
        df['EMA_21'] = ta.ema(df['close'], length=21)
        df['EMA_200'] = ta.ema(df['close'], length=200)
        
        # RSI for momentum filter
        df['RSI_14'] = ta.rsi(df['close'], length=14)
        
        # ATR for SL/TP
        df['ATRr_14'] = ta.atr(df['high'], df['low'], df['close'], length=14)
        return df
    
    def generate_signal(self, df, extra_data=None):
        if df.empty or len(df) < 200:
            return None
        
        self.add_indicators(df)
        
        params = self.config.get("params", {})
        rsi_min = params.get("rsi_min", 40)
        rsi_max = params.get("rsi_max", 60)
        
        # Current and previous values
        close = df['close'].iloc[-1]
        prev_close = df['close'].iloc[-2]
        low = df['low'].iloc[-1]
        prev_low = df['low'].iloc[-2]
        high = df['high'].iloc[-1]
        prev_high = df['high'].iloc[-2]
        
        ema_9 = df['EMA_9'].iloc[-1]
        ema_21 = df['EMA_21'].iloc[-1]
        ema_200 = df['EMA_200'].iloc[-1]
        rsi = df['RSI_14'].iloc[-1]
        atr = df['ATRr_14'].iloc[-1]
        
        # LONG: Bullish trend + bounce off EMA 21
        if close > ema_200 and ema_9 > ema_21:  # Uptrend
            # Previous candle touched EMA 21, current bouncing
            if prev_low <= ema_21 and close > ema_21:
                if rsi_min < rsi < rsi_max:  # Not too weak, not overbought
                    return {
                        "signal": "BUY",
                        "sl": ema_21 - (0.5 * atr),  # Tight SL below EMA
                        "tp": close + (1.5 * atr),  # 3:1 R:R
                        "comment": "EMA 21 Bounce (Bullish)"
                    }
        
        # SHORT: Bearish trend + bounce off EMA 21
        if close < ema_200 and ema_9 < ema_21:  # Downtrend
            # Previous candle touched EMA 21, current bouncing
            if prev_high >= ema_21 and close < ema_21:
                if (100 - rsi_max) < rsi < (100 - rsi_min):  # Inverse for shorts
                    return {
                        "signal": "SELL",
                        "sl": ema_21 + (0.5 * atr),
                        "tp": close - (1.5 * atr),
                        "comment": "EMA 21 Bounce (Bearish)"
                    }
        
        return None
    
    def calculate_progress(self, df, extra_data=None):
        """Calculate progress based on proximity to EMA 21 and trend strength"""
        if df.empty or len(df) < 200:
            return 0
        
        try:
            self.add_indicators(df)
            
            close = df['close'].iloc[-1]
            ema_9 = df['EMA_9'].iloc[-1]
            ema_21 = df['EMA_21'].iloc[-1]
            ema_200 = df['EMA_200'].iloc[-1]
            rsi = df['RSI_14'].iloc[-1]
            
            progress = 0
            
            # Trend alignment (40 points)
            if (close > ema_200 and ema_9 > ema_21) or (close < ema_200 and ema_9 < ema_21):
                progress += 40
            
            # Proximity to EMA 21 (40 points)
            dist_to_ema = abs(close - ema_21) / ema_21
            if dist_to_ema < 0.002:  # Within 0.2%
                progress += 40
            elif dist_to_ema < 0.005:  # Within 0.5%
                progress += 20
            
            # RSI in range (20 points)
            if 40 < rsi < 60:
                progress += 20
            
            return min(100, max(0, progress))
        except:
            return 0


class TripleEMA(BaseStrategy):
    """
    Triple EMA Crossover Strategy
    Uses 3 EMAs to filter false signals and catch strong trends
    """
    def add_indicators(self, df):
        # Triple EMAs
        df['EMA_8'] = ta.ema(df['close'], length=8)
        df['EMA_21'] = ta.ema(df['close'], length=21)
        df['EMA_55'] = ta.ema(df['close'], length=55)
        
        # Volume for confirmation
        df['volume_sma'] = df['volume'].rolling(window=20).mean()
        
        # ATR
        df['ATRr_14'] = ta.atr(df['high'], df['low'], df['close'], length=14)
        return df
    
    def generate_signal(self, df, extra_data=None):
        if df.empty or len(df) < 60:
            return None
        
        self.add_indicators(df)
        
        params = self.config.get("params", {})
        require_volume = params.get("require_volume", True)
        
        # Current and previous values
        close = df['close'].iloc[-1]
        ema_8 = df['EMA_8'].iloc[-1]
        prev_ema_8 = df['EMA_8'].iloc[-2]
        ema_21 = df['EMA_21'].iloc[-1]
        prev_ema_21 = df['EMA_21'].iloc[-2]
        ema_55 = df['EMA_55'].iloc[-1]
        
        volume = df['volume'].iloc[-1]
        volume_sma = df['volume_sma'].iloc[-1]
        atr = df['ATRr_14'].iloc[-1]
        
        # LONG: EMA 8 crosses above EMA 21, both above EMA 55
        if prev_ema_8 <= prev_ema_21 and ema_8 > ema_21:  # Crossover
            if ema_21 > ema_55 and close > ema_55:  # Trend confirmed
                if not require_volume or volume > volume_sma:  # Volume confirmation
                    return {
                        "signal": "BUY",
                        "sl": ema_55 - (1.5 * atr),  # SL below EMA 55
                        "tp": close + (3.0 * atr),  # 2:1 R:R
                        "comment": "Triple EMA Bullish Cross"
                    }
        
        # SHORT: EMA 8 crosses below EMA 21, both below EMA 55
        if prev_ema_8 >= prev_ema_21 and ema_8 < ema_21:  # Crossover
            if ema_21 < ema_55 and close < ema_55:  # Trend confirmed
                if not require_volume or volume > volume_sma:
                    return {
                        "signal": "SELL",
                        "sl": ema_55 + (1.5 * atr),
                        "tp": close - (3.0 * atr),
                        "comment": "Triple EMA Bearish Cross"
                    }
        
        return None
    
    def calculate_progress(self, df, extra_data=None):
        """Calculate progress based on EMA proximity to crossover"""
        if df.empty or len(df) < 60:
            return 0
        
        try:
            self.add_indicators(df)
            
            ema_8 = df['EMA_8'].iloc[-1]
            ema_21 = df['EMA_21'].iloc[-1]
            ema_55 = df['EMA_55'].iloc[-1]
            close = df['close'].iloc[-1]
            
            progress = 0
            
            # Trend alignment (40 points)
            if (ema_21 > ema_55 and close > ema_55) or (ema_21 < ema_55 and close < ema_55):
                progress += 40
            
            # Proximity to crossover (60 points)
            ema_diff = abs(ema_8 - ema_21)
            ema_avg = (ema_8 + ema_21) / 2
            if ema_avg > 0:
                proximity = 1 - min(1, ema_diff / (ema_avg * 0.01))  # Within 1%
                progress += int(60 * proximity)
            
            return min(100, max(0, progress))
        except:
            return 0


class RSIBollingerBands(BaseStrategy):
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



# ============================================
# STRATEGY: Golden Cross (Trend Following)
# ============================================
class StrategyGoldenCross(BaseStrategy):
    """
    Classic Trend Following strategy using SMA crossovers.
    
    Entry:
    - LONG: SMA 50 crosses above SMA 200 (Golden Cross)
    - SHORT: SMA 50 crosses below SMA 200 (Death Cross)
    
    Exit:
    - Close LONG if price closes below SMA 50
    - Close SHORT if price closes above SMA 50
    """
    
    def add_indicators(self, df):
        df['SMA_50'] = ta.sma(df['close'], length=50)
        df['SMA_200'] = ta.sma(df['close'], length=200)
        return df
    
    def generate_signal(self, df, extra_data=None):
        df = self.add_indicators(df)
        
        if len(df) < 201:  # Need at least 201 candles for SMA 200
            return None
        
        # Current and previous values
        sma_50_curr = df['SMA_50'].iloc[-1]
        sma_50_prev = df['SMA_50'].iloc[-2]
        sma_200_curr = df['SMA_200'].iloc[-1]
        sma_200_prev = df['SMA_200'].iloc[-2]
        close = df['close'].iloc[-1]
        
        # Golden Cross: SMA 50 crosses above SMA 200
        if sma_50_prev <= sma_200_prev and sma_50_curr > sma_200_curr:
            return {
                'signal': 'BUY',
                'price': close,
                'sl': sma_50_curr * 0.97,  # 3% below SMA 50
                'tp': close * 1.10,  # 10% profit target
                'comment': 'Golden Cross detected - SMA 50 crossed above SMA 200'
            }
        
        # Death Cross: SMA 50 crosses below SMA 200
        if sma_50_prev >= sma_200_prev and sma_50_curr < sma_200_curr:
            return {
                'signal': 'SELL',
                'price': close,
                'sl': sma_50_curr * 1.03,  # 3% above SMA 50
                'tp': close * 0.90,  # 10% profit target
                'comment': 'Death Cross detected - SMA 50 crossed below SMA 200'
            }
        
        return None
    
    def calculate_progress(self, df, extra_data=None):
        """Calculate proximity to Golden/Death Cross"""
        try:
            df = self.add_indicators(df)
            if len(df) < 201:
                return 0
            
            sma_50 = df['SMA_50'].iloc[-1]
            sma_200 = df['SMA_200'].iloc[-1]
            
            # Calculate distance between SMAs (as percentage)
            distance_pct = abs(sma_50 - sma_200) / sma_200 * 100
            
            # Closer = higher progress
            if distance_pct < 0.5:  # Very close
                return 90
            elif distance_pct < 1.0:
                return 70
            elif distance_pct < 2.0:
                return 50
            elif distance_pct < 5.0:
                return 30
            else:
                return 10
        except:
            return 0


# ============================================
# STRATEGY: RSI Reversal (Intraday)
# ============================================
class StrategyRSIReversal(BaseStrategy):
    """
    RSI Reversal V3 - Optimized Version
    
    Intraday reversal strategy based on RSI exits from extreme zones.
    
    Entry:
    - LONG: RSI was < 30 (N-1) and now > 30 (N) - Exit from oversold
    - SHORT: RSI was > 70 (N-1) and now < 70 (N) - Exit from overbought
           + FILTER: Price must be below EMA 200 (bearish trend)
    
    Risk Management:
    - Stop Loss: 1.5% from entry
    - Take Profit: 3.0% from entry (1:2 ratio)
    
    Performance: +11.49% on BTC 15m (vs +8.36% for V1)
    Improvement: SHORT improved from -10.42% to -1.15%
    """
    
    def add_indicators(self, df):
        params = self.config.get("params", {})
        rsi_len = params.get("rsi_period", 14)
        use_short_filter = params.get("use_short_filter", True)
        
        df['RSI'] = ta.rsi(df['close'], length=rsi_len)
        
        # EMA 200 for SHORT filter
        df['EMA_200'] = ta.ema(df['close'], length=200)
        
        return df
    
    def generate_signal(self, df, extra_data=None):
        df = self.add_indicators(df)
        
        if len(df) < 210:  # Need 200 for EMA + 10 buffer
            return None
        
        params = self.config.get("params", {})
        use_short_filter = params.get("use_short_filter", True)
        sl_pct = params.get("sl_pct", 0.015)  # 1.5%
        tp_pct = params.get("tp_pct", 0.030)  # 3.0%
        
        rsi_curr = df['RSI'].iloc[-1]
        rsi_prev = df['RSI'].iloc[-2]
        close = df['close'].iloc[-1]
        ema_200 = df['EMA_200'].iloc[-1]
        
        # LONG: Exit from oversold (RSI crosses above 30)
        # No filter - keep V1 logic (works well)
        if rsi_prev < 30 and rsi_curr > 30:
            sl = close * (1 - sl_pct)
            tp = close * (1 + tp_pct)
            
            return {
                'signal': 'BUY',
                'price': close,
                'sl': sl,
                'tp': tp,
                'comment': f'RSI Reversal V3 Long - Exit from oversold (RSI: {rsi_curr:.1f})'
            }
        
        # SHORT: Exit from overbought (RSI crosses below 70)
        # V3: Add EMA 200 filter to improve SHORT performance
        short_filter_ok = not use_short_filter or close < ema_200
        
        if rsi_prev > 70 and rsi_curr < 70 and short_filter_ok:
            sl = close * (1 + sl_pct)
            tp = close * (1 - tp_pct)
            
            return {
                'signal': 'SELL',
                'price': close,
                'sl': sl,
                'tp': tp,
                'comment': f'RSI Reversal V3 Short - Exit from overbought (RSI: {rsi_curr:.1f}, Trend: Bearish)'
            }
        
        return None
    
    def calculate_progress(self, df, extra_data=None):
        """Calculate proximity to RSI reversal zones"""
        try:
            df = self.add_indicators(df)
            if len(df) < 210:
                return 0
            
            rsi = df['RSI'].iloc[-1]
            close = df['close'].iloc[-1]
            ema_200 = df['EMA_200'].iloc[-1]
            
            progress = 0
            
            # In oversold zone (approaching long signal)
            if rsi < 30:
                progress = int(100 * (30 - rsi) / 30)  # Deeper = higher progress
            
            # In overbought zone (approaching short signal)
            elif rsi > 70:
                base_progress = int(100 * (rsi - 70) / 30)
                
                # Bonus if in bearish trend (better SHORT setup)
                if close < ema_200:
                    progress = min(100, base_progress + 20)
                else:
                    progress = base_progress
            
            # Approaching zones
            elif 30 <= rsi <= 40:
                progress = int(50 * (40 - rsi) / 10)
            elif 60 <= rsi <= 70:
                base_progress = int(50 * (rsi - 60) / 10)
                
                # Bonus if approaching in bearish trend
                if close < ema_200:
                    progress = min(100, base_progress + 10)
                else:
                    progress = base_progress
            
            return min(100, max(0, progress))
        except:
            return 0


# ============================================
# STRATEGY: Bollinger Breakout
# ============================================
class StrategyBollingerBreakout(BaseStrategy):
    """
    Bollinger Breakout V2 - Optimized Version
    
    Entry:
    - LONG: Green candle closes above Upper Band + impulsive body + trend filter
    - SHORT: Red candle closes below Lower Band + impulsive body + trend filter
    
    Filters:
    - Candle body must be 1.5x larger than average (more selective)
    - EMA 200 trend filter (LONG if above, SHORT if below)
    - RSI filter (LONG if RSI > 50, SHORT if RSI < 50)
    
    Exit:
    - Fixed SL: 2% from entry
    - Fixed TP: 3% from entry (1:1.5 ratio)
    
    Performance: +298% on BTC 15m (vs -0.15% for V1)
    """
    
    def add_indicators(self, df):
        params = self.config.get("params", {})
        bb_length = params.get("bb_length", 20)
        bb_std = params.get("bb_std", 2.0)
        body_ratio_min = params.get("min_body_ratio", 1.5)
        sl_pct = params.get("sl_pct", 0.02)  # 2%
        tp_pct = params.get("tp_pct", 0.03)  # 3%
        use_trend_filter = params.get("use_trend_filter", True)
        
        # Bollinger Bands
        bbands = ta.bbands(df['close'], length=bb_length, std=bb_std)
        df['BB_UPPER'] = bbands['BBU']
        df['BB_MIDDLE'] = bbands['BBM']
        df['BB_LOWER'] = bbands['BBL']
        
        # Trend filter
        df['EMA_200'] = ta.ema(df['close'], length=200)
        
        # RSI filter
        df['RSI'] = ta.rsi(df['close'], length=14)
        
        # Candle body size
        df['BODY'] = abs(df['close'] - df['open'])
        df['AVG_BODY_10'] = df['BODY'].rolling(window=10).mean()
        
        return df
    
    def generate_signal(self, df, extra_data=None):
        df = self.add_indicators(df)
        
        if len(df) < 210:  # Need 200 for EMA + 10 for body avg
            return None
        
        params = self.config.get("params", {})
        body_ratio_min = params.get("min_body_ratio", 1.5)
        sl_pct = params.get("sl_pct", 0.02)
        tp_pct = params.get("tp_pct", 0.03)
        use_trend_filter = params.get("use_trend_filter", True)
        
        close = df['close'].iloc[-1]
        open_price = df['open'].iloc[-1]
        bb_upper = df['BB_UPPER'].iloc[-1]
        bb_lower = df['BB_LOWER'].iloc[-1]
        ema_200 = df['EMA_200'].iloc[-1]
        rsi = df['RSI'].iloc[-1]
        body = df['BODY'].iloc[-1]
        avg_body = df['AVG_BODY_10'].iloc[-1]
        
        # Check if candle is impulsive (body > 1.5x average)
        is_impulsive = body > avg_body * body_ratio_min
        
        if not is_impulsive:
            return None
        
        # Trend filters
        bullish_trend = not use_trend_filter or close > ema_200
        bearish_trend = not use_trend_filter or close < ema_200
        
        # LONG: Green candle + above BB upper + bullish trend + RSI > 50
        if (close > open_price and close > bb_upper and 
            bullish_trend and rsi > 50):
            
            sl = close * (1 - sl_pct)
            tp = close * (1 + tp_pct)
            
            return {
                'signal': 'BUY',
                'price': close,
                'sl': sl,
                'tp': tp,
                'comment': f'Bollinger V2 Long - Impulsive breakout (Body: {body/avg_body:.2f}x, RSI: {rsi:.1f})'
            }
        
        # SHORT: Red candle + below BB lower + bearish trend + RSI < 50
        if (close < open_price and close < bb_lower and 
            bearish_trend and rsi < 50):
            
            sl = close * (1 + sl_pct)
            tp = close * (1 - tp_pct)
            
            return {
                'signal': 'SELL',
                'price': close,
                'sl': sl,
                'tp': tp,
                'comment': f'Bollinger V2 Short - Impulsive breakout (Body: {body/avg_body:.2f}x, RSI: {rsi:.1f})'
            }
        
        return None
    
    def calculate_progress(self, df, extra_data=None):
        """Calculate proximity to Bollinger Band breakout"""
        try:
            df = self.add_indicators(df)
            if len(df) < 210:
                return 0
            
            params = self.config.get("params", {})
            body_ratio_min = params.get("min_body_ratio", 1.5)
            
            close = df['close'].iloc[-1]
            bb_upper = df['BB_UPPER'].iloc[-1]
            bb_lower = df['BB_LOWER'].iloc[-1]
            ema_200 = df['EMA_200'].iloc[-1]
            rsi = df['RSI'].iloc[-1]
            body = df['BODY'].iloc[-1]
            avg_body = df['AVG_BODY_10'].iloc[-1]
            
            progress = 0
            
            # Proximity to bands (30 points)
            dist_to_upper = abs(close - bb_upper) / bb_upper
            dist_to_lower = abs(close - bb_lower) / bb_lower
            
            if dist_to_upper < 0.002:
                progress += 30
            elif dist_to_upper < 0.005:
                progress += 15
            
            if dist_to_lower < 0.002:
                progress += 30
            elif dist_to_lower < 0.005:
                progress += 15
            
            # Impulsive candle (30 points)
            if body > avg_body * body_ratio_min:
                impulse_ratio = min(body / avg_body, 3.0)
                progress += int(30 * impulse_ratio / 3.0)
            
            # Trend alignment (20 points)
            if close > ema_200 and dist_to_upper < 0.01:  # Bullish + near upper
                progress += 20
            elif close < ema_200 and dist_to_lower < 0.01:  # Bearish + near lower
                progress += 20
            
            # RSI alignment (20 points)
            if rsi > 50 and dist_to_upper < 0.01:  # Bullish RSI + near upper
                progress += 20
            elif rsi < 50 and dist_to_lower < 0.01:  # Bearish RSI + near lower
                progress += 20
            
            return min(100, max(0, progress))
        except:
            return 0

# ============================================
# CHARTIST PATTERNS STRATEGIES
# ============================================

class StrategyDoubleTopBottom(BaseStrategy):
    """
    Double Top/Bottom Pattern Detection
    
    Entry:
    - LONG: Double Bottom + RSI divergence bullish
    - SHORT: Double Top + RSI divergence bearish
    
    Detection:
    - 2 peaks/troughs at similar levels (±2%)
    - Minimum 10 candles between peaks
    - Volume confirmation
    """
    
    def add_indicators(self, df):
        params = self.config.get("params", {})
        
        df['RSI'] = ta.rsi(df['close'], length=14)
        df['Volume_SMA'] = ta.sma(df['volume'], length=20)
        
        # Find local peaks and troughs
        df['High_Peak'] = df['high'].rolling(window=5, center=True).max() == df['high']
        df['Low_Trough'] = df['low'].rolling(window=5, center=True).min() == df['low']
        
        return df
    
    def generate_signal(self, df, extra_data=None):
        df = self.add_indicators(df)
        
        if len(df) < 50:
            return None
        
        current_price = df['close'].iloc[-1]
        current_rsi = df['RSI'].iloc[-1]
        
        # Get recent peaks and troughs
        recent_peaks = df[df['High_Peak'] == True].tail(3)
        recent_troughs = df[df['Low_Trough'] == True].tail(3)
        
        # DOUBLE BOTTOM (Bullish)
        if len(recent_troughs) >= 2:
            trough1 = recent_troughs.iloc[-2]
            trough2 = recent_troughs.iloc[-1]
            
            # Check if troughs are at similar level (±2%)
            price_diff = abs(trough1['low'] - trough2['low']) / trough1['low']
            
            if price_diff < 0.02:  # Within 2%
                # Check RSI divergence (bullish)
                rsi1_idx = trough1.name
                rsi2_idx = trough2.name
                
                if rsi2_idx in df.index and rsi1_idx in df.index:
                    rsi1 = df.loc[rsi1_idx, 'RSI']
                    rsi2 = df.loc[rsi2_idx, 'RSI']
                    
                    # Bullish divergence: price lower, RSI higher
                    if trough2['low'] <= trough1['low'] and rsi2 > rsi1:
                        # Neckline break
                        neckline = max(df.loc[rsi1_idx:rsi2_idx, 'high'])
                        
                        if current_price > neckline:
                            return {
                                'signal': 'BUY',
                                'price': current_price,
                                'sl': trough2['low'] * 0.99,
                                'tp': current_price + (current_price - trough2['low']) * 1.5,
                                'comment': f'Double Bottom detected - Bullish divergence (RSI: {current_rsi:.1f})'
                            }
        
        # DOUBLE TOP (Bearish)
        if len(recent_peaks) >= 2:
            peak1 = recent_peaks.iloc[-2]
            peak2 = recent_peaks.iloc[-1]
            
            # Check if peaks are at similar level (±2%)
            price_diff = abs(peak1['high'] - peak2['high']) / peak1['high']
            
            if price_diff < 0.02:  # Within 2%
                # Check RSI divergence (bearish)
                rsi1_idx = peak1.name
                rsi2_idx = peak2.name
                
                if rsi2_idx in df.index and rsi1_idx in df.index:
                    rsi1 = df.loc[rsi1_idx, 'RSI']
                    rsi2 = df.loc[rsi2_idx, 'RSI']
                    
                    # Bearish divergence: price higher, RSI lower
                    if peak2['high'] >= peak1['high'] and rsi2 < rsi1:
                        # Neckline break
                        neckline = min(df.loc[rsi1_idx:rsi2_idx, 'low'])
                        
                        if current_price < neckline:
                            return {
                                'signal': 'SELL',
                                'price': current_price,
                                'sl': peak2['high'] * 1.01,
                                'tp': current_price - (peak2['high'] - current_price) * 1.5,
                                'comment': f'Double Top detected - Bearish divergence (RSI: {current_rsi:.1f})'
                            }
        
        return None
    
    def calculate_progress(self, df, extra_data=None):
        """Calculate proximity to Double Top/Bottom pattern"""
        try:
            df = self.add_indicators(df)
            if len(df) < 50:
                return 0
            
            recent_peaks = df[df['High_Peak'] == True].tail(2)
            recent_troughs = df[df['Low_Trough'] == True].tail(2)
            
            progress = 0
            
            # Check for forming double bottom
            if len(recent_troughs) >= 2:
                trough1 = recent_troughs.iloc[-2]
                trough2 = recent_troughs.iloc[-1]
                price_diff = abs(trough1['low'] - trough2['low']) / trough1['low']
                
                if price_diff < 0.05:  # Within 5%
                    progress = max(progress, int(100 * (1 - price_diff / 0.05)))
            
            # Check for forming double top
            if len(recent_peaks) >= 2:
                peak1 = recent_peaks.iloc[-2]
                peak2 = recent_peaks.iloc[-1]
                price_diff = abs(peak1['high'] - peak2['high']) / peak1['high']
                
                if price_diff < 0.05:  # Within 5%
                    progress = max(progress, int(100 * (1 - price_diff / 0.05)))
            
            return min(100, progress)
        except:
            return 0


class StrategyTriangleBreakout(BaseStrategy):
    """
    Triangle Pattern Breakout
    
    Entry:
    - LONG: Ascending triangle breakout (resistance break)
    - SHORT: Descending triangle breakout (support break)
    
    Detection:
    - Converging trendlines
    - Decreasing volatility (ATR)
    - Volume spike on breakout
    """
    
    def add_indicators(self, df):
        df['ATR'] = ta.atr(df['high'], df['low'], df['close'], length=14)
        df['Volume_SMA'] = ta.sma(df['volume'], length=20)
        df['EMA_20'] = ta.ema(df['close'], length=20)
        
        # Calculate highs and lows for trendlines
        df['Rolling_High'] = df['high'].rolling(window=20).max()
        df['Rolling_Low'] = df['low'].rolling(window=20).min()
        
        return df
    
    def generate_signal(self, df, extra_data=None):
        df = self.add_indicators(df)
        
        if len(df) < 40:
            return None
        
        current_price = df['close'].iloc[-1]
        current_volume = df['volume'].iloc[-1]
        avg_volume = df['Volume_SMA'].iloc[-1]
        
        # Get recent data for pattern detection
        recent_df = df.tail(30)
        
        # Calculate resistance and support levels
        resistance = recent_df['high'].max()
        support = recent_df['low'].min()
        
        # Check for decreasing volatility (triangle formation)
        atr_current = df['ATR'].iloc[-1]
        atr_20_ago = df['ATR'].iloc[-20] if len(df) >= 20 else atr_current
        
        volatility_decreasing = atr_current < atr_20_ago * 0.8
        
        if not volatility_decreasing:
            return None
        
        # ASCENDING TRIANGLE (Bullish)
        # Flat resistance, rising support
        recent_highs = recent_df['high'].tail(10)
        recent_lows = recent_df['low'].tail(10)
        
        # Check if highs are relatively flat (resistance)
        high_std = recent_highs.std() / recent_highs.mean()
        
        # Check if lows are rising (support)
        lows_slope = (recent_lows.iloc[-1] - recent_lows.iloc[0]) / len(recent_lows)
        
        if high_std < 0.02 and lows_slope > 0:  # Ascending triangle
            # Breakout confirmation
            if current_price > resistance and current_volume > avg_volume * 1.5:
                triangle_height = resistance - support
                
                return {
                    'signal': 'BUY',
                    'price': current_price,
                    'sl': support * 0.99,
                    'tp': current_price + triangle_height * 1.0,
                    'comment': f'Ascending Triangle Breakout - Volume spike ({current_volume/avg_volume:.1f}x)'
                }
        
        # DESCENDING TRIANGLE (Bearish)
        # Flat support, falling resistance
        low_std = recent_lows.std() / recent_lows.mean()
        highs_slope = (recent_highs.iloc[-1] - recent_highs.iloc[0]) / len(recent_highs)
        
        if low_std < 0.02 and highs_slope < 0:  # Descending triangle
            # Breakout confirmation
            if current_price < support and current_volume > avg_volume * 1.5:
                triangle_height = resistance - support
                
                return {
                    'signal': 'SELL',
                    'price': current_price,
                    'sl': resistance * 1.01,
                    'tp': current_price - triangle_height * 1.0,
                    'comment': f'Descending Triangle Breakout - Volume spike ({current_volume/avg_volume:.1f}x)'
                }
        
        return None
    
    def calculate_progress(self, df, extra_data=None):
        """Calculate proximity to triangle breakout"""
        try:
            df = self.add_indicators(df)
            if len(df) < 40:
                return 0
            
            recent_df = df.tail(30)
            resistance = recent_df['high'].max()
            support = recent_df['low'].min()
            current_price = df['close'].iloc[-1]
            
            # Calculate distance to breakout levels
            dist_to_resistance = abs(current_price - resistance) / resistance
            dist_to_support = abs(current_price - support) / support
            
            min_dist = min(dist_to_resistance, dist_to_support)
            
            # Check volatility compression
            atr_current = df['ATR'].iloc[-1]
            atr_20_ago = df['ATR'].iloc[-20] if len(df) >= 20 else atr_current
            
            volatility_compression = 1 - (atr_current / atr_20_ago) if atr_20_ago > 0 else 0
            
            # Combine factors
            progress = 0
            
            if min_dist < 0.01:  # Very close to breakout
                progress += 50
            elif min_dist < 0.02:
                progress += 30
            
            if volatility_compression > 0.2:  # Significant compression
                progress += 50
            
            return min(100, progress)
        except:
            return 0


class StrategyHeadShoulders(BaseStrategy):
    """
    Head and Shoulders Pattern
    
    Entry:
    - LONG: Inverse H&S - neckline break upward
    - SHORT: H&S - neckline break downward
    
    Detection:
    - 3 peaks: left shoulder, head (highest), right shoulder
    - Neckline drawn through troughs
    - Volume decreasing on right shoulder
    """
    
    def add_indicators(self, df):
        df['RSI'] = ta.rsi(df['close'], length=14)
        df['Volume_SMA'] = ta.sma(df['volume'], length=20)
        
        # Detect peaks and troughs
        df['High_Peak'] = df['high'].rolling(window=7, center=True).max() == df['high']
        df['Low_Trough'] = df['low'].rolling(window=7, center=True).min() == df['low']
        
        return df
    
    def generate_signal(self, df, extra_data=None):
        df = self.add_indicators(df)
        
        if len(df) < 60:
            return None
        
        current_price = df['close'].iloc[-1]
        
        # Get recent peaks for H&S pattern
        recent_peaks = df[df['High_Peak'] == True].tail(5)
        recent_troughs = df[df['Low_Trough'] == True].tail(4)
        
        # HEAD AND SHOULDERS (Bearish)
        if len(recent_peaks) >= 3 and len(recent_troughs) >= 2:
            # Get the 3 most recent peaks
            left_shoulder = recent_peaks.iloc[-3]
            head = recent_peaks.iloc[-2]
            right_shoulder = recent_peaks.iloc[-1]
            
            # Validate pattern: head is highest
            if head['high'] > left_shoulder['high'] and head['high'] > right_shoulder['high']:
                # Shoulders should be roughly equal (±5%)
                shoulder_diff = abs(left_shoulder['high'] - right_shoulder['high']) / left_shoulder['high']
                
                if shoulder_diff < 0.05:
                    # Calculate neckline (support through troughs)
                    trough1 = recent_troughs.iloc[-2]
                    trough2 = recent_troughs.iloc[-1]
                    neckline = (trough1['low'] + trough2['low']) / 2
                    
                    # Breakout confirmation
                    if current_price < neckline:
                        pattern_height = head['high'] - neckline
                        
                        return {
                            'signal': 'SELL',
                            'price': current_price,
                            'sl': neckline * 1.02,
                            'tp': current_price - pattern_height * 1.0,
                            'comment': f'Head & Shoulders pattern - Neckline break'
                        }
        
        # INVERSE HEAD AND SHOULDERS (Bullish)
        recent_troughs_inv = df[df['Low_Trough'] == True].tail(5)
        recent_peaks_inv = df[df['High_Peak'] == True].tail(4)
        
        if len(recent_troughs_inv) >= 3 and len(recent_peaks_inv) >= 2:
            # Get the 3 most recent troughs
            left_shoulder = recent_troughs_inv.iloc[-3]
            head = recent_troughs_inv.iloc[-2]
            right_shoulder = recent_troughs_inv.iloc[-1]
            
            # Validate pattern: head is lowest
            if head['low'] < left_shoulder['low'] and head['low'] < right_shoulder['low']:
                # Shoulders should be roughly equal (±5%)
                shoulder_diff = abs(left_shoulder['low'] - right_shoulder['low']) / left_shoulder['low']
                
                if shoulder_diff < 0.05:
                    # Calculate neckline (resistance through peaks)
                    peak1 = recent_peaks_inv.iloc[-2]
                    peak2 = recent_peaks_inv.iloc[-1]
                    neckline = (peak1['high'] + peak2['high']) / 2
                    
                    # Breakout confirmation
                    if current_price > neckline:
                        pattern_height = neckline - head['low']
                        
                        return {
                            'signal': 'BUY',
                            'price': current_price,
                            'sl': neckline * 0.98,
                            'tp': current_price + pattern_height * 1.0,
                            'comment': f'Inverse Head & Shoulders - Neckline break'
                        }
        
        return None
    
    def calculate_progress(self, df, extra_data=None):
        """Calculate proximity to H&S pattern completion"""
        try:
            df = self.add_indicators(df)
            if len(df) < 60:
                return 0
            
            recent_peaks = df[df['High_Peak'] == True].tail(3)
            recent_troughs = df[df['Low_Trough'] == True].tail(3)
            
            # Check if we have 3 peaks (potential H&S forming)
            if len(recent_peaks) >= 3:
                left_shoulder = recent_peaks.iloc[-3]
                head = recent_peaks.iloc[-2]
                right_shoulder = recent_peaks.iloc[-1]
                
                # Check if head is highest
                if head['high'] > left_shoulder['high'] and head['high'] > right_shoulder['high']:
                    shoulder_diff = abs(left_shoulder['high'] - right_shoulder['high']) / left_shoulder['high']
                    
                    if shoulder_diff < 0.1:  # Shoulders within 10%
                        return int(100 * (1 - shoulder_diff / 0.1))
            
            # Check for inverse H&S
            if len(recent_troughs) >= 3:
                left_shoulder = recent_troughs.iloc[-3]
                head = recent_troughs.iloc[-2]
                right_shoulder = recent_troughs.iloc[-1]
                
                # Check if head is lowest
                if head['low'] < left_shoulder['low'] and head['low'] < right_shoulder['low']:
                    shoulder_diff = abs(left_shoulder['low'] - right_shoulder['low']) / left_shoulder['low']
                    
                    if shoulder_diff < 0.1:  # Shoulders within 10%
                        return int(100 * (1 - shoulder_diff / 0.1))
            
            return 0
        except:
            return 0

class StrategyGoldenCross(BaseStrategy):
    """
    Golden Cross V2 (Intraday Optimized)
    
    Logic:
    - Faster EMAs: EMA 20 crossing EMA 50 (instead of SMA 50/200)
    - Trend Filter: Price must be above/below EMA 200
    - RSI Filter: RSI > 50 for LONG, < 50 for SHORT
    
    Performance: +7.54% on BTC 15m (vs -15% for V1)
    """
    
    def add_indicators(self, df):
        params = self.config.get("params", {})
        fast_len = params.get("fast_length", 20)
        slow_len = params.get("slow_length", 50)
        trend_len = params.get("trend_length", 200)
        rsi_len = params.get("rsi_length", 14)
        
        df['EMA_FAST'] = ta.ema(df['close'], length=fast_len)
        df['EMA_SLOW'] = ta.ema(df['close'], length=slow_len)
        df['EMA_TREND'] = ta.ema(df['close'], length=trend_len)
        df['RSI'] = ta.rsi(df['close'], length=rsi_len)
        
        return df
    
    def generate_signal(self, df, extra_data=None):
        df = self.add_indicators(df)
        
        if len(df) < 210:
            return None
            
        params = self.config.get("params", {})
        sl_pct = params.get("sl_pct", 0.015)
        tp_pct = params.get("tp_pct", 0.030)
        
        # Candles
        close = df['close'].iloc[-1]
        
        # Indicators current
        ema_fast = df['EMA_FAST'].iloc[-1]
        ema_slow = df['EMA_SLOW'].iloc[-1]
        ema_trend = df['EMA_TREND'].iloc[-1]
        rsi = df['RSI'].iloc[-1]
        
        # Indicators previous (for crossover)
        ema_fast_prev = df['EMA_FAST'].iloc[-2]
        ema_slow_prev = df['EMA_SLOW'].iloc[-2]
        
        # Logic
        golden_cross = ema_fast_prev < ema_slow_prev and ema_fast > ema_slow
        death_cross = ema_fast_prev > ema_slow_prev and ema_fast < ema_slow
        
        bullish_trend = close > ema_trend
        bearish_trend = close < ema_trend
        
        # LONG: Golden Cross + Bullish Trend + RSI > 50
        if golden_cross and bullish_trend and rsi > 50:
            sl = close * (1 - sl_pct)
            tp = close * (1 + tp_pct)
            return {
                'signal': 'BUY',
                'price': close,
                'sl': sl,
                'tp': tp,
                'comment': f'Golden Cross V2 Long (EMA 20/50 + Trend)'
            }
            
        # SHORT: Death Cross + Bearish Trend + RSI < 50
        if death_cross and bearish_trend and rsi < 50:
            sl = close * (1 + sl_pct)
            tp = close * (1 - tp_pct)
            return {
                'signal': 'SELL',
                'price': close,
                'sl': sl,
                'tp': tp,
                'comment': f'Death Cross V2 Short (EMA 20/50 + Trend)'
            }
            
        return None

    def calculate_progress(self, df, extra_data=None):
        # Calculate how close EMAs are to crossing
        try:
            df = self.add_indicators(df)
            ema_fast = df['EMA_FAST'].iloc[-1]
            ema_slow = df['EMA_SLOW'].iloc[-1]
            diff_pct = abs(ema_fast - ema_slow) / ema_slow
            
            # Closer = Higher progress (Max 1.0% diff considered "close")
            progress = max(0, min(100, int((0.01 - diff_pct) * 10000)))
            return progress
        except:
            return 0
