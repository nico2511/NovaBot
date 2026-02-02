
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
        params = self.config.get("params", {})
        adx_threshold = params.get("adx_threshold", 25)
        if 'ADX_14' in df.columns:
            adx = df['ADX_14'].iloc[-2]
            if adx < adx_threshold:  # Weak trend - use config threshold
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
                    # Volume Filter
                    volume_multiplier = params.get("volume_multiplier", 1.3)
                    if 'volume' in df.columns:
                        current_vol = df['volume'].iloc[-2]
                        avg_vol = df['volume'].iloc[-22:-2].mean()
                        if avg_vol > 0 and current_vol < avg_vol * volume_multiplier:
                            return None
                    
                    # SL: Recent Swing Low with buffer
                    sl_buffer_pct = params.get("sl_buffer_pct", 0.008)
                    sl_base = df['low'].iloc[-5:-1].min()
                    sl = sl_base * (1 - sl_buffer_pct)
                    
                    min_rr = params.get("min_rr", 1.5)
                    tp = close + (abs(close - sl) * min_rr)
                    
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
                    # Volume Filter
                    volume_multiplier = params.get("volume_multiplier", 1.3)
                    if 'volume' in df.columns:
                        current_vol = df['volume'].iloc[-2]
                        avg_vol = df['volume'].iloc[-22:-2].mean()
                        if avg_vol > 0 and current_vol < avg_vol * volume_multiplier:
                            return None
                    
                    # SL: Recent Swing High with buffer
                    sl_buffer_pct = params.get("sl_buffer_pct", 0.008)
                    sl_base = df['high'].iloc[-5:-1].max()
                    sl = sl_base * (1 + sl_buffer_pct)
                    
                    min_rr = params.get("min_rr", 1.5)
                    tp = close - (abs(sl - close) * min_rr)
                    
                    return {
                        "signal": "SELL",
                        "sl": sl,
                        "tp": tp,
                        "comment": f"Trend Rally Short (RSI {rsi:.1f}, <EMA200)"
                    }
            
        return None

    def calculate_progress(self, df, extra_data=None):
        """
        Returns detailed progress stages for monitoring.
        Stages:
        1. Regime (Trend & ADX)
        2. Dip Zone (RSI & Position)
        3. Trigger (Reversal Candle)
        """
        if df is None or df.empty or len(df) < 50:
             return {
                "strategy": "Smart Mean Rev",
                "score": 0,
                "stages": [{"name": "Data Check", "status": "FAIL", "details": "Not enough data"}]
            }
        
        try:
            self.add_indicators(df)
            params = self.config.get("params", {})
            
            # Pointers
            c_close = df['close'].iloc[-1]
            c_open = df['open'].iloc[-1]
            c_rsi = df[f'RSI_{params.get("rsi_period", 14)}'].iloc[-1]
            ema_200 = df['EMA_200'].iloc[-1] if 'EMA_200' in df.columns else ta.ema(df['close'], length=200).iloc[-1]
            ema_50 = df['EMA_50'].iloc[-1] if 'EMA_50' in df.columns else ta.ema(df['close'], length=50).iloc[-1]
            
            # --- Stage 1: Trend Regime ---
            adx_val = 0
            if 'ADX_14' in df.columns:
                adx_val = df['ADX_14'].iloc[-1]
            
            adx_ok = adx_val > params.get("adx_threshold", 25)
            
            # Check Trend Alignment
            is_uptrend = c_close > ema_200 and c_close > ema_50
            is_downtrend = c_close < ema_200 and c_close < ema_50
            
            s1_status = "WAIT"
            s1_details = "Choppy / Weak Trend"
            
            if adx_ok:
                if is_uptrend:
                    s1_status = "BULLISH"
                    s1_details = f"Strong Uptrend (ADX {adx_val:.0f})"
                elif is_downtrend:
                    s1_status = "BEARISH"
                    s1_details = f"Strong Downtrend (ADX {adx_val:.0f})"
            else:
                 s1_details = f"ADX Low ({adx_val:.0f} < 25)"

            stages = []
            stages.append({
                "name": "1. Trend Regime",
                "status": "PASS" if (s1_status in ["BULLISH", "BEARISH"]) else "WAIT",
                "details": s1_details,
                "metrics": {
                    "adx": {"value": round(adx_val, 1), "threshold": 25, "op": ">"}
                }
            })
            
            # --- Stage 2: Dip Zone (RSI) ---
            # Long: RSI 40-55
            # Short: RSI 45-60
            
            s2_status = "WAIT"
            s2_details = f"RSI {c_rsi:.1f} (Neutral)"
            
            in_buy_zone = 40 <= c_rsi <= 55
            in_sell_zone = 45 <= c_rsi <= 60
            
            if s1_status == "BULLISH":
                if in_buy_zone:
                    s2_status = "READY"
                    s2_details = "RSI in Buy Zone (40-55)"
                elif c_rsi < 40:
                    s2_status = "OVERSOLD" 
                    s2_details = f"RSI {c_rsi:.1f} (Warning < 40)"
                else: 
                     s2_details = f"RSI {c_rsi:.1f} (Req 40-55)"
                     
            elif s1_status == "BEARISH":
                if in_sell_zone:
                    s2_status = "READY"
                    s2_details = "RSI in Sell Zone (45-60)"
                elif c_rsi > 60:
                     s2_status = "OVERBOUGHT"
                     s2_details = f"RSI {c_rsi:.1f} (Warning > 60)"
                else:
                     s2_details = f"RSI {c_rsi:.1f} (Req 45-60)"

            stages.append({
                "name": "2. Dip Zone",
                "status": s2_status,
                "details": s2_details,
                "metrics": {
                    "rsi": {"value": round(c_rsi, 1), "threshold": "Zone", "op": "in"}
                }
            })
            
            # --- Stage 3: Trigger (Candle Color) ---
            s3_status = "WAIT"
            s3_details = "Waiting for setup..."
            
            if s2_status == "READY":
                if s1_status == "BULLISH":
                    # Require Green Candle (Close > Open)
                    if c_close > c_open:
                        s3_status = "TRIGGER!"
                        s3_details = "Bullish Candle Formed"
                    else:
                        s3_details = "Waiting for Green Candle"
                elif s1_status == "BEARISH":
                    # Require Red Candle (Close < Open)
                    if c_close < c_open:
                        s3_status = "TRIGGER!"
                        s3_details = "Bearish Candle Formed"
                    else:
                        s3_details = "Waiting for Red Candle"
                        
            stages.append({
                "name": "3. Reversal Trigger",
                "status": s3_status,
                "details": s3_details
            })
            
            # Score
            score = 0
            if s1_status in ["BULLISH", "BEARISH"]: score += 30
            if s2_status == "READY": score += 40
            if s3_status == "TRIGGER!": score += 30
            
            return {
                "strategy": "Smart Mean Rev",
                "score": score,
                "stages": stages
            }

        except Exception as e:
            return {
                "strategy": "Smart Mean Rev",
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
