#!/usr/bin/env python3
"""
Verification script for StrategySmartTrend MTF logic.
Tests that the strategy correctly identifies 15m context and 1m triggers.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import pandas as pd
import numpy as np
from strategies.definitions import StrategySmartTrend
from app.services.indicators import ta

def create_synthetic_15m_data():
    """Create synthetic 15m data with a trend and pullback to EMA 21"""
    dates = pd.date_range(start='2025-01-01', periods=100, freq='15min')
    
    # Create uptrend 
    close_prices = np.linspace(50000, 52000, 100)
    
    # Calculate what EMA 21 will be approximately at the end
    # For simplicity, we'll create a pullback that touches around 51700
    # which should be near EMA 21
    close_prices[95:] = [51950, 51900, 51750, 51720, 51800]  # Pullback then bounce
    
    df = pd.DataFrame({
        'open': close_prices - 50,
        'high': close_prices + 100,
        'low': close_prices - 100,  # Low will touch lower
        'close': close_prices,
        'volume': np.random.uniform(100, 200, 100)
    }, index=dates)
    
    # Adjust the last candle's low to ensure it touches EMA 21
    # We'll do this after calculating EMA
    return df

def create_synthetic_1m_data_with_bos():
    """Create synthetic 1m data with a clear micro-BOS (break of structure)"""
    dates = pd.date_range(start='2025-01-01 20:00', periods=20, freq='1min')
    
    # Create data where:
    # - Candles 16, 17, 18 have highs around 51750
    # - Candle 19 (last) closes ABOVE those highs (clear BOS)
    close_prices = [51700, 51710, 51705, 51715, 51720, 51718, 51722, 51725, 
                   51730, 51728, 51732, 51735, 51733, 51738, 51740, 51742,
                   51745, 51743, 51748, 51760]  # Last one clearly breaks above
    
    # Make sure highs of last 3 before current are lower than current close
    highs = [c + 10 for c in close_prices]
    highs[-4] = 51752  # Candle 16 high
    highs[-3] = 51753  # Candle 17 high  
    highs[-2] = 51754  # Candle 18 high
    # Current close (51760) > all these highs
    
    df = pd.DataFrame({
        'open': [c - 5 for c in close_prices],
        'high': highs,
        'low': [c - 10 for c in close_prices],
        'close': close_prices,
        'volume': np.random.uniform(10, 20, 20)
    }, index=dates)
    
    return df

def create_synthetic_1m_data_no_bos():
    """Create synthetic 1m data WITHOUT a micro-BOS"""
    dates = pd.date_range(start='2025-01-01 20:00', periods=20, freq='1min')
    
    # Create ranging data
    close_prices = [51700 + np.random.uniform(-10, 10) for _ in range(20)]
    
    df = pd.DataFrame({
        'open': [c - 5 for c in close_prices],
        'high': [c + 10 for c in close_prices],
        'low': [c - 10 for c in close_prices],
        'close': close_prices,
        'volume': np.random.uniform(10, 20, 20)
    }, index=dates)
    
    return df

def test_strategy():
    """Test the StrategySmartTrend"""
    print("=" * 60)
    print("Testing StrategySmartTrend MTF Logic")
    print("=" * 60)
    
    # Initialize strategy
    strategy = StrategySmartTrend(config={"params": {}})
    
    # Test 1: 15m context + 1m trigger (should generate signal)
    print("\n[TEST 1] 15m Context + 1m Trigger (BOS)")
    df_15m = create_synthetic_15m_data()
    df_1m_bos = create_synthetic_1m_data_with_bos()
    
    signal = strategy.generate_signal(df_15m, extra_data={"1m": df_1m_bos})
    
    if signal:
        print("✅ SIGNAL GENERATED")
        print(f"   Signal: {signal['signal']}")
        print(f"   Entry: {signal['price']:.2f}")
        print(f"   SL: {signal['sl']:.2f}")
        print(f"   TP: {signal['tp']:.2f}")
        print(f"   RR: {(signal['tp'] - signal['price']) / (signal['price'] - signal['sl']):.2f}")
        print(f"   Comment: {signal['comment']}")
    else:
        print("❌ NO SIGNAL (Expected signal)")
    
    # Test 2: 15m context + 1m NO trigger (should NOT generate signal)
    print("\n[TEST 2] 15m Context + 1m NO Trigger")
    df_1m_no_bos = create_synthetic_1m_data_no_bos()
    
    signal = strategy.generate_signal(df_15m, extra_data={"1m": df_1m_no_bos})
    
    if signal:
        print("❌ SIGNAL GENERATED (Should not generate)")
        print(f"   Signal: {signal}")
    else:
        print("✅ NO SIGNAL (Correct)")
    
    # Test 3: No 1m data (should NOT generate signal)
    print("\n[TEST 3] No 1m Data")
    signal = strategy.generate_signal(df_15m, extra_data=None)
    
    if signal:
        print("❌ SIGNAL GENERATED (Should not generate without 1m data)")
    else:
        print("✅ NO SIGNAL (Correct - needs 1m data)")
    
    print("\n" + "=" * 60)
    print("Verification Complete")
    print("=" * 60)

if __name__ == "__main__":
    test_strategy()
