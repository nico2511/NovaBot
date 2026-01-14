import pandas as pd
import numpy as np

def get_dynamic_context(df: pd.DataFrame) -> dict:
    """
    Calculate dynamic context (slopes, trends, variations) from the last 2 candles.
    Used to give the AI 'vision' of movement not just static values.
    
    Args:
        df: DataFrame with at least columns: close, volume. 
            Optional columns: rsi, adx, atr.
            
    Returns:
        dict: Flat dictionary with keys like 'vol_slope', 'rsi_trend', etc.
    """
    if df.empty or len(df) < 2: 
        return {}
    
    # Get last 2 rows
    curr = df.iloc[-1]
    prev = df.iloc[-2]
    
    ctx = {}
    
    # 1. Volume Dynamics
    # Check if 'volume' column exists (case insensitive)
    vol_col = next((c for c in df.columns if c.lower() == 'volume'), None)
    if vol_col:
        try:
            curr_vol = float(curr[vol_col])
            prev_vol = float(prev[vol_col])
            
            # Avoid division by zero
            if prev_vol > 0:
                vol_chg = ((curr_vol - prev_vol) / prev_vol * 100)
            else:
                vol_chg = 0 if curr_vol == 0 else 100
                
            ctx['vol_slope'] = round(vol_chg, 2)
            ctx['vol_current'] = f"{curr_vol:,.0f}"
            
            # Trend Label
            if vol_chg > 50:
                ctx['vol_trend'] = "🔥 SPIKE"
            elif vol_chg > 20: 
                ctx['vol_trend'] = "↗️ RISING"
            elif vol_chg < -30: 
                ctx['vol_trend'] = "📉 DROP"
            else: 
                ctx['vol_trend'] = "➡️ STABLE"
        except Exception:
            ctx['vol_slope'] = 0
            ctx['vol_trend'] = "UNKNOWN"
            ctx['vol_current'] = "0"

    # 2. RSI Dynamics (Generic search for RSI columns)
    rsi_col = next((c for c in df.columns if 'rsi' in c.lower() and 'stoch' not in c.lower()), None)
    # Prefer explicit 'RSI_14' if available
    if 'RSI_14' in df.columns: rsi_col = 'RSI_14'
    
    if rsi_col:
        try:
            curr_rsi = float(curr[rsi_col])
            prev_rsi = float(prev[rsi_col])
            diff = curr_rsi - prev_rsi
            
            ctx['rsi_val'] = round(curr_rsi, 1)
            ctx['rsi_slope'] = round(diff, 1)
            
            # Trend Label
            if diff > 2:
                ctx['rsi_trend'] = "↗️ SURGE"
            elif diff > 0.5:
                ctx['rsi_trend'] = "↗️ RISING"
            elif diff < -2:
                ctx['rsi_trend'] = "↘️ PLUNGING"
            elif diff < -0.5:
                ctx['rsi_trend'] = "↘️ FALLING"
            else:
                ctx['rsi_trend'] = "➡️ FLAT"
        except Exception:
            ctx['rsi_val'] = 0
            ctx['rsi_slope'] = 0
            ctx['rsi_trend'] = "UNKNOWN"
            
    # 3. ADX Dynamics
    adx_col = next((c for c in df.columns if 'adx' in c.lower()), None)
    if 'ADX_14' in df.columns: adx_col = 'ADX_14'
    
    if adx_col:
        try:
            curr_adx = float(curr[adx_col])
            prev_adx = float(prev[adx_col])
            
            ctx['adx_val'] = round(curr_adx, 1)
            ctx['adx_slope'] = round(curr_adx - prev_adx, 1)
        except Exception:
             ctx['adx_val'] = 0
             ctx['adx_slope'] = 0

    # 4. Price Dynamics
    try:
        curr_price = float(curr['close'])
        prev_price = float(prev['close'])
        price_chg = ((curr_price - prev_price) / prev_price * 100)
        
        ctx['price_change_15m'] = round(price_chg, 2)
        ctx['price_trend'] = "🟢" if price_chg > 0 else "🔴"
    except Exception:
        pass
        
    return ctx
