from app.services.indicators import ta
import pandas as pd
from strategies.base import BaseStrategy

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

        # Values (Use iloc[-2] for signal stability / avoiding repainting)
        # However, checking cross often needs current vs prev.
        # To be strict, we check if cross happened at Close of Prev.
        
        current_fast = df[fast_col].iloc[-2]
        prev_fast = df[fast_col].iloc[-3]
        current_slow = df[slow_col].iloc[-2]
        prev_slow = df[slow_col].iloc[-3]
        
        current_trend = df[trend_col].iloc[-2]
        current_rsi = df[rsi_col].iloc[-2]
        close = df['close'].iloc[-2] # Closed price of previous candle
        atr = df[atr_col].iloc[-2]
        
        # BUY: Bullish setup (EMA alignment + Trend + RSI)
        # Trigger on: 1) Active crossover OR 2) Already aligned with all conditions met
        is_bullish_cross = prev_fast <= prev_slow and current_fast > current_slow
        is_bullish_aligned = current_fast > current_slow  # EMAs already aligned
        
        if is_bullish_cross or is_bullish_aligned:
            if close > current_trend:  # Above 200 EMA
                if 50 < current_rsi < 70:  # RSI in momentum zone
                # Check RR
                sl = close - (1.5 * atr)
                tp = close + (2.5 * atr)
                
                risk = abs(close - sl)
                reward = abs(tp - close)
                
                if risk > 0 and (reward / risk) >= params.get("min_rr", 1.3):
                    return {
                        "signal": "BUY",
                        "sl": sl,
                        "tp": tp,
                        "comment": "EMA Bullish + Trend + RSI" if is_bullish_aligned else "EMA Cross + Trend + RSI"
                    }
                
        # SELL: Bearish setup (EMA alignment + Trend + RSI)
        is_bearish_cross = prev_fast >= prev_slow and current_fast < current_slow
        is_bearish_aligned = current_fast < current_slow
        
        if is_bearish_cross or is_bearish_aligned:
            if close < current_trend:  # Below 200 EMA
                if 30 < current_rsi < 50:  # RSI in momentum zone
                # Check RR
                sl = close + (1.5 * atr)
                tp = close - (2.5 * atr)
                
                risk = abs(sl - close)
                reward = abs(close - tp)
                
                if risk > 0 and (reward / risk) >= params.get("min_rr", 1.3):
                    return {
                        "signal": "SELL",
                        "sl": sl,
                        "tp": tp,
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

    def check_conditions(self, df, extra_data=None):
        """Detailed conditions for UI"""
        if df.empty or len(df) < 200: return []
        
        try:
            self.add_indicators(df)
            params = self.config.get("params", {})
            ema_fast_len = params.get("ema_fast", 9)
            ema_slow_len = params.get("ema_slow", 21)
            rsi_len = params.get("rsi_period", 14)
            
            # Get values
            fast = df[f"EMA_{ema_fast_len}"].iloc[-1]
            slow = df[f"EMA_{ema_slow_len}"].iloc[-1]
            close = df['close'].iloc[-1]
            trend = df['EMA_200'].iloc[-1]
            rsi = df[f"RSI_{rsi_len}"].iloc[-1]
            
            conditions = []
            
            # 1. EMA State
            is_bull_aligned = fast > slow
            is_bear_aligned = fast < slow
            ema_state = "Bullish" if is_bull_aligned else "Bearish" if is_bear_aligned else "Neutral"
            conditions.append({
                "name": f"EMA {ema_fast_len}/{ema_slow_len} Alignment",
                "status": True, # Always valid state
                "value": ema_state
            })
            
            # 2. Trend Filter
            is_trend_bull = close > trend
            is_trend_bear = close < trend
            
            # Strategy requires trend match
            trend_ok = (is_bull_aligned and is_trend_bull) or (is_bear_aligned and is_trend_bear)
            
            conditions.append({
                "name": f"Trend Filter (EMA 200)",
                "status": trend_ok,
                "value": f"Price {'Above' if is_trend_bull else 'Below'} Trend"
            })
            
            # 3. RSI Filter
            rsi_ok = (50 < rsi < 70) or (30 < rsi < 50)
            conditions.append({
                "name": f"RSI Momentum Zone",
                "status": rsi_ok, 
                "value": f"{rsi:.1f}"
            })
            
            return conditions
        except Exception as e:
            return [{"name": "Error", "status": False, "value": str(e)}]
