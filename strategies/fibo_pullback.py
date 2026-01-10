from app.services.indicators import ta
import pandas as pd
from strategies.base import BaseStrategy

class StrategyFiboPullback(BaseStrategy):
    """
    Fibonacci Pullback Strategy V2 - REFACTORED (2026-01-08)
    
    FIXES APPLIED:
    ✅ Anti-repainting: All signals use iloc[-2] (completed candles only)
    ✅ Swing confirmation: Exclude last 10 bars for swing detection
    ✅ Wider Fibo zone: 50-78.6% (golden zone) instead of 50-65%
    ✅ Volume filter: Require 1.5x average volume for entry
    ✅ Consistent UI: Progress/conditions use same anti-repainting logic
    ✅ SHORT Logic Added: Supports both Bullish and Bearish pullbacks
    
    Logic (LONG):
    1. Trend Filter: Price > EMA 200 AND ADX >= 20
    2. Swing Detection: Find confirmed Highest High (10+ bars old) and preceding Lowest Low
    3. Fibonacci Levels: Calculate 50%, 61.8%, and 78.6% retracement zones
    4. Entry Trigger: Price in 50-78.6% zone + Volume > 1.5x average
    5. Risk Management: SL below 78.6%, TP at Swing High
    6. R:R Filter: Minimum 1.5 ratio required

    Logic (SHORT):
    1. Trend Filter: Price < EMA 200 AND ADX >= 20
    2. Swing Detection: Find confirmed Lowest Low (10+ bars old) and preceding Highest High
    3. Fibo Retracement: Upward retracement 50-78.6%
    4. Entry Trigger: Price in zone + Volume
    
    Timeframe: 15m optimized
    Type: TREND (Pullback continuation)
    """

    AI_PERSONA = """
    CODENAME: "GOLDEN RETRACEMENT - FIBONACCI PHANTOM"

    ROLE:
    You are a PRECISION TREND HUNTER. You specialize in the sacred art of Fibonacci confluence in trending markets.

    PRIME DIRECTIVE:
    "Respect the golden zone." Pullbacks are not weakness; they are breathing room for the next leg up.

    RULES OF ENGAGEMENT (OVERRIDES):
    1. TREND IS KING: EMA 200 + ADX >=20 is non-negotiable. No chop, no counter-trend. Only continuation.
    2. GOLDEN ZONE ONLY: 50-78.6% is the sacred retracement. Do NOT enter outside it, even if price looks tempting.
    3. VOLUME CONFIRMATION: 1.5x average or GTFO. Fake pullbacks die without fuel.
    4. PATIENCE IS POWER: Wait for confirmed swing + zone + volume. No FOMO entries.
    5. RISK IS SACRED: SL below 78.6%, TP at previous high, RR >=1.5 or no trade.

    RESPONSE STYLE:
    Calm, precise, almost spiritual.
    "The market breathes... now it exhales upward.", "Golden zone respected. Alignment complete.", "Fibonacci whispers: Enter."
    """
    
    def __init__(self, config=None):
        super().__init__(config)
        
        # Configurable Parameters
        self.ema_period = self.config.get('ema_period', 200)
        self.adx_threshold = self.config.get('adx_threshold', 20)
        self.swing_lookback = self.config.get('swing_lookback', 50)
        self.swing_confirmation_bars = self.config.get('swing_confirmation_bars', 10)
        self.min_rr = self.config.get('min_rr', 1.5)
        self.volume_multiplier = self.config.get('volume_multiplier', 1.5)
        
        # Fibonacci Levels (FIXED: Wider zone)
        self.fibo_entry_min = 0.50   # 50% retracement
        self.fibo_entry_max = 0.786  # 78.6% retracement (golden zone)
        self.fibo_sl_level = 0.786   # 78.6% for SL placement
    
    def add_indicators(self, df):
        """Add required indicators to dataframe"""
        df['EMA_200'] = ta.ema(df['close'], length=self.ema_period)
        adx_result = ta.adx(df['high'], df['low'], df['close'], length=14)
        df['ADX_14'] = adx_result['ADX'] if isinstance(adx_result, pd.DataFrame) else adx_result
        
        # Add volume SMA for filter
        if 'volume' in df.columns:
            df['volume_sma_20'] = df['volume'].rolling(20).mean()
        
        return df
    
    def generate_signal(self, df, extra_data=None):
        """
        Generate Fibonacci Pullback signal (FIXED VERSION)
        Supports LONG and SHORT
        
        Returns:
            dict with signal details or None
        """
        # Need extra bars for swing confirmation
        min_bars = self.swing_lookback + self.ema_period + self.swing_confirmation_bars
        if df.empty or len(df) < min_bars:
            return None
        
        # Add indicators
        self.add_indicators(df)
        
        # ✅ FIX #1: Use completed candles (iloc[-2])
        current_price = df['close'].iloc[-2]
        current_low = df['low'].iloc[-2]
        current_high = df['high'].iloc[-2]
        ema_200 = df['EMA_200'].iloc[-2]
        adx = df['ADX_14'].iloc[-2]
        
        # Check ADX for both directions
        if adx < self.adx_threshold:
            return None

        # ============================================
        # DECISION: LONG OR SHORT?
        # ============================================
        is_bullish = current_price > ema_200
        is_bearish = current_price < ema_200

        if not is_bullish and not is_bearish: 
            return None

        # ============================================
        # SWING DETECTION & LOGIC (Merged)
        # ============================================
        
        # Select data for confirmed swing
        confirmed_end = -self.swing_confirmation_bars
        confirmed_start = -(self.swing_lookback + self.swing_confirmation_bars)
        confirmed_df = df.iloc[confirmed_start:confirmed_end].copy()
        
        if len(confirmed_df) < 20:
            return None
        
        signal_data = None

        # --- LONG SETUP ---
        if is_bullish:
            # Find Swing High (Highest High)
            swing_high_idx = confirmed_df['high'].idxmax()
            swing_high = confirmed_df.loc[swing_high_idx, 'high']
            
            # Find Swing Low (Lowest Low BEFORE Swing High)
            data_before = confirmed_df.loc[:swing_high_idx]
            if len(data_before) < 10: return None
            
            swing_low_idx = data_before['low'].idxmin()
            swing_low = data_before.loc[swing_low_idx, 'low']
            
            if swing_high <= swing_low: return None
            
            # Calc Levels
            diff = swing_high - swing_low
            entry_zone_high = swing_high - (diff * self.fibo_entry_min)
            entry_zone_low = swing_high - (diff * self.fibo_entry_max)
            
            # Entry Trigger
            in_zone = (current_low <= entry_zone_high and current_high >= entry_zone_low)
            if not in_zone: return None
            
            entry = current_price
            sl = swing_high - (diff * 0.786) - (diff * 0.01) # Below 78.6%
            tp = swing_high

            signal_data = {
                "signal": "BUY",
                "sl": sl,
                "tp": tp,
                "swing_h": swing_high,
                "swing_l": swing_low,
                "diff": diff
            }

        # --- SHORT SETUP ---
        if is_bearish:
            # Find Swing Low (Lowest Low)
            swing_low_idx = confirmed_df['low'].idxmin()
            swing_low = confirmed_df.loc[swing_low_idx, 'low']
            
            # Find Swing High (Highest High BEFORE Swing Low)
            data_before = confirmed_df.loc[:swing_low_idx]
            if len(data_before) < 10: return None
            
            swing_high_idx = data_before['high'].idxmax()
            swing_high = data_before.loc[swing_high_idx, 'high']
            
            if swing_low >= swing_high: return None
            
            # Calc Levels (Retracement goes UP)
            diff = swing_high - swing_low
            # 50% retracement is higher than Low
            entry_zone_low = swing_low + (diff * self.fibo_entry_min)
            entry_zone_high = swing_low + (diff * self.fibo_entry_max)
            
            # Entry Trigger
            in_zone = (current_high >= entry_zone_low and current_low <= entry_zone_high)
            if not in_zone: return None
            
            entry = current_price
            sl = swing_low + (diff * 0.786) + (diff * 0.01) # Above 78.6%
            tp = swing_low # Target Low

            signal_data = {
                "signal": "SELL",
                "sl": sl,
                "tp": tp,
                "swing_h": swing_high,
                "swing_l": swing_low,
                "diff": diff
            }
            
        if not signal_data:
            return None

        # ============================================
        # VOLUME FILTER & R:R CHECK (Shared)
        # ============================================
        
        # Volume Filter
        current_vol = 0
        avg_vol = 0
        if 'volume' in df.columns:
            current_vol = df['volume'].iloc[-2]
            avg_vol = df['volume'].iloc[-22:-2].mean()
            if avg_vol > 0 and current_vol < avg_vol * self.volume_multiplier:
                return None
        
        # R:R Check
        entry_price = current_price
        dist_tp = abs(signal_data["tp"] - entry_price)
        dist_sl = abs(entry_price - signal_data["sl"])
        
        if dist_sl == 0: return None
        rr = dist_tp / dist_sl
        
        if rr < self.min_rr:
            return None
            
        # ============================================
        # RETURN SIGNAL
        # ============================================
        vol_ratio = current_vol / avg_vol if avg_vol > 0 else 0
        diff = signal_data["diff"]
        retracement_pct = abs(signal_data["swing_h"] - current_price) / diff * 100 if is_bullish else abs(current_price - signal_data["swing_l"]) / diff * 100
        
        return {
            "signal": signal_data["signal"],
            "sl": signal_data["sl"],
            "tp": signal_data["tp"],
            "comment": f"Fibo Pullback V2 (RR:{rr:.1f}, Vol:{vol_ratio:.1f}x, Retrace:{retracement_pct:.0f}%)",
            "metadata": {
                "swing_high": signal_data["swing_h"],
                "swing_low": signal_data["swing_l"],
                "adx": adx,
                "rr_ratio": round(rr, 2),
                "volume_ratio": round(vol_ratio, 2)
            }
        }
    
    def calculate_progress(self, df, extra_data=None):
        """Calculate progress (0-100%)"""
        if df.empty or len(df) < 200: return 0
        try:
            self.add_indicators(df)
            current_price = df['close'].iloc[-2]
            ema_200 = df['EMA_200'].iloc[-2]
            adx = df['ADX_14'].iloc[-2]
            
            progress = 0
            
            # Trend (20%) + ADX (20%)
            # LONG or SHORT
            if (current_price > ema_200) or (current_price < ema_200):
                 progress += 20
            if adx >= self.adx_threshold:
                 progress += 20
                 
            # Note: Hard to detect precise swing progress without full logic duplication
            # Assuming if Trend+ADX ok, we are 40% there.
            return progress
        except: return 0

    def check_conditions(self, df, extra_data=None):
        """Diagnostic Card Conditions - Full Funnel Visibility"""
        if df.empty: return []
        try:
            self.add_indicators(df)
            current_price = df['close'].iloc[-2]
            ema_200 = df['EMA_200'].iloc[-2]
            adx = df['ADX_14'].iloc[-2]
            
            is_bull = current_price > ema_200
            trend_txt = "Bullish" if is_bull else "Bearish"
            
            conditions = [
                {"name": f"1. Trend ({trend_txt})", "status": True, "value": "Price vs EMA200"},
                {"name": "2. ADX > 20", "status": adx >= self.adx_threshold, "value": f"{adx:.1f}"}
            ]

            # Swing Check
            confirmed_end = -self.swing_confirmation_bars
            confirmed_start = -(self.swing_lookback + self.swing_confirmation_bars)
            confirmed_df = df.iloc[confirmed_start:confirmed_end].copy()
            
            has_swing = False
            swing_info = "Waiting..."
            in_zone = False
            retrace_pct = 0.0
            
            if len(confirmed_df) >= 20:
                if is_bull:
                    high_idx = confirmed_df['high'].idxmax()
                    low_idx = confirmed_df.loc[:high_idx]['low'].idxmin() # Low before High
                    swing_h = confirmed_df.loc[high_idx, 'high']
                    swing_l = confirmed_df.loc[low_idx, 'low']
                    if swing_h > swing_l:
                        has_swing = True
                        diff = swing_h - swing_l
                        retrace_pct = (swing_h - current_price) / diff * 100
                        in_zone = 50 <= retrace_pct <= 78.6
                        swing_info = f"Retrace: {retrace_pct:.1f}%"
                else:
                    low_idx = confirmed_df['low'].idxmin()
                    high_idx = confirmed_df.loc[:low_idx]['high'].idxmax() # High before Low
                    swing_l = confirmed_df.loc[low_idx, 'low']
                    swing_h = confirmed_df.loc[high_idx, 'high']
                    if swing_l < swing_h:
                        has_swing = True
                        diff = swing_h - swing_l
                        retrace_pct = (current_price - swing_l) / diff * 100 # Upward retrace
                        in_zone = 50 <= retrace_pct <= 78.6
                        swing_info = f"Retrace: {retrace_pct:.1f}%"

            conditions.append({
                "name": "3. Swing Structure",
                "status": has_swing,
                "value": swing_info if has_swing else "Searching..."
            })
            
            conditions.append({
                "name": "4. Fibo Zone (50-78%)",
                "status": in_zone,
                "value": f"{retrace_pct:.1f}%" if has_swing else "--"
            })

            # Volume Check
            vol_ok = False
            vol_txt = "Low"
            if 'volume' in df.columns:
                cur_vol = df['volume'].iloc[-2]
                avg_vol = df['volume'].iloc[-22:-2].mean()
                if avg_vol > 0:
                    ratio = cur_vol / avg_vol
                    vol_ok = ratio >= self.volume_multiplier
                    vol_txt = f"{ratio:.1f}x"
            
            conditions.append({
                "name": "5. Volume Trigger",
                "status": vol_ok,
                "value": vol_txt
            })
            
            return conditions
        except Exception as e: 
            return [{"name": "Error", "status": False, "value": str(e)}]

    def get_threshold_comparisons(self, df, extra_data=None):
        """Detailed parameters for UI"""
        if df.empty: return {}
        try:
            self.add_indicators(df)
            adx = df['ADX_14'].iloc[-1]
            return {
                "ADX": f"{adx:.1f} (Threshold: {self.adx_threshold})",
                "EMA200": "Active"
            }
        except: return {}
