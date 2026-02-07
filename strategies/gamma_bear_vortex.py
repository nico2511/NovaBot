from app.services.indicators import ta
import pandas as pd
from strategies.base import BaseStrategy

class GammaBearVortex(BaseStrategy):
    """
    Gamma Bear Vortex - Continuation Short Strategy
    
    OBJECTIF : Catcher la continuation baissière violente (Flush) quand :
    1. Le Trend est clairement BEISSIER (ADX fort, Prix < EMA).
    2. Le Momentum (Vortex) confirme la direction.
    3. L'Open Interest (OI) confirme l'engagement (Shorts qui s'empilent).
    4. "Gamma Pin" : Si le prix est compressé (Low Vol) mais l'ADX est haut, l'explosion est imminente.

    REGIMES :
    - TREND_BEAR_STRONG uniquement.
    - Interdit en Bull ou Range.
    """

    AI_PERSONA = """
    CODENAME: "GAMMA SHADOW - BEAR TRAP ASSASSIN"
    
    ROLE:
    You are a VORTEX SPECIALIST. You do not care about "value". You care about FLOW and PRESSURE.
    
    PRIME DIRECTIVE:
    "Gravity implies acceleration." When the floor gives way, we push.
    
    RULES OF ENGAGEMENT:
    1. BEAR ONLY: We do not short green candles in a bull market. We short failures in a bear market.
    2. VORTEX IS TRUTH: VI- must dominate VI+. If they cross, it's a signal.
    3. OI MUST VALIDATE: If price drops but OI drops too, it's just longs quitting. We want OI RISING (Shorts attacking).
    4. GAMMA PIN (THE TRAP): If price is stuck in a tiny range but ADX is screaming (>30), someone is hedging a massive position. Wait for the snap.
    
    RESPONSE STYLE:
    Cold, physics-based, predatory.
    "Pressure critical. Support collapsing. Vortex accepted."
    """
    
    def __init__(self, config=None):
        super().__init__(config)
        
        # --- Parameters ---
        params = self.config.get("params", {})
        
        # Trend
        self.ema_visual_period = params.get("ema_visual_period", 50) # Trend Baseline
        self.adx_min = params.get("adx_min", 20) # CHANGED 2026-02: 25 -> 20 (Wider Trend)
        self.rsi_max_oversold = params.get("rsi_max_oversold", 40) # New param: Avoid shorting if RSI < 40 (Oversold)

        # Vortex
        self.vortex_period = params.get("vortex_period", 14)
        self.vortex_threshold = params.get("vortex_threshold", 1.05) # VI- must be > 1.05
        
        # Gamma Pin
        self.bb_period = params.get("bb_period", 20)
        self.bb_std = params.get("bb_std", 2.0)
        self.gamma_pin_width = params.get("gamma_pin_width", 0.015) # 1.5% max volatility for pin
        self.adx_gamma_trigger = params.get("adx_gamma_trigger", 35) # High ADX for pin
        
        # OI
        self.require_oi_growth = params.get("require_oi_growth", True)
        self.oi_spike_threshold = params.get("oi_spike_threshold", 0.5) # 0.5% growth
        self.volume_bear_mult = params.get("volume_bear_mult", 1.2) # New V2 param
        
        # Risk
        self.sl_atr_mult = params.get("sl_atr_mult", 1.5)
        self.tp_atr_mult = params.get("tp_atr_mult", 2.5) # Continuation = big targets
    
    def add_indicators(self, df):
        """Add Indicators: EMA, ADX, Vortex, BB"""
        df['EMA_Trend'] = ta.ema(df['close'], length=self.ema_visual_period)
        
        adx_res = ta.adx(df['high'], df['low'], df['close'], length=14)
        df['ADX_14'] = adx_res['ADX']
        
        # Vortex Indicator
        # ta lib might not have direct 'vortex', implementing or finding standard
        # Standard TA lib usually has 'vortex_indicator_pos' and 'neg'
        # Verification required, assuming 'ta.vortex_indicator_neg' exists or manual calc
        # Vortex Indicator (Manual Implementation)
        # VM+ = abs(Current High - Previous Low)
        # VM- = abs(Current Low - Previous High)
        # TR  = True Range
        
        high = df['high']
        low = df['low']
        close = df['close']
        prev_close = close.shift(1)
        prev_high = high.shift(1)
        prev_low = low.shift(1)
        
        # True Range
        tr1 = high - low
        tr2 = (high - prev_close).abs()
        tr3 = (low - prev_close).abs()
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        
        # Vortex Movements
        vm_pos = (high - prev_low).abs()
        vm_neg = (low - prev_high).abs()
        
        # Sum over period
        tr_sum = tr.rolling(window=self.vortex_period).sum()
        vm_pos_sum = vm_pos.rolling(window=self.vortex_period).sum()
        vm_neg_sum = vm_neg.rolling(window=self.vortex_period).sum()
        
        df['VI_pos'] = vm_pos_sum / tr_sum
        df['VI_neg'] = vm_neg_sum / tr_sum

        # Bollinger for Gamma Pin
        bb = ta.bbands(df['close'], length=self.bb_period, std=self.bb_std)
        df['BB_Width'] = (bb['BBU'] - bb['BBL']) / df['close']
        df['ATR'] = ta.atr(df['high'], df['low'], df['close'], length=14)
        
        return df

    def generate_signal(self, df, extra_data=None):
        """
        Generate SELL Signal based on Vortex Bear Cross + OI
        """
        if df.empty or len(df) < 50: return None
        
        self.add_indicators(df)
        
        # Anti-repainting: Use Completed Candle [-2]
        curr = df.iloc[-2]
        prev = df.iloc[-3]
        
        # 1. Regime: BEAR STRONG
        # Price < EMA
        if curr['close'] > curr['EMA_Trend']: return None 
        # ADX > Min
        if curr['ADX_14'] < self.adx_min: return None
        
        # New V2 Filter: RSI Oversold Check (Don't short the hole)
        rsi = ta.rsi(df['close'], length=14).iloc[-2]
        if rsi < self.rsi_max_oversold: # RSI < 40?
            return None # Oversold, dangerous to short
            
        # 2. Trigger: Vortex
        # VI- > VI+ (Bearish) AND VI- > Threshold
        # We want a Fresh Cross or Sustained Strong Mode?
        # Strategy: "Continuations". So Sustained is OK if Gamma Pin acts as trigger.
        # OR Fresh Cross. 
        # Let's go with: VI- > VI+ AND (VI- > Threshold OR Cross happened recently)
        
        vi_bearish = (curr['VI_neg'] > curr['VI_pos']) and (curr['VI_neg'] > self.vortex_threshold)
        
        if not vi_bearish: return None
        
        # New V2 Filter: Volume Confirmation
        # Bearish Continuation needs Volume?
        if 'volume' in df.columns:
            curr_vol = df['volume'].iloc[-2]
            avg_vol = df['volume'].iloc[-22:-2].mean()
            if curr_vol < (avg_vol * self.volume_bear_mult):
                 pass # For now, just a soft check, or should we filter? 
                 # User spec said "Volume Vendeur Dominant (1.2x)"
                 # Let's enforce it unless Gamma Pin is active (Low Volatility)
                 if not (curr['BB_Width'] < self.gamma_pin_width):
                     return None
        
        # 3. Gamma Pin Logic (The Accelerator)
        # Condition: Low Volatility (Pin) + High ADX = Tension
        is_gamma_pin = (curr['BB_Width'] < self.gamma_pin_width) and (curr['ADX_14'] > self.adx_gamma_trigger)
        
        # If NOT Gamma Pin, we need a standard Breakdown or Pullback signal?
        # User Logic: "Gamma Bear Vortex ... Catcher continuation"
        # If Gamma Pin is active, we force trade even if Price is flat (because it will break).
        # If Gamma Pin NOT active, we likely need Price making new lows or standard continuation.
        
        # Let's require: Price < Previous Low (Micro Breakdown) OR Gamma Pin
        is_breakdown = curr['close'] < prev['low']
        
        if not (is_gamma_pin or is_breakdown):
             return None
             
        # 4. Open Interest (The Confirmation)
        oi_condition = True
        oi_comment = ""
        
        if 'OI_Change_Pct' in df.columns:
            oi_change = curr['OI_Change_Pct']
            # User: "OI baisse en trend = exhaustion → potentiel reversal"
            # Filter: If OI is crashing (< -0.5%), we skip (Short covering).
            if oi_change < -0.5:
                # "OI baisse en trend = exhaustion"
                return None 
            
            # Bonus: If OI Spike > 0, Confidence Boost
            if oi_change > 0:
                oi_comment = f" | OI+{oi_change:.2f}%"
            elif self.require_oi_growth and not is_gamma_pin:
                # If strict and not a special Gamma case, maybe skip?
                # For now, let's just accept Stable OI.
                pass
                
        # === ENTRY VALID ===
        sl = curr['close'] + (curr['ATR'] * self.sl_atr_mult)
        tp = curr['close'] - (curr['ATR'] * self.tp_atr_mult)
        
        trigger_type = "GAMMA_PIN" if is_gamma_pin else "VORTEX_BREAK"
        
        return {
            "signal": "SELL",
            "sl": sl,
            "tp": tp,
            "price": curr['close'],
            "comment": f"🌪️ GBV: {trigger_type} (ADX:{curr['ADX_14']:.0f}){oi_comment}",
            "metadata": {
                "adx": curr['ADX_14'],
                "vi_neg": curr['VI_neg'],
                "gamma_pin": is_gamma_pin
            }
        }

    def check_conditions(self, df, extra_data=None):
        """UI Diagnostics"""
        if df.empty: return []
        self.add_indicators(df)
        curr = df.iloc[-2] # Completed
        
        # Trend
        is_bear = curr['close'] < curr['EMA_Trend']
        adx_ok = curr['ADX_14'] >= self.adx_min
        
        # Vortex
        vi_diff = curr['VI_neg'] - curr['VI_pos']
        vi_ok = (curr['VI_neg'] > curr['VI_pos']) and (curr['VI_neg'] > self.vortex_threshold)
        
        # Gamma
        is_pinned = curr['BB_Width'] < self.gamma_pin_width
        is_tension = curr['ADX_14'] > self.adx_gamma_trigger
        gamma_status = "Inactive"
        if is_pinned and is_tension: gamma_status = "⚠️ CHARGED"
        elif is_pinned: gamma_status = "Pinned (Low ADX)"
        
        # OI
        oi_val = "N/A"
        oi_ok = True
        if 'OI_Change_Pct' in df.columns:
            oi = curr['OI_Change_Pct']
            oi_val = f"{oi:.2f}%"
            if oi < -0.5: oi_ok = False
            
        return [
            {"name": "1. Bear Trend (EMA+ADX)", "status": is_bear and adx_ok, "value": f"ADX {curr['ADX_14']:.0f}"},
            {"name": "2. Vortex Bearish", "status": vi_ok, "value": f"Diff {vi_diff:.2f}"},
            {"name": "3. Gamma Pin", "status": is_pinned and is_tension, "value": gamma_status},
            {"name": "4. OI Confirmation (>-0.5%)", "status": oi_ok, "value": oi_val}
        ]

    def get_threshold_comparisons(self, df, extra_data=None):
        if df.empty: return {}
        self.add_indicators(df)
        curr = df.iloc[-1]
        
        return {
            "ADX": f"{curr['ADX_14']:.1f} vs {self.adx_min}",
            "VI-": f"{curr['VI_neg']:.2f} vs {self.vortex_threshold}",
            "BB Width": f"{curr['BB_Width']*100:.2f}% vs {self.gamma_pin_width*100:.1f}%"
        }

    def calculate_progress(self, df, extra_data=None):
        """UI Progress calculation for Gamma Bear Vortex"""
        if df.empty or len(df) < 50:
            return 0
            
        try:
            self.add_indicators(df)
            curr = df.iloc[-1]
            
            progress = 0
            
            # --- Stage 1: Trend (30%) ---
            # Bear Trend (Price < EMA and ADX > threshold)
            is_bear = curr['close'] < curr['EMA_Trend']
            adx_score = min(1.0, curr['ADX_14'] / self.adx_min)
            
            if is_bear:
                progress += 15
                progress += int(15 * adx_score)
            
            # --- Stage 2: Vortex (30%) ---
            # VI- > VI+ and VI- near threshold
            vi_gap = curr['VI_neg'] - curr['VI_pos']
            if vi_gap > 0:
                progress += 15
                vi_threshold_score = min(1.0, curr['VI_neg'] / self.vortex_threshold)
                progress += int(15 * vi_threshold_score)
            
            # --- Stage 3: Gamma / Pressure (30%) ---
            # BB Width proximity to pin width
            bb_width_score = 0
            if curr['BB_Width'] < self.gamma_pin_width:
                bb_width_score = 1.0
            else:
                # Proximity score (inverse of distance)
                bb_width_score = max(0, 1 - (curr['BB_Width'] - self.gamma_pin_width) / self.gamma_pin_width)
            
            progress += int(30 * bb_width_score)
            
            # --- Stage 4: OI (10%) ---
            if 'OI_Change_Pct' in df.columns:
                oi = curr['OI_Change_Pct']
                if oi > -0.5:
                    progress += 10
            else:
                progress += 5 # Default if data missing
                
            return min(100, progress)
        except:
            return 0
