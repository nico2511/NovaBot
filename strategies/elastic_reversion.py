
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
        ext_pct = params.get("extension_pct", 0.032)
        
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
            
            # GUARD CLAUSE: Elasticity limit (ADX < 50)
            # We want to catch extension, but not stand in front of a freight train (ADX > 50)
            if 'ADX_14' in df.columns:
                current_adx = df['ADX_14'].iloc[-2]
            # GUARD CLAUSE: Elasticity limit (ADX < 50)
            # We want to catch extension, but not stand in front of a freight train (ADX > 50)
            if 'ADX_14' in df.columns:
                current_adx = df['ADX_14'].iloc[-2]
                if current_adx > 50:
                    # Note: adx_threshold renamed from adx_limit for standardization
                    return None  # Trend too strong (Runaway), skip mean reversion

            # ==========================================
            # 1. SETUP LOGIC (Checked on Previous Candle P)
            # ==========================================
            
            # Short Setup (Overbought)
            # RSI > 80 AND Price > EMA + 4%
            is_setup_short = (p_rsi > params.get("overbought_rsi", 76)) and \
                             (p_close > p_ema * (1 + ext_pct))
            
            # Long Setup (Oversold)
            # RSI < 20 AND Price < EMA - 4%
            is_setup_long = (p_rsi < params.get("oversold_rsi", 24)) and \
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
                rsi_delta = self.get_rsi_delta(df)
                
                if rr_ratio >= params.get("min_rr", 1.5):
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
        """Calculate how close we are to triggering a signal (0-100%)."""
        if df is None or df.empty or len(df) < 50:
            return 0
        
        try:
            self.add_indicators(df)
            params = self.config.get("params", {})
            
            p_rsi = df[f'RSI_{params.get("rsi_period", 14)}'].iloc[-3]
            c_close = df['close'].iloc[-2]
            c_ema = df[f'EMA_{params.get("ema_period", 20)}'].iloc[-2]
            ext_pct = params.get("extension_pct", 0.04)
            
            progress = 0
            
            # 1. RSI Proximity (40 points)
            # For LONG: RSI < 20 is ideal
            if p_rsi < 20:
                progress += 40
            elif p_rsi < 30:
                # Linear scale: 30 -> 0%, 20 -> 100%
                progress += int(40 * (30 - p_rsi) / 10)
            
            # 2. Price Extension (30 points)
            # For LONG: Price < EMA - 4% is ideal
            price_vs_ema = (c_close - c_ema) / c_ema
            target_ext = -ext_pct  # -0.04 for long
            
            if price_vs_ema <= target_ext:
                progress += 30
            elif price_vs_ema < 0:
                # Approaching: scale from 0% to -4%
                progress += int(30 * abs(price_vs_ema) / ext_pct)
            
            # 3. Momentum (30 points)
            # Check if RSI is turning up (delta > 0)
            if len(df) > 3:
                rsi_delta = self.get_rsi_delta(df)
                if rsi_delta > 0:
                    progress += 30
                elif rsi_delta > -5:
                    progress += int(30 * (5 + rsi_delta) / 5)
            
            return min(100, progress)
        except:
            return 0

    def check_conditions(self, df, extra_data=None):
        """Check detailed conditions for UI - Simple names only"""
        if df is None or df.empty or len(df) < 50:
            return []
        
        try:
            self.add_indicators(df)
            params = self.config.get("params", {})
            
            p_rsi = df[f'RSI_{params.get("rsi_period", 14)}'].iloc[-3]
            c_close = df['close'].iloc[-2]
            p_close = df['close'].iloc[-3]
            p_high = df['high'].iloc[-3]
            c_ema = df[f'EMA_{params.get("ema_period", 20)}'].iloc[-2]
            ext_pct = params.get("extension_pct", 0.04)
            
            conditions = []
            
            # 1. Setup (RSI + Extension)
            # RSI Oversold Check
            rsi_ok = p_rsi < 20
            # Price Extension Check (Dist from EMA)
            price_vs_ema_pct = ((c_close - c_ema) / c_ema) * 100
            ext_ok = price_vs_ema_pct < -(ext_pct * 100)
            
            setup_ok = rsi_ok and ext_ok
            
            conditions.append({
                "name": "1. Setup (RSI<20 + Ext)",
                "status": setup_ok,
                "value": f"RSI:{p_rsi:.1f}, Ext:{price_vs_ema_pct:.1f}%"
            })
            
            # 2. Trigger (Reversal)
            trigger_ok = c_close > p_high
            trigger_val = "Waiting for Reversal..."
            
            if trigger_ok:
                trigger_val = "Close > Prev High"
            elif setup_ok:
                trigger_val = f"Need > {p_high:.2f}"
                
            conditions.append({
                "name": "2. Trigger (Reversal)",
                "status": trigger_ok,
                "value": trigger_val
            })
            
            return conditions
        except Exception as e:
            return [{"name": "Error", "status": False, "value": str(e)}]
    
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
