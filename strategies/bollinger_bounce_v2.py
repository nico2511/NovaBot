"""
Bollinger Bounce - AGGRESSIVE RANGE VERSION
Trades volatility within "Choppy" markets, not just perfect flats.
"""

import pandas as pd
import numpy as np
from typing import Optional, Dict, List
from strategies.base import BaseStrategy
from app.services.indicators import ta

class BollingerBounceStrategy(BaseStrategy):
    """
    Bollinger Bounce strategy tuned for CHOPPY/VOLATILE ranges.
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
    2. CLOSE ENOUGH IS GOOD ENOUGH: Do not wait for a pixel-perfect touch of the Bollinger Band. If price is in the "Kill Zone" (outer 15% of the bands), TRIGGER THE TRADE.
    3. FADE THE MOVEMENT: If a green candle shoots up to the upper band without volume support, SHORT IT immediately.
    4. IGNORE SMALL SLOPES: Who cares if the EMA50 is slightly tilted? If the price is bouncing between bands, we trade the bounce.
    
    RESPONSE STYLE:
    Aggressive, opportunistic.
    "Kill zone reached - Shorting the pump.", "Dip detected in chop zone - Buying."
    """
    
    def __init__(self, config=None):
        super().__init__(config)
        self.bb_period = self.params.get("bb_period", 20)
        self.bb_std = self.params.get("bb_std", 2.0)
        
        # --- PARAMÈTRES DÉBRIDÉS POUR DÉCLENCHER PLUS SOUVENT ---
        # On monte l'ADX à 45 (Crypto "Choppy" = Range)
        self.adx_threshold = self.params.get("adx_threshold", 45) 
        self.adx_period = self.params.get("adx_period", 14)
        
        # On tolère une pente d'EMA beaucoup plus forte avant de dire "C'est une tendance"
        self.ema50_slope_threshold = self.params.get("ema50_slope_threshold", 0.005) 
        
        self.atr_period = self.params.get("atr_period", 14)
        self.min_rr = self.params.get("min_rr", 1.0) # On accepte 1:1 en range car le winrate est élevé
    
    def is_ranging(self, df: pd.DataFrame) -> tuple[bool, str]:
        """
        Detect if market is tradable as a range (relaxed criteria).
        """
        try:
            # ADX Check
            adx_res = ta.adx(df['high'], df['low'], df['close'], length=self.adx_period)
            current_adx = adx_res['ADX'].iloc[-2]
            
            # Si ADX > 45, c'est vraiment une tendance très forte, on touche pas.
            # Mais entre 25 et 45, c'est souvent du "Chop" tradable en Bounce.
            if current_adx >= self.adx_threshold:
                return False, f"Trend too strong (ADX {current_adx:.1f})"
            
            # EMA Slope Check (Vérifie si ça monte/descend trop vite)
            ema_50 = ta.ema(df['close'], length=50)
            ema_slope = (ema_50.iloc[-1] - ema_50.iloc[-5]) / ema_50.iloc[-5]
            
            # On tolère une pente légère
            if abs(ema_slope) > self.ema50_slope_threshold:
                return False, f"Slope too steep ({ema_slope:.4f})"
            
            return True, f"Choppy/Range confirmed (ADX={current_adx:.1f})"
        
        except Exception as e:
            return False, f"Error detection: {e}"
    
    def generate_signal(self, df: pd.DataFrame, extra_data=None) -> Optional[Dict]:
        """
        Generate signal with RELAXED proximity checks.
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
            
            current_price = df['close'].iloc[-1]
            current_high = df['high'].iloc[-1]
            current_low = df['low'].iloc[-1]
            
            bb_upper = bb['BBU'].iloc[-1]
            bb_lower = bb['BBL'].iloc[-1]
            bb_basis = bb['BBM'].iloc[-1] # Middle Band
            current_atr = atr.iloc[-1]
            
            # Calcul de la largeur du range
            bb_width = bb_upper - bb_lower
            
            # FILTRE DE VOLATILITÉ MINIMALE
            # Si les bandes sont trop serrées (moins de 0.3% de spread), on ne trade pas (frais trop chers)
            if bb_width / current_price < 0.003: 
                return None

            # --- LOGIQUE D'ENTRÉE ASSOUPLIE (PROXIMITY FACTOR) ---
            # On définit une "Kill Zone" : les 15% supérieurs et inférieurs du range
            kill_zone_size = bb_width * 0.15
            
            upper_trigger_zone = bb_upper - kill_zone_size
            lower_trigger_zone = bb_lower + kill_zone_size
            
            # Dynamic TP (On vise le milieu + un petit chouia)
            tp_padding = bb_width * 0.05 
            
            # === SIGNAL LONG ===
            # Si le prix est dans la zone basse (pas besoin de toucher la ligne)
            if current_low <= lower_trigger_zone:
                # On vérifie juste qu'on n'est pas en train de crasher (pas de grosse bougie rouge pleine qui défonce la bande)
                # Idéalement : le prix actuel remonte un peu ou mèche
                
                entry = current_price
                tp = bb_basis + tp_padding
                sl = bb_lower - (current_atr * 1.0) # SL sous la bande
                
                risk = entry - sl
                reward = tp - entry
                
                # Check RR (Relaxed)
                if risk > 0 and (reward / risk) >= 0.9: # On accepte 0.9 car haute probabilité en range
                    return {
                        "signal": "BUY",
                        "sl": sl,
                        "tp": tp,
                        "comment": f"Range Dip Buying (Zone: {lower_trigger_zone:.4f})"
                    }
            
            # === SIGNAL SHORT ===
            # Si le prix est dans la zone haute
            if current_high >= upper_trigger_zone:
                
                entry = current_price
                tp = bb_basis - tp_padding
                sl = bb_upper + (current_atr * 1.0)
                
                risk = sl - entry
                reward = entry - tp
                
                if risk > 0 and (reward / risk) >= 0.9:
                    return {
                        "signal": "SELL",
                        "sl": sl,
                        "tp": tp,
                        "comment": f"Range Top Shorting (Zone: {upper_trigger_zone:.4f})"
                    }
            
            return None
        
        except Exception as e:
            # print(f"Error BB: {e}")
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
            
            # 1. ADX Check
            adx_res = ta.adx(df['high'], df['low'], df['close'], length=self.adx_period)
            adx = adx_res['ADX'].iloc[-1]
            adx_ok = adx < self.adx_threshold
            conditions.append({
                "name": "Régime de Marché (Range)",
                "status": adx_ok,
                "value": ""
            })
            
            # 2. EMA Slope
            ema_50 = ta.ema(df['close'], length=50)
            if len(ema_50) >= 6:
                slope = abs((ema_50.iloc[-1] - ema_50.iloc[-5]) / ema_50.iloc[-5])
                slope_ok = slope <= self.ema50_slope_threshold
                conditions.append({
                    "name": "Pente EMA50",
                    "status": slope_ok,
                    "value": ""
                })
            
            # 3. Kill Zone Proximity
            bb = ta.bbands(df['close'], length=self.bb_period, std=self.bb_std)
            price = df['close'].iloc[-1]
            width = bb['BBU'].iloc[-1] - bb['BBL'].iloc[-1]
            kill_zone = width * 0.15
            
            dist_lower = price - bb['BBL'].iloc[-1]
            dist_upper = bb['BBU'].iloc[-1] - price
            min_dist = min(dist_lower, dist_upper)
            
            # Logic: In zone if close to either band
            in_zone = dist_lower < kill_zone or dist_upper < kill_zone
            conditions.append({
                "name": "Proximité Bande (Kill Zone)",
                "status": in_zone,
                "value": ""
            })
            
            # 4. Volatility Filter
            vol_ratio = width / price
            vol_ok = vol_ratio >= 0.003
            conditions.append({
                "name": "Filtre Volatilité (Spread)",
                "status": vol_ok,
                "value": ""
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
            
            ema_50 = ta.ema(df['close'], length=50)
            slope = abs((ema_50.iloc[-1] - ema_50.iloc[-5]) / ema_50.iloc[-5]) if len(ema_50) >= 6 else 0
            
            bb = ta.bbands(df['close'], length=self.bb_period, std=self.bb_std)
            price = df['close'].iloc[-1]
            width = bb['BBU'].iloc[-1] - bb['BBL'].iloc[-1]
            vol_ratio = width / price
            
            dist_lower = price - bb['BBL'].iloc[-1]
            dist_upper = bb['BBU'].iloc[-1] - price
            min_dist = min(dist_lower, dist_upper)
            
            return {
                "ADX": f"{adx:.1f} vs Max: {self.adx_threshold}",
                "EMA50 Slope": f"{slope:.4f} vs Max: {self.ema50_slope_threshold}",
                "Band Proximity": f"{min_dist/width*100:.1f}% vs Req: <15%",
                "Volatility Spread": f"{vol_ratio*100:.2f}% vs Min: 0.3%"
            }
        except Exception as e:
            return {"Error": str(e)}
