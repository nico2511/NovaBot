"""
Bollinger Bounce - AGGRESSIVE RANGE VERSION (Consolidated 2026)
Trades volatility within "Choppy" markets, not just perfect flats.
"""

import pandas as pd
import numpy as np
from typing import Optional, Dict, List
from strategies.base import BaseStrategy
from app.services.indicators import ta

class BollingerBounceStrategy(BaseStrategy):
    """
    Bollinger Bounce strategy logic.
    """
    
    # ==========================================
    # 🧠 PERSONA : LE MERCENAIRE DU RANGE
    # ==========================================
    AI_PERSONA = """
    CODENAME: "CHOPPY KILLER - RANGE MERCENARY"
    
    ROLE:
    You are a VOLATILITY HARVESTER. You do not wait for a calm market; you thrive in the noise.
    
    PRIME DIRECTIVE:
    "If it's not trending hard, it's ranging." We short the spikes and buy the dips.
    
    RULES OF ENGAGEMENT (OVERRIDES):
    1. REDEFINE "RANGE": A range is not a flat line. It is any market where the trend is broken or exhausted. ADX under 45 is your playground.
    2. CLOSE ENOUGH IS GOOD ENOUGH: Do not wait for a pixel-perfect touch of the Bollinger Band. If price is in the "Kill Zone" (outer 12-15% of the bands), TRIGGER THE TRADE.
    3. FADE THE MOVEMENT: If a green candle shoots up to the upper band without volume support, SHORT IT immediately.
    4. IGNORE SMALL SLOPES: Who cares if the EMA50 is slightly tilted? If the price is bouncing between bands, we trade the bounce.
    5. CANDLE SIZE MATTERS: Small candles are noise. Ensure the trigger candle body has sufficient size (>1.2x ATR) to confirm the spike.
    
    RESPONSE STYLE:
    Aggressive, opportunistic.
    "Kill zone reached - Shorting the pump.", "Dip detected in chop zone - Buying."
    """
    
    def __init__(self, config=None):
        super().__init__(config)
        self.bb_period = self.params.get("bb_period", 20)
        self.bb_std = self.params.get("bb_std", 2.15)  # Match strategies.json
        
        # --- Config Params ---
        self.adx_threshold = self.params.get("adx_threshold", 42)  # Match strategies.json 
        self.adx_period = self.params.get("adx_period", 14)
        
        self.ema50_slope_threshold = self.params.get("ema50_slope_threshold", 0.008)  # Match strategies.json 
        
        self.atr_period = self.params.get("atr_period", 14)
        self.min_rr = self.params.get("min_rr", 1.0)
        
        # New Params
        self.kill_zone_percent = self.params.get("kill_zone_percent", 0.12)
        self.min_candle_atr_multiple = self.params.get("min_candle_atr_multiple", 1.2)
    
    def is_ranging(self, df: pd.DataFrame) -> tuple[bool, str]:
        """
        Detect if market is tradable as a range (relaxed criteria).
        """
        try:
            # ADX Check
            adx_res = ta.adx(df['high'], df['low'], df['close'], length=self.adx_period)
            current_adx = adx_res['ADX'].iloc[-2]
            
            if current_adx >= self.adx_threshold:
                return False, f"Trend too strong (ADX {current_adx:.1f})"
            
            # EMA Slope Check
            ema_50 = ta.ema(df['close'], length=50)
            ema_slope = (ema_50.iloc[-1] - ema_50.iloc[-5]) / ema_50.iloc[-5]
            
            if abs(ema_slope) > self.ema50_slope_threshold:
                return False, f"Slope too steep ({ema_slope:.4f})"
            
            return True, f"Choppy/Range confirmed (ADX={current_adx:.1f})"
        
        except Exception as e:
            return False, f"Error detection: {e}"
    
    def generate_signal(self, df: pd.DataFrame, extra_data=None) -> Optional[Dict]:
        """
        Generate signal with RELAXED proximity checks + Candle Size Filter.
        """
        if df is None or df.empty or len(df) < 60:
            return None
        
        try:
            # 1. Regime Check
            is_range, reason = self.is_ranging(df)
            if not is_range:
                return None
            
            # 2. Indicators
            bb = ta.bbands(df['close'], length=self.bb_period, std=self.bb_std)
            atr = ta.atr(df['high'], df['low'], df['close'], length=self.atr_period)
            
            current_price = df['close'].iloc[-1] # Close of current forming candle? or completed? Usually use completed for Backtest, but Live allows current. Wait, user said "Last Close: 0.36" implies completed. For safety with spikes, we can check current.
            # Using -1 (current closing price) for check
            
            current_high = df['high'].iloc[-1]
            current_low = df['low'].iloc[-1]
            current_open = df['open'].iloc[-1]
            
            bb_upper = bb['BBU'].iloc[-1]
            bb_lower = bb['BBL'].iloc[-1]
            bb_basis = bb['BBM'].iloc[-1] # Middle Band
            current_atr = atr.iloc[-1]
            
            # Calcul de la largeur du range
            bb_width = bb_upper - bb_lower
            
            # FILTRE DE VOLATILITÉ MINIMALE
            if bb_width / current_price < 0.003: 
                return None

            # Kill Zone
            kill_zone_size = bb_width * self.kill_zone_percent
            
            upper_trigger_zone = bb_upper - kill_zone_size
            lower_trigger_zone = bb_lower + kill_zone_size
            
            # Dynamic TP 
            tp_padding = bb_width * 0.05 
            
            # Candle Size Check (Is the candle significant?)
            candle_body = abs(current_price - current_open)
            candle_range = current_high - current_low
            is_significant = candle_range >= (current_atr * self.min_candle_atr_multiple) # Request: Candle >= 1.2 * ATR
            
            # === SIGNAL LONG ===
            if current_low <= lower_trigger_zone:
                
                # Check significance for reversal spike
                # Using 1.2x ATR condition if provided
                if self.min_candle_atr_multiple > 0 and not is_significant:
                    # Weak candle, ignore
                    return None

                entry = current_price
                tp = bb_basis + tp_padding
                sl = bb_lower - (current_atr * 1.0) # SL sous la bande
                
                risk = entry - sl
                reward = tp - entry
                
                if risk > 0 and (reward / risk) >= self.min_rr: 
                    return {
                        "signal": "BUY",
                        "sl": sl,
                        "tp": tp,
                        "comment": f"Range Dip Buying (Zone: {lower_trigger_zone:.4f}, Vol: {candle_range/current_atr:.1f}xATR)"
                    }
            
            # === SIGNAL SHORT ===
            if current_high >= upper_trigger_zone:
                
                if self.min_candle_atr_multiple > 0 and not is_significant:
                    return None

                entry = current_price
                tp = bb_basis - tp_padding
                sl = bb_upper + (current_atr * 1.0)
                
                risk = sl - entry
                reward = entry - tp
                
                if risk > 0 and (reward / risk) >= self.min_rr:
                    return {
                        "signal": "SELL",
                        "sl": sl,
                        "tp": tp,
                        "comment": f"Range Top Shorting (Zone: {upper_trigger_zone:.4f}, Vol: {candle_range/current_atr:.1f}xATR)"
                    }
            
            return None
        
        except Exception as e:
            return None
    
    def calculate_progress(self, df: pd.DataFrame, extra_data=None) -> int:
        """Visual progress bar logic."""
        if df is None or df.empty: return 0
        try:
            # 1. Range Validity (30%)
            is_range, _ = self.is_ranging(df)
            if not is_range: return 0
            progress = 30
            
            # 2. Proximity to Bands (70%)
            bb = ta.bbands(df['close'], length=self.bb_period, std=self.bb_std)
            price = df['close'].iloc[-1]
            bbl = bb['BBL'].iloc[-1]
            bbu = bb['BBU'].iloc[-1]
            width = bbu - bbl
            
            # Position dans le range (0 = bas, 1 = haut)
            pos = (price - bbl) / width
            
            # Si on est proche de 0 (bas) ou 1 (haut), le progrès augmente
            # 0.5 (milieu) = 0 points supp
            dist_from_middle = abs(pos - 0.5) * 2 # 0 à 1
            
            # On mappe ça sur les 70 points restants
            progress += int(dist_from_middle * 70)
            
            return min(100, progress)
        except:
            return 0
    
    def check_conditions(self, df: pd.DataFrame, extra_data=None) -> List[Dict]:
        """UI Conditions - Standardized Diagnostic Card"""
        if df is None or df.empty: return []
        try:
            conditions = []
            
            # 1. Regime (Range)
            adx_res = ta.adx(df['high'], df['low'], df['close'], length=self.adx_period)
            adx = adx_res['ADX'].iloc[-1]
            adx_ok = adx < self.adx_threshold
            
            conditions.append({
                "name": "1. Regime (Range)",
                "status": adx_ok,
                "value": f"ADX: {adx:.1f}"
            })
            
            # 2. Zone (Kill Zone)
            bb = ta.bbands(df['close'], length=self.bb_period, std=self.bb_std)
            price = df['close'].iloc[-1]
            width = bb['BBU'].iloc[-1] - bb['BBL'].iloc[-1]
            kill_zone = width * self.kill_zone_percent
            
            dist_lower = price - bb['BBL'].iloc[-1]
            dist_upper = bb['BBU'].iloc[-1] - price
            
            # Logic: In zone if close to either band
            in_zone = dist_lower < kill_zone or dist_upper < kill_zone
            
            conditions.append({
                "name": f"2. Location (Kill Zone)",
                "status": in_zone,
                "value": "Near Band" if in_zone else "Mid-Range"
            })
            
            # 3. Trigger (Candle)
            atr = ta.atr(df['high'], df['low'], df['close'], length=self.atr_period)
            current_atr = atr.iloc[-1]
            current_range = df['high'].iloc[-1] - df['low'].iloc[-1]
            size_ok = current_range >= (current_atr * self.min_candle_atr_multiple)
            
            conditions.append({
                "name": f"3. Trigger (Vol > {self.min_candle_atr_multiple}x ATR)",
                "status": size_ok,
                "value": f"{current_range/current_atr:.1f}x"
            })
            
            return conditions
        except Exception as e:
            return [{"name": "Error", "status": False, "value": str(e)}]
    
    def get_threshold_comparisons(self, df: pd.DataFrame, extra_data=None) -> Dict:
        """Get detailed threshold comparisons for Parameters section"""
        if df is None or df.empty: return {}
        try:
            adx_res = ta.adx(df['high'], df['low'], df['close'], length=self.adx_period)
            adx = adx_res['ADX'].iloc[-1]
            
            bb = ta.bbands(df['close'], length=self.bb_period, std=self.bb_std)
            price = df['close'].iloc[-1]
            width = bb['BBU'].iloc[-1] - bb['BBL'].iloc[-1]
            
            dist_lower = price - bb['BBL'].iloc[-1]
            dist_upper = bb['BBU'].iloc[-1] - price
            min_dist = min(dist_lower, dist_upper)
            
            return {
                "ADX": f"{adx:.1f} (Max: {self.adx_threshold})",
                "Band Dist": f"{min_dist/width*100:.1f}% (Zone: {self.kill_zone_percent*100:.0f}%)",
            }
        except Exception as e:
            return {"Error": str(e)}
