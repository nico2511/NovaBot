from app.services.indicators import ta
import pandas as pd
from strategies.base import BaseStrategy

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
