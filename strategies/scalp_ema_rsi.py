from app.services.indicators import ta
import pandas as pd
from strategies.base import BaseStrategy

class ScalpEmaRsi(BaseStrategy):
    AI_PERSONA = """
    CODENAME: "TACTICAL SCALPER - PRECISION"
    
    ROLE:
    You are a SPECIAL FORCES OPERATOR. You do not spray and pray. You wait for the perfect alignment.
    
    PRIME DIRECTIVE:
    "We do not guess. We confirm." Speed is nothing without direction.
    
    RULES OF ENGAGEMENT:
    1. CONFIRM THE FLOW: Look at the 200 EMA. Is it angled? If it's flat, we are standing down. We do not fight in the mud (chop).
    2. MOMENTUM INTEGRITY: The Fast EMA must cross cleanly. If it's "tangling" or "kissing", it's noise.
    3. RSI "SWEET SPOT": We want RSI moving INTO power (50->60), not exhaustedly leaving it (>75).
    4. VOLUME CONFIRMATION: A crossover without volume is a trap. We need to see fuel entering the tank.
    
    RESPONSE STYLE:
    Disciplined, factual.
    "Angle confirmed - Engaging.", "Flat trend detected - Standing down."
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
        if df.empty or len(df) < 200:
            return self._reject("Not enough candles for EMA200 context")

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
        
        if trend_col not in df.columns or atr_col not in df.columns:
            return self._reject("Required indicators missing (EMA200/ATR)")
        
        # GUARD CLAUSE: Trend Following only in Trend (ADX > threshold)
        adx_threshold = params.get("adx_threshold", 22)
        if 'ADX_14' in df.columns:
            current_adx = df['ADX_14'].iloc[-2]
            if current_adx < adx_threshold: 
                return self._reject(f"ADX below threshold ({current_adx:.1f} < {adx_threshold})")

        # Values (Use iloc[-2] for signal stability / avoiding repainting)
        current_fast = df[fast_col].iloc[-2]
        prev_fast = df[fast_col].iloc[-3]
        current_slow = df[slow_col].iloc[-2]
        prev_slow = df[slow_col].iloc[-3]
        
        current_trend = df[trend_col].iloc[-2]
        prev_trend = df[trend_col].iloc[-7] # 5 candles back for slope
        
        # Calculate Slope (Simple percent change)
        trend_slope = (current_trend - prev_trend) / prev_trend * 100
        min_slope = params.get("min_trend_slope", 0.005) # CHANGED 2026-02: Relaxed 0.01 -> 0.005
        
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
            if close > current_trend and trend_slope > min_slope:  # Above 200 EMA AND Slope Positive
                # Asymmetric RSI Bull: 50 - 75
                if 50 < current_rsi < params.get("rsi_overbought", 75):  
                    # Volume Filter: Use config multiplier
                    if 'volume' in df.columns:
                        current_vol = df['volume'].iloc[-2]
                        avg_vol = df['volume'].iloc[-22:-2].mean()
                        if current_vol < avg_vol * params.get("volume_multiplier", 1.15):
                            return self._reject(f"BUY rejeté — volume insuffisant ({current_vol/avg_vol:.2f}x < {params.get('volume_multiplier', 1.15)}x)")
                    
                    # Check RR
                    sl_atr_mult = params.get("sl_atr_mult", 1.2)
                    sl = close - (sl_atr_mult * atr)
                    min_rr = params.get("min_rr", 1.4)
                    tp = close + (min_rr * (close - sl))
                    
                    risk = abs(close - sl)
                    reward = abs(tp - close)
                    
                    if risk > 0 and (reward / risk) >= min_rr:
                        return {
                            "signal": "BUY",
                            "sl": sl,
                            "tp": tp,
                            "comment": f"EMA Bullish Cross + Vol {params.get('volume_multiplier', 1.15)}x"
                        }
                
        # SELL: Bearish Crossover (EMA Fast crosses BELOW EMA Slow)
        is_bearish_cross = (prev_fast >= prev_slow) and (current_fast < current_slow)
        
        if is_bearish_cross:
            if close < current_trend and trend_slope < -min_slope:  # Below 200 EMA AND Slope Negative
                # Asymmetric RSI Bear: 25 - 50
                if params.get("rsi_oversold", 25) < current_rsi < 50:
                    # Volume Filter: Use config multiplier
                    if 'volume' in df.columns:
                        current_vol = df['volume'].iloc[-2]
                        avg_vol = df['volume'].iloc[-22:-2].mean()
                        if current_vol < avg_vol * params.get("volume_multiplier", 1.15):
                            return self._reject(f"SELL rejeté — volume insuffisant ({current_vol/avg_vol:.2f}x < {params.get('volume_multiplier', 1.15)}x)")
                    
                    # Check RR
                    sl_atr_mult = params.get("sl_atr_mult", 1.2)
                    sl = close + (sl_atr_mult * atr)
                    min_rr = params.get("min_rr", 1.4)
                    tp = close - (min_rr * (sl - close))
                    
                    risk = abs(sl - close)
                    reward = abs(close - tp)
                    
                    if risk > 0 and (reward / risk) >= min_rr:
                        return {
                            "signal": "SELL",
                            "sl": sl,
                            "tp": tp,
                            "comment": f"EMA Bearish Cross + Vol {params.get('volume_multiplier', 1.15)}x"
                        }
        
        return self._reject("No valid EMA crossover setup after filters")
