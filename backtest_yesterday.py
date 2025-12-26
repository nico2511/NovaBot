#!/usr/bin/env python3
"""
Backtest script to analyze yesterday's trading activity
Checks if any strategies would have triggered signals
"""
import pandas as pd
import sys
import os
from datetime import datetime, timedelta

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.services.hyperliquid_service import hyperliquid_service
from strategies.engine import StrategyEngine
from app.core.risk_manager import RiskManager

def analyze_period(symbol="BTC", hours_back=24):
    """
    Analyze a specific time period to see if strategies would have triggered
    """
    print("=" * 80)
    print(f"🔍 BACKTEST ANALYSIS: {symbol}")
    print(f"📅 Period: Last {hours_back} hours (Yesterday until now)")
    print("=" * 80)
    
    # Calculate how many 15m candles we need
    # 1 hour = 4 candles (15m each)
    # Plus 200 extra for indicator warmup (EMA200, etc.)
    candles_needed = (hours_back * 4) + 200
    
    print(f"\n📡 Fetching {candles_needed} candles ({hours_back}h + warmup)...")
    df = hyperliquid_service.get_candles(symbol, interval="15m", limit=candles_needed)
    
    if df.empty:
        print("❌ No data received from Hyperliquid API")
        return
    
    print(f"✅ Received {len(df)} candles")
    print(f"📊 Time range: {df.index[0]} to {df.index[-1]}")
    
    # Calculate the cutoff time (24h ago from now)
    # Make timezone-naive to match the dataframe index
    now = pd.Timestamp.now()
    cutoff_time = now - pd.Timedelta(hours=hours_back)
    
    # Filter to only analyze the target period
    analysis_df = df[df.index >= cutoff_time]
    print(f"\n🎯 Analyzing {len(analysis_df)} candles from {cutoff_time} onwards")
    
    # Setup strategy engine
    rm = RiskManager()
    engine = StrategyEngine(rm)
    
    # Load strategies config
    import json
    with open('strategies.json', 'r') as f:
        config = json.load(f)
    
    enabled_strategies = [name for name, cfg in config['strategies'].items() if cfg.get('enabled', False)]
    print(f"\n⚙️ Enabled strategies: {', '.join(enabled_strategies)}")
    
    # Track signals
    all_signals = []
    candle_count = 0
    
    print("\n" + "=" * 80)
    print("🔄 SCANNING FOR SIGNALS...")
    print("=" * 80)
    
    # Simulate going through each candle in the analysis period
    min_window = 200  # Need enough data for indicators
    
    for i in range(len(df)):
        current_time = df.index[i]
        
        # Only analyze candles in our target period
        if current_time < cutoff_time:
            continue
        
        candle_count += 1
        
        # Get data window up to this point
        window = df.iloc[:i+1]
        
        if len(window) < min_window:
            continue
        
        # Analyze with strategy engine
        result = engine.analyze(window)
        
        current_candle = window.iloc[-1]
        current_price = current_candle['close']
        
        # Check if any signals were generated
        if result.get("signals"):
            for sig in result["signals"]:
                signal_info = {
                    'time': current_time,
                    'strategy': sig.get('strategy', 'Unknown'),
                    'signal': sig.get('signal'),
                    'price': sig.get('price', current_price),
                    'sl': sig.get('sl'),
                    'tp': sig.get('tp'),
                    'comment': sig.get('comment', ''),
                    'regime': result.get('regime', 'UNKNOWN')
                }
                all_signals.append(signal_info)
                
                # Print signal immediately
                print(f"\n🚨 SIGNAL DETECTED!")
                print(f"   Time: {current_time}")
                print(f"   Strategy: {sig.get('strategy')}")
                print(f"   Action: {sig.get('signal')}")
                print(f"   Price: ${sig.get('price', current_price):.2f}")
                print(f"   SL: ${sig.get('sl'):.2f}")
                print(f"   TP: ${sig.get('tp'):.2f}")
                print(f"   Comment: {sig.get('comment')}")
                print(f"   Market Regime: {result.get('regime')}")
    
    # Summary
    print("\n" + "=" * 80)
    print("📊 ANALYSIS SUMMARY")
    print("=" * 80)
    print(f"Total candles analyzed: {candle_count}")
    print(f"Total signals found: {len(all_signals)}")
    
    if all_signals:
        print("\n📋 DETAILED SIGNAL LIST:")
        print("-" * 80)
        for i, sig in enumerate(all_signals, 1):
            print(f"\n{i}. {sig['time']}")
            print(f"   Strategy: {sig['strategy']}")
            print(f"   Action: {sig['signal']} @ ${sig['price']:.2f}")
            print(f"   SL: ${sig['sl']:.2f} | TP: ${sig['tp']:.2f}")
            print(f"   Risk/Reward: {abs((sig['tp'] - sig['price']) / (sig['price'] - sig['sl'])):.2f}")
            print(f"   Comment: {sig['comment']}")
        
        # Strategy breakdown
        print("\n" + "=" * 80)
        print("📈 SIGNALS BY STRATEGY:")
        print("-" * 80)
        strategy_counts = {}
        for sig in all_signals:
            strat = sig['strategy']
            strategy_counts[strat] = strategy_counts.get(strat, 0) + 1
        
        for strat, count in sorted(strategy_counts.items(), key=lambda x: x[1], reverse=True):
            print(f"   {strat}: {count} signal(s)")
    else:
        print("\n⚠️ NO SIGNALS DETECTED")
        print("\nPossible reasons:")
        print("   1. Strategies are too strict (conditions not met)")
        print("   2. Market conditions didn't match strategy requirements")
        print("   3. No clear trend or setup during this period")
        print("\n💡 Suggestions:")
        print("   - Review strategy parameters in strategies.json")
        print("   - Check if market regime detection is too restrictive")
        print("   - Consider adjusting RSI thresholds, EMA periods, etc.")
    
    print("\n" + "=" * 80)
    
    return all_signals


if __name__ == "__main__":
    # Default: analyze last 24 hours
    hours = 30  # Slightly more than 24h to cover "yesterday until now"
    
    if len(sys.argv) > 1:
        try:
            hours = int(sys.argv[1])
        except:
            print("Usage: python backtest_yesterday.py [hours_back]")
            sys.exit(1)
    
    signals = analyze_period(hours_back=hours)
    
    if signals:
        print(f"\n✅ Analysis complete. Found {len(signals)} potential trade(s).")
    else:
        print("\n⚠️ Analysis complete. No signals detected - strategies may be too strict.")
