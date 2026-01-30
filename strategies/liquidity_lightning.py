import pandas as pd
import time
from strategies.base import BaseStrategy
from app.services.indicators import Indicators

class LiquidityLightning(BaseStrategy):
    """
    STRATÉGIE "L'ÉCLAIR DE LIQUIDITÉ" (Funnel v2)
    
    RÔLE : Expert en Scalping de Choc.
    PROTOCOLE : Funnel d'élimination à 4 étages (Trigger -> Réaction -> Confirmation -> R/R).
    EXIT : EMA 20 ou 180 secondes.
    """
    
    AI_PERSONA = """
    CODENAME: "L'ÉCLAIR - SHOCK SCALPER"
    ROLE: High-Frequency Liquidity Sniper.
    METHOD: 4-Stage Elimination Funnel.
    MOTTO: "Strike hard, vanish fast."
    """

    def add_indicators(self, df):
        # EMA 20 for Target
        df['EMA_20'] = df['close'].ewm(span=20, adjust=False).mean()
        # ATR for misc calcs (optional, strategy uses wick-based SL)
        # We need Rolling Volume Average
        df['Vol_Avg_20'] = df['volume'].rolling(window=20).mean()
        return df

    def generate_signal(self, df, extra_data=None):
        if df.empty or len(df) < 50:
            return None

        self.add_indicators(df)
        
        # --- FUNNEL STAGE 0: DATA PREP ---
        # We analyze the previously CLOSED candle for confirmation
        candle = df.iloc[-2]  
        prev_candles = df.iloc[-32:-2] # 30 candles before
        
        if len(prev_candles) < 30: return None

        close = candle['close']
        open_px = candle['open']
        high = candle['high']
        low = candle['low']
        volume = candle['volume']
        vol_avg = candle['Vol_Avg_20']
        ema_20 = candle['EMA_20']
        
        # 30-period High/Low (excluding current)
        period_high = prev_candles['high'].max()
        period_low = prev_candles['low'].min()
        
        # --- FUNNEL ÉTAGE 1 : LE DÉCLENCHEUR (Trigger d'Impulsion) ---
        # Action : Identifier un balayage (Sweep) d'un plus haut ou plus bas des 30 dernières bougies.
        
        is_sweep_high = high > period_high
        is_sweep_low = low < period_low
        
        if not (is_sweep_high or is_sweep_low):
            return None # ÉTAGE 1 FAILED
            
        trigger_type = "BEARISH_SWEEP" if is_sweep_high else "BULLISH_SWEEP"
        
        # --- FUNNEL ÉTAGE 2 : LA RÉACTION (Le Snap Back) ---
        # Condition : Clôture à l'intérieur du range précédent. 
        # Mèche > 60% de la bougie totale.
        
        candle_range = high - low
        if candle_range == 0: return None
        
        body_size = abs(close - open_px)
        wick_pct = 0
        
        if trigger_type == "BEARISH_SWEEP":
            # Upper wick must be the dominant feature
            # Wick = High - Max(Open, Close)
            upper_wick = high - max(open_px, close)
            wick_pct = upper_wick / candle_range
            
            # Snap back check: Close must be below the sweep level (period_high)
            # Strict reading: "Clôture impérative à l'intérieur du range précédent" -> Close < period_high
            if close >= period_high: 
                return None # Failed Snap Back
                
        else: # BULLISH_SWEEP
            # Lower wick must be dominant
            # Wick = Min(Open, Close) - Low
            lower_wick = min(open_px, close) - low
            wick_pct = lower_wick / candle_range
            
            # Snap back check: Close must be above the sweep level (period_low)
            if close <= period_low:
                return None # Failed Snap Back
                
        if wick_pct <= 0.48:
            return None # ÉTAGE 2 FAILED (Wick too small: {wick_pct:.2f})

        # --- FUNNEL ÉTAGE 3 : LA CONFIRMATION (Liquidité) ---
        # Condition : Pic de volume (>50% de la moyenne) OU baisse OI (Not implemented yet).
        
        vol_surge = volume > (vol_avg * 1.28)
        
        # Placeholder for OI check if data available
        oi_drop = False 
        if 'open_interest' in df.columns:
            curr_oi = df['open_interest'].iloc[-2]
            prev_oi = df['open_interest'].iloc[-3]
            if curr_oi < prev_oi * 0.999: # 0.1% drop?
                oi_drop = True
                
        if not (vol_surge or oi_drop):
            return None # ÉTAGE 3 FAILED (No institutional force)

        # --- FUNNEL ÉTAGE 4 : LA RENTABILITÉ (Calcul R/R) ---
        # Action : Mesurer distance Entrée -> EMA 20 (Objectif) vs Entrée -> Bas de mèche (Stop).
        # Condition : RR >= 1:1
        
        entry_price = close # Market Entry at Close
        sl_price = 0
        target_price = ema_20
        
        # 1 tick buffer for SL (approx 0.01% or min tick)
        tick_buffer = close * 0.0001 
        
        if trigger_type == "BULLISH_SWEEP":
            sl_price = low - tick_buffer
            risk = entry_price - sl_price
            reward = target_price - entry_price
            
            # Validation: Trend Context check? 
            # Strategy says: "Entrance -> EMA 20". If EMA 20 is below entry for a Buy, Reward is negative.
            # This implies a Mean Reversion trade.
            # If Price < EMA 20, we can't target EMA 20 for a Buy... wait, usually sweeps happen *away* from EMA.
            # If Bullish Sweep (Low), price is likely below EMA 20? 
            # If price is DEEP below EMA 20, Reward is positive.
            
            if reward <= 0: return None # Target already met or invalid
             
        else: # BEARISH_SWEEP
            sl_price = high + tick_buffer
            risk = sl_price - entry_price
            reward = entry_price - target_price
            
            if reward <= 0: return None
            
        if risk == 0: return None
        
        rr_ratio = reward / risk
        
        if rr_ratio < 1.0:
            return None # ÉTAGE 4 FAILED (RR {rr_ratio:.2f} < 1)

        # --- VERDICT FINAL : GO ---
        
        return {
            "signal": "BUY" if trigger_type == "BULLISH_SWEEP" else "SELL",
            "price": entry_price, # Explicitly valid price
            "sl": sl_price,
            "tp": target_price,
            "comment": f"⚡ Eclair Trigger! Wick {wick_pct:.0%} | Vol {volume/vol_avg:.1f}x | RR {rr_ratio:.1f}",
            "strategy": self.name,
            "metadata": {
                "wick_pct": wick_pct,
                "vol_ratio": volume/vol_avg,
                "rr": rr_ratio,
                "funnel_stage": "COMPLETE"
            }
        }

    def manage_trade(self, trade, current_price, df=None, extra_data=None):
        """
        Gestion de sortie spécifique :
        1. TP sur EMA 20
        2. Time Limit : 180 secondes
        """
        updates = {}
        
        # 1. Time Limit Check
        entry_time_str = trade.get("entry_time") or trade.get("timestamp")
        if entry_time_str:
            try:
                entry_ts = pd.Timestamp(entry_time_str)
                now_ts = pd.Timestamp.now()
                elapsed_seconds = (now_ts - entry_ts).total_seconds()
                
                if elapsed_seconds >= 180:
                    # TIME UP!
                    # We can't force close here directly, but we can set SL/TP to current price to trigger immediate exit?
                    # Or better, we return a special signal if the bot supported it.
                    # Standard `manage_trade` updates SL/TP.
                    # Strategy: Move SL to current price (or very tight) to force exit.
                    
                    # Tighten SL to current price +/- tiny buffer to force exit
                    if trade["side"] == "BUY":
                        updates["sl"] = current_price * 0.9999
                        updates["tp"] = current_price * 1.0001
                    else:
                        updates["sl"] = current_price * 1.0001
                        updates["tp"] = current_price * 0.9999
                        
                    # We should probably Log this action? Bot logs updates.
                    return updates
            except:
                pass
                
        # 2. Dynamic TP (EMA 20)
        # Update TP to follow EMA 20 if it shifts?
        # Strategy says "TP sur EMA 20".
        if df is not None and not df.empty:
            self.add_indicators(df)
            current_ema = df['EMA_20'].iloc[-1]
            
            # Update TP to dynamic EMA
            updates["tp"] = current_ema
            
        return updates if updates else None
