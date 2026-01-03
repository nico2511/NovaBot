
from app.services.indicators import ta
import pandas as pd
from strategies.base import BaseStrategy

class SmartMeanReversionStrategy(BaseStrategy):
    """
    Smart Mean Reversion Strategy (Long Only for now as per "Bottom Fishing" request)
    Captures rebound from oversold conditions with safety filters.

    LOGIC:
    1. ENTRY SIGNAL:
       - RSI (14) < 30 (Oversold)
       
    2. SAFETY FILTER (Momentum Floor):
       - ROC (Rate of Change) over 10 periods > -15% (Avoid falling knives)
       
    3. CONFIRMATION (Mean Reversion):
       - Price < Lower Bollinger Band
       - Price > Previous Close (Stabilization/Green Candle)
       
    4. EXIT:
       - TP: Middle Bollinger Band (Mean) or specific %
       - SL: Low of previous candle - margin
    """
    
    def add_indicators(self, df):
        params = self.config.get("params", {})
        rsi_len = params.get("rsi_period", 14)
        roc_len = params.get("roc_period", 10)
        bb_len = params.get("bb_period", 20)
        bb_std = params.get("bb_std", 2.0)
        
        # RSI
        df[f'RSI_{rsi_len}'] = ta.rsi(df['close'], length=rsi_len)
        
        # ROC (Rate of Change) - Momentum
        # (Close - Close_prev_n) / Close_prev_n * 100
        # df[f'ROC_{roc_len}'] = ta.roc(df['close'], length=roc_len)
        df[f'ROC_{roc_len}'] = df['close'].pct_change(periods=roc_len) * 100
        
        # Bollinger Bands
        bb = ta.bbands(df['close'], length=bb_len, std=bb_std)
        if bb is not None:
             df['BBL'] = bb['BBL'] # Lower
             df['BBM'] = bb['BBM'] # Middle (Basis)
             df['BBU'] = bb['BBU'] # Upper
             
        return df

    def generate_signal(self, df, extra_data=None):
        """
        Generate signal based on Smart Mean Reversion logic.
        """
        if df is None or df.empty or len(df) < 30: 
            return None
        
        self.add_indicators(df)
        
        params = self.config.get("params", {})
        rsi_threshold = params.get("rsi_threshold", 30)
        roc_floor = params.get("roc_floor", -15.0) # -15% max drop
        
        rsi_col = f'RSI_{params.get("rsi_period", 14)}'
        roc_col = f'ROC_{params.get("roc_period", 10)}'
        
        # Current Candle (C) -> iloc[-1]
        # Previous Candle (P) -> iloc[-2]
        
        try:
            c_close = df['close'].iloc[-1]
            c_open = df['open'].iloc[-1]
            c_rsi = df[rsi_col].iloc[-1]
            c_roc = df[roc_col].iloc[-1]
            c_bbl = df['BBL'].iloc[-1]
            c_bbm = df['BBM'].iloc[-1]
            
            p_close = df['close'].iloc[-2]
            
            # --- CONDITION 1: RSI OVERSOLD ---
            if c_rsi >= rsi_threshold:
                return None
                
            # --- CONDITION 2: MOMENTUM FLOOR (Safety) ---
            # If ROC is too negative (e.g. -20%), it's a crash. We want it ABOVE -15%.
            if c_roc < roc_floor:
                # print(f"⚠️ SmartMR: Falling Knife detected (ROC {c_roc:.2f}% < {roc_floor}%)")
                return None
                
            # --- CONDITION 3: BOLLINGER CONFIRMATION ---
            # Price under Lower Band AND Stabilization (Green Candle or Close > Prev Close)
            below_band = c_close < c_bbl
            stabilizing = c_close > p_close # Simple reversal check
            
            if not (below_band and stabilizing):
                return None
            
            # === TRIGGER LONG ===
            
            # SL: Low of last 3 candles - small margin
            recent_low = df['low'].iloc[-3:].min()
            sl = recent_low * 0.995 # 0.5% below recent low
            
            # TP: Revert to Mean (Middle Band)
            tp = c_bbm
            
            # Sanity Check R:R
            risk = c_close - sl
            reward = tp - c_close
            
            if risk <= 0: return None
            
            # If reward is too small (bands compressed), skip
            if reward < (c_close * 0.005): # Min 0.5% potential
                return None
                
            return {
                "signal": "BUY",
                "sl": sl,
                "tp": tp,
                "comment": f"Smart Mean Reversion (RSI {c_rsi:.1f}, ROC {c_roc:.1f}%)"
            }
            
        except Exception as e:
            print(f"Error in SmartMeanReversion: {e}")
            return None
