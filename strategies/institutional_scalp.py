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
        """Calculate proximity to liquidity grab signal"""
        if df is None or df.empty or len(df) < 30:
            return 0
        
        try:
            self.add_indicators(df)
            params = self.config.get("params", {})
            lookback = params.get("liq_grab_lookback", 20)
            
            current = df.iloc[-1]
            close = current['close']
            high = current['high']
            low = current['low']
            
            recent = df.tail(lookback + 1)
            recent_high = recent['high'].iloc[:-1].max()
            recent_low = recent['low'].iloc[:-1].min()
            
            progress = 0
            
            # Check proximity to recent high/low
            distance_to_high = abs(high - recent_high) / recent_high
            distance_to_low = abs(low - recent_low) / recent_low
            
            if distance_to_high < 0.01 or distance_to_low < 0.01:
                progress += 50
            elif distance_to_high < 0.02 or distance_to_low < 0.02:
                progress += 30
            
            # Check for wick formation
            candle_range = high - low
            if candle_range > 0:
                upper_wick = (high - max(close, current['open'])) / candle_range
                lower_wick = (min(close, current['open']) - low) / candle_range
                
                if upper_wick > 0.4 or lower_wick > 0.4:
                    progress += 30
            
            return min(100, progress)
        except:
            return 0
    
    def check_conditions(self, df, extra_data=None):
        """Check detailed conditions for UI - Diagnostic Card"""
        if df is None or df.empty or len(df) < 30:
            return []
        
        try:
            self.add_indicators(df)
            params = self.config.get("params", {})
            lookback = params.get("liq_grab_lookback", 20)
            
            current = df.iloc[-1]
            close = current['close']
            high = current['high']
            low = current['low']
            
            recent = df.tail(lookback + 1)
            recent_high = recent['high'].iloc[:-1].max()
            recent_low = recent['low'].iloc[:-1].min()
            
            conditions = []
            
            # 1. Proximity (Level)
            dist_high = abs(high - recent_high) / recent_high
            dist_low = abs(low - recent_low) / recent_low
            
            at_high = dist_high < 0.01
            at_low = dist_low < 0.01
            
            is_near = at_high or at_low
            
            conditions.append({
                "name": "1. Proximity (Liquidity Level)",
                "status": is_near,
                "value": "Near High" if at_high else "Near Low" if at_low else "Mid-Range"
            })
            
            # 2. Wick (Indecision)
            candle_range = high - low
            has_wick = False
            wick_txt = "No Wick"
            
            if candle_range > 0:
                upper_wick = (high - max(close, current['open'])) / candle_range
                lower_wick = (min(close, current['open']) - low) / candle_range
                
                has_wick = upper_wick > 0.4 or lower_wick > 0.4
                if upper_wick > 0.4: wick_txt = "Upper Wick"
                elif lower_wick > 0.4: wick_txt = "Lower Wick"
                
            conditions.append({
                "name": "2. Wick Formation (>40%)",
                "status": has_wick,
                "value": wick_txt
            })
            
            # 3. Trigger (Reversal)
            bullish_reversal = low < recent_low and close > recent_low
            bearish_reversal = high > recent_high and close < recent_high
            
            rev_status = "None"
            if bullish_reversal: rev_status = "Bullish Reclaim"
            elif bearish_reversal: rev_status = "Bearish Reclaim"
            
            conditions.append({
                "name": "3. Trigger (Level Reclaim)",
                "status": bullish_reversal or bearish_reversal,
                "value": rev_status
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
