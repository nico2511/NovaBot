#!/usr/bin/env python3
"""
Test New Strategies - Pattern Recognition & Range Trading
Tests the 6 newly implemented strategies on historical data
"""

import sys
import os
import json
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))

from backtest.backtest_engine import BacktestEngine
from app.services.hyperliquid_service import hyperliquid_service

# List of new strategies to test
NEW_STRATEGIES = [
    # Pattern Recognition Strategies
    "double_bottom",
    "double_top",
    "bull_flag",
    "head_shoulders",
    
    # Range Trading Strategies
    "bollinger_bounce",
    # "rsi_ping_pong", # Disabled for now
    
    # Scalping Strategies
    "institutional_scalp"
]

def test_single_strategy(strategy_name, df, symbol):
    """Test a specific strategy only"""
    # Load base config
    with open("strategies.json", "r") as f:
        base_config = json.load(f)
    
    # Create config with ONLY this strategy enabled
    test_config = {
        "market_regime": base_config["market_regime"],
        "strategies": {}
    }
    
    # Enable only the target strategy
    for strat_name, strat_conf in base_config["strategies"].items():
        test_config["strategies"][strat_name] = strat_conf.copy()
        test_config["strategies"][strat_name]["enabled"] = (strat_name == strategy_name)
    
    # Run backtest
    engine = BacktestEngine(initial_balance=1000.0, fee_rate=0.0005)
    result = engine.run(df, symbol, test_config, verbose=False)
    
    return result

def main():
    print("\n" + "="*60)
    print("🧪 TESTING NEW STRATEGIES (Pattern Recognition + Range Trading)")
    print("="*60 + "\n")
    
    # Fetch historical data (30 days of 15m candles)
    symbol = "DOGE"
    print(f"📡 Fetching {symbol} data (30 days, 15m)...")
    df = hyperliquid_service.get_candles(symbol, "15m", limit=2880)
    
    if df is None or df.empty:
        print("❌ Failed to fetch data")
        return
    
    print(f"✅ Loaded {len(df)} candles ({df.index[0]} → {df.index[-1]})\n")
    
    # Test each strategy
    results_summary = []
    
    for strategy_name in NEW_STRATEGIES:
        print(f"\n{'='*60}")
        print(f"Testing: {strategy_name}")
        print(f"{'='*60}")
        
        try:
            result = test_single_strategy(strategy_name, df, symbol)
            stats = result['stats']
            
            results_summary.append({
                'strategy': strategy_name,
                'roi': stats['roi_pct'],
                'total_trades': stats['total_trades'],
                'win_rate': stats['win_rate'],
                'avg_win': stats['avg_win'],
                'avg_loss': stats['avg_loss'],
                'total_pnl': stats['total_pnl']
            })
            
        except Exception as e:
            print(f"❌ Error testing {strategy_name}: {e}")
            results_summary.append({
                'strategy': strategy_name,
                'roi': 0,
                'total_trades': 0,
                'win_rate': 0,
                'avg_win': 0,
                'avg_loss': 0,
                'total_pnl': 0,
                'error': str(e)
            })
    
    # Display comparison
    print("\n" + "="*60)
    print("📊 STRATEGY COMPARISON - NEW STRATEGIES")
    print("="*60)
    print(f"{'Strategy':<25} {'ROI':<10} {'Trades':<10} {'Win Rate':<12} {'Avg Win':<12}")
    print("-"*60)
    
    for r in results_summary:
        if 'error' not in r:
            print(f"{r['strategy']:<25} {r['roi']:>8.2f}% {r['total_trades']:>8} {r['win_rate']:>10.2f}% ${r['avg_win']:>10.2f}")
        else:
            print(f"{r['strategy']:<25} ERROR: {r['error']}")
    
    print("="*60)
    
    # Save results
    output_file = f"backtest_results_new_strategies_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(output_file, "w") as f:
        json.dump(results_summary, f, indent=2)
    
    print(f"\n💾 Results saved to: {output_file}")
    
    # Recommendations
    print("\n🎯 RECOMMENDATIONS:")
    
    # Pattern strategies
    pattern_strats = [r for r in results_summary if r['strategy'] in ['double_bottom', 'double_top', 'bull_flag', 'head_shoulders']]
    range_strats = [r for r in results_summary if r['strategy'] in ['bollinger_bounce', 'rsi_ping_pong']]
    
    print("\n📈 PATTERN RECOGNITION STRATEGIES:")
    for r in pattern_strats:
        if 'error' not in r:
            status = "✅ ENABLE" if r['roi'] > 3 and r['win_rate'] > 50 else "⚠️ TUNE" if r['total_trades'] > 0 else "❌ SKIP"
            print(f"   {status} {r['strategy']:<20} (ROI: {r['roi']:>6.2f}%, WR: {r['win_rate']:>5.1f}%)")
    
    print("\n🎯 RANGE TRADING STRATEGIES:")
    for r in range_strats:
        if 'error' not in r:
            status = "✅ ENABLE" if r['roi'] > 3 and r['win_rate'] > 50 else "⚠️ TUNE" if r['total_trades'] > 0 else "❌ SKIP"
            print(f"   {status} {r['strategy']:<20} (ROI: {r['roi']:>6.2f}%, WR: {r['win_rate']:>5.1f}%)")
    
    print("\n" + "="*60)
    print("✅ Backtest complete!")
    print("="*60 + "\n")

if __name__ == "__main__":
    main()
