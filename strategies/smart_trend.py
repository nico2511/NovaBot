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
        CODENAME: "VECTOR ALPHA - MOMENTUM"
        
        ROLE:
        You are an AGGRESSIVE MOMENTUM TRADER. Your specialty is capturing "Parabolic Runs".
        
        PRIME DIRECTIVE:
        Never miss a vertical pump. Your enemy is not loss; it is inaction during a massive move.
        
        RULES OF ENGAGEMENT (OVERRIDE STANDARD SAFETY):
        1. NO PULLBACK WAITING: If price is blasting away from EMA20, this is a sign of STRENGTH, not a need for retracement. Do NOT wait for a dip. BUY THE BREAKOUT.
        2. RSI IS FUEL: An RSI between 70 and 85 is NOT a sell signal. It is the "Power Zone". If RSI > 70 and price is surging, you MUST validate the entry.
        3. PRICE ACTION IS KING: If price breaks a resistance with speed, ignore low volume or other divergences. The tape doesn't lie.
        4. RISK MANAGEMENT: Do not reject a trade because the Stop-Loss is too wide. Instead, validate the trade but instruct to REDUCE POSITION SIZE (Risk parity).
        
        RESPONSE STYLE:
        Direct, short, and decisive. 
        If you see a green impulse candle, shout "GO". Do not look for excuses to sit out.
        Only reject if there is a clear REVERSAL signal (e.g., massive engulfing red candle).
    """
    
    def __init__(self, config=None):
        super().__init__(config)
        self.looking_for_entry = False
        self.entry_direction = None  # "LONG" or "SHORT"
        
        # Paramètres V2 (Configurable)
        self.pullback_tolerance = self.config.get('pullback_tolerance', 0.01)
        self.bos_lookback = self.config.get('bos_lookback', 2)
        self.rr_ratio = self.config.get('min_rr', 2.0)  # Use min_rr key from json
        self.sl_buffer = self.config.get('sl_buffer', 0.3)
        self.adx_threshold = self.config.get('adx_threshold', 25)
        self.rsi_min = self.config.get('rsi_min', 30)
        self.rsi_max = self.config.get('rsi_max', 70)
    
    def add_indicators(self, df):
        """Add indicators to 15m dataframe"""
        df['EMA_21'] = ta.ema(df['close'], length=21)
        df['EMA_50'] = ta.ema(df['close'], length=50)
        df['ATRr_14'] = ta.atr(df['high'], df['low'], df['close'], length=14)
        df['RSI_14'] = ta.rsi(df['close'], length=14)
        return df
    
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
        
        # Check for setup
        # LONG Setup: Conditions assouplies
        long_trend = close_15m > ema_50 or (close_15m > ema_21 and ema_21 > ema_50)
        long_pullback = (low_15m <= ema_21 * (1 + self.pullback_tolerance) and 
                        low_15m >= ema_21 * (1 - self.pullback_tolerance))
        
        if long_trend and long_pullback:
            self.looking_for_entry = True
            self.entry_direction = "LONG"
        
        # SHORT Setup: Conditions assouplies
        short_trend = close_15m < ema_50 or (close_15m < ema_21 and ema_21 < ema_50)
        short_pullback = (high_15m >= ema_21 * (1 - self.pullback_tolerance) and 
                         high_15m <= ema_21 * (1 + self.pullback_tolerance))
        
        if short_trend and short_pullback:
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
                # Find swing low for SL
                swing_low = df_1m.tail(10)['low'].min()
                sl = swing_low - (self.sl_buffer * atr_15m)
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
                    "comment": f"Smart Trend V2: 15m Pullback + 1m BOS (R:R 1:{self.rr_ratio})"
                }
        
        # SHORT Trigger: Close < Low of last N
        elif self.entry_direction == "SHORT":
            low_of_last_n = last_n_1m['low'].min()
            if close_1m < low_of_last_n:
                # Find swing high for SL
                swing_high = df_1m.tail(10)['high'].max()
                sl = swing_high + (self.sl_buffer * atr_15m)
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
                    "comment": f"Smart Trend V2: 15m Pullback + 1m BOS (R:R 1:{self.rr_ratio})"
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
        
        # Trend (25%)
        long_trend = close_15m > ema_50 or (close_15m > ema_21 and ema_21 > ema_50)
        short_trend = close_15m < ema_50 or (close_15m < ema_21 and ema_21 < ema_50)
        
        if long_trend or short_trend:
            progress += 25
        
        # Pullback (25%)
        long_pullback = (low_15m <= ema_21 * (1 + self.pullback_tolerance) and 
                        low_15m >= ema_21 * (1 - self.pullback_tolerance))
        short_pullback = (high_15m >= ema_21 * (1 - self.pullback_tolerance) and 
                         high_15m <= ema_21 * (1 + self.pullback_tolerance))
        
        if long_pullback or short_pullback:
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
        """Detailed conditions for UI"""
        if df.empty or len(df) < 50: return []
        
        try:
            self.add_indicators(df)
            
            # 15m Values
            close_15m = df['close'].iloc[-1]
            ema_21 = df['EMA_21'].iloc[-1]
            ema_50 = df['EMA_50'].iloc[-1]
            rsi_15m = df['RSI_14'].iloc[-1]
            low_15m = df['low'].iloc[-1]
            high_15m = df['high'].iloc[-1]
            
            conditions = []
            
            # 1. Trend Filter
            long_trend = close_15m > ema_50 or (close_15m > ema_21 and ema_21 > ema_50)
            short_trend = close_15m < ema_50 or (close_15m < ema_21 and ema_21 < ema_50)
            
            trend_val = "Bullish" if long_trend else "Bearish" if short_trend else "Neutral"
            trend_ok = long_trend or short_trend
            
            conditions.append({
                "name": "Trend Filter (15m)",
                "status": trend_ok,
                "value": trend_val
            })
            
            # 2. Pullback Zone
            # Check proximity to EMA 21
            dist_ema21 = abs(close_15m - ema_21) / ema_21
            in_zone = dist_ema21 <= self.pullback_tolerance
            
            conditions.append({
                "name": f"Pullback Zone (EMA 21 +/- {self.pullback_tolerance*100:.0f}%)",
                "status": in_zone,
                "value": f"Dist: {dist_ema21*100:.2f}%"
            })

            # 3. RSI Filter
            rsi_ok = 30 < rsi_15m < 70
            conditions.append({
                "name": "RSI Filter (30-70)",
                "status": rsi_ok,
                "value": f"{rsi_15m:.1f}"
            })
            
            # 4. Trigger (1m)
            trigger_status = False
            trigger_val = "Waiting"
            
            if extra_data and "1m" in extra_data:
                df_1m = extra_data["1m"]
                if not df_1m.empty and len(df_1m) >= (self.bos_lookback + 2):
                    close_1m = df_1m['close'].iloc[-1]
                    # Logic simplified for display
                    trigger_val = f"1m Close: {close_1m}"
                    # If we were looking for entry, we could show more details
                    if self.looking_for_entry:
                        trigger_val = f"Watching {self.entry_direction} BOS"
                        trigger_status = True # Active monitoring
            
            conditions.append({
                "name": "Trigger Conditions (1m)",
                "status": trigger_status, # True means we have data and are monitoring
                "value": trigger_val
            })
            
            return conditions
        except Exception as e:
            return [{"name": "Error", "status": False, "value": str(e)}]
