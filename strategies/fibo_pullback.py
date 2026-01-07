from app.services.indicators import ta
import pandas as pd
from strategies.base import BaseStrategy

class StrategyFiboPullback(BaseStrategy):
    """
    Fibonacci Pullback Strategy - Sniper Entries on Trend Corrections
    
    Logic:
    1. Trend Filter: Price > EMA 200 AND ADX >= 20
    2. Swing Detection: Find Highest High (50 bars) and preceding Lowest Low
    3. Fibonacci Levels: Calculate 61.8% and 78.6% retracement zones
    4. Entry Trigger: Price touches 50-65% retracement zone
    5. Risk Management: SL below 78.6%, TP at Swing High
    6. R:R Filter: Minimum 1.5 ratio required
    
    Timeframe: 15m optimized
    Type: SCALPING_15M
    """
    
    def __init__(self, config=None):
        super().__init__(config)
        
        # Configurable Parameters
        self.ema_period = self.config.get('ema_period', 200)
        self.adx_threshold = self.config.get('adx_threshold', 20)
        self.swing_lookback = self.config.get('swing_lookback', 50)
        self.min_rr = self.config.get('min_rr', 1.5)
        
        # Fibonacci Levels
        self.fibo_entry_min = 0.50  # 50% retracement
        self.fibo_entry_max = 0.65  # 65% retracement (around 61.8%)
        self.fibo_sl_level = 0.786  # 78.6% retracement
    
    def add_indicators(self, df):
        """Add required indicators to dataframe"""
        df['EMA_200'] = ta.ema(df['close'], length=self.ema_period)
        df['ADX_14'] = ta.adx(df['high'], df['low'], df['close'], length=14)
        return df
    
    def generate_signal(self, df, extra_data=None):
        """
        Generate Fibonacci Pullback signal
        
        Returns:
            dict with signal details or None
        """
        if df.empty or len(df) < self.swing_lookback + self.ema_period:
            return None
        
        # Add indicators
        self.add_indicators(df)
        
        # Get current values
        current_price = df['close'].iloc[-1]
        current_low = df['low'].iloc[-1]
        current_high = df['high'].iloc[-1]
        ema_200 = df['EMA_200'].iloc[-1]
        adx = df['ADX_14'].iloc[-1]
        
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
        # SWING DETECTION
        # ============================================
        
        # Get recent data for swing analysis
        recent_df = df.iloc[-self.swing_lookback:].copy()
        
        # Find Swing High (Highest High)
        swing_high_idx = recent_df['high'].idxmax()
        swing_high = recent_df.loc[swing_high_idx, 'high']
        
        # Find Swing Low (Lowest Low BEFORE the Swing High)
        # Get all data up to swing high
        data_before_high = recent_df.loc[:swing_high_idx]
        
        if len(data_before_high) < 5:
            return None  # Not enough data before swing high
        
        swing_low_idx = data_before_high['low'].idxmin()
        swing_low = data_before_high.loc[swing_low_idx, 'low']
        
        # Validate swing structure
        if swing_high <= swing_low:
            return None  # Invalid swing
        
        # ============================================
        # FIBONACCI LEVELS
        # ============================================
        
        diff = swing_high - swing_low
        
        # Calculate key Fibonacci levels
        level_618 = swing_high - (diff * 0.618)
        level_786 = swing_high - (diff * 0.786)
        level_50 = swing_high - (diff * 0.50)
        
        # Entry zone boundaries
        entry_zone_high = swing_high - (diff * self.fibo_entry_min)  # 50%
        entry_zone_low = swing_high - (diff * self.fibo_entry_max)   # 65%
        
        # ============================================
        # ENTRY TRIGGER
        # ============================================
        
        # Check if current price is in the entry zone (50-65% retracement)
        # Price should touch or be within the zone
        in_entry_zone = (current_low <= entry_zone_high and 
                        current_high >= entry_zone_low)
        
        if not in_entry_zone:
            return None
        
        # ============================================
        # RISK MANAGEMENT
        # ============================================
        
        # Entry: Current close price
        entry_price = current_price
        
        # Stop Loss: Below 78.6% level (with small buffer)
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
        
        return {
            "signal": "BUY",
            "type": "SCALPING_15M",
            "strategy": "FiboPullback",
            "price": entry_price,
            "sl": sl_price,
            "tp": tp_price,
            "reason": f"Fibo Retracement 61.8% in Uptrend (RR: {rr_ratio:.1f})",
            "metadata": {
                "swing_high": swing_high,
                "swing_low": swing_low,
                "fibo_618": level_618,
                "fibo_786": level_786,
                "adx": adx,
                "rr_ratio": round(rr_ratio, 2)
            }
        }
    
    def calculate_progress(self, df, extra_data=None):
        """
        Calculate how close we are to a Fibonacci setup (0-100%)
        """
        if df.empty or len(df) < self.swing_lookback + self.ema_period:
            return 0
        
        self.add_indicators(df)
        
        current_price = df['close'].iloc[-1]
        ema_200 = df['EMA_200'].iloc[-1]
        adx = df['ADX_14'].iloc[-1]
        
        progress = 0
        
        # Check trend filter (40% weight)
        if current_price > ema_200:
            progress += 20
        
        if adx >= self.adx_threshold:
            progress += 20
        
        # Check for valid swing structure (30% weight)
        recent_df = df.iloc[-self.swing_lookback:].copy()
        swing_high_idx = recent_df['high'].idxmax()
        data_before_high = recent_df.loc[:swing_high_idx]
        
        if len(data_before_high) >= 5:
            swing_high = recent_df.loc[swing_high_idx, 'high']
            swing_low = data_before_high['low'].min()
            
            if swing_high > swing_low:
                progress += 30
                
                # Check proximity to Fibonacci zone (30% weight)
                diff = swing_high - swing_low
                level_618 = swing_high - (diff * 0.618)
                
                # Distance from 61.8% level
                distance_pct = abs(current_price - level_618) / diff
                
                if distance_pct < 0.15:  # Within 15% of swing range
                    proximity_score = int((1 - distance_pct / 0.15) * 30)
                    progress += proximity_score
        
        return min(progress, 100)
    
    def check_conditions(self, df, extra_data=None):
        """
        Check specific conditions for UI display
        """
        if df.empty or len(df) < self.swing_lookback + self.ema_period:
            return []
        
        self.add_indicators(df)
        
        current_price = df['close'].iloc[-1]
        ema_200 = df['EMA_200'].iloc[-1]
        adx = df['ADX_14'].iloc[-1]
        
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
        recent_df = df.iloc[-self.swing_lookback:].copy()
        swing_high_idx = recent_df['high'].idxmax()
        data_before_high = recent_df.loc[:swing_high_idx]
        
        has_valid_swing = False
        if len(data_before_high) >= 5:
            swing_high = recent_df.loc[swing_high_idx, 'high']
            swing_low = data_before_high['low'].min()
            has_valid_swing = swing_high > swing_low
            
            if has_valid_swing:
                diff = swing_high - swing_low
                level_618 = swing_high - (diff * 0.618)
                
                conditions.append({
                    "name": "Fibo 61.8% Level",
                    "status": True,
                    "value": f"${level_618:.2f}"
                })
                
                # Distance to entry zone
                distance_pct = abs(current_price - level_618) / diff * 100
                conditions.append({
                    "name": "Distance to Zone",
                    "status": distance_pct < 15,
                    "value": f"{distance_pct:.1f}%"
                })
        
        conditions.append({
            "name": "Valid Swing Structure",
            "status": has_valid_swing,
            "value": "✓" if has_valid_swing else "✗"
        })
        
        return conditions
