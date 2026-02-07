from app.services.indicators import ta
import pandas as pd
import numpy as np
from strategies.base import BaseStrategy

class StrategySupertrend(BaseStrategy):
    """
    Supertrend Strategy with MTF Funnel (15m Context / 1m Trigger)
    
    Setup (15m):
    - Trend Filter: Price > SMA 200 (Long) or Price < SMA 200 (Short)
    - Supertrend Filter: Supertrend must be BULLISH for Long, BEARISH for Short.
    - ADX Filter: ADX > threshold (Trend presence)
    
    Trigger (1m):
    - Supertrend Flip: Enter when 1m Supertrend flips to match 15m bias.
    - OR: Pullback to 1m Supertrend line if 15m is strong.
    
    Risk:
    - SL: Fixed at Supertrend line or ATR swing.
    - TP: Risk-Reward 1.5 - 2.0.
    """

    AI_PERSONA = """
    CODENAME: "SUPERTREND SURFER"
    
    ROLE:
    You are a TREND RIDER. You don't try to predict reversals; you follow the momentum until it breaks.
    
    PRIME DIRECTIVE:
    Ride the wave. Protect capital by trailing stops precisely at the trend line.
    
    RULES OF ENGAGEMENT:
    1. TREND IS KING: Only trade in the direction of the 15m trend (EMA 200).
    2. VOLATILITY PROTECTION: Ensure ATR is healthy. If the market is dead (low volatility), avoid entry.
    3. MOMENTUM CONFIRMATION: Enter when the 1m chart aligns with the 15m tide.
    """

    def __init__(self, config=None):
        super().__init__(config)
        self.looking_for_entry = False
        self.entry_direction = None
        
        # Params from strategies.json (nested under the strategy key)
        params = self.config.get("params", {})
        self.st_period = params.get("period", 10)
        self.st_multiplier = params.get("multiplier", 3.0)
        self.ema_filter = params.get("ema_filter_period", 200)
        self.adx_threshold = params.get("adx_threshold", 15)
        self.vol_mult = params.get("volume_multiplier", 1.2)
        self.rr_ratio = params.get("min_rr", 1.5)
        self.sl_atr_mult = params.get("sl_atr_mult", 1.0)

    def add_indicators(self, df):
        """Add indicators to 15m dataframe"""
        df['SMA_200'] = ta.sma(df['close'], length=self.ema_filter)
        df['ADX_14'] = ta.adx(df['high'], df['low'], df['close'])['ADX']
        st_data = ta.supertrend(df['high'], df['low'], df['close'], period=self.st_period, multiplier=self.st_multiplier)
        df['Supertrend'] = st_data['Supertrend']
        df['ST_Direction'] = st_data['Direction']
        df['ATR_14'] = ta.atr(df['high'], df['low'], df['close'], length=14)
        return df

    def generate_signal(self, df, extra_data=None):
        """
        Args:
            df: 15m context
            extra_data: {"1m": df_1m} trigger
        """
        if df.empty or len(df) < (self.ema_filter + 10):
            return None
            
        if not extra_data or "1m" not in extra_data:
            return None
            
        df_1m = extra_data["1m"]
        if df_1m.empty or len(df_1m) < 20:
            return None

        # 1. Add 15m indicators
        self.add_indicators(df)
        
        # Latest 15m values (completed candle)
        last_15m = df.iloc[-2]
        close_15m = last_15m['close']
        sma_200_15m = last_15m['SMA_200']
        st_dir_15m = last_15m['ST_Direction']
        adx_15m = last_15m['ADX_14']
        
        # --- 15m SETUP ---
        if adx_15m < self.adx_threshold:
            self.looking_for_entry = False
            return None
            
        if close_15m > sma_200_15m and st_dir_15m == 1:
            self.entry_direction = "LONG"
            self.looking_for_entry = True
        elif close_15m < sma_200_15m and st_dir_15m == -1:
            self.entry_direction = "SHORT"
            self.looking_for_entry = True
        else:
            self.looking_for_entry = False
            return None
            
        # --- 1m TRIGGER ---
        if self.looking_for_entry:
            # Add 1m indicators
            st_data_1m = ta.supertrend(df_1m['high'], df_1m['low'], df_1m['close'], period=self.st_period, multiplier=self.st_multiplier)
            df_1m = df_1m.copy()
            df_1m['ST_Direction'] = st_data_1m['Direction']
            df_1m['Supertrend'] = st_data_1m['Supertrend']
            
            last_1m = df_1m.iloc[-2]
            prev_1m = df_1m.iloc[-3]
            
            # TRIGGER: 1m Supertrend Flip in direction of 15m trend
            if self.entry_direction == "LONG":
                # Flip detected: was bearish, now bullish
                if last_1m['ST_Direction'] == 1 and prev_1m['ST_Direction'] == -1:
                    # SL at ST line or ATR
                    sl = min(last_1m['Supertrend'], last_1m['close'] - (self.sl_atr_mult * last_15m['ATR_14']))
                    risk = last_1m['close'] - sl
                    tp = last_1m['close'] + (self.rr_ratio * risk)
                    
                    self.looking_for_entry = False
                    return {
                        "signal": "BUY",
                        "sl": sl,
                        "tp": tp,
                        "price": last_1m['close'],
                        "comment": f"Supertrend: 15m {self.entry_direction} + 1m Flip. ADX: {adx_15m:.1f}"
                    }
            
            elif self.entry_direction == "SHORT":
                if last_1m['ST_Direction'] == -1 and prev_1m['ST_Direction'] == 1:
                    sl = max(last_1m['Supertrend'], last_1m['close'] + (self.sl_atr_mult * last_15m['ATR_14']))
                    risk = sl - last_1m['close']
                    tp = last_1m['close'] - (self.rr_ratio * risk)
                    
                    self.looking_for_entry = False
                    return {
                        "signal": "SELL",
                        "sl": sl,
                        "tp": tp,
                        "price": last_1m['close'],
                        "comment": f"Supertrend: 15m {self.entry_direction} + 1m Flip. ADX: {adx_15m:.1f}"
                    }
                    
        return None

    def calculate_progress(self, df, extra_data=None):
        """UI Progress calculation"""
        if df.empty or len(df) < self.ema_filter:
            return 0
            
        self.add_indicators(df)
        last_15m = df.iloc[-1]
        
        progress = 0
        
        # 1. EMA Filter (30%)
        if (last_15m['close'] > last_15m['SMA_200'] and last_15m['ST_Direction'] == 1) or \
           (last_15m['close'] < last_15m['SMA_200'] and last_15m['ST_Direction'] == -1):
            progress += 50
            
        # 2. ADX (20%)
        if last_15m['ADX_14'] >= self.adx_threshold:
            progress += 20
        else:
            progress += int((last_15m['ADX_14'] / self.adx_threshold) * 20)
            
        # 3. 1m alignment (30%)
        if extra_data and "1m" in extra_data:
            df_1m = extra_data["1m"]
            if not df_1m.empty:
                st_data_1m = ta.supertrend(df_1m['high'], df_1m['low'], df_1m['close'], period=self.st_period, multiplier=self.st_multiplier)
                if st_data_1m['Direction'].iloc[-1] == last_15m['ST_Direction']:
                    progress += 30
        
        return min(100, progress)
