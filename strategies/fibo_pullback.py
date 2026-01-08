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
    
    Logic:
    1. Trend Filter: Price > EMA 200 AND ADX >= 20
    2. Swing Detection: Find confirmed Highest High (10+ bars old) and preceding Lowest Low
    3. Fibonacci Levels: Calculate 50%, 61.8%, and 78.6% retracement zones
    4. Entry Trigger: Price in 50-78.6% zone + Volume > 1.5x average
    5. Risk Management: SL below 78.6%, TP at Swing High
    6. R:R Filter: Minimum 1.5 ratio required
    
    Timeframe: 15m optimized
    Type: TREND (Pullback continuation)
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
        
        # ============================================
        # GATEKEEPER: Trend Filter
        # ============================================
        
        # 1. Price must be above EMA 200
        if current_price <= ema_200:
            return None
        
        # 2. ADX must be >= threshold (avoid ranging markets)
        if adx < self.adx_threshold:
            return None
        
        # ============================================
        # SWING DETECTION (FIXED)
        # ============================================
        
        # ✅ FIX #2: Exclude last N bars for swing confirmation
        # This ensures swing high is confirmed and not the current price action
        confirmed_end = -self.swing_confirmation_bars
        confirmed_start = -(self.swing_lookback + self.swing_confirmation_bars)
        confirmed_df = df.iloc[confirmed_start:confirmed_end].copy()
        
        if len(confirmed_df) < 20:
            return None  # Not enough confirmed data
        
        # Find Swing High (Highest High in confirmed range)
        swing_high_idx = confirmed_df['high'].idxmax()
        swing_high = confirmed_df.loc[swing_high_idx, 'high']
        
        # Verify swing is not too recent within confirmed range
        swing_position_in_confirmed = list(confirmed_df.index).index(swing_high_idx)
        if swing_position_in_confirmed > len(confirmed_df) - 5:
            return None  # Swing too recent even in confirmed range
        
        # Find Swing Low (Lowest Low BEFORE the Swing High)
        data_before_high = confirmed_df.loc[:swing_high_idx]
        
        if len(data_before_high) < 10:
            return None  # Not enough data before swing high
        
        swing_low_idx = data_before_high['low'].idxmin()
        swing_low = data_before_high.loc[swing_low_idx, 'low']
        
        # Validate swing structure
        if swing_high <= swing_low:
            return None  # Invalid swing
        
        # Additional validation: Swing should be significant
        swing_range_pct = (swing_high - swing_low) / swing_low
        if swing_range_pct < 0.02:  # Less than 2% range
            return None  # Swing too small, likely noise
        
        # ============================================
        # FIBONACCI LEVELS (FIXED)
        # ============================================
        
        diff = swing_high - swing_low
        
        # Calculate key Fibonacci levels
        level_50 = swing_high - (diff * 0.50)
        level_618 = swing_high - (diff * 0.618)
        level_786 = swing_high - (diff * 0.786)
        
        # ✅ FIX #3: Wider entry zone (50-78.6% instead of 50-65%)
        entry_zone_high = swing_high - (diff * self.fibo_entry_min)  # 50%
        entry_zone_low = swing_high - (diff * self.fibo_entry_max)   # 78.6%
        
        # ============================================
        # ENTRY TRIGGER (FIXED)
        # ============================================
        
        # Check if current price is in the entry zone
        # Using completed candle high/low for accurate zone detection
        in_entry_zone = (current_low <= entry_zone_high and 
                        current_high >= entry_zone_low)
        
        if not in_entry_zone:
            return None
        
        # ✅ FIX #4: Volume Filter (NEW)
        # Require volume confirmation to avoid fakeouts
        if 'volume' in df.columns:
            current_vol = df['volume'].iloc[-2]  # Completed candle volume
            avg_vol = df['volume'].iloc[-22:-2].mean()  # Average of last 20 completed
            
            if avg_vol > 0 and current_vol < avg_vol * self.volume_multiplier:
                return None  # Insufficient volume, likely fakeout
        
        # ============================================
        # RISK MANAGEMENT
        # ============================================
        
        # Entry: Current close price
        entry_price = current_price
        
        # Stop Loss: Below 78.6% level with small buffer
        sl_buffer = diff * 0.01  # 1% of swing range
        sl_price = level_786 - sl_buffer
        
        # Take Profit: Swing High (0% retracement)
        tp_price = swing_high
        
        # ============================================
        # R:R FILTER (CRITICAL)
        # ============================================
        
        # Calculate distances
        distance_to_tp = abs(tp_price - entry_price)
        distance_to_sl = abs(entry_price - sl_price)
        
        # Avoid division by zero
        if distance_to_sl == 0:
            return None
        
        # Calculate Risk:Reward ratio
        rr_ratio = distance_to_tp / distance_to_sl
        
        # REJECT if R:R is below minimum threshold
        if rr_ratio < self.min_rr:
            return None
        
        # ============================================
        # SIGNAL GENERATION
        # ============================================
        
        # Calculate volume ratio for metadata
        vol_ratio = 0
        if 'volume' in df.columns and avg_vol > 0:
            vol_ratio = current_vol / avg_vol
        
        return {
            "signal": "BUY",
            "sl": sl_price,
            "tp": tp_price,
            "comment": f"Fibo Pullback V2 (RR:{rr_ratio:.1f}, Vol:{vol_ratio:.1f}x, Zone:{((swing_high - current_price) / diff * 100):.0f}%)",
            "metadata": {
                "swing_high": swing_high,
                "swing_low": swing_low,
                "fibo_50": level_50,
                "fibo_618": level_618,
                "fibo_786": level_786,
                "adx": adx,
                "rr_ratio": round(rr_ratio, 2),
                "volume_ratio": round(vol_ratio, 2),
                "retracement_pct": round((swing_high - current_price) / diff * 100, 1)
            }
        }
    
    def calculate_progress(self, df, extra_data=None):
        """
        Calculate how close we are to a Fibonacci setup (0-100%)
        ✅ FIX #5: Uses iloc[-2] for consistency
        """
        min_bars = self.swing_lookback + self.ema_period + self.swing_confirmation_bars
        if df.empty or len(df) < min_bars:
            return 0
        
        try:
            self.add_indicators(df)
            
            # ✅ Use completed candles (iloc[-2])
            current_price = df['close'].iloc[-2]
            ema_200 = df['EMA_200'].iloc[-2]
            adx = df['ADX_14'].iloc[-2]
            
            progress = 0
            
            # Check trend filter (40% weight)
            if current_price > ema_200:
                progress += 20
            
            if adx >= self.adx_threshold:
                progress += 20
            
            # Check for valid swing structure (30% weight)
            confirmed_end = -self.swing_confirmation_bars
            confirmed_start = -(self.swing_lookback + self.swing_confirmation_bars)
            confirmed_df = df.iloc[confirmed_start:confirmed_end].copy()
            
            if len(confirmed_df) >= 20:
                swing_high_idx = confirmed_df['high'].idxmax()
                data_before_high = confirmed_df.loc[:swing_high_idx]
                
                if len(data_before_high) >= 10:
                    swing_high = confirmed_df.loc[swing_high_idx, 'high']
                    swing_low = data_before_high['low'].min()
                    
                    if swing_high > swing_low:
                        progress += 30
                        
                        # Check proximity to Fibonacci zone (30% weight)
                        diff = swing_high - swing_low
                        level_618 = swing_high - (diff * 0.618)
                        
                        # Distance from 61.8% level
                        distance_pct = abs(current_price - level_618) / diff
                        
                        if distance_pct < 0.20:  # Within 20% of swing range
                            proximity_score = int((1 - distance_pct / 0.20) * 30)
                            progress += proximity_score
            
            return min(progress, 100)
        except:
            return 0
    
    def check_conditions(self, df, extra_data=None):
        """
        Check specific conditions for UI display
        ✅ FIX #5: Uses iloc[-2] for consistency
        """
        min_bars = self.swing_lookback + self.ema_period + self.swing_confirmation_bars
        if df.empty or len(df) < min_bars:
            return []
        
        try:
            self.add_indicators(df)
            
            # ✅ Use completed candles (iloc[-2])
            current_price = df['close'].iloc[-2]
            ema_200 = df['EMA_200'].iloc[-2]
            adx = df['ADX_14'].iloc[-2]
            
            conditions = []
            
            # Trend Filter
            conditions.append({
                "name": f"Price > EMA {self.ema_period}",
                "status": current_price > ema_200,
                "value": f"${current_price:.2f} vs ${ema_200:.2f}"
            })
            
            conditions.append({
                "name": f"ADX >= {self.adx_threshold}",
                "status": adx >= self.adx_threshold,
                "value": f"{adx:.1f}"
            })
            
            # Swing Structure
            confirmed_end = -self.swing_confirmation_bars
            confirmed_start = -(self.swing_lookback + self.swing_confirmation_bars)
            confirmed_df = df.iloc[confirmed_start:confirmed_end].copy()
            
            has_valid_swing = False
            if len(confirmed_df) >= 20:
                swing_high_idx = confirmed_df['high'].idxmax()
                data_before_high = confirmed_df.loc[:swing_high_idx]
                
                if len(data_before_high) >= 10:
                    swing_high = confirmed_df.loc[swing_high_idx, 'high']
                    swing_low = data_before_high['low'].min()
                    has_valid_swing = swing_high > swing_low
                    
                    if has_valid_swing:
                        diff = swing_high - swing_low
                        level_618 = swing_high - (diff * 0.618)
                        level_786 = swing_high - (diff * 0.786)
                        
                        conditions.append({
                            "name": "Fibo Zone (50-78.6%)",
                            "status": True,
                            "value": f"${level_786:.2f} - ${swing_high - (diff * 0.50):.2f}"
                        })
                        
                        # Distance to entry zone
                        retracement_pct = (swing_high - current_price) / diff * 100
                        in_zone = 50 <= retracement_pct <= 78.6
                        
                        conditions.append({
                            "name": "In Fibo Zone",
                            "status": in_zone,
                            "value": f"{retracement_pct:.1f}% retracement"
                        })
                        
                        # Volume check
                        if 'volume' in df.columns:
                            current_vol = df['volume'].iloc[-2]
                            avg_vol = df['volume'].iloc[-22:-2].mean()
                            vol_ratio = current_vol / avg_vol if avg_vol > 0 else 0
                            vol_ok = vol_ratio >= self.volume_multiplier
                            
                            conditions.append({
                                "name": f"Volume >= {self.volume_multiplier}x",
                                "status": vol_ok,
                                "value": f"{vol_ratio:.2f}x"
                            })
            
            conditions.append({
                "name": "Valid Swing Structure",
                "status": has_valid_swing,
                "value": "✓" if has_valid_swing else "✗"
            })
            
            return conditions
        except Exception as e:
            return [{"name": "Error", "status": False, "value": str(e)}]
