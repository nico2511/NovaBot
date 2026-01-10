from app.services.indicators import ta
import pandas as pd
from strategies.base import BaseStrategy

class ScalpEmaRsi(BaseStrategy):
    AI_PERSONA = """
    CODENAME: "VELOCITY VANGUARD - SCALPER"
    
    ROLE:
    You are an ELITE SCALP COMMANDER. Your domain is the short-term timeframe (1m-15m).
    You prioritize SPEED and KINETIC ENERGY over perfect safety metrics.
    
    PRIME DIRECTIVE:
    Capture the burst. We do not marry positions; we date them for 15 minutes.
    
    RULES OF ENGAGEMENT (OVERRIDES):
    1. RSI IS FUEL, NOT FEAR: In a scalping context, RSI > 70 is NOT a signal to sell. It is "TURBO MODE". If the EMAs just crossed and RSI is high, it means the momentum is explosive. GO WITH IT.
    2. VOLUME REALITY CHECK: While we love volume, do not reject a clean technical breakout just because volume is only "average". If the candle body is large (Marubozu), price action rules over volume.
    3. NO HESITATION: If the Fast EMA crosses the Slow EMA, the signal is NOW. Do not ask for a pullback. Do not ask for a retest. Scalping requires immediate execution.
    
    RESPONSE STYLE:
    Sharp, military, decisive.
    "Target Acquired", "Momentum Confirmed", "Kill Trade - Low Vol".
    No paragraphs. Just decision and tactical reason.
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
        # STRICTER: 25 -> 28 if desired, sticking to 25 for now but strictly enforced
        if 'ADX_14' in df.columns:
            current_adx = df['ADX_14'].iloc[-2]
            if current_adx < 25:
                return None  # No trend, skip trend following strategy

        # Values (Use iloc[-2] for signal stability / avoiding repainting)
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
        
        # BUY: Bullish Crossover (EMA Fast crosses ABOVE EMA Slow)
        is_bullish_cross = (prev_fast <= prev_slow) and (current_fast > current_slow)
        
        if is_bullish_cross:
            # Additional Filters (Optimized 2026)
            if close > current_trend:  # Above 200 EMA (trend filter)
                # Asymmetric RSI Bull: 52 - 68
                if 52 < current_rsi < 68:  
                    # Volume Filter: Strict 1.5x
                    if 'volume' in df.columns:
                        current_vol = df['volume'].iloc[-2]
                        avg_vol = df['volume'].iloc[-22:-2].mean()
                        if current_vol < avg_vol * 1.5:
                            return None  # Insufficient volume
                    
                    # Check RR
                    # Tight Scalp: SL 1.2 ATR, TP 2.0 ATR (Ratio ~1.66)
                    sl = close - (1.2 * atr)
                    tp = close + (2.0 * atr)
                    
                    risk = abs(close - sl)
                    reward = abs(tp - close)
                    
                    if risk > 0 and (reward / risk) >= params.get("min_rr", 1.5):
                        return {
                            "signal": "BUY",
                            "sl": sl,
                            "tp": tp,
                            "comment": "EMA Bullish Cross (Strict V2) + Vol 1.5x"
                        }
                
        # SELL: Bearish Crossover (EMA Fast crosses BELOW EMA Slow)
        is_bearish_cross = (prev_fast >= prev_slow) and (current_fast < current_slow)
        
        if is_bearish_cross:
            if close < current_trend:  # Below 200 EMA (trend filter)
                # Asymmetric RSI Bear: 32 - 48
                if 32 < current_rsi < 48:
                    # Volume Filter: Strict 1.5x
                    if 'volume' in df.columns:
                        current_vol = df['volume'].iloc[-2]
                        avg_vol = df['volume'].iloc[-22:-2].mean()
                        if current_vol < avg_vol * 1.5:
                            return None  # Insufficient volume
                    
                    # Check RR
                    sl = close + (1.2 * atr)
                    tp = close - (2.0 * atr)
                    
                    risk = abs(sl - close)
                    reward = abs(close - tp)
                    
                    if risk > 0 and (reward / risk) >= params.get("min_rr", 1.5):
                        return {
                            "signal": "SELL",
                            "sl": sl,
                            "tp": tp,
                            "comment": "EMA Bearish Cross (Strict V2) + Vol 1.5x"
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
        """Detailed conditions for UI - Diagnostic Card"""
        if df.empty or len(df) < 200: return []
        
        try:
            self.add_indicators(df)
            params = self.config.get("params", {})
            ema_fast_len = params.get("ema_fast", 9)
            ema_slow_len = params.get("ema_slow", 21)
            rsi_len = params.get("rsi_period", 14)
            
            # Get values (Use ILOC -1 for UI display - current state)
            fast = df[f"EMA_{ema_fast_len}"].iloc[-1]
            slow = df[f"EMA_{ema_slow_len}"].iloc[-1]
            close = df['close'].iloc[-1]
            trend = df['EMA_200'].iloc[-1]
            rsi = df[f"RSI_{rsi_len}"].iloc[-1]
            
            conditions = []
            
            # 1. EMA State
            is_bull_aligned = fast > slow
            is_bear_aligned = fast < slow
            ema_diff = abs(fast - slow)
            
            state_val = "Bullish" if is_bull_aligned else "Bearish"
            
            conditions.append({
                "name": f"1. EMA Alignment ({state_val})",
                "status": True, 
                "value": f"Diff: {ema_diff:.2f}"
            })
            
            # 2. Trend Filter
            is_trend_bull = close > trend
            is_trend_bear = close < trend
            
            # Strategy requires trend match
            trend_ok = (is_bull_aligned and is_trend_bull) or (is_bear_aligned and is_trend_bear)
            
            conditions.append({
                "name": f"2. Trend Filter (EMA 200)",
                "status": trend_ok,
                "value": "Above" if is_trend_bull else "Below"
            })
            
            # 3. RSI Filter
            rsi_ok = (50 < rsi < 70) or (30 < rsi < 50)
            
            if is_bull_aligned:
                target_range = "50-70"
            else:
                target_range = "30-50"
                
            conditions.append({
                "name": f"3. RSI Filter ({target_range})",
                "status": rsi_ok, 
                "value": f"{rsi:.1f}"
            })
            
            return conditions
        except Exception as e:
            return [{"name": "Error", "status": False, "value": str(e)}]

    
    def get_threshold_comparisons(self, df, extra_data=None):
        """Get detailed threshold comparisons for Parameters section"""
        if df is None or df.empty:
            return {}
        try:
            self.add_indicators(df)
            params = self.config.get("params", {})
            ema_fast_len = params.get("ema_fast", 9)
            ema_slow_len = params.get("ema_slow", 21)
            rsi_len = params.get("rsi_period", 14)
            
            fast = df[f"EMA_{ema_fast_len}"].iloc[-1]
            slow = df[f"EMA_{ema_slow_len}"].iloc[-1]
            close = df['close'].iloc[-1]
            trend = df['EMA_200'].iloc[-1]
            rsi = df[f"RSI_{rsi_len}"].iloc[-1]
            
            is_bull_aligned = fast > slow
            is_trend_bull = close > trend
            ema_diff = abs(fast - slow)
            
            state_val = "Bullish" if is_bull_aligned else "Bearish"
            target_range = "50-70" if is_bull_aligned else "30-50"
            
            return {
                "EMA Alignment": f"{state_val} (Diff: {ema_diff:.2f})",
                "Trend (EMA 200)": f"Price {'Above' if is_trend_bull else 'Below'} Trend",
                "RSI Momentum": f"{rsi:.1f} (Req: {target_range})"
            }
        except Exception as e:
            return {"Error": str(e)}
