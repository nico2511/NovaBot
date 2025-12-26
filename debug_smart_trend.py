#!/usr/bin/env python3
"""
Debug script to understand why StrategySmartTrend is not generating signals.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import pandas as pd
import numpy as np
from strategies.definitions import StrategySmartTrend
from app.services.indicators import ta

def create_synthetic_15m_data():
    """Create synthetic 15m data with a trend and pullback"""
    dates = pd.date_range(start='2025-01-01', periods=100, freq='15min')
    
    # Create uptrend with pullback
    close_prices = np.linspace(50000, 52000, 100)
    # Add a pullback around candle 80
    close_prices[80:85] = [51800, 51600, 51500, 51550, 51700]
    
    df = pd.DataFrame({
        'open': close_prices - 50,
        'high': close_prices + 100,
        'low': close_prices - 100,
        'close': close_prices,
        'volume': np.random.uniform(100, 200, 100)
    }, index=dates)
    
    return df

def create_synthetic_1m_data_with_bos():
    """Create synthetic 1m data with a micro-BOS (break of structure)"""
    dates = pd.date_range(start='2025-01-01 20:00', periods=20, freq='1min')
    
    # Create data where last candle breaks above previous 3 highs
    close_prices = [51700, 51710, 51705, 51715, 51720, 51718, 51722, 51725, 
                   51730, 51728, 51732, 51735, 51733, 51738, 51740, 51742,
                   51745, 51743, 51748, 51755]  # Last one breaks above
    
    df = pd.DataFrame({
        'open': [c - 5 for c in close_prices],
        'high': [c + 10 for c in close_prices],
        'low': [c - 10 for c in close_prices],
        'close': close_prices,
        'volume': np.random.uniform(10, 20, 20)
    }, index=dates)
    
    return df

# Initialize strategy
strategy = StrategySmartTrend(config={"params": {}})

# Create data
df_15m = create_synthetic_15m_data()
df_1m = create_synthetic_1m_data_with_bos()

# Add indicators manually to debug
strategy.add_indicators(df_15m)

print("=" * 60)
print("DEBUG: 15m Data Analysis")
print("=" * 60)
print(f"Last 5 candles of 15m:")
print(df_15m[['close', 'low', 'high']].tail())
print(f"\nEMA_21: {df_15m['EMA_21'].iloc[-1]:.2f}")
print(f"EMA_50: {df_15m['EMA_50'].iloc[-1]:.2f}")
print(f"Close: {df_15m['close'].iloc[-1]:.2f}")
print(f"Low: {df_15m['low'].iloc[-1]:.2f}")
print(f"\nChecking LONG setup conditions:")
print(f"  Close > EMA_50? {df_15m['close'].iloc[-1]} > {df_15m['EMA_50'].iloc[-1]} = {df_15m['close'].iloc[-1] > df_15m['EMA_50'].iloc[-1]}")
print(f"  Low <= EMA_21 * 1.002? {df_15m['low'].iloc[-1]} <= {df_15m['EMA_21'].iloc[-1] * 1.002} = {df_15m['low'].iloc[-1] <= df_15m['EMA_21'].iloc[-1] * 1.002}")

print("\n" + "=" * 60)
print("DEBUG: 1m Data Analysis")
print("=" * 60)
print(f"Last 5 candles of 1m:")
print(df_1m[['close', 'low', 'high']].tail())

last_3_1m = df_1m.iloc[-4:-1]
current_1m = df_1m.iloc[-1]
print(f"\nLast 3 candles high max: {last_3_1m['high'].max():.2f}")
print(f"Current close: {current_1m['close']:.2f}")
print(f"Current close > Last 3 high? {current_1m['close']} > {last_3_1m['high'].max()} = {current_1m['close'] > last_3_1m['high'].max()}")

print("\n" + "=" * 60)
print("Calling generate_signal...")
print("=" * 60)

signal = strategy.generate_signal(df_15m, extra_data={"1m": df_1m})

if signal:
    print("✅ SIGNAL GENERATED")
    print(signal)
else:
    print("❌ NO SIGNAL")
    print(f"Strategy state:")
    print(f"  looking_for_entry: {strategy.looking_for_entry}")
    print(f"  entry_direction: {strategy.entry_direction}")
