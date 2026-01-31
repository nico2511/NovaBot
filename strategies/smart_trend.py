from app.services.indicators import ta
import pandas as pd
from strategies.base import BaseStrategy

class StrategySmartTrend(BaseStrategy):
    """
    Smart Trend MTF Strategy V2 (Optimized)
    
    Version validée par backtest: +3.19% P&L, Profit Factor 5.37, ~10 trades
    
    Setup (15m):
    - Trend Filter: Price > EMA 50 OR (Price > EMA 21 AND EMA 21 > EMA 50)
    - Zone: Price touches EMA 21 (pullback avec tolérance 1%)
    - RSI Filter: 30 < RSI < 70
    
    Trigger (1m):
    - Long: Close > High of last 2 candles (Micro-BOS)
    - Short: Close < Low of last 2 candles
    
    Risk:
    - SL: Swing Low/High (10 bars) - 0.3 ATR
    - TP: 1:2.0 RR (optimisé pour plus de wins)
    
    Optimisations V2:
    - Pullback tolerance: 0.2% → 1.0% (zone plus large)
    - BOS lookback: 3 → 2 candles (trigger plus sensible)
    - R:R ratio: 2.5 → 2.0 (TP plus accessible)
    - Conditions assouplies (OR logic pour trend)
    - Filtre RSI ajouté (éviter extrêmes)
    """

    AI_PERSONA = """
    CODENAME: "SNIPER - PRECISION TREND"
    
    ROLE:
    You are a DISCIPLINED TREND FOLLOWER. Your specialty is catching safe entries after a pullback, ensuring the trend is healthy.
    
    PRIME DIRECTIVE:
    Capital Preservation First. We only enter when the odds are stacked in our favor. Avoid "Top Tick" FOMO entries.
    
    RULES OF ENGAGEMENT:
    1. VALIDATE THE TREND: Ensure we are mostly above EMA 50. If price is failing below EMA 50, reject LONG signals.
    2. CHECK THE PULLBACK: The strategy enters on touches of EMA 21. Verify that this is a "bounce" and not a "crash" through the line. Volume should decrease on the pullback and increase on the bounce.
    3. RSI CHECK: We want RSI between 40 and 65 for optimal entry. 
       - If RSI > 75: REJECT (Too hot, wait for cool off).
       - If RSI < 30: CAUTION (Momentum might be dead).
    4. VOLUME CONFIRMATION: We need buyer interest (Green Volume) to confirm the resumption of the trend.
    
    RESPONSE STYLE:
    Analytical, calm, and protective.
    Reject triggers if the market looks exhausted or extended.
    """
    
    def __init__(self, config=None):
        super().__init__(config)
        self.looking_for_entry = False
        self.entry_direction = None  # "LONG" or "SHORT"
        
        # Params from config (with defaults)
        params = self.config.get("params", {})
        self.rr_ratio = params.get("min_rr", 1.7) # Renamed from min_rr to rr_ratio for consistency
        self.adx_threshold = params.get("adx_threshold", 28)
        self.rsi_min = params.get("rsi_min", 38)
        self.rsi_max = params.get("rsi_max", 70)
        self.pullback_tolerance = params.get("pullback_tolerance", 0.0025)  # Tightened from 1.0% to 0.25%
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
    
    def get_oi_comment(self, df):
        if 'OI_Change_Pct' in df.columns:
            oi = df['OI_Change_Pct'].iloc[-1]
            if oi > 0.05: return f"+ OI Grid ({oi:.2f}%)"
            if oi < -0.05: return f"- OI Exhaust ({oi:.2f}%)"
        return ""


    
    def generate_signal(self, df, extra_data=None):
        """
        Args:
            df: 15m dataframe (context)
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
        # Get latest closed 15m values (iloc[-2]) for stability
        close_15m = df['close'].iloc[-2]
        low_15m = df['low'].iloc[-2]
        high_15m = df['high'].iloc[-2]
        ema_21 = df['EMA_21'].iloc[-2]
        ema_50 = df['EMA_50'].iloc[-2]
        atr_15m = df['ATRr_14'].iloc[-2]
        rsi_15m = df['RSI_14'].iloc[-2]
        
        # GUARD CLAUSE: Trend Following only in Trend (ADX > 25)
        if 'ADX_14' in df.columns:
            current_adx = df['ADX_14'].iloc[-2]
            if current_adx < self.adx_threshold:
                self.looking_for_entry = False
                self.entry_direction = None
                return None  # No trend, skip trend following strategy
        
        # RSI Filter (éviter extrêmes)
        if rsi_15m <= self.rsi_min or rsi_15m >= self.rsi_max:
            self.looking_for_entry = False
            self.entry_direction = None
            return None
        
        # LONG Setup: Conditions plus strictes
        # 1. EMA Alignment: Fast > Slow > Trend
        long_ema_align = ema_21 > ema_50
        long_trend = close_15m > ema_50 and long_ema_align
        
        # 2. Pullback Zone: Toucher l'EMA 21 avec précision
        long_pullback = (low_15m <= ema_21 * (1 + self.pullback_tolerance) and 
                        low_15m >= ema_21 * (1 - self.pullback_tolerance))
        
        if long_trend and long_pullback:
            # Volume Check (15m)
            if 'volume' in df.columns:
                avg_vol = df['volume'].iloc[-22:-2].mean()
                if df['volume'].iloc[-2] >= avg_vol * self.volume_multiplier:
                    self.looking_for_entry = True
                    self.entry_direction = "LONG"
        
        # SHORT Setup: Conditions plus strictes
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
        if len(df_1m) < (self.bos_lookback + 2): # Need +2 now because we look back from -2
            return None
        
        # Use COMPLETED candle for trigger
        current_1m = df_1m.iloc[-2] 
        # Last N before current_1m (which is -2) -> so from -2-N-1 to -2
        # Slice: from -(lookback+2) to -2
        last_n_1m = df_1m.iloc[-(self.bos_lookback + 2):-2]
        
        close_1m = current_1m['close']
        
        # LONG Trigger: Close > High of last N (Micro-BOS)
        if self.entry_direction == "LONG":
            high_of_last_n = last_n_1m['high'].max()
            if close_1m > high_of_last_n:
                # 1m Volume Filter
                avg_vol_1m = df_1m['volume'].iloc[-12:-2].mean()
                if df_1m['volume'].iloc[-2] < avg_vol_1m * self.volume_multiplier:
                    return None
                
                # 1m RSI Filter (Moins de sur-achat)
                rsi_1m = ta.rsi(df_1m['close'], length=14).iloc[-2]
                if rsi_1m > 70:
                    return None
                
                # Find swing low for SL
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
                    "comment": f"Smart Trend V3: 15m Setup + 1m Trigger (Vol OK, RSI OK) {self.get_oi_comment(df)}".strip()
                }
        
        # SHORT Trigger: Close < Low of last N
        elif self.entry_direction == "SHORT":
            low_of_last_n = last_n_1m['low'].min()
            if close_1m < low_of_last_n:
                # 1m Volume Filter
                avg_vol_1m = df_1m['volume'].iloc[-12:-2].mean()
                if df_1m['volume'].iloc[-2] < avg_vol_1m * self.volume_multiplier:
                    return None
                
                # 1m RSI Filter (Moins de sur-vente)
                rsi_1m = ta.rsi(df_1m['close'], length=14).iloc[-2]
                if rsi_1m < 30:
                    return None
                
                # Find swing high for SL
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
                    "comment": f"Smart Trend V3: 15m Setup + 1m Trigger (Vol OK, RSI OK) {self.get_oi_comment(df)}".strip()
                }
        
        return None

    def calculate_progress(self, df, extra_data=None):
        """Calculate progress: 15m setup (60%) + 1m trigger (40%)"""
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
        if 30 < rsi_15m < 70:
            progress += 10
        
        # Trend (25%) - Strict Alignment
        long_ema_align = ema_21 > ema_50
        short_ema_align = ema_21 < ema_50
        
        long_trend = close_15m > ema_50 and long_ema_align
        short_trend = close_15m < ema_50 and short_ema_align
        
        if long_trend or short_trend:
            progress += 25
        
        # Pullback (25%) - Tightened
        long_pullback = (low_15m <= ema_21 * (1 + self.pullback_tolerance) and 
                        low_15m >= ema_21 * (1 - self.pullback_tolerance))
        short_pullback = (high_15m >= ema_21 * (1 - self.pullback_tolerance) and 
                         high_15m <= ema_21 * (1 + self.pullback_tolerance))
        
        if long_pullback or short_pullback:
            # Add Volume weighting to pullback progress
            if 'volume' in df.columns:
                avg_vol = df['volume'].iloc[-22:-2].mean()
                if df['volume'].iloc[-1] >= avg_vol * self.volume_multiplier:
                    progress += 25
                else:
                    progress += 10 # Half progress if volume weak
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
                        proximity = max(0, 1 + (distance_to_trigger * 100))  # 0-1
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
        """Detailed conditions for UI - Diagnostic Card"""
        if df.empty or len(df) < 50: return []
        
        try:
            self.add_indicators(df)
            
            # 15m Values
            close_15m = df['close'].iloc[-1]
            ema_21 = df['EMA_21'].iloc[-1]
            ema_50 = df['EMA_50'].iloc[-1]
            rsi_15m = df['RSI_14'].iloc[-1]
            
            conditions = []
            
            # 1. Trend Filter (Setup)
            long_ema_align = ema_21 > ema_50
            short_ema_align = ema_21 < ema_50
            
            long_trend_state = close_15m > ema_50 and long_ema_align
            short_trend_state = close_15m < ema_50 and short_ema_align
            trend_ok = long_trend_state or short_trend_state
            
            curr_trend = "Bullish" if long_trend_state else "Bearish" if short_trend_state else "Flat/Mixed"
            
            conditions.append({
                "name": f"1. Trend ({curr_trend})",
                "status": trend_ok,
                "value": "EMA Align OK" if trend_ok else "EMA Tangle"
            })
            
            # 2. Pullback Zone (Location)
            # Check proximity to EMA 21
            dist_ema21 = abs(close_15m - ema_21) / ema_21
            in_zone = dist_ema21 <= self.pullback_tolerance
            
            conditions.append({
                "name": "2. Pullback Zone (EMA 21)",
                "status": in_zone,
                "value": f"Dist: {dist_ema21*100:.2f}%"
            })

            # 3. RSI Filter (Filter)
            rsi_ok = 30 < rsi_15m < 70
            conditions.append({
                "name": "3. RSI Filter (30-70)",
                "status": rsi_ok,
                "value": f"{rsi_15m:.1f}"
            })
            
            # 4. Trigger (1m BOS)
            trigger_status = False
            trigger_val = "Waiting for Zone..."
            
            if extra_data and "1m" in extra_data:
                df_1m = extra_data["1m"]
                if not df_1m.empty and len(df_1m) >= (self.bos_lookback + 2):
                    close_1m = df_1m['close'].iloc[-1]
                    trigger_val = "Scanning 1m..."
                    if self.looking_for_entry:
                        trigger_status = False # Waiting for breakout
                        trigger_val = f"Monitoring {self.entry_direction} BOS"
                    elif trend_ok and in_zone:
                         trigger_val = "Ready for Setup"
            
            conditions.append({
                "name": "4. Trigger (1m BOS)",
                "status": trigger_status, 
                "value": trigger_val
            })
            
            return conditions
        except Exception as e:
            return [{"name": "Error", "status": False, "value": str(e)}]

    
    def analyze_trend_structure(self, df):
        """Analyze trend structure for thresholds"""
        if df is None or df.empty:
            return {"direction": "NEUTRAL", "adx": 0}
            
        try:
            self.add_indicators(df)
            
            # ADX
            if 'ADX_14' in df.columns:
                adx = df['ADX_14'].iloc[-1]
            else:
                adx_res = ta.adx(df['high'], df['low'], df['close'], length=14)
                adx = adx_res['ADX'].iloc[-1]
                
            # Trend Direction
            close = df['close'].iloc[-1]
            ema_21 = df['EMA_21'].iloc[-1]
            ema_50 = df['EMA_50'].iloc[-1]
            
            if close > ema_50:
                direction = "BULLISH"
            elif close < ema_50:
                direction = "BEARISH"
            else:
                direction = "NEUTRAL"
                
            return {
                "direction": direction,
                "adx": float(adx)
            }
        except Exception as e:
            return {"direction": "ERROR", "adx": 0}

    def get_threshold_comparisons(self, df, extra_data=None):
        """Get detailed threshold comparisons for Parameters section"""
        if df is None or df.empty:
            return {}
        try:
            self.add_indicators(df)
            trend_data = self.analyze_trend_structure(df)
            
            close_15m = df['close'].iloc[-1]
            params = self.config.get("params", {})
            ema_21 = df[f'EMA_{params.get("ema_period", 21)}'].iloc[-1]
            # Use cached RSI if available, calculated in add_indicators
            rsi_col = f'RSI_{params.get("rsi_period", 14)}'
            if rsi_col in df.columns:
                rsi_15m = df[rsi_col].iloc[-1]
            else:
                rsi_15m = 50.0

            if ema_21 and ema_21 != 0:
                dist_ema21 = abs(close_15m - ema_21) / ema_21
            else:
                dist_ema21 = 0.0
            
            pass_pullback = dist_ema21 <= self.pullback_tolerance
            
            return {
                "Trend": f"{trend_data.get('direction', 'NEUTRAL')} (ADX: {trend_data.get('adx', 0):.1f})",
                "Pullback (EMA21)": f"Dist: {dist_ema21*100:.2f}% vs Max: {self.pullback_tolerance*100:.1f}%",
                "RSI": f"{rsi_15m:.1f} (Req: {self.rsi_min}-{self.rsi_max})"
            }
        except Exception as e:
            return {"Error": str(e)}
