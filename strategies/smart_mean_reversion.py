
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
        
        # ANTI-REPAINTING: Use completed candles only
        # Current Candle (C) -> iloc[-2] (last completed)
        # Previous Candle (P) -> iloc[-3] (before that)
        
        try:
            c_close = df['close'].iloc[-2]
            c_open = df['open'].iloc[-2]
            c_rsi = df[rsi_col].iloc[-2]
            c_roc = df[roc_col].iloc[-2]
            c_bbl = df['BBL'].iloc[-2]
            c_bbm = df['BBM'].iloc[-2]
            
            p_close = df['close'].iloc[-3]
            
            # GUARD CLAUSE: Mean Reversion only in Range (ADX < 25)
            if 'ADX_14' in df.columns:
                current_adx = df['ADX_14'].iloc[-2]
                if current_adx > 25:
                    return None  # Trend detected, skip mean reversion
            
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
            
            # SL: Low of last 3 completed candles - small margin
            recent_low = df['low'].iloc[-4:-1].min()  # Last 3 completed candles
            sl = recent_low * 0.995 # 0.5% below recent low
            
            # TP: Revert to Mean (Middle Band)
            tp = c_bbm
            
            # Sanity Check R:R (crypto 2026: min 1.5:1 obligatoire)
            risk = c_close - sl
            reward = tp - c_close
            
            if risk <= 0: 
                return None
            
            # R:R minimum 1.5:1 instead of absolute 0.5%
            rr_ratio = reward / risk
            if rr_ratio < 1.5:
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

    def calculate_progress(self, df, extra_data=None):
        """Calculate how close we are to triggering a signal (0-100%)."""
        if df is None or df.empty or len(df) < 30:
            return 0
        
        try:
            self.add_indicators(df)
            params = self.config.get("params", {})
            
            c_rsi = df[f'RSI_{params.get("rsi_period", 14)}'].iloc[-2]
            c_roc = df[f'ROC_{params.get("roc_period", 10)}'].iloc[-2]
            c_close = df['close'].iloc[-2]
            c_bbl = df['BBL'].iloc[-2]
            p_close = df['close'].iloc[-3]
            
            rsi_threshold = params.get("rsi_threshold", 30)
            roc_floor = params.get("roc_floor", -15.0)
            
            progress = 0
            
            # 1. RSI Oversold (30 points)
            if c_rsi < rsi_threshold:
                progress += 30
            elif c_rsi < 40:
                # Scale: 40 -> 0%, 30 -> 100%
                progress += int(30 * (40 - c_rsi) / 10)
            
            # 2. ROC Safety (25 points)
            if c_roc > roc_floor:
                progress += 25
            elif c_roc > -25:
                # Scale: -25 -> 0%, -15 -> 100%
                progress += int(25 * (c_roc + 25) / 10)
            
            # 3. BB Position (25 points)
            if c_close < c_bbl:
                progress += 25
            else:
                # Distance to lower band
                dist_pct = ((c_close - c_bbl) / c_bbl) * 100
                if dist_pct < 2:
                    progress += int(25 * (2 - dist_pct) / 2)
            
            # 4. Stabilization (20 points)
            if c_close > p_close:
                progress += 20
            
            return min(100, progress)
        except:
            return 0

    def check_conditions(self, df, extra_data=None):
        """Check detailed conditions for UI display."""
        if df is None or df.empty or len(df) < 30:
            return []
        
        try:
            self.add_indicators(df)
            params = self.config.get("params", {})
            
            c_rsi = df[f'RSI_{params.get("rsi_period", 14)}'].iloc[-2]
            c_roc = df[f'ROC_{params.get("roc_period", 10)}'].iloc[-2]
            c_close = df['close'].iloc[-2]
            c_bbl = df['BBL'].iloc[-2]
            p_close = df['close'].iloc[-3]
            
            rsi_threshold = params.get("rsi_threshold", 30)
            roc_floor = params.get("roc_floor", -15.0)
            
            conditions = []
            
            # 1. RSI Oversold
            rsi_ok = c_rsi < rsi_threshold
            conditions.append({
                "name": f"RSI Oversold (< {rsi_threshold})",
                "status": rsi_ok,
                "value": f"{c_rsi:.1f}"
            })
            
            # 2. Momentum Floor
            roc_ok = c_roc > roc_floor
            conditions.append({
                "name": f"ROC Safety (> {roc_floor}%)",
                "status": roc_ok,
                "value": f"{c_roc:.1f}%"
            })
            
            # 3. Below BB Lower
            bb_ok = c_close < c_bbl
            conditions.append({
                "name": "Price < BB Lower",
                "status": bb_ok,
                "value": f"${c_close:.4f} vs ${c_bbl:.4f}"
            })
            
            # 4. Stabilization
            stab_ok = c_close > p_close
            conditions.append({
                "name": "Stabilization (Green Candle)",
                "status": stab_ok,
                "value": "Yes" if stab_ok else "No"
            })
            
            return conditions
        except Exception as e:
            return [{"name": "Error", "status": False, "value": str(e)}]
