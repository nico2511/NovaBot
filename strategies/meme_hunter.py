from app.services.indicators import TaAdapter
from strategies.base import BaseStrategy
import pandas as pd
import numpy as np

# Use the singleton adapter
ta = TaAdapter()

class StrategyMemeHunter(BaseStrategy):
    """
    MEME HUNTER STRATEGY
    Designed for volatile assets using 15m Momentum.
    
    Trigger:
    - EMA 20 / EMA 50 Crossover (Golden/Death Cross)
    
    Filters:
    - Trend Filter: Price vs EMA 200
    - Supple RSI: Allows entries up to RSI 85 (Buy) / 15 (Sell) in strong trends.
    - Volatility Check: Bollinger Band Width should be expanding.
    
    Risk Management:
    - SL: 2.0x ATR
    - TP: 1.5x Risk (Ratio 1:1.5) or Trend reversal.
    """

    AI_PERSONA = """
    CODENAME: "VOLATILITY VOYAGER"
    
    ROLE:
    You are a momentum sniper. You don't fear extreme RSI; you fear missing a confirmed trend shift.
    
    PRIME DIRECTIVE:
    Identify when the short-term momentum (EMA 20) flips the medium-term balance (EMA 50) in a high-volatility environment.
    """

    def __init__(self, config=None):
        super().__init__(config)
        params = self.config.get("params", {})
        self.ema_fast = params.get("ema_fast", 20)
        self.ema_slow = params.get("ema_slow", 50)
        self.ema_trend = params.get("ema_trend", 200)
        self.rsi_buy_max = params.get("rsi_buy_max", 85)
        self.rsi_sell_min = params.get("rsi_sell_min", 15)
        self.atr_mult = params.get("atr_multiplier", 2.0)
        self.rr_ratio = params.get("min_rr", 1.5)

    def add_indicators(self, df):
        """Add indicators to dataframe"""
        # We need standard EMAs for crossovers
        df[f'EMA_{self.ema_fast}'] = ta.ema_std(df['close'], length=self.ema_fast)
        df[f'EMA_{self.ema_slow}'] = ta.ema_std(df['close'], length=self.ema_slow)
        df[f'EMA_{self.ema_trend}'] = ta.ema_std(df['close'], length=self.ema_trend)
        
        df['RSI'] = ta.rsi(df['close'], length=14)
        df['ATR'] = ta.atr(df['high'], df['low'], df['close'], length=14)
        
        # Bollinger Bands for volatility check
        bb = ta.bbands(df['close'], length=20, std=2.0)
        df['BB_Width'] = (bb['BBU'] - bb['BBL']) / bb['BBM']
        
        return df

    def generate_signal(self, df, extra_data=None):
        """Generate signals based on EMA crossover and volatility"""
        if len(df) < self.ema_trend + 10: # Extra padding for accurate EMA/Slope
            return self._reject("Not enough candles for stable EMA trend/slope")
            
        df = self.add_indicators(df.copy())
        
        # --- STABILITY FIX ---
        # Use iloc[-2] (last confirmed candle) and iloc[-3] (previous confirmed)
        # to detect the crossover on CLOSED data. This prevents repainting.
        curr = df.iloc[-2]
        prev = df.iloc[-3]
        
        # Also get forming candle (iloc[-1]) just for logging price context
        live = df.iloc[-1]
        
        ema_fast_col = f'EMA_{self.ema_fast}'
        ema_slow_col = f'EMA_{self.ema_slow}'
        ema_trend_col = f'EMA_{self.ema_trend}'
        
        # Calculate Slope (EMA 50 orientation)
        ema_slow_prev_slope = df[ema_slow_col].iloc[-7] # 5 candles lookback
        ema_slope = (curr[ema_slow_col] - ema_slow_prev_slope) / ema_slow_prev_slope * 100
        
        params = self.config.get("params", {})
        min_slope = params.get("min_slope", 0.001)
        test_mode = params.get("test_mode", False)
        buy_rsi_limit = params.get("rsi_buy_max", self.rsi_buy_max)
        sell_rsi_limit = params.get("rsi_sell_min", self.rsi_sell_min)

        # Crossover Detection
        is_bullish_cross = prev[ema_fast_col] <= prev[ema_slow_col] and curr[ema_fast_col] > curr[ema_slow_col]
        is_bearish_cross = prev[ema_fast_col] >= prev[ema_slow_col] and curr[ema_fast_col] < curr[ema_slow_col]


        # --- BULLISH SIGNAL ---
        if is_bullish_cross:
            # 1. Trend Filter
            if not curr['close'] > curr[ema_trend_col]:
                print(f"[MemeHunter] Cross UP detected but rejected: Price ({curr['close']:.4f}) below EMA 200 ({curr[ema_trend_col]:.4f})")
                return self._reject("Bull cross below EMA trend filter")
            
            # 2. Slope Filter
            if ema_slope < min_slope:
                print(f"[MemeHunter] Cross UP detected but rejected: EMA 50 Slope ({ema_slope:.5f}) below Min ({min_slope})")
                return self._reject("Bull cross slope below minimum")

            # 3. RSI Filter
            if not curr['RSI'] < buy_rsi_limit:
                print(f"[MemeHunter] Cross UP detected but rejected: RSI ({curr['RSI']:.1f}) above limit ({buy_rsi_limit})")
                return self._reject("Bull cross RSI above buy limit")

            vol_ok = curr['BB_Width'] > prev['BB_Width'] or curr['BB_Width'] > 0.02
            if not vol_ok:
                print(f"[MemeHunter] Cross UP detected but rejected: BB Width ({curr['BB_Width']:.4f}) not expanding")
                return self._reject("Bull cross volatility filter failed")

            # If all PASS -> BUY
            sl = curr['close'] - (self.atr_mult * curr['ATR'])
            risk = curr['close'] - sl
            tp = curr['close'] + (risk * self.rr_ratio)
            
            return {
                "signal": "BUY",
                "price": float(live['close']), # Use live price for entry
                "sl": float(sl),
                "tp": float(tp),
                "strategy": "MemeVolatilityHunter",
                "comment": f"{'[TEST MODE] ' if test_mode else ''}EMA {self.ema_fast}/{self.ema_slow} Golden Cross | Slope: {ema_slope:.4f}"
            }

        # --- BEARISH SIGNAL ---
        elif is_bearish_cross:
            # 1. Trend Filter
            if not curr['close'] < curr[ema_trend_col]:
                print(f"[MemeHunter] Cross DOWN detected but rejected: Price ({curr['close']:.4f}) above EMA 200")
                return self._reject("Bear cross above EMA trend filter")
                
            # 2. Slope Filter
            if ema_slope > -min_slope:
                print(f"[MemeHunter] Cross DOWN detected but rejected: EMA 50 Slope ({ema_slope:.5f}) not negative enough (< {-min_slope})")
                return self._reject("Bear cross slope not negative enough")

            # 3. RSI Filter
            if not curr['RSI'] > sell_rsi_limit:
                print(f"[MemeHunter] Cross DOWN detected but rejected: RSI ({curr['RSI']:.1f}) below limit ({sell_rsi_limit})")
                return self._reject("Bear cross RSI below sell limit")

            vol_ok = curr['BB_Width'] > prev['BB_Width'] or curr['BB_Width'] > 0.02
            if not vol_ok:
                print(f"[MemeHunter] Cross DOWN detected but rejected: BB Width not expanding")
                return self._reject("Bear cross volatility filter failed")

            # If all PASS -> SELL
            sl = curr['close'] + (self.atr_mult * curr['ATR'])
            risk = sl - curr['close']
            tp = curr['close'] - (risk * self.rr_ratio)
            
            return {
                "signal": "SELL",
                "price": float(live['close']),
                "sl": float(sl),
                "tp": float(tp),
                "strategy": "MemeVolatilityHunter",
                "comment": f"EMA {self.ema_fast}/{self.ema_slow} Death Cross | Slope: {ema_slope:.4f}"
            }
                        
        return self._reject("No fresh EMA20/50 crossover on confirmed candles")

    def calculate_progress(self, df, extra_data=None):
        """UI Progress for Meme Hunter"""
        if len(df) < self.ema_slow:
             return {"strategy": "MemeHunter", "score": 0, "stages": []}
             
        df = self.add_indicators(df.copy())
        curr = df.iloc[-1]
        
        stages = []
        score = 0
        
        # 1. Trend Direction
        trend_ok = (curr['close'] > curr[f'EMA_{self.ema_trend}']) or (curr['close'] < curr[f'EMA_{self.ema_trend}'])
        stages.append({
            "name": "Trend Bias",
            "status": "PASS" if trend_ok else "WAIT",
            "details": f"Price vs EMA {self.ema_trend}"
        })
        if trend_ok: score += 30
        
        # 2. EMA Alignment
        ema_gap = abs(curr[f'EMA_{self.ema_fast}'] - curr[f'EMA_{self.ema_slow}']) / curr['close'] * 100
        ema_align = (curr['close'] > curr[f'EMA_{self.ema_fast}']) or (curr['close'] < curr[f'EMA_{self.ema_fast}'])
        stages.append({
            "name": "Momentum Alignment",
            "status": "PASS" if ema_align else "WAIT",
            "details": f"Price vs EMA {self.ema_fast}"
        })
        if ema_align: score += 40
        
        # 3. Volatility Check
        vol_ok = curr['BB_Width'] > 0.015
        stages.append({
            "name": "Volatility Health",
            "status": "PASS" if vol_ok else "WAIT",
            "details": f"BB Width: {curr['BB_Width']*100:.2f}%"
        })
        if vol_ok: score += 30
        
        return {
            "strategy": "MemeHunter",
            "score": score,
            "bias": "LONG" if curr['close'] > curr[f'EMA_{self.ema_trend}'] else "SHORT",
            "stages": stages
        }
