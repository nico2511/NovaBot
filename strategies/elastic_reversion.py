
from app.services.indicators import ta
import pandas as pd
from strategies.base import BaseStrategy

class ElasticReversionStrategy(BaseStrategy):
    """
    Elastic Mean Reversion Strategy (Long & Short)
    Captures "snap-back" from market extremes (Parabolic/Waterfall).

    Tunable via strategies.json params (defaults shown):
    1. SETUP (15m):
       - Short: RSI > rsi_overbought (70) AND Price > EMA * (1 + extension_pct)
       - Long:  RSI < rsi_oversold (30) AND Price < EMA * (1 - extension_pct)
       - Guard: ADX < adx_max (skip runaway trends)

    2. TRIGGER:
       - Short: Close < Previous Low
       - Long: Close > Previous High (blocked if bearish RSI divergence)

    3. EXIT:
       - TP: Current EMA
       - SL: sl_lookback extremum +/- sl_buffer_pct
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
            return self._reject("Not enough candles (need 50+)")
        
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
            return self._reject("Indicateurs RSI/EMA manquants")

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
            
            if pd.isna(p_ema) or pd.isna(p_rsi): return self._reject("EMA/RSI NaN — pas assez de données")
            
            # GUARD CLAUSE: Elasticity limit (ADX < adx_max)
            # Param "adx_max" is now editable via strategies.json / API (default: 60).
            adx_max = float(params.get("adx_max", 60))
            if 'ADX_14' in df.columns:
                current_adx = df['ADX_14'].iloc[-2]
                if current_adx > adx_max:
                    return self._reject(f"ADX trop fort ({current_adx:.1f} > {adx_max:.1f}) — tendance runaway")

            # ==========================================
            # 1. SETUP LOGIC (Checked on Previous Candle P)
            # ==========================================
            
            # Short Setup (Overbought)
            is_setup_short = (p_rsi > params.get("rsi_overbought", 70)) and \
                             (p_close > p_ema * (1 + ext_pct))

            # Long Setup (Oversold)
            is_setup_long = (p_rsi < params.get("rsi_oversold", 30)) and \
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
                # SL Calculation: Max High of last N candles + Margin
                lookback = params.get("sl_lookback", 5)
                recent_high = df['high'].iloc[-lookback:].max()
                sl_buffer_pct = params.get("sl_buffer_pct", 0.005)
                sl = recent_high * (1 + sl_buffer_pct)

                # TP Calculation: Current EMA
                tp = c_ema

                # Filter: Mean Reversion TP must be below Entry for Short
                if tp >= c_close:
                    return self._reject(f"EMA TP ({tp:.4f}) >= entrée ({c_close:.4f}) — reversion déjà effectuée")

                risk = abs(sl - c_close)
                reward = abs(c_close - tp)

                if risk == 0:
                    return self._reject("Risque SL=0 — invalide")
                rr_ratio = reward / risk

                rsi_delta = df[rsi_col].iloc[-1] - df[rsi_col].iloc[-2]

                if rr_ratio >= params.get("min_rr", 1.5):
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
                    return self._reject("Divergence baissière détectée — Long annulé")

                lookback = params.get("sl_lookback", 5)
                recent_low = df['low'].iloc[-lookback:].min()
                sl_buffer_pct = params.get("sl_buffer_pct", 0.005)
                sl = recent_low * (1 - sl_buffer_pct)

                tp = c_ema

                if tp <= c_close:
                    return self._reject(f"EMA TP ({tp:.4f}) <= entrée ({c_close:.4f}) — reversion déjà effectuée")

                risk = abs(c_close - sl)
                reward = abs(tp - c_close)

                if risk == 0:
                    return self._reject("Risque SL=0 — invalide")
                rr_ratio = reward / risk

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
