from app.services.indicators import ta
import pandas as pd
from strategies.base import BaseStrategy

class ScalpEmaRsi(BaseStrategy):
    AI_PERSONA = """
    CODENAME: "VELOCITY VANGUARD - SCALPER"
    
    ROLE:
    You are a HIGH-FREQUENCY SCALP COMMANDER. You live for speed and momentum.
    
    PRIME DIRECTIVE:
    Capture short-term kinetic energy. We do not marry positions; we date them for 15 minutes.
    
    RULES OF ENGAGEMENT:
    1. VOLUME IS OXYGEN: A crossover without volume is a trap. If Volume is weak, KILL THE TRADE.
    2. TREND IS YOUR FRIEND: Never trade against the 200 EMA unless it's a massive reversal with 3x volume.
    3. MOMENTUM ZONE: RSI must be moving IN FAVOR of the trade (50-70 for Longs). If RSI is flat, we stay flat.
    4. SNIPER ENTRIES: We need immediate reaction. If the signal candle is weak/doji, hesitate.
    
    RESPONSE STYLE:
    Sharp, energetic, military-style.
    "Target Acquired", "Volume confirmed", "Fakeout detected - STAND DOWN".
    """

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
        
        # GUARD CLAUSE: Trend Following only in Trend (ADX > 25)
        if 'ADX_14' in df.columns:
            current_adx = df['ADX_14'].iloc[-2]
            if current_adx < 25:
                return None  # No trend, skip trend following strategy

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
        
        # ============================================
        # EVENT-BASED LOGIC (Crossover Detection)
        # ============================================
        # Signal triggers ONLY on the exact crossover event, not continuous alignment.
        # This prevents signal spam when EMAs remain aligned.
        
        # BUY: Bullish Crossover (EMA Fast crosses ABOVE EMA Slow)
        # Condition: prev_fast <= prev_slow AND current_fast > current_slow
        is_bullish_cross = (prev_fast <= prev_slow) and (current_fast > current_slow)
        
        if is_bullish_cross:
            # Additional Filters (only checked on crossover event)
            if close > current_trend:  # Above 200 EMA (trend filter)
                if 50 < current_rsi < 70:  # RSI in momentum zone
                    # Volume Filter: Crossover without volume = fakeout (crypto 2026)
                    if 'volume' in df.columns:
                        current_vol = df['volume'].iloc[-2]
                        avg_vol = df['volume'].iloc[-22:-2].mean()
                        if current_vol < avg_vol * 1.3:
                            return None  # Insufficient volume
                    
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
                            "comment": "EMA Bullish Crossover + Trend + RSI + Vol"
                        }
                
        # SELL: Bearish Crossover (EMA Fast crosses BELOW EMA Slow)
        # Condition: prev_fast >= prev_slow AND current_fast < current_slow
        is_bearish_cross = (prev_fast >= prev_slow) and (current_fast < current_slow)
        
        if is_bearish_cross:
            if close < current_trend:  # Below 200 EMA (trend filter)
                if 30 < current_rsi < 50:  # RSI in momentum zone
                    # Volume Filter: Crossover without volume = fakeout (crypto 2026)
                    if 'volume' in df.columns:
                        current_vol = df['volume'].iloc[-2]
                        avg_vol = df['volume'].iloc[-22:-2].mean()
                        if current_vol < avg_vol * 1.3:
                            return None  # Insufficient volume
                    
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
                            "comment": "EMA Bearish Crossover + Trend + RSI + Vol"
                        }
        
        # ============================================
        # OPTIONAL: PULLBACK RE-ENTRY LOGIC (Future Enhancement)
        # ============================================
        # To add pullback entries WITHOUT spam, use a state machine:
        # 
        # 1. Detect Initial Crossover (as above) → Set internal flag: self.pullback_armed = True
        # 2. Wait for Pullback: Price touches EMA_fast (e.g., close <= ema_fast * 1.005)
        # 3. Detect Bounce: Price closes above EMA_fast again
        # 4. Trigger Re-Entry Signal → Reset flag: self.pullback_armed = False
        # 
        # Example Code (commented for future use):
        # 
        # if hasattr(self, 'pullback_armed') and self.pullback_armed:
        #     # Check if price touched EMA_fast
        #     if close <= current_fast * 1.005:  # Within 0.5% of EMA
        #         self.pullback_touched = True
        #     
        #     # Check if price bounced back above EMA
        #     if self.pullback_touched and close > current_fast:
        #         # Trigger pullback entry
        #         self.pullback_armed = False
        #         self.pullback_touched = False
        #         return {
        #             "signal": "BUY",
        #             "sl": close - (1.5 * atr),
        #             "tp": close + (2.5 * atr),
        #             "comment": "Pullback Re-Entry"
        #         }
        # 
        # Note: Requires adding __init__ method to initialize flags:
        # def __init__(self, config=None):
        #     super().__init__(config)
        #     self.pullback_armed = False
        #     self.pullback_touched = False
        
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
