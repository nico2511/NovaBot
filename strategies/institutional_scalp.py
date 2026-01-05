from app.services.indicators import ta
import pandas as pd
from strategies.base import BaseStrategy

class InstitutionalScalp(BaseStrategy):
    """
    Institutional Scalp Strategy - Liquidity Grab Detection
    
    Detects institutional liquidity grabs (stop hunts) and trades the reversal.
    """
    
    def add_indicators(self, df):
        df['ATRr_14'] = ta.atr(df['high'], df['low'], df['close'], length=14)
        return df

    def generate_signal(self, df, extra_data=None):
        if df.empty or len(df) < 30:
            return None

        self.add_indicators(df)

        params = self.config.get("params", {})
        lookback = params.get("liq_grab_lookback", 20)
        atr_col = "ATRr_14"

        if atr_col not in df.columns:
            return None
        
        # GUARD CLAUSE: Mean Reversion only in Range (ADX < 25)
        # Check if ADX is available (added by engine.py)
        if 'ADX_14' in df.columns:
            current_adx = df['ADX_14'].iloc[-2]
            if current_adx > 25:
                return None  # Trend detected, skip mean reversion

        current = df.iloc[-2]  # Use confirmed candle (anti-repainting)
        close = current['close']
        high = current['high']
        low = current['low']
        atr = current[atr_col]

        recent = df.tail(lookback + 1)
        recent_high = recent['high'].iloc[:-1].max()
        recent_low = recent['low'].iloc[:-1].min()

        # BULLISH LIQUIDITY GRAB
        if low < recent_low and close > recent_low:
            candle_range = high - low
            if candle_range > 0 and (close - low) / candle_range > 0.5:
                # PHASE 2: Volume Spike Filter
                # Liquidity grabs need volume confirmation to avoid fakeouts
                if 'volume' in df.columns:
                    current_volume = current['volume']
                    avg_volume = df['volume'].iloc[-21:-1].mean()  # Last 20 candles (excluding current)
                    
                    if current_volume < (avg_volume * 1.5):
                        # Insufficient volume, likely a fakeout
                        return None
                
                return {
                    "signal": "BUY",
                    "sl": low - (0.5 * atr),
                    "tp": close + (2.0 * atr),
                    "comment": "Bullish Liquidity Grab"
                }

        # BEARISH LIQUIDITY GRAB
        if high > recent_high and close < recent_high:
            candle_range = high - low
            if candle_range > 0 and (high - close) / candle_range > 0.5:
                # PHASE 2: Volume Spike Filter
                # Liquidity grabs need volume confirmation to avoid fakeouts
                if 'volume' in df.columns:
                    current_volume = current['volume']
                    avg_volume = df['volume'].iloc[-21:-1].mean()  # Last 20 candles (excluding current)
                    
                    if current_volume < (avg_volume * 1.5):
                        # Insufficient volume, likely a fakeout
                        return None
                
                return {
                    "signal": "SELL",
                    "sl": high + (0.5 * atr),
                    "tp": close - (2.0 * atr),
                    "comment": "Bearish Liquidity Grab"
                }
        
        return None
    
    def calculate_progress(self, df, extra_data=None):
        """Calculate proximity to liquidity grab signal"""
        if df is None or df.empty or len(df) < 30:
            return 0
        
        try:
            self.add_indicators(df)
            params = self.config.get("params", {})
            lookback = params.get("liq_grab_lookback", 20)
            
            current = df.iloc[-1]
            close = current['close']
            high = current['high']
            low = current['low']
            
            recent = df.tail(lookback + 1)
            recent_high = recent['high'].iloc[:-1].max()
            recent_low = recent['low'].iloc[:-1].min()
            
            progress = 0
            
            # Check proximity to recent high/low
            distance_to_high = abs(high - recent_high) / recent_high
            distance_to_low = abs(low - recent_low) / recent_low
            
            if distance_to_high < 0.01 or distance_to_low < 0.01:
                progress += 50
            elif distance_to_high < 0.02 or distance_to_low < 0.02:
                progress += 30
            
            # Check for wick formation
            candle_range = high - low
            if candle_range > 0:
                upper_wick = (high - max(close, current['open'])) / candle_range
                lower_wick = (min(close, current['open']) - low) / candle_range
                
                if upper_wick > 0.4 or lower_wick > 0.4:
                    progress += 30
            
            return min(100, progress)
        except:
            return 0
    
    def check_conditions(self, df, extra_data=None):
        """Check detailed conditions for UI display"""
        if df is None or df.empty or len(df) < 30:
            return []
        
        try:
            self.add_indicators(df)
            params = self.config.get("params", {})
            lookback = params.get("liq_grab_lookback", 20)
            
            current = df.iloc[-1]
            close = current['close']
            high = current['high']
            low = current['low']
            
            recent = df.tail(lookback + 1)
            recent_high = recent['high'].iloc[:-1].max()
            recent_low = recent['low'].iloc[:-1].min()
            
            conditions = []
            
            # Liquidity Level Proximity
            at_high = abs(high - recent_high) / recent_high < 0.01
            at_low = abs(low - recent_low) / recent_low < 0.01
            
            conditions.append({
                "name": "At Liquidity Level",
                "status": at_high or at_low,
                "value": f"High: ${recent_high:.4f}, Low: ${recent_low:.4f}"
            })
            
            # Wick Formation
            candle_range = high - low
            if candle_range > 0:
                upper_wick = (high - max(close, current['open'])) / candle_range
                lower_wick = (min(close, current['open']) - low) / candle_range
                
                has_wick = upper_wick > 0.4 or lower_wick > 0.4
                conditions.append({
                    "name": "Wick Formation (>40%)",
                    "status": has_wick,
                    "value": f"Upper: {upper_wick*100:.0f}%, Lower: {lower_wick*100:.0f}%"
                })
            
            # Reversal Candle
            bullish_reversal = low < recent_low and close > recent_low
            bearish_reversal = high > recent_high and close < recent_high
            
            conditions.append({
                "name": "Reversal Candle",
                "status": bullish_reversal or bearish_reversal,
                "value": "Bullish" if bullish_reversal else "Bearish" if bearish_reversal else "None"
            })
            
            return conditions
        except Exception as e:
            return [{"name": "Error", "status": False, "value": str(e)}]
