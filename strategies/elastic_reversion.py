
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
        ext_pct = params.get("extension_pct", 0.04)
        
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

            # ==========================================
            # 1. SETUP LOGIC (Checked on Previous Candle P)
            # ==========================================
            
            # Short Setup (Overbought)
            # RSI > 80 AND Price > EMA + 4%
            is_setup_short = (p_rsi > params.get("overbought_rsi", 80)) and \
                             (p_close > p_ema * (1 + ext_pct))
            
            # Long Setup (Oversold)
            # RSI < 20 AND Price < EMA - 4%
            is_setup_long = (p_rsi < params.get("oversold_rsi", 20)) and \
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
                sl_margin = params.get("sl_margin", 0.005)
                sl = recent_high * (1 + sl_margin)
                
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
                
                if rr_ratio >= params.get("risk_reward", 1.5):
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
                sl_margin = params.get("sl_margin", 0.005)
                sl = recent_low * (1 - sl_margin)
                
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
                
                if rr_ratio >= params.get("risk_reward", 1.5):
                    # Soft Entry Filter: Want RSI Delta > 0 (Momentum turning up)
                    if rsi_delta > 0:
                         print(f"⚡ Elastic Long Triggered! RSI: {p_rsi:.1f}, RR: {rr_ratio:.2f}")
                         return {
                             "signal": "BUY",
                             "sl": sl,
                             "tp": tp,
                             "comment": f"Elastic Long (RSI {p_rsi:.0f}, Delta +{rsi_delta:.1f})"
                         }
                    else:
                        # Optional: Skip or Log weak momentum
                        # print(f"⚠️ Elastic Long Wait: RSI Delta {rsi_delta:.1f} (Not bouncing yet)")
                        pass
                    
        except Exception as e:
            print(f"Error in ElasticReversion logic: {e}")
            return None
        
        return None
