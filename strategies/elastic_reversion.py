
from app.services.indicators import ta
import pandas as pd
from strategies.base import BaseStrategy

class ElasticReversionStrategy(BaseStrategy):
    """
    Elastic Mean Reversion Strategy (Long & Short)
    Captures "snap-back" from market extremes (Parabolic/Waterfall).
    
    1. SETUP (15m):
       - Short: RSI > 80 AND Price > EMA20 + 4%
       - Long: RSI < 20 AND Price < EMA20 - 4%
       
    2. TRIGGER:
       - Short: Close < Previous Low
       - Long: Close > Previous High
       
    3. EXIT:
       - TP: Dynamic EMA20
       - SL: 5-candle extremum +/- 0.5%
    """

    AI_PERSONA = """
    CODENAME: "ELASTICITY GUARD - PHYSICS SAFETY"
    
    ROLE:
    You are a RISK-AVERSE PHYSICIST. You calculate the breaking point of price tension.
    
    PRIME DIRECTIVE:
    "We do not stop the train; we wait for it to stop, then we push it back."
    
    RULES OF ENGAGEMENT:
    1. RESPECT MOMENTUM (ADX): If ADX is screaming (>50), do NOT touch it. The rubber band might snap in your face.
    2. LOOK FOR DECELERATION: Before entering, you want to see the candles get smaller or show rejections (wicks). Do not catch large full-body candles.
    3. RSI DIVERGENCE: Ideally, price makes a new high but RSI makes a lower high. This is the "Crack" in the structure we are looking for.
    4. CONFIRMATION: We need a clear "Reverse Trigger" (Close past previous extreme). No "Blind Limit Orders".
    
    RESPONSE STYLE:
    Calculated, cautious.
    "Momentum too high - Abort.", "Elastic tension confirmed - Reversion likely."
    """
    
    def add_indicators(self, df):
        params = self.config.get("params", {})
        ema_len = params.get("ema_period", 20)
        rsi_len = params.get("rsi_period", 14)
        
        # Calculate Indicators
        df[f'EMA_{ema_len}'] = ta.ema(df['close'], length=ema_len)
        df[f'RSI_{rsi_len}'] = ta.rsi(df['close'], length=rsi_len)
        return df

    def generate_signal(self, df, extra_data=None):
        """
        Generate signal based on Elastic Reversion logic.
        """
        # Ensure enough data
        if df is None or df.empty or len(df) < 50: 
            return None
        
        # Add indicators locally (idempotent usually)
        self.add_indicators(df)
        
        params = self.config.get("params", {})
        ema_len = params.get("ema_period", 20)
        rsi_len = params.get("rsi_period", 14)
        ext_pct = params.get("extension_pct", 0.025)  # FIX: Relaxed from 0.032 for more signals
        
        rsi_col = f'RSI_{rsi_len}'
        ema_col = f'EMA_{ema_len}'
        
        # Check columns exist
        if rsi_col not in df.columns or ema_col not in df.columns:
            return None

        # CANDLE DATA POINTERS
        # T (Current/Trigger) -> iloc[-1] (Just Closed)
        # P (Previous/Setup) -> iloc[-2]
        
        try:
            c_close = df['close'].iloc[-1]
            c_high = df['high'].iloc[-1]
            c_low = df['low'].iloc[-1]
            c_rsi = df[rsi_col].iloc[-1]
            c_ema = df[ema_col].iloc[-1]
            
            p_close = df['close'].iloc[-2]
            p_low = df['low'].iloc[-2]
            p_high = df['high'].iloc[-2]
            p_rsi = df[rsi_col].iloc[-2]
            p_ema = df[ema_col].iloc[-2]
            
            if pd.isna(p_ema) or pd.isna(p_rsi): return None
            
            # GUARD CLAUSE: Elasticity limit (ADX < 60)
            # CHANGED 2026-02: Relaxed 50 -> 60
            if 'ADX_14' in df.columns:
                current_adx = df['ADX_14'].iloc[-2]
                if current_adx > 60:
                    return None  # Trend too strong (Runaway), skip mean reversion

            # ==========================================
            # 1. SETUP LOGIC (Checked on Previous Candle P)
            # ==========================================
            
            # Short Setup (Overbought) - FIX: Relaxed 75→72
            is_setup_short = (p_rsi > params.get("rsi_overbought", 72)) and \
                             (p_close > p_ema * (1 + ext_pct))
            
            # Long Setup (Oversold) - FIX: Relaxed 25→28
            is_setup_long = (p_rsi < params.get("rsi_oversold", 28)) and \
                            (p_close < p_ema * (1 - ext_pct))

            # Logging Setups (Debug / Info)
            # Note: This runs every candle, so only log if setup is active to reduce spam, 
            # or rely on trigger logs.
            # if is_setup_short:
            #     print(f"👀 Elastic Short ARMED (RSI {p_rsi:.1f}, Ext {p_close/p_ema:.3f})")
            
            # ==========================================
            # 2. TRIGGER LOGIC (Checked on Current Candle C)
            # ==========================================
            
            # --- SHORT TRIGGER ---
            # Condition: Setup ARMED on P AND Close(C) < Low(P)
            if is_setup_short and (c_close < p_low):
                bonus_rsi = params.get("bonus_rsi_short", 75)
                confidence = "HIGH" if c_rsi < bonus_rsi else "NORMAL"
                
                # SL Calculation: Max High of last 5 candles + Margin
                lookback = params.get("sl_lookback", 5)
                recent_high = df['high'].iloc[-lookback:].max()
                sl_buffer_pct = params.get("sl_buffer_pct", 0.005)
                sl = recent_high * (1 + sl_buffer_pct)
                
                # TP Calculation: Current EMA 20
                tp = c_ema 
                
                # Filter: Mean Reversion TP must be below Entry for Short
                if tp >= c_close: 
                    # If EMA is above price, we literally reverted past mean? Unlikely if Setup verified.
                    # Or EMA moved fast. Fallback or skip.
                    return None

                # Risk/Reward Check
                risk = abs(sl - c_close)
                reward = abs(c_close - tp)
                
                if risk == 0: return None
                rr_ratio = reward / risk
                
                # RSI Delta Check (momentum filter)
                rsi_delta = df[rsi_col].iloc[-1] - df[rsi_col].iloc[-2] # Simplified delta

                # Min RR 1.3 (Relaxed from 1.5)
                # CHANGED 2026-02: 1.5 -> 1.3
                if rr_ratio >= params.get("min_rr", 1.3):
                    # Soft Entry: Prefer RSI Delta < 0 for Short (Momentum turning down)
                    # But since this is Reversion, simply repassing < 75 is the main trigger.
                    # We can use Delta for commentary.
                    
                    print(f"⚡ Elastic Short Triggered! RSI: {p_rsi:.1f}, RR: {rr_ratio:.2f}")
                    return {
                        "signal": "SELL",
                        "sl": sl,
                        "tp": tp,
                        "comment": f"Elastic Short (RSI {p_rsi:.0f}, Delta {rsi_delta:.1f})"
                    }

            # --- LONG TRIGGER ---
            # Condition: Setup ARMED on P AND Close(C) > High(P)
            if is_setup_long and (c_close > p_high):
                # CHECK DIVERGENCE (Flag Bearish Divergence = No Longs)
                if self.detect_bearish_divergence(df, rsi_col=rsi_col, lookback=10):
                    # print("⚠️ Elastic Long Skipped: BEARISH DIVERGENCE detected")
                    return None
                
                bonus_rsi = params.get("bonus_rsi_long", 25)
                
                # SL: Min Low of last 5 candles - Margin
                lookback = params.get("sl_lookback", 5)
                recent_low = df['low'].iloc[-lookback:].min()
                sl_buffer_pct = params.get("sl_buffer_pct", 0.005)
                sl = recent_low * (1 - sl_buffer_pct)
                
                # TP: Current EMA 20
                tp = c_ema
                
                if tp <= c_close:
                    return None
                    
                risk = abs(c_close - sl)
                reward = abs(tp - c_close)
                
                if risk == 0: return None
                rr_ratio = reward / risk
                
                # RSI Delta Check
                rsi_delta = self.get_rsi_delta(df)
                
                if rr_ratio >= params.get("min_rr", 1.5):
                     print(f"⚡ Elastic Long Triggered! RSI: {p_rsi:.1f}, RR: {rr_ratio:.2f}")
                     return {
                         "signal": "BUY",
                         "sl": sl,
                         "tp": tp,
                         "comment": f"Elastic Long (RSI {p_rsi:.0f}, Delta {rsi_delta:+.1f})"
                     }
                    
        except Exception as e:
            print(f"Error in ElasticReversion logic: {e}")
            return None
        
        return None

    def calculate_progress(self, df, extra_data=None):
        """
        Returns detailed progress stages for monitoring.
        Stages:
        1. Context (ADX Safety)
        2. Setup (Extension & RSI)
        3. Trigger (Reversal)
        """
        if df is None or df.empty or len(df) < 50:
            return {
                "strategy": "Elastic Reversion",
                "score": 0,
                "stages": [{"name": "Data Check", "status": "FAIL", "details": "Not enough data"}]
            }
        
        try:
            self.add_indicators(df)
            params = self.config.get("params", {})
            
            # Pointers: P (Setup Candidate), C (Trigger Candidate)
            # We want to show "how close is C to triggering?" or "Is P a valid setup?"
            # Actually, monitoring is usually on the *forming* candle or the *just closed* candle.
            # Let's assess the *current* state (iloc[-1]) as the potential Setup or Trigger.
            
            # Since this strategy looks for Setup on P and Trigger on C, 
            # we will display the status of the "Current Potential Trade".
            
            c_close = df['close'].iloc[-1]
            c_high = df['high'].iloc[-1]
            c_low = df['low'].iloc[-1]
            c_rsi = df[f'RSI_{params.get("rsi_period", 14)}'].iloc[-1]
            c_ema = df[f'EMA_{params.get("ema_period", 20)}'].iloc[-1]
            
            ext_pct = params.get("extension_pct", 0.032)
            
            # --- Stage 1: Context (Safety) ---
            # ADX < 50
            adx_val = 0
            if 'ADX_14' in df.columns:
                adx_val = df['ADX_14'].iloc[-1]
                
            s1_status = "PASS"
            s1_details = f"ADX {adx_val:.1f} (Safe)"
            if adx_val > 50:
                s1_status = "FAIL"
                s1_details = f"ADX {adx_val:.1f} (Too volatile)"
                
            stages = []
            stages.append({
                "name": "1. Safety (ADX)",
                "status": s1_status,
                "details": s1_details,
                "metrics": {
                    "adx": {"value": round(adx_val, 1), "threshold": 50, "op": "<"}
                }
            })
            
            # --- Stage 2: Setup (Elasticity) ---
            # Long Setup: Price < EMA*(1-ext) AND RSI < 20
            # Short Setup: Price > EMA*(1+ext) AND RSI > 80
            
            # Calculate distances
            dist_pct = (c_close - c_ema) / c_ema
            
            # Thresholds
            long_ext_thresh = -ext_pct
            short_ext_thresh = ext_pct
            
            rsi_long_thresh = params.get("oversold_rsi", 24)
            rsi_short_thresh = params.get("overbought_rsi", 76)
            
            s2_status = "WAIT"
            s2_details = "Neutral Zone"
            
            # Long Check
            is_long_ext = dist_pct < long_ext_thresh
            is_long_rsi = c_rsi < rsi_long_thresh
            
            # Short Check
            is_short_ext = dist_pct > short_ext_thresh
            is_short_rsi = c_rsi > rsi_short_thresh
            
            if is_long_ext or is_long_rsi:
                if is_long_ext and is_long_rsi:
                    s2_status = "READY (LONG)"
                    s2_details = "Oversold + Extended"
                elif is_long_ext:
                    s2_status = "PARTIAL"
                    s2_details = f"Extended ({dist_pct*100:.2f}%) but RSI High"
                else:
                    s2_status = "PARTIAL"
                    s2_details = f"RSI Low ({c_rsi:.1f}) but Expecting Ext"
            
            elif is_short_ext or is_short_rsi:
                if is_short_ext and is_short_rsi:
                    s2_status = "READY (SHORT)"
                    s2_details = "Overbought + Extended"
                elif is_short_ext:
                    s2_status = "PARTIAL"
                    s2_details = f"Extended ({dist_pct*100:.2f}%) but RSI Low"
                else:
                    s2_status = "PARTIAL"
                    s2_details = f"RSI High ({c_rsi:.1f}) but Expecting Ext"
            
            stages.append({
                "name": "2. Elastic Setup",
                "status": s2_status,
                "details": s2_details,
                "metrics": {
                    "dist": {"value": round(dist_pct*100, 2), "threshold": round(ext_pct*100, 2), "op": "abs >"},
                    "rsi": {"value": round(c_rsi, 1), "threshold": "20/80", "op": "limit"}
                }
            })
            
            # --- Stage 3: Trigger ---
            # Reversal check
            # We look at the Previous candle (P) to see if it WAS a setup, and if Current (C) IS a reversal.
            # But here `c_close` is `iloc[-1]`. Let's assume `iloc[-1]` is the Potential Trigger.
            # So we check if `iloc[-2]` was a setup.
            
            p_close = df['close'].iloc[-2]
            p_ema = df[f'EMA_{params.get("ema_period", 20)}'].iloc[-2]
            p_rsi = df[f'RSI_{params.get("rsi_period", 14)}'].iloc[-2]
            
            p_dist_pct = (p_close - p_ema) / p_ema
            
            was_long_setup = (p_dist_pct < long_ext_thresh) and (p_rsi < rsi_long_thresh)
            was_short_setup = (p_dist_pct > short_ext_thresh) and (p_rsi > rsi_short_thresh)
            
            s3_status = "WAIT"
            s3_details = "Waiting for Setup..."
            
            if was_long_setup:
                # Need Close > Prev High
                p_high = df['high'].iloc[-2]
                if c_close > p_high:
                    s3_status = "TRIGGER!"
                    s3_details = "Reversal (Close > Prev High)"
                else:
                    s3_status = "WAIT"
                    s3_details = f"Need Close > {p_high:.2f}"
            
            elif was_short_setup:
                # Need Close < Prev Low
                p_low = df['low'].iloc[-2]
                if c_close < p_low:
                    s3_status = "TRIGGER!"
                    s3_details = "Reversal (Close < Prev Low)"
                else:
                    s3_status = "WAIT"
                    s3_details = f"Need Close < {p_low:.2f}"

            stages.append({
                "name": "3. Reversal Trigger",
                "status": s3_status,
                "details": s3_details
            })
            
            # Determine Bias
            bias = "NEUTRAL"
            if was_long_setup or s2_status == "READY (LONG)": bias = "LONG"
            elif was_short_setup or s2_status == "READY (SHORT)": bias = "SHORT"
            elif "READY" in s2_status or "TRIGGER" in s3_status:
                # Fallback if status strings change
                bias = "LONG" if "LONG" in s2_status or "LONG" in s3_status else "SHORT"

            return {
                "strategy": "Elastic Reversion",
                "score": 0, # Placeholder score - update if needed
                "bias": bias,
                "stages": stages
            }

        except Exception as e:
             return {
                "strategy": "Elastic Reversion",
                "score": 0,
                "error": str(e),
                "bias": "NEUTRAL",
                "stages": []
            }

    def check_conditions(self, df, extra_data=None):
        # Legacy method kept for safety, but calculate_progress is preferred
        return []
    
    def get_threshold_comparisons(self, df, extra_data=None):
        """Get detailed threshold comparisons for Parameters section"""
        if df is None or df.empty or len(df) < 50:
            return {}
        
        try:
            self.add_indicators(df)
            params = self.config.get("params", {})
            
            p_rsi = df[f'RSI_{params.get("rsi_period", 14)}'].iloc[-3]
            c_close = df['close'].iloc[-2]
            p_high = df['high'].iloc[-3]
            c_ema = df[f'EMA_{params.get("ema_period", 20)}'].iloc[-2]
            ext_pct = params.get("extension_pct", 0.04)
            price_vs_ema_pct = ((c_close - c_ema) / c_ema) * 100
            
            return {
                "RSI": f"{p_rsi:.1f} vs Max: 20",
                "Distance from EMA": f"{price_vs_ema_pct:.1f}% vs Req: -{ext_pct*100:.1f}%",
                "Close > Prev High": "Yes" if c_close > p_high else "No"
            }
        except Exception as e:
            return {"Error": str(e)}
