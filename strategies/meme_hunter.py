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
        if len(df) < self.ema_trend:
            return None
            
        df = self.add_indicators(df.copy())
        
        curr = df.iloc[-1]
        prev = df.iloc[-2]
        
        ema_fast_col = f'EMA_{self.ema_fast}'
        ema_slow_col = f'EMA_{self.ema_slow}'
        ema_trend_col = f'EMA_{self.ema_trend}'
        
        # --- BULLISH SIGNAL (EMA 20 crosses above EMA 50) ---
        if prev[ema_fast_col] <= prev[ema_slow_col] and curr[ema_fast_col] > curr[ema_slow_col]:
            # Basic Trend Filter
            if curr['close'] > curr[ema_trend_col]:
                # Supple RSI Filter
                if curr['RSI'] < self.rsi_buy_max:
                    # Volatility Check: BB Width expanding or > threshold
                    if curr['BB_Width'] > prev['BB_Width'] or curr['BB_Width'] > 0.02:
                        sl = curr['close'] - (self.atr_mult * curr['ATR'])
                        risk = curr['close'] - sl
                        tp = curr['close'] + (risk * self.rr_ratio)
                        
                        return {
                            "signal": "BUY",
                            "price": float(curr['close']),
                            "sl": float(sl),
                            "tp": float(tp),
                            "strategy": "MemeVolatilityHunter",
                            "comment": f"EMA {self.ema_fast}/{self.ema_slow} Golden Cross | RSI: {curr['RSI']:.1f}"
                        }

        # --- BEARISH SIGNAL (EMA 20 crosses below EMA 50) ---
        elif prev[ema_fast_col] >= prev[ema_slow_col] and curr[ema_fast_col] < curr[ema_slow_col]:
            # Basic Trend Filter
            if curr['close'] < curr[ema_trend_col]:
                # Supple RSI Filter
                if curr['RSI'] > self.rsi_sell_min:
                    if curr['BB_Width'] > prev['BB_Width'] or curr['BB_Width'] > 0.02:
                        sl = curr['close'] + (self.atr_mult * curr['ATR'])
                        risk = sl - curr['close']
                        tp = curr['close'] - (risk * self.rr_ratio)
                        
                        return {
                            "signal": "SELL",
                            "price": float(curr['close']),
                            "sl": float(sl),
                            "tp": float(tp),
                            "strategy": "MemeVolatilityHunter",
                            "comment": f"EMA {self.ema_fast}/{self.ema_slow} Death Cross | RSI: {curr['RSI']:.1f}"
                        }
                        
        return None

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
