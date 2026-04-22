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

    def calculate_progress(self, df, extra_data=None):
        """
        Returns detailed progress stages for monitoring.
        Stages:
        1. Context (EMA Trend)
        2. Filter (RSI & Volume)
        3. Trigger (Crossover Event)
        """
        if df.empty or len(df) < 200:
            return {
                "strategy": "Scalp EMA RSI",
                "score": 0,
                "stages": [{"name": "Data Check", "status": "FAIL", "details": "Not enough data"}]
            }
        
        try:
            # Re-calc indicators just for monitoring snapshot
            params = self.config.get("params", {})
            ema_fast_len = params.get("ema_fast", 9)
            ema_slow_len = params.get("ema_slow", 21)
            rsi_len = params.get("rsi_period", 14)

            # Recalculate basic series needed for last candle
            # (In production, we might want to optimize this to not re-calc full series)
            ema_fast_s = ta.ema(df['close'], length=ema_fast_len)
            ema_slow_s = ta.ema(df['close'], length=ema_slow_len)
            ema_200_s = ta.ema(df['close'], length=200)
            rsi_s = ta.rsi(df['close'], length=rsi_len)
            
            # Use iloc[-1] for "current forming state" monitoring
            # Use iloc[-2] for "confirmed signal" monitoring?
            # User wants "progress", so usually live price (iloc[-1]) is better to see it approaching.
            
            current_fast = ema_fast_s.iloc[-1]
            current_slow = ema_slow_s.iloc[-1]
            current_200 = ema_200_s.iloc[-1]
            current_rsi = rsi_s.iloc[-1]
            close = df['close'].iloc[-1]
            
            # --- Stage 1: Context (Trend) ---
            # Bullish Context: Close > 200 EMA
            # Bearish Context: Close < 200 EMA
            is_bull_context = close > current_200
            is_bear_context = close < current_200
            
            s1_status = "NEUTRAL"
            s1_details = "Price near 200 EMA"
            if is_bull_context:
                s1_status = "BULLISH"
                s1_details = "Price ABOVE 200 EMA"
            elif is_bear_context:
                s1_status = "BEARISH"
                s1_details = "Price BELOW 200 EMA"
                
            stages = []
            stages.append({
                "name": "1. Trend Context",
                "status": "PASS" if (is_bull_context or is_bear_context) else "WAIT",
                "details": s1_details,
                "metrics": {
                    "price": {"value": close, "threshold": round(current_200, 2), "op": "vs EMA200"}
                }
            })
            
            # --- Stage 2: Filter (RSI) ---
            # Bull req: 50 < RSI < 70 (approx from code 52-68)
            # Bear req: 30 < RSI < 50 (approx from code 32-48)
            
            rsi_ok = False
            rsi_details = f"RSI {current_rsi:.1f} (Neutral)"
            
            if is_bull_context:
                if 52 < current_rsi < 68:
                    rsi_ok = True
                    rsi_details = f"RSI {current_rsi:.1f} (Target: 52-68)"
                else:
                    rsi_details = f"RSI {current_rsi:.1f} (Req: 52-68)"
            elif is_bear_context:
                if 32 < current_rsi < 48:
                    rsi_ok = True
                    rsi_details = f"RSI {current_rsi:.1f} (Target: 32-48)"
                else:
                    rsi_details = f"RSI {current_rsi:.1f} (Req: 32-48)"

            stages.append({
                "name": "2. RSI Filter",
                "status": "PASS" if rsi_ok else "WAIT",
                "details": rsi_details,
                "metrics": {
                    "rsi": {"value": round(current_rsi, 1), "threshold": "Zone", "op": "in"}
                }
            })
            
            # --- Stage 3: Trigger (EMA Cross) ---
            # We look at the convergence.
            # Bull Trigger: Fast crosses ABOVE Slow
            # Bear Trigger: Fast crosses BELOW Slow
            
            ema_dist_pct = (current_fast - current_slow) / current_slow * 100
            s3_status = "WAIT"
            s3_details = f"Gap: {ema_dist_pct:.3f}%"
            
            # Check for FRESH crossover (on live candle iloc[-1] or last closed iloc[-2])
            # We use iloc[-2] vs [-3] for confirmed, and [-1] vs [-2] for live
            
            # Live Cross (Forming)
            is_live_bull_cross = (ema_fast_s.iloc[-2] <= ema_slow_s.iloc[-2]) and (current_fast > current_slow)
            is_live_bear_cross = (ema_fast_s.iloc[-2] >= ema_slow_s.iloc[-2]) and (current_fast < current_slow)
            
            if is_bull_context:
                # We want Fast > Slow.
                if is_live_bull_cross:
                     s3_status = "TRIGGER!" 
                     s3_details = "Cross UP Detected (Live)"
                elif current_fast > current_slow:
                     # Already crossed / aligned
                     s3_status = "ALIGNED"
                     s3_details = "Fast > Slow (Trend Active)"
                elif current_fast < current_slow:
                    # Approaching?
                    if abs(ema_dist_pct) < 0.1:
                        s3_status = "READY (LONG)"
                        s3_details = "Approaching Cross Up"
                        
            elif is_bear_context:
                 # We want Fast < Slow
                if is_live_bear_cross:
                     s3_status = "TRIGGER!" 
                     s3_details = "Cross DOWN Detected (Live)"
                elif current_fast < current_slow:
                     s3_status = "ALIGNED"
                     s3_details = "Fast < Slow (Trend Active)"
                elif current_fast > current_slow:
                    if abs(ema_dist_pct) < 0.1:
                        s3_status = "READY (SHORT)"
                        s3_details = "Approaching Cross Down"

            stages.append({
                "name": "3. EMA Cross",
                "status": s3_status,
                "details": s3_details,
                "metrics": {
                    "gap": {"value": round(ema_dist_pct, 4), "threshold": 0, "op": "cross"}
                }
            })
            
            # Score
            score = 0
            if is_bull_context or is_bear_context: score += 30
            if rsi_ok: score += 30
            
            # Trigger = 100%, Aligned = 60-80% (Missed entry but good context)
            if s3_status == "TRIGGER!": 
                score += 40
            elif s3_status == "ALIGNED":
                score += 10 # Only small boost for being aligned, as entry is passed
            elif "READY" in s3_status: 
                score += 20
            
            # Determine Bias
            bias = "NEUTRAL"
            if is_bull_context: bias = "LONG"
            elif is_bear_context: bias = "SHORT"

            return {
                "strategy": "Scalp EMA RSI",
                "score": score,
                "bias": bias,
                "stages": stages
            }
        except Exception as e:
            return {
                "strategy": "Scalp EMA RSI",
                "score": 0,
                "error": str(e),
                "bias": "NEUTRAL",
                "stages": []
            }

    
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
