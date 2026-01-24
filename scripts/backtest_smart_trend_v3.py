
import pandas as pd
import sys
import os
import time

# Add project root to path
sys.path.append(os.getcwd())

from strategies.smart_trend import StrategySmartTrend
from app.services.indicators import ta

class OptimizedSmartTrend(StrategySmartTrend):
    def add_indicators(self, df):
        return df

def run_backtest(csv_path):
    print(f"📥 Loading data from {csv_path}...")
    try:
        df = pd.read_csv(csv_path)
    except Exception as e:
        print(f"❌ Error loading CSV: {e}")
        return
        
    df.rename(columns={'Open':'open','High':'high','Low':'low','Close':'close','Volume':'volume'}, inplace=True)
    
    config = {"params": {"pullback_tolerance": 0.0025, "adx_threshold": 28, "volume_multiplier": 1.3}}
    
    print("💎 Pre-calculating Indicators (EMA, ATR, ADX)...")
    df['EMA_21'] = ta.ema(df['close'], length=21)
    df['EMA_50'] = ta.ema(df['close'], length=50)
    df['ATR_15'] = ta.atr(df['high'], df['low'], df['close'], length=14)
    adx_df = ta.adx(df['high'], df['low'], df['close'], length=14)
    df['ADX_14'] = adx_df['ADX']
    
    strategy = OptimizedSmartTrend(config)
    
    print(f"🔬 Running analysis on {len(df)} candles...")
    
    long_setups = 0
    short_setups = 0
    
    for i in range(200, len(df)):
        window = df.iloc[i-100:i+1]
        
        adx = window['ADX_14'].iloc[-1]
        if adx < 28: continue
            
        close_15m = window['close'].iloc[-1]
        ema_21 = window['EMA_21'].iloc[-1]
        ema_50 = window['EMA_50'].iloc[-1]
        
        # LONG check
        long_ema_align = ema_21 > ema_50
        long_trend = close_15m > ema_50 and long_ema_align
        if long_trend:
            low_15m = window['low'].iloc[-1]
            long_pullback = (low_15m <= ema_21 * (1 + 0.0025) and low_15m >= ema_21 * (1 - 0.0025))
            if long_pullback:
                avg_vol = window['volume'].iloc[-22:-2].mean()
                if window['volume'].iloc[-2] >= avg_vol * 1.3:
                    long_setups += 1
        
        # SHORT check
        short_ema_align = ema_21 < ema_50
        short_trend = close_15m < ema_50 and short_ema_align
        if short_trend:
            high_15m = window['high'].iloc[-1]
            short_pullback = (high_15m >= ema_21 * (1 - 0.0025) and high_15m <= ema_21 * (1 + 0.0025))
            if short_pullback:
                avg_vol = window['volume'].iloc[-22:-2].mean()
                if window['volume'].iloc[-2] >= avg_vol * 1.3:
                    short_setups += 1

    print(f"\n📊 FINAL RESULTS (BTC 15m 6mo):")
    print(f"Total LONG Setups: {long_setups}")
    print(f"Total SHORT Setups: {short_setups}")
    print(f"Total signals: {long_setups + short_setups}")
    print(f"Avg Frequency: ~{(long_setups + short_setups)/180:.2f} signals/day")
    
if __name__ == "__main__":
    run_backtest("data/BTC_15m_6months.csv")
