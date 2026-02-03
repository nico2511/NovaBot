from strategies.base import BaseStrategy
from app.services.indicators import ta

class ElasticNibblerStrategy(BaseStrategy):
    """
    The Elastic Nibbler Strategy
    ----------------------------
    Type: Reversion Scalp (BTC/ETH Only)
    Timeframe: 1m or 5m
    
    Logic:
    - BB Breakout (Price > Upper or < Lower)
    - RSI Extreme (<20 or >80)
    - Volume Spike (>2x Avg)
    - Filter: ADX > 25 (skip strong trends)
    
    Management (Custom):
    - No fixed TP
    - Trailing SL: 
      - Trigger at +0.15% PnL -> Move SL to Break-Even + Fees (+0.08%)
      - Above +0.30% PnL -> Tight Trail (ATR based or logical step)
    """
    
    def __init__(self, config):
        super().__init__(config)
        self.params = self.config.get("params", {})
    
    # AI Persona for signal validation
    AI_PERSONA = """CODENAME: "ELASTIC NIBBLER - MEAN REVERSION AGGRESSOR"

Tu es un scalper de MEAN REVERSION agressif spécialisé dans les excès de marché.

🎯 TON STYLE: Tu cherches les "élastiques étirés" - quand le prix va TROP LOIN, TROP VITE, il revient.

📈 SIGNAL LONG (Achat):
- Prix SOUS la Bollinger Band basse (3 SD)
- RSI < 20 (survente extrême)
- Volume > 2x moyenne (panique vendeuse)
- ADX < 25 (pas de tendance baissière forte)
→ Le prix va REMONTER vers la moyenne

📉 SIGNAL SHORT (Vente):
- Prix AU-DESSUS de la Bollinger Band haute (3 SD)
- RSI > 80 (surachat extrême)
- Volume > 2x moyenne (euphorie acheteuse)
- ADX < 25 (pas de tendance haussière forte)
→ Le prix va REDESCENDRE vers la moyenne

⚠️ NE REJETTE PAS À CAUSE DE:
- RSI extrême → C'est JUSTEMENT le signal
- Prix loin des moyennes → C'est l'opportunité

✅ APPROUVE SI: Conditions réunies + ADX faible
❌ REJETTE SI: ADX > 25 (tendance trop forte)"""
        
    def generate_signal(self, df, extra_data=None):
        # 0. BTC-Only Restriction (Best-Effort)
        # Check if symbol is provided in extra_data, otherwise infer from price
        # Default to False so it doesn't break other strategies if copied without config
        is_btc_only = self.params.get("is_btc_only", False)
        
        if is_btc_only:
            symbol = None
            if extra_data and isinstance(extra_data, dict):
                symbol = extra_data.get("symbol", "").upper()
            
            # If symbol explicitly provided and not BTC, skip
            if symbol and symbol != "BTC":
                return None
            
            # Fallback: If no symbol provided, infer from price (BTC > $5000)
            if not symbol:
                current_price = df['close'].iloc[-1]
                if current_price < 5000:  # Likely ETH or other, not BTC
                    return None
                    
        # 0B. Time Filter (Grok Recommendation) - Avoid Asia Low Liq (02:00-06:00 UTC)
        from datetime import datetime
        current_hour = datetime.utcnow().hour
        if 2 <= current_hour < 6:
            return None

        # 1. Indicators
        close = df['close']
        high = df['high']
        low = df['low']
        volume = df['volume']
        
        # Bollinger Bands (20, 2.2) - CHANGED 2026-02: Relaxed 3.0 -> 2.2
        bb_period = self.params.get("bb_length", 20)
        bb_std = self.params.get("bb_std", 2.2)
        
        bb_df = ta.bbands(close, length=bb_period, std=bb_std)
        bb_upper = bb_df['BBU']
        bb_lower = bb_df['BBL']
        
        # RSI (14)
        rsi_period = self.params.get("rsi_period", 14)
        rsi = ta.rsi(close, length=rsi_period)
        
        # Volume Avg (using 50 periods like others)
        vol_avg = ta.sma(volume, length=50)
        
        # ADX (for filtering strong trends)
        adx_df = ta.adx(high, low, close, length=14)
        adx = adx_df['ADX'].iloc[-1]
        
        # ATR for volatility-adapted SL/TP (Grok Phase 2)
        atr = ta.atr(high, low, close, length=14).iloc[-1]
        
        # Current Values
        current_close = close.iloc[-1]
        current_rsi = rsi.iloc[-1]
        current_vol = volume.iloc[-1]
        current_vol_avg = vol_avg.iloc[-1]
        
        upper_band = bb_upper.iloc[-1]
        lower_band = bb_lower.iloc[-1]
        
        # PARAMS
        entry_vol_mult = self.params.get("volume_multiplier", 1.5) # CHANGED 2026-02: 1.8 -> 1.5
        adx_limit = self.params.get("adx_threshold", 25) # Updated name
        
        # 2. Conditions
        # A. Volume Spike
        # Avoid division by zero
        if current_vol_avg == 0: return None
        is_vol_spike = current_vol > (current_vol_avg * entry_vol_mult)
        
        # New Filter: Avoid massive spikes (>5x) often indicating trend continuation (Grok Phase 3)
        if current_vol > (current_vol_avg * 5.0):
            return None
        
        # B. ADX Filter (Skip if trend is too strong)
        # User said: "Skip si ADX > 25" -- Keeping 25 as hard limit for Nibbler
        if adx > adx_limit:
            return None
        
        # C. BB Width Filter - Skip dead ranges (Grok Phase 2)
        bb_width_pct = (upper_band - lower_band) / current_close * 100
        min_bb_width = self.params.get("min_bb_width_pct", 0.5)  # CHANGED 2026-02: 0.7 -> 0.5
        if bb_width_pct < min_bb_width:
            return None
        
        # ATR-based SL/TP (Grok Phase 3 - Improved R:R)
        # SL reduced to 1.5 (was 1.8), TP increased to 2.0 (was 1.2)
        # User requested 1.4 / 2.2 for final
        sl_atr_mult = self.params.get("sl_atr_mult", 1.4)
        tp_atr_mult = self.params.get("tp_atr_mult", 2.0)
        
        sl_distance = atr * sl_atr_mult
        tp_distance = atr * tp_atr_mult
        
        # Partial targets metadata (for future execution support)
        percentage_targets = [
            {"pct": 0.5, "multiplier": 1.2},   # 50% at +1.2 ATR
            {"pct": 0.3, "multiplier": 1.8}    # 30% at +1.8 ATR
        ]
            
        # D. LONG Setup
        # Price < BB Lower AND RSI < 28 (Compromise)
        # CHANGED 2026-02: RSI 24 -> 28
        rsi_min = self.params.get("rsi_min", 28)
        if current_close < lower_band and current_rsi < rsi_min and is_vol_spike:
            sl_price = current_close - sl_distance
            tp_price = current_close + tp_distance
            return {
                "signal": "BUY",
                "price": current_close,
                "sl": sl_price,
                "tp": tp_price,
                "metadata": {
                    "reason": f"BB Breakout (Low V2) + RSI {current_rsi:.1f} + Vol {current_vol/current_vol_avg:.1f}x",
                    "adx": adx,
                    "atr": atr,
                    "bb_width": bb_width_pct,
                    "partial_targets": percentage_targets
                }
            }
            
        # E. SHORT Setup
        # Price > BB Upper AND RSI > 72 (Compromise)
        # CHANGED 2026-02: RSI 76 -> 72
        rsi_max = self.params.get("rsi_max", 72)
        if current_close > upper_band and current_rsi > rsi_max and is_vol_spike:
            sl_price = current_close + sl_distance
            tp_price = current_close - tp_distance
            return {
                "signal": "SELL",
                "price": current_close,
                "sl": sl_price,
                "tp": tp_price,
                "metadata": {
                    "reason": f"BB Breakout (High V2) + RSI {current_rsi:.1f} + Vol {current_vol/current_vol_avg:.1f}x",
                    "adx": adx,
                    "atr": atr,
                    "bb_width": bb_width_pct,
                    "partial_targets": percentage_targets
                }
            }
            
        return None

    def manage_trade(self, trade, current_price, df=None, extra_data=None):
        """
        Custom Trailing Logic for Elastic Nibbler (Tightened & Dynamic ATR-based)
        """
        if not trade: return None
        
        entry_price = trade.get("entry")
        side = trade.get("side")
        sl_price = trade.get("sl")
        
        if not entry_price: return None
        
        # Calculate ATR for dynamic trailing
        atr = 0
        if df is not None and not df.empty:
            try:
                atr_series = ta.atr(df['high'], df['low'], df['close'], length=14)
                atr = atr_series.iloc[-1]
            except Exception:
                pass
        
        # Fallback if no ATR (use fixed % approx 0.2%)
        # But we really want ATR. If fails, we might just default to previous fixed logic or skip.
        if atr == 0:
            # Fallback to metadata ATR if available
            atr = trade.get("metadata", {}).get("atr", current_price * 0.002)

        # Dynamic Trailing Levels (ATR Multipliers) - Grok Phase 3 Aggressive
        # Early activation and tightening trail distances
        
        # Thresholds in price distance (lower activation)
        dist_activation = atr * 0.4
        dist_level_2 = atr * 0.9
        dist_level_3 = atr * 1.6
        
        updates = {}
        target_sl = None

        if side == "BUY":
            pnl = current_price - entry_price
            
            # Secure Fees First (Fixed small amount)
            min_profit_dist = entry_price * 0.0008
            if pnl > min_profit_dist:
                be_sl = entry_price * 1.0004
                if not sl_price or be_sl > sl_price:
                    target_sl = be_sl

            # ATR Trailing Logic (Phase 3: Tighter as profit increases)
            trail_dist = None
            if pnl >= dist_level_3:
                trail_dist = atr * 0.7   # Very tight at high profit
            elif pnl >= dist_level_2:
                trail_dist = atr * 1.0
            elif pnl >= dist_activation:
                trail_dist = atr * 1.4   # Wider at start
            
            if trail_dist:
                dynamic_sl = current_price - trail_dist
                # Take the higher of BE SL or Dynamic SL
                if target_sl is None or dynamic_sl > target_sl:
                    target_sl = dynamic_sl

            if target_sl and (not sl_price or target_sl > sl_price):
                updates["sl"] = target_sl
                    
        else: # SELL
            pnl = entry_price - current_price
            
            # Secure Fees
            min_profit_dist = entry_price * 0.0008
            if pnl > min_profit_dist:
                be_sl = entry_price * 0.9996
                if not sl_price or be_sl < sl_price:
                    target_sl = be_sl

            # ATR Trailing Logic (Phase 3)
            trail_dist = None
            if pnl >= dist_level_3:
                trail_dist = atr * 0.7
            elif pnl >= dist_level_2:
                trail_dist = atr * 1.0
            elif pnl >= dist_activation:
                trail_dist = atr * 1.4
                
            if trail_dist:
                dynamic_sl = current_price + trail_dist
                # Take the lower of BE SL or Dynamic SL (for SHORT)
                if target_sl is None or dynamic_sl < target_sl:
                    target_sl = dynamic_sl

            if target_sl and (not sl_price or target_sl < sl_price):
                updates["sl"] = target_sl
                     
        return updates if updates else {}

    def calculate_progress(self, df, extra_data=None):
        """
        Returns detailed progress of the strategy triggers for monitoring.
        Stages:
        1. Context (ADX, BB Width) - Is the market environment right?
        2. Price Extension (Bollinger) - Is price at the extremes?
        3. Trigger (RSI, Volume) - Is the reversal signal valid?
        """
        try:
            # Re-calculate indicators (duplicated from generate_signal for isolation)
            # This ensures monitoring doesn't interfere with main loop if implemented differently
            # But ideally we'd reuse calculated values. For now, re-calc is safer for stateless monitor.
            
            close = df['close']
            high = df['high']
            low = df['low']
            volume = df['volume']
            
            # --- 1. Indicators ---
            bb_period = self.params.get("bb_period", 20)
            bb_std = self.params.get("bb_std", 3.0)
            bb_df = ta.bbands(close, length=bb_period, std=bb_std)
            upper = bb_df['BBU'].iloc[-1]
            lower = bb_df['BBL'].iloc[-1]
            
            rsi = ta.rsi(close, length=self.params.get("rsi_period", 14)).iloc[-1]
            
            vol_avg = ta.sma(volume, length=50).iloc[-1]
            current_vol = volume.iloc[-1]
            
            adx_df = ta.adx(high, low, close, length=14)
            adx = adx_df['ADX'].iloc[-1]
            
            current_price = close.iloc[-1]
            bb_width_pct = (upper - lower) / current_price * 100
            
            # --- Thresholds ---
            adx_limit = self.params.get("adx_threshold", 25)
            min_bb_width = self.params.get("min_bb_width_pct", 0.7)
            entry_vol_mult = self.params.get("volume_multiplier", 1.8)
            
            # --- Stage Logic ---
            stages = []
            
            # Stage 1: Context (Filter)
            # Status: PASS if ADX < Limit AND BB Width > Min
            s1_pass = (adx < adx_limit) and (bb_width_pct > min_bb_width)
            s1_details = f"ADX: {adx:.1f} (Max {adx_limit}) | Width: {bb_width_pct:.2f}% (Min {min_bb_width}%)"
            stages.append({
                "name": "1. Market Regime",
                "status": "PASS" if s1_pass else "FAIL",
                "details": s1_details,
                "metrics": {
                    "adx": {"value": round(adx, 1), "threshold": adx_limit, "op": "<"},
                    "bb_width": {"value": round(bb_width_pct, 2), "threshold": min_bb_width, "op": ">"}
                }
            })
            
            # Stage 2: Price Extension (Bollinger)
            # Check proximity to bands. 
            # If Price < Lower (Long Setup) OR Price > Upper (Short Setup)
            dist_lower = ((current_price - lower) / lower) * 100
            dist_upper = ((current_price - upper) / upper) * 100
            
            is_below_lower = current_price < lower
            is_above_upper = current_price > upper
            
            s2_status = "NEUTRAL"
            s2_details = "Price inside bands"
            
            if is_below_lower:
                s2_status = "READY (LONG)"
                s2_details = f"Price BELOW Lower Band ({dist_lower:.2f}%)"
            elif is_above_upper:
                s2_status = "READY (SHORT)"
                s2_details = f"Price ABOVE Upper Band (+{dist_upper:.2f}%)"
            else:
                # Proximity warning (e.g. within 0.5%)
                if abs(dist_lower) < 0.5: s2_details = f"Approaching Lower ({dist_lower:.2f}%)"
                elif abs(dist_upper) < 0.5: s2_details = f"Approaching Upper (+{dist_upper:.2f}%)"
            
            stages.append({
                "name": "2. Price Extension",
                "status": s2_status if (is_below_lower or is_above_upper) else "WAIT",
                "details": s2_details,
                 "metrics": {
                    "dist_lower": {"value": round(dist_lower, 2), "threshold": 0, "op": "<"},
                    "dist_upper": {"value": round(dist_upper, 2), "threshold": 0, "op": ">"}
                }
            })
            
            # Stage 3: Trigger (RSI & Volume)
            # Dependent on Stage 2 Direction
            s3_status = "WAIT"
            s3_details = []
            
            vol_ratio = current_vol / vol_avg if vol_avg > 0 else 0
            is_vol_ok = (vol_ratio > entry_vol_mult) and (vol_ratio < 5.0)
            
            if is_below_lower: # LONG Context
                is_rsi_ok = rsi < 24
                s3_details.append(f"RSI: {rsi:.1f} (Req < 24)")
            elif is_above_upper: # SHORT Context
                is_rsi_ok = rsi > 76
                s3_details.append(f"RSI: {rsi:.1f} (Req > 76)")
            else:
                is_rsi_ok = False
                s3_details.append(f"RSI: {rsi:.1f} (Wait for Band)")

            s3_details.append(f"Vol: {vol_ratio:.1f}x (Req > {entry_vol_mult}x)")
            
            if is_vol_ok and is_rsi_ok:
                s3_status = "TRIGGER!"
            elif is_vol_ok or is_rsi_ok:
                s3_status = "PARTIAL"
            
            stages.append({
                "name": "3. Trigger",
                "status": s3_status,
                "details": " | ".join(s3_details),
                "metrics": {
                    "rsi": {"value": round(rsi, 1), "threshold": "24/76", "op": "extremes"},
                    "volume": {"value": round(vol_ratio, 2), "threshold": entry_vol_mult, "op": ">"}
                }
            })
            
            # Overall Readiness Score (0-100)
            score = 0
            if s1_pass: score += 20
            if is_below_lower or is_above_upper: score += 40
            if is_rsi_ok: score += 20
            if is_vol_ok: score += 20
            
            return {
                "strategy": "Elastic Nibbler",
                "score": score,
                "stages": stages
            }
            
        except Exception as e:
            return {
                "strategy": "Elastic Nibbler",
                "error": str(e),
                "stages": []
            } 
