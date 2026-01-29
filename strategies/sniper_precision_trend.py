from app.services.indicators import ta
import pandas as pd
from strategies.base import BaseStrategy

class SniperPrecisionTrend(BaseStrategy):
    """
    SNIPER - PRECISION TREND (Smart Trend MTF V3)
    
    Master Prompt Persona Integration:
    - Disciplined, protective, capital preservation first
    - Rejects 90% of setups if odds not favorable
    - Avoids FOMO entries at top tick
    
    Setup (15m):
    - Trend Filter: Price > EMA 50 OR (Price > EMA 21 AND EMA 21 > EMA 50)
    - Pullback Zone: Price touches EMA 21 (tolerance configurable)
    - RSI Filter: 38-70 (optimal range, rejects extremes)
    - ADX Filter: > 28 (trend strength) AND rising
    - Volume: > 1.3x average (buyer/seller interest)
    
    Trigger (1m):
    - BOS (Break of Structure): Close > High of last N candles (LONG)
    - Volume 1m: > 1.3x average
    - RSI 1m: < 70 (LONG) / > 30 (SHORT) - avoid extremes
    
    Risk Management:
    - SL: Swing low/high (10 bars) +/- 0.35 ATR
    - TP: 2:1 R:R minimum (configurable)
    - Capital risk: 1-2% max per trade
    
    Checklist (from Master Prompt):
    1. Trend sain et aligné (EMA + ADX) ?
    2. Pullback valide (zone + volume decrease/increase) ?
    3. RSI optimal, pas d'extrêmes ?
    4. Trigger BOS confirmé sans FOMO, avec volume/RSI 1m OK ?
    5. R:R >= 2:1 avec SL/TP réalistes ?
    """
    
    AI_PERSONA = """
    CODENAME: "SNIPER - PRECISION TREND"
    
    ROLE:
    You are a DISCIPLINED TREND FOLLOWER and CAPITAL PROTECTOR. Your specialty is catching safe entries 
    after pullbacks in healthy trends. You reject 90% of setups if the odds are not stacked in our favor.
    
    PRIME DIRECTIVE:
    Capital Preservation First. We only enter when the trend is healthy, pullback is validated, 
    and trigger is confirmed. Avoid "Top Tick" FOMO entries.
    
    RULES OF ENGAGEMENT:
    1. VALIDATE THE TREND: Ensure price is mostly above EMA 50. If price is failing below EMA 50, 
       reject LONG signals. ADX must be > 28 AND rising (not crashing).
    
    2. CHECK THE PULLBACK: We enter on touches of EMA 21. Verify this is a "bounce" and not a "crash" 
       through the line. Volume should decrease on pullback and increase on bounce.
    
    3. RSI CHECK: We want RSI between 40 and 65 for optimal entry.
       - If RSI > 75: REJECT (Too hot, wait for cool off)
       - If RSI < 30: REJECT (Momentum might be dead)
    
    4. VOLUME CONFIRMATION: We need buyer interest (Green Volume for LONG, Red for SHORT) to confirm 
       the resumption of the trend.
    
    5. TRIGGER CONFIRMATION: 1m Break of Structure (BOS) must be clean, with volume spike and RSI not extreme.
    
    CHECKLIST (Answer OUI/NON before approval):
    - Trend sain et aligné (EMA + ADX) ?
    - Pullback valide (zone + volume) ?
    - RSI optimal (38-70 on 15m) ?
    - Trigger BOS confirmé (1m) ?
    - R:R >= 2:1 ?
    
    RESPONSE STYLE:
    Analytical, calm, and protective. Reject triggers if the market looks exhausted or extended.
    Always cite specific values (ADX, RSI, Volume ratio) in your reasoning.
    
    DISCLAIMER:
    "Ceci n'est pas un conseil d'investissement – backteste et valide par toi-même."
    """
    
    def __init__(self, config=None):
        super().__init__(config)
        self.looking_for_entry = False
        self.entry_direction = None  # "LONG" or "SHORT"
        
        # Params from config (with defaults from master prompt)
        params = self.config.get("params", {})
        self.rr_ratio = params.get("rr_ratio", 2.0)  # 2:1 R:R minimum
        self.adx_threshold = params.get("adx_threshold", 28)
        self.rsi_min = params.get("rsi_min", 38)
        self.rsi_max = params.get("rsi_max", 70)
        self.pullback_tolerance = params.get("pullback_tolerance", 0.0025)  # 0.25%
        self.bos_lookback = params.get("bos_lookback", 3)
        self.sl_atr_mult = params.get("sl_atr_mult", 0.35)
        self.volume_multiplier = params.get("volume_multiplier", 1.3)
    
    def add_indicators(self, df):
        """Add indicators to 15m dataframe"""
        df['EMA_21'] = ta.ema(df['close'], length=21)
        df['EMA_50'] = ta.ema(df['close'], length=50)
        df['ATRr_14'] = ta.atr(df['high'], df['low'], df['close'], length=14)
        df['RSI_14'] = ta.rsi(df['close'], length=14)
        return df
    
    def generate_signal(self, df, extra_data=None):
        """
        Generate signal using MTF logic (15m setup + 1m trigger)
        
        Args:
            df: 15m dataframe (setup)
            extra_data: dict with {"1m": df_1m} (trigger)
        """
        if df.empty or len(df) < 50:
            return None
        
        # Get 1m data
        if not extra_data or "1m" not in extra_data:
            return None
        
        df_1m = extra_data["1m"]
        if df_1m.empty or len(df_1m) < 5:
            return None
        
        # Add indicators to 15m
        self.add_indicators(df)
        
        # === STEP 1: Setup Check (15m) ===
        # Use confirmed candle (iloc[-2]) for stability
        close_15m = df['close'].iloc[-2]
        low_15m = df['low'].iloc[-2]
        high_15m = df['high'].iloc[-2]
        ema_21 = df['EMA_21'].iloc[-2]
        ema_50 = df['EMA_50'].iloc[-2]
        atr_15m = df['ATRr_14'].iloc[-2]
        rsi_15m = df['RSI_14'].iloc[-2]
        
        # ADX Filter (Trend Strength + Rising)
        if 'ADX_14' in df.columns:
            current_adx = df['ADX_14'].iloc[-2]
            prev_adx = df['ADX_14'].iloc[-3]
            adx_rising = current_adx >= prev_adx
            
            if current_adx < self.adx_threshold:
                self.looking_for_entry = False
                self.entry_direction = None
                return None  # No trend, skip
            
            # SNIPER RULE: ADX must be rising (not crashing)
            if not adx_rising:
                self.looking_for_entry = False
                self.entry_direction = None
                return None
        
        # RSI Filter (Avoid extremes)
        if rsi_15m <= self.rsi_min or rsi_15m >= self.rsi_max:
            self.looking_for_entry = False
            self.entry_direction = None
            return None
        
        # === LONG Setup ===
        # 1. EMA Alignment: EMA21 > EMA50
        long_ema_align = ema_21 > ema_50
        long_trend = close_15m > ema_50 and long_ema_align
        
        # 2. Pullback Zone: Touch EMA 21 with precision
        long_pullback = (low_15m <= ema_21 * (1 + self.pullback_tolerance) and 
                        low_15m >= ema_21 * (1 - self.pullback_tolerance))
        
        if long_trend and long_pullback:
            # Volume Check (15m)
            if 'volume' in df.columns:
                avg_vol = df['volume'].iloc[-22:-2].mean()
                if df['volume'].iloc[-2] >= avg_vol * self.volume_multiplier:
                    self.looking_for_entry = True
                    self.entry_direction = "LONG"
        
        # === SHORT Setup ===
        # 1. EMA Alignment
        short_ema_align = ema_21 < ema_50
        short_trend = close_15m < ema_50 and short_ema_align
        
        # 2. Pullback Zone
        short_pullback = (high_15m >= ema_21 * (1 - self.pullback_tolerance) and 
                         high_15m <= ema_21 * (1 + self.pullback_tolerance))
        
        if short_trend and short_pullback:
            # Volume Check (15m)
            if 'volume' in df.columns:
                avg_vol = df['volume'].iloc[-22:-2].mean()
                if df['volume'].iloc[-2] >= avg_vol * self.volume_multiplier:
                    self.looking_for_entry = True
                    self.entry_direction = "SHORT"
        
        # Cancel if trend broken
        if self.entry_direction == "LONG" and close_15m < ema_50 and ema_21 < ema_50:
            self.looking_for_entry = False
            self.entry_direction = None
        elif self.entry_direction == "SHORT" and close_15m > ema_50 and ema_21 > ema_50:
            self.looking_for_entry = False
            self.entry_direction = None
        
        # === STEP 2: Trigger Check (1m) ===
        if not self.looking_for_entry:
            return None
        
        # Get latest 1m values
        if len(df_1m) < (self.bos_lookback + 2):
            return None
        
        # Use COMPLETED candle for trigger
        current_1m = df_1m.iloc[-2]
        last_n_1m = df_1m.iloc[-(self.bos_lookback + 2):-2]
        
        close_1m = current_1m['close']
        
        # === LONG Trigger: BOS (Break of Structure) ===
        if self.entry_direction == "LONG":
            high_of_last_n = last_n_1m['high'].max()
            if close_1m > high_of_last_n:
                # 1m Volume Filter
                avg_vol_1m = df_1m['volume'].iloc[-12:-2].mean()
                if df_1m['volume'].iloc[-2] < avg_vol_1m * self.volume_multiplier:
                    return None
                
                # 1m RSI Filter (Avoid overbought)
                rsi_1m = ta.rsi(df_1m['close'], length=14).iloc[-2]
                if rsi_1m > 70:
                    return None
                
                # Calculate SL/TP
                swing_low = df_1m.tail(10)['low'].min()
                sl = swing_low - (self.sl_atr_mult * atr_15m)
                risk = close_1m - sl
                tp = close_1m + (self.rr_ratio * risk)
                
                # Reset state
                self.looking_for_entry = False
                self.entry_direction = None
                
                return {
                    "signal": "BUY",
                    "sl": sl,
                    "tp": tp,
                    "price": close_1m,
                    "comment": f"SNIPER: 15m Setup + 1m BOS (ADX OK, RSI {rsi_15m:.1f}, Vol OK)"
                }
        
        # === SHORT Trigger: BOS ===
        elif self.entry_direction == "SHORT":
            low_of_last_n = last_n_1m['low'].min()
            if close_1m < low_of_last_n:
                # 1m Volume Filter
                avg_vol_1m = df_1m['volume'].iloc[-12:-2].mean()
                if df_1m['volume'].iloc[-2] < avg_vol_1m * self.volume_multiplier:
                    return None
                
                # 1m RSI Filter (Avoid oversold)
                rsi_1m = ta.rsi(df_1m['close'], length=14).iloc[-2]
                if rsi_1m < 30:
                    return None
                
                # Calculate SL/TP
                swing_high = df_1m.tail(10)['high'].max()
                sl = swing_high + (self.sl_atr_mult * atr_15m)
                risk = sl - close_1m
                tp = close_1m - (self.rr_ratio * risk)
                
                # Reset state
                self.looking_for_entry = False
                self.entry_direction = None
                
                return {
                    "signal": "SELL",
                    "sl": sl,
                    "tp": tp,
                    "price": close_1m,
                    "comment": f"SNIPER: 15m Setup + 1m BOS (ADX OK, RSI {rsi_15m:.1f}, Vol OK)"
                }
        
        return None

    def calculate_progress(self, df, extra_data=None):
        """Calculate progress: Trend (25%) + Pullback (25%) + RSI (10%) + Trigger (40%)"""
        if df.empty or len(df) < 50:
            return 0
        
        self.add_indicators(df)
        
        # Get latest 15m values
        close_15m = df['close'].iloc[-1]
        low_15m = df['low'].iloc[-1]
        high_15m = df['high'].iloc[-1]
        ema_21 = df['EMA_21'].iloc[-1]
        ema_50 = df['EMA_50'].iloc[-1]
        rsi_15m = df['RSI_14'].iloc[-1]
        
        progress = 0
        
        # RSI Filter (10%)
        if self.rsi_min < rsi_15m < self.rsi_max:
            progress += 10
        
        # Trend (25%) - Strict Alignment
        long_ema_align = ema_21 > ema_50
        short_ema_align = ema_21 < ema_50
        
        long_trend = close_15m > ema_50 and long_ema_align
        short_trend = close_15m < ema_50 and short_ema_align
        
        if long_trend or short_trend:
            progress += 25
        
        # Pullback (25%)
        long_pullback = (low_15m <= ema_21 * (1 + self.pullback_tolerance) and 
                        low_15m >= ema_21 * (1 - self.pullback_tolerance))
        short_pullback = (high_15m >= ema_21 * (1 - self.pullback_tolerance) and 
                         high_15m <= ema_21 * (1 + self.pullback_tolerance))
        
        if long_pullback or short_pullback:
            # Add Volume weighting
            if 'volume' in df.columns:
                avg_vol = df['volume'].iloc[-22:-2].mean()
                if df['volume'].iloc[-1] >= avg_vol * self.volume_multiplier:
                    progress += 25
                else:
                    progress += 10  # Half progress if volume weak
            else:
                progress += 25
        
        # Trigger (40%) - Requires 1m data
        if extra_data and "1m" in extra_data:
            df_1m = extra_data["1m"]
            if not df_1m.empty and len(df_1m) >= (self.bos_lookback + 1):
                current_1m = df_1m.iloc[-1]
                last_n_1m = df_1m.iloc[-(self.bos_lookback + 1):-1]
                
                close_1m = current_1m['close']
                high_of_last_n = last_n_1m['high'].max()
                low_of_last_n = last_n_1m['low'].min()
                
                # Distance to trigger
                if long_trend and long_pullback:
                    distance_to_trigger = (close_1m - high_of_last_n) / high_of_last_n
                    if distance_to_trigger > 0:
                        progress += 40  # Triggered
                    else:
                        # Partial progress based on proximity
                        proximity = max(0, 1 + (distance_to_trigger * 100))
                        progress += int(40 * proximity)
                
                elif short_trend and short_pullback:
                    distance_to_trigger = (low_of_last_n - close_1m) / low_of_last_n
                    if distance_to_trigger > 0:
                        progress += 40  # Triggered
                    else:
                        proximity = max(0, 1 + (distance_to_trigger * 100))
                        progress += int(40 * proximity)
        
        return min(100, progress)

    def check_conditions(self, df, extra_data=None):
        """Detailed conditions for UI - SNIPER Checklist"""
        if df.empty or len(df) < 50:
            return []
        
        try:
            self.add_indicators(df)
            
            # 15m Values
            close_15m = df['close'].iloc[-1]
            ema_21 = df['EMA_21'].iloc[-1]
            ema_50 = df['EMA_50'].iloc[-1]
            rsi_15m = df['RSI_14'].iloc[-1]
            
            conditions = []
            
            # 1. Trend sain et aligné (EMA + ADX)
            long_ema_align = ema_21 > ema_50
            short_ema_align = ema_21 < ema_50
            
            long_trend_state = close_15m > ema_50 and long_ema_align
            short_trend_state = close_15m < ema_50 and short_ema_align
            trend_ok = long_trend_state or short_trend_state
            
            curr_trend = "Bullish" if long_trend_state else "Bearish" if short_trend_state else "Flat/Mixed"
            
            # Check ADX
            adx_status = "?"
            if 'ADX_14' in df.columns:
                adx_val = df['ADX_14'].iloc[-1]
                adx_status = f"ADX {adx_val:.1f}"
            
            conditions.append({
                "name": f"1. Trend sain ({curr_trend})",
                "status": trend_ok,
                "value": adx_status
            })
            
            # 2. Pullback valide (zone + volume)
            dist_ema21 = abs(close_15m - ema_21) / ema_21
            in_zone = dist_ema21 <= self.pullback_tolerance
            
            vol_status = "?"
            if 'volume' in df.columns:
                avg_vol = df['volume'].iloc[-22:-2].mean()
                vol_ratio = df['volume'].iloc[-1] / avg_vol if avg_vol > 0 else 0
                vol_status = f"Vol {vol_ratio:.2f}x"
            
            conditions.append({
                "name": "2. Pullback valide (EMA21)",
                "status": in_zone,
                "value": f"Dist {dist_ema21*100:.2f}% | {vol_status}"
            })

            # 3. RSI optimal (38-70)
            rsi_ok = self.rsi_min < rsi_15m < self.rsi_max
            conditions.append({
                "name": f"3. RSI optimal ({self.rsi_min}-{self.rsi_max})",
                "status": rsi_ok,
                "value": f"{rsi_15m:.1f}"
            })
            
            # 4. Trigger BOS confirmé (1m)
            trigger_status = False
            trigger_val = "Waiting for Zone..."
            
            if extra_data and "1m" in extra_data:
                df_1m = extra_data["1m"]
                if not df_1m.empty and len(df_1m) >= (self.bos_lookback + 2):
                    trigger_val = "Scanning 1m..."
                    if self.looking_for_entry:
                        trigger_status = False
                        trigger_val = f"Monitoring {self.entry_direction} BOS"
                    elif trend_ok and in_zone:
                        trigger_val = "Ready for Setup"
            
            conditions.append({
                "name": "4. Trigger BOS (1m)",
                "status": trigger_status,
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
            
            close_15m = df['close'].iloc[-1]
            ema_21 = df['EMA_21'].iloc[-1]
            rsi_15m = df['RSI_14'].iloc[-1]
            
            # ADX
            adx_val = 0
            if 'ADX_14' in df.columns:
                adx_val = df['ADX_14'].iloc[-1]
            
            # Pullback distance
            dist_ema21 = abs(close_15m - ema_21) / ema_21 if ema_21 != 0 else 0
            
            return {
                "ADX": f"{adx_val:.1f} (Min: {self.adx_threshold})",
                "RSI": f"{rsi_15m:.1f} (Range: {self.rsi_min}-{self.rsi_max})",
                "Pullback (EMA21)": f"Dist: {dist_ema21*100:.2f}% (Max: {self.pullback_tolerance*100:.2f}%)",
                "R:R Ratio": f"{self.rr_ratio}:1"
            }
        except Exception as e:
            return {"Error": str(e)}
