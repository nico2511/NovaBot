
from app.services.indicators import ta
import pandas as pd
from strategies.base import BaseStrategy

class SmartMeanReversionStrategy(BaseStrategy):
    """
    Smart Trend Dip Buyer (Formerly Mean Reversion)
    buys "Healthy Dips" in strong trends. NOT a falling knife catcher.
    
    LOGIC:
    1. REGIME:
       - Trend must be active (ADX > 25)
       - Price must be above EMA 200 (for Long)
       
    2. SETUP (The Dip):
       - RSI pulls back to "Sweet Spot" (40-55 for Long)
       - Price touches EMA 20
       
    3. TRIGGER:
       - Green candle closes above previous high (Reversal confirmed)
    """
    
    AI_PERSONA = """
    CODENAME: "TREND ARCHITECT - DIP BUYER"
    
    ROLE:
    You are a MOMENTUM SUSTAINABILITY EXPERT. You hate catching knives. You love catching "Breathers".
    
    PRIME DIRECTIVE:
    "The trend is your friend, until the bend." We buy into strength during its temporary weakness.
    
    RULES OF ENGAGEMENT:
    1. TREND IS MANDATORY: If price is below EMA 200, DO NOT BUY DIPS. We only short rallies. Context is everything.
    2. THE "HEALTHY" DIP: We want a slow, corrective drift down to the EMA 20 or 50. NOT a violent crash.
    3. RSI RECHARGE: We look for RSI resetting from >70 down to 45-50. This is the "Recharge" zone.
    4. TRIGGER DISCIPLINE: Do not buy the red candle touching the line. Buy the FIRST GREEN candle that proves the support held.
    
    RESPONSE STYLE:
    Constructive, encouraging.
    "Trend healthy - Support confirmed - Reloading.", "Structure broken - Abort dip buy."
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
        Generate signal based on Trend Dip Buying logic.
        """
        if df is None or df.empty or len(df) < 50: 
            return None
        
        self.add_indicators(df)
        
        # Trend indicators
        ema_200 = ta.ema(df['close'], length=200).iloc[-2]
        ema_50 = ta.ema(df['close'], length=50).iloc[-2]
        
        # Momentum
        rsi = ta.rsi(df['close'], length=14).iloc[-2]
        
        # Regime (ADX)
        if 'ADX_14' in df.columns:
            adx = df['ADX_14'].iloc[-2]
            if adx < 20: # Weak trend
                return None
                
        # Price Action
        close = df['close'].iloc[-2]
        open_p = df['open'].iloc[-2]
        
        # === LONG DIP ===
        # 1. Trend Filter: Above EMA 200 AND EMA 50
        if close > ema_200 and close > ema_50:
            # 2. RSI "Recharge" Zone (40-55) - Not oversold yet, just cooling off
            if 40 <= rsi <= 55:
                # 3. Trigger: Green Candle (Close > Open) indicating support found
                if close > open_p:
                    # SL: Recent Swing Low
                    sl = df['low'].iloc[-5:-1].min()
                    tp = close + (abs(close - sl) * 2.0) # R:R 2.0
                    
                    return {
                        "signal": "BUY",
                        "sl": sl,
                        "tp": tp,
                        "comment": f"Trend Dip Buy (RSI {rsi:.1f}, >EMA200)"
                    }

        # === SHORT RALLY (Dip in downtrend) ===
        # 1. Trend Filter: Below EMA 200 AND EMA 50
        if close < ema_200 and close < ema_50:
            # 2. RSI "Recharge" Zone (45-60)
            if 45 <= rsi <= 60:
                # 3. Trigger: Red Candle
                if close < open_p:
                    # SL: Recent Swing High
                    sl = df['high'].iloc[-5:-1].max()
                    tp = close - (abs(sl - close) * 2.0)
                    
                    return {
                        "signal": "SELL",
                        "sl": sl,
                        "tp": tp,
                        "comment": f"Trend Rally Short (RSI {rsi:.1f}, <EMA200)"
                    }
            
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
        """Check detailed conditions for UI - Diagnostic Card (FUNNEL LOGIC)"""
        if df is None or df.empty or len(df) < 30:
            return []
        
        try:
            self.add_indicators(df)
            params = self.config.get("params", {})
            
            c_rsi = df[f'RSI_{params.get("rsi_period", 14)}'].iloc[-1]
            c_roc = df[f'ROC_{params.get("roc_period", 10)}'].iloc[-1]
            c_close = df['close'].iloc[-1]
            c_bbl = df['BBL'].iloc[-1]
            p_close = df['close'].iloc[-2]
            
            rsi_threshold = params.get("rsi_threshold", 30)
            roc_floor = params.get("roc_floor", -15.0)
            
            conditions = []
            
            # 1. Setup (RSI < 30) - GATEKEEPER
            rsi_ok = c_rsi < rsi_threshold
            conditions.append({
                "name": "1. Setup (RSI < 30)",
                "status": rsi_ok,
                "value": f"{c_rsi:.1f}"
            })
            
            # 2. Safety (ROC > -15%) - DEPENDS ON SETUP
            if not rsi_ok:
                conditions.append({
                    "name": "2. Safety (ROC > -15%)",
                    "status": False,
                    "value": "Waiting for Setup..."
                })
                roc_ok = False # Enforce failure cascade
            else:
                roc_ok = c_roc > roc_floor
                conditions.append({
                    "name": "2. Safety (ROC > -15%)",
                    "status": roc_ok,
                    "value": f"{c_roc:.1f}%"
                })
            
            # 3. Trigger (Stabilization) - DEPENDS ON SETUP & SAFETY
            if not rsi_ok or not roc_ok:
                 conditions.append({
                    "name": "3. Trigger (BB + Green)",
                    "status": False,
                    "value": "Waiting for conditions..."
                })
            else:
                # Price under BB Lower AND Green Candle
                bb_ok = c_close < c_bbl
                stab_ok = c_close > p_close
                trigger_ok = bb_ok and stab_ok
                
                trigger_val = "Waiting..."
                if not bb_ok: trigger_val = "Price above Lower Band"
                elif not stab_ok: trigger_val = "Falling (Red Candle)"
                elif trigger_ok: trigger_val = "Stabilized"
                
                conditions.append({
                    "name": "3. Trigger (BB + Green)",
                    "status": trigger_ok,
                    "value": trigger_val
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
            
            c_rsi = df[f'RSI_{params.get("rsi_period", 14)}'].iloc[-1]
            c_roc = df[f'ROC_{params.get("roc_period", 10)}'].iloc[-1]
            c_close = df['close'].iloc[-1]
            c_bbl = df['BBL'].iloc[-1]
            p_close = df['close'].iloc[-2]
            
            rsi_threshold = params.get("rsi_threshold", 30)
            roc_floor = params.get("roc_floor", -15.0)
            
            # Distance in %
            dist_pct = ((c_close - c_bbl) / c_bbl) * 100
            bb_ok = c_close < c_bbl
            stab_ok = c_close > p_close
            
            return {
                "RSI": f"{c_rsi:.1f} vs Max: {rsi_threshold}",
                "ROC": f"{c_roc:.2f}% vs Min: {roc_floor}%",
                "Price vs Band": f"{'Below' if bb_ok else 'Above'} Band (Dist: {dist_pct:.2f}%)",
                "Stabilization": "Close > Prev Close" if stab_ok else "Falling"
            }
        except Exception as e:
            return {"Error": str(e)}
