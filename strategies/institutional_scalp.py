from app.services.indicators import ta
import pandas as pd
from strategies.base import BaseStrategy

class InstitutionalScalp(BaseStrategy):
    """
    Institutional Scalp Strategy - Liquidity Grab Detection
    
    Detects institutional liquidity grabs (stop hunts) and trades the reversal.
    """
    
    # ==========================================
    # 🧠 PERSONA : THE BANKER (SMART MONEY)
    # ==========================================
    AI_PERSONA = """
    CODENAME: "THE BANKER - LIQUIDITY HUNTER"
    
    ROLE:
    You are an INSTITUTIONAL MARKET MAKER. You see the chart as a map of "Pain" (Stop Losses).
    
    PRIME DIRECTIVE:
    "Retail traders panic where we accumulate." We buy their fear (Stop Runs) and sell their greed (Breakout Traps).
    
    RULES OF ENGAGEMENT:
    1. IDENTIFY THE TRAP: We need to see a "Sweep" of a recent High/Low. The price must pierce the level to trigger stops, then IMMEDIATELY reverse.
    2. NO SUSTAINED BREAKOUTS: If price closes outside the level and stays there, it's real. We want a "Fakeout" (Wick down, Close up).
    3. VOLUME IS TRUTH: A true liquidity grab MUST have high volume (Stops triggering). Low volume means nobody cares -> No trade.
    4. TREND CONTEXT: 
       - If trending UP: We buy volume dips (Bear traps).
       - If trending DOWN: We sell volume spikes (Bull traps).
       - Do not trade against a massive news candle.
    
    RESPONSE STYLE:
    Cynical, sophisticated.
    "Retail trapped at lows - Accumulating.", "Stop run completed - Reversing."
    """
    
    def add_indicators(self, df):
        df['ATRr_14'] = ta.atr(df['high'], df['low'], df['close'], length=14)
        return df

    def generate_signal(self, df, extra_data=None):
        if df.empty or len(df) < 30:
            return None

        self.add_indicators(df)

        params = self.config.get("params", {})
        lookback = params.get("liq_grab_lookback", 18)
        atr_col = "ATRr_14"

        if atr_col not in df.columns:
            return None
        
        # GUARD CLAUSE: ADX Logic - Relaxed for Liquidity Grabs
        # Liquidity grabs can happen in Trends (Pullbacks) or Ranges. 
        # We only filter if ADX is EXTREME (> configured threshold) to avoid catching a crashing knife.
        adx_extreme_limit = params.get("adx_extreme_limit", 60)  # High default for liquidity grabs
        if 'ADX_14' in df.columns:
            current_adx = df['ADX_14'].iloc[-2]
            if current_adx > adx_extreme_limit:
                # Extreme trend, liquidations might be genuine breakouts. Safe to avoid.
                return None  

        current = df.iloc[-2]  # Use confirmed candle (anti-repainting)
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
            if candle_range > 0 and (close - low) / candle_range > 0.42:
                # PHASE 2: Volume Spike Filter
                # CRITICAL FIX: Use completed candle volume (iloc[-2]), not forming candle
                # Comparing partial volume to full average is mathematically incorrect
                vol_mult = params.get("volume_multiplier", 1.35)
                if 'volume' in df.columns:
                    current_volume = df['volume'].iloc[-2]  # ✅ Completed candle volume
                    avg_volume = df['volume'].iloc[-22:-2].mean()  # Last 20 completed candles
                    
                    if current_volume < (avg_volume * vol_mult):
                        return None  # Insufficient volume
                
                sl_atr_mult = params.get("sl_atr_mult", 0.5)
                sl = low - (sl_atr_mult * atr)
                tp = close + (2.0 * atr)
                
                # Check Min R:R
                risk = abs(close - sl)
                reward = abs(tp - close)
                if risk > 0:
                    rr = reward / risk
                    min_rr = params.get("min_rr", 1.2)
                    if rr < min_rr:
                        return None
                
                comment = "Bullish Liquidity Grab"
                
                return {
                    "signal": "BUY",
                    "sl": sl,
                    "tp": tp,
                    "comment": comment
                }

        # BEARISH LIQUIDITY GRAB
        if high > recent_high and close < recent_high:
            candle_range = high - low
            if candle_range > 0 and (high - close) / candle_range > 0.42:
                # PHASE 2: Volume Spike Filter
                # CRITICAL FIX: Use completed candle volume (iloc[-2]), not forming candle
                vol_mult = params.get("volume_multiplier", 1.35)
                if 'volume' in df.columns:
                    current_volume = df['volume'].iloc[-2]  # ✅ Completed candle volume
                    avg_volume = df['volume'].iloc[-22:-2].mean()  # Last 20 completed candles
                    
                    if current_volume < (avg_volume * vol_mult):
                        return None  # Insufficient volume
                
                sl_atr_mult = params.get("sl_atr_mult", 0.6)
                sl = high + (sl_atr_mult * atr)
                tp = close - (1.8 * atr)
                
                # Check Min R:R
                risk = abs(sl - close)
                reward = abs(close - tp)
                if risk > 0:
                    rr = reward / risk
                    min_rr = params.get("min_rr", 1.2)
                    if rr < min_rr:
                        return None
                
                comment = "Bearish Liquidity Grab"

                return {
                    "signal": "SELL",
                    "sl": sl,
                    "tp": tp,
                    "comment": comment
                }
        
        return None
    
    def calculate_progress(self, df, extra_data=None):
        """
        Returns detailed progress stages for monitoring.
        Stages:
        1. Context (ADX Safety)
        2. Setup (Liquidity Grab)
        3. Trigger (Reversal Candle)
        """
        if df is None or df.empty or len(df) < 30:
            return {
                "strategy": "Inst. Scalp",
                "score": 0,
                "stages": [{"name": "Data Check", "status": "FAIL", "details": "Not enough data"}]
            }
        
        try:
            self.add_indicators(df)
            params = self.config.get("params", {})
            lookback = params.get("liq_grab_lookback", 20)
            
            # Use confirmed candle for analysis to match signal logic?
            # Signal logic uses iloc[-2]. Let's monitor the *current forming* situation relative to history.
            # Current = iloc[-1].
            
            current = df.iloc[-1]
            close = current['close']
            high = current['high']
            low = current['low']
            
            recent = df.iloc[-(lookback+1):-1] # Exclude current
            recent_high = recent['high'].max()
            recent_low = recent['low'].min()
            
            # 1. Context (ADX Safety)
            # We want ADX < Limit (defaults to 60)
            adx_val = 0
            if 'ADX_14' in df.columns:
                adx_val = df['ADX_14'].iloc[-1]
            
            adx_limit = params.get("adx_extreme_limit", 60)
            s1_status = "PASS"
            s1_details = f"ADX {adx_val:.1f} (Safe)"
            if adx_val > adx_limit:
                 s1_status = "FAIL"
                 s1_details = f"ADX {adx_val:.1f} (Too Volatile)"
            
            stages = []
            stages.append({
                "name": "1. Safety (ADX)",
                "status": s1_status,
                "details": s1_details,
                "metrics": {
                    "adx": {"value": round(adx_val, 1), "threshold": adx_limit, "op": "<"}
                }
            })
            
            # 2. Setup (Proximity to Liquidity)
            # Are we near High or Low?
            dist_high = (high - recent_high) / recent_high
            dist_low = (low - recent_low) / recent_low
            
            # If we pierced the level, distance is negative (overshoot) or close to 0
            # Let's verify "Grab" potential: price went beyond level?
            
            grab_high = high > recent_high
            grab_low = low < recent_low
            
            s2_status = "WAIT"
            s2_details = "Mid-Range"
            
            if grab_high:
                s2_status = "READY (BEAR)"
                s2_details = "Pierced Recent High"
            elif grab_low:
                s2_status = "READY (BULL)"
                s2_details = "Pierced Recent Low"
            else:
                # Check proximity
                if abs(dist_high) < 0.005:
                     s2_details = f"Near High ({dist_high*100:.2f}%)"
                elif abs(dist_low) < 0.005:
                     s2_details = f"Near Low ({dist_low*100:.2f}%)"
            
            stages.append({
                "name": "2. Liquidity Level",
                "status": s2_status,
                "details": s2_details
            })
            
            # 3. Trigger (Reversal + Wick)
            # Need Close inside range (Reversal) + Volume + Wick
            
            s3_status = "WAIT"
            s3_details = "Waiting for rejection..."
            
            if "READY" in s2_status:
                candle_range = high - low
                if candle_range > 0:
                    upper_wick = (high - max(close, current['open'])) / candle_range
                    lower_wick = (min(close, current['open']) - low) / candle_range
                    
                    if s2_status == "READY (BEAR)":
                        # Need Bearish Reversal (Close < Low) -> Wait, logic is Close < Recent High
                        reclaimed = close < recent_high
                        if reclaimed:
                             if upper_wick > 0.4:
                                 s3_status = "POTENTIAL"
                                 s3_details = f"Bearish Reclaim + Wick ({upper_wick*100:.0f}%)"
                             else:
                                 s3_details = "Bearish Reclaim, Weak Wick"
                        else:
                             s3_details = "Above High (Breakout?)"
                             
                    elif s2_status == "READY (BULL)":
                        # Need Bullish Reversal (Close > Recent Low)
                        reclaimed = close > recent_low
                        if reclaimed:
                             if lower_wick > 0.4:
                                 s3_status = "POTENTIAL"
                                 s3_details = f"Bullish Reclaim + Wick ({lower_wick*100:.0f}%)"
                             else:
                                 s3_details = "Bullish Reclaim, Weak Wick"
                        else:
                             s3_details = "Below Low (Breakdown?)"

            stages.append({
                "name": "3. Rejection Wick",
                "status": s3_status,
                "details": s3_details
            })
            
            # Score
            score = 0
            if s1_status == "PASS": score += 20
            if "READY" in s2_status: score += 40
            if s3_status == "POTENTIAL": score += 40
            
            return {
                "strategy": "Inst. Scalp",
                "score": score,
                "stages": stages
            }

        except Exception as e:
            return {
                "strategy": "Inst. Scalp",
                "score": 0,
                "error": str(e),
                "stages": []
            }
    
    def check_conditions(self, df, extra_data=None):
        return []

    
    def get_threshold_comparisons(self, df, extra_data=None):
        """Get detailed threshold comparisons for Parameters section"""
        if df is None or df.empty:
            return {}
        try:
            self.add_indicators(df)
            current = df.iloc[-1]
            close = current['close']
            high = current['high']
            low = current['low']
            
            highs = df['high'].iloc[-50:-1]
            lows = df['low'].iloc[-50:-1]
            recent_high = highs.max()
            recent_low = lows.min()
            
            dist_high = abs(close - recent_high) / recent_high * 100
            dist_low = abs(close - recent_low) / recent_low * 100
            min_dist = min(dist_high, dist_low)
            
            candle_range = high - low
            upper_wick = (high - max(close, current['open'])) / candle_range if candle_range > 0 else 0
            lower_wick = (min(close, current['open']) - low) / candle_range if candle_range > 0 else 0
            max_wick_pct = max(upper_wick, lower_wick) * 100
            
            bullish_reversal = low < recent_low and close > recent_low
            bearish_reversal = high > recent_high and close < recent_high
            
            return {
                "Proximity": f"{min_dist:.2f}% vs Req: <0.5%",
                "Wick Size": f"{max_wick_pct:.1f}% vs Req: >40%",
                "Trigger": "Confirming" if (bullish_reversal or bearish_reversal) else "Waiting"
            }
        except Exception as e:
            return {"Error": str(e)}
