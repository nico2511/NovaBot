#!/usr/bin/env python3
"""
Test Individual Strategies - Backtest Each Strategy Separately
"""

import sys
import os
import json

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from backtest.backtest_engine import BacktestEngine
from strategies.engine import StrategyEngine
from app.core.risk_manager import RiskManager

# List of all strategies to test
STRATEGIES_TO_TEST = [
    "scalp_ema_rsi",
    "institutional_scalp",
    "elastic_reversion",
    "swing_trend_pullback",
    "smart_trend",
    "double_top_bottom",
    "triangle_breakout",
    "head_shoulders"
]

def test_single_strategy(strategy_name, df_slice, exchange, symbol):
    """Test a specific strategy only"""
    risk_manager = RiskManager()
    engine = StrategyEngine(risk_manager)
    
    # Analyze with engine
    result = engine.analyze(df_slice)
    
    if result.get('signals'):
        for signal in result['signals']:
            # Filter: Only execute if signal comes from target strategy
            if signal.get('strategy') == strategy_name:
                balance = exchange.get_account_balance()
                equity = balance['equity']
                
                size = risk_manager.calculate_position_size(
                    price=signal['price'],
                    sl_price=signal['sl'],
                    equity=equity,
                    method="risk_pct",
                    risk_per_trade_pct=0.01
                )
                
                # Cap position to 50% of equity
                max_position_value = equity * 0.5
                max_size = max_position_value / signal['price']
                size = min(size, max_size)
                
                return {
                    "symbol": symbol,
                    "side": signal['signal'],
                    "size": size,
                    "sl": signal['sl'],
                    "tp": signal['tp']
                }
    
    return None


if __name__ == "__main__":
    print("="*60)
    print("🧪 INDIVIDUAL STRATEGY TESTING")
    print("="*60)
    
    DATA_FILE = "data/historical/BTC_15m.csv"
    SYMBOL = "BTC"
    INITIAL_BALANCE = 1000.0
    
    if not os.path.exists(DATA_FILE):
        print(f"❌ Data file not found: {DATA_FILE}")
        print("Run: python scripts/download_historical_data.py")
        sys.exit(1)
    
    # Load strategies.json to check which are enabled
    with open("strategies.json", "r") as f:
        config = json.load(f)
    
    enabled_strategies = [
        name for name, cfg in config["strategies"].items()
        if cfg.get("enabled", False)
    ]
    
    print(f"\n📋 Enabled Strategies: {len(enabled_strategies)}")
    for strat in enabled_strategies:
        print(f"   - {strat}")
    
    print(f"\n🚀 Testing {len(enabled_strategies)} strategies individually...\n")
    
    results_summary = []
    
    for strategy_name in enabled_strategies:
        print("="*60)
        print(f"🔬 Testing: {strategy_name}")
        print("="*60)
        
        # Create wrapper for this specific strategy
        def strategy_wrapper(df_slice, exchange, symbol):
            return test_single_strategy(strategy_name, df_slice, exchange, symbol)
        
        # Run backtest
        engine = BacktestEngine(initial_balance=INITIAL_BALANCE)
        
        try:
            stats = engine.run(
                data_csv_path=DATA_FILE,
                strategy_func=strategy_wrapper,
                symbol=SYMBOL,
                warmup_candles=50
            )
            
            results_summary.append({
                "strategy": strategy_name,
                "roi": stats['roi_pct'],
                "trades": stats['total_trades'],
                "win_rate": stats['win_rate'],
                "profit_factor": stats.get('profit_factor', 0)
            })
            
        except Exception as e:
            print(f"❌ Error testing {strategy_name}: {e}")
            results_summary.append({
                "strategy": strategy_name,
                "roi": 0,
                "trades": 0,
                "win_rate": 0,
                "profit_factor": 0,
                "error": str(e)
            })
        
        print("\n")
    
    # Final Summary
    print("="*60)
    print("📊 STRATEGY COMPARISON SUMMARY")
    print("="*60)
    print(f"{'Strategy':<25} {'ROI':<10} {'Trades':<8} {'Win%':<8} {'PF':<6}")
    print("-"*60)
    
    # Sort by ROI
    results_summary.sort(key=lambda x: x['roi'], reverse=True)
    
    for result in results_summary:
        roi_color = "✅" if result['roi'] > 5 else "⚠️" if result['roi'] > 0 else "❌"
        print(f"{result['strategy']:<25} {roi_color} {result['roi']:>6.2f}%  {result['trades']:>6}  {result['win_rate']:>6.1f}%  {result.get('profit_factor', 0):>5.2f}")
    
    print("="*60)
    
    # Save results
    with open("strategy_comparison.json", "w") as f:
        json.dump(results_summary, f, indent=2)
    
    print(f"\n💾 Results saved to: strategy_comparison.json")
    
    # Recommendations
    print("\n🎯 RECOMMENDATIONS:")
    winners = [r for r in results_summary if r['roi'] > 5]
    losers = [r for r in results_summary if r['roi'] < 0]
    
    if winners:
        print(f"\n✅ KEEP ENABLED ({len(winners)}):")
        for w in winners:
            print(f"   - {w['strategy']} (ROI: {w['roi']:.2f}%)")
    
    if losers:
        print(f"\n❌ CONSIDER DISABLING ({len(losers)}):")
        for l in losers:
            print(f"   - {l['strategy']} (ROI: {l['roi']:.2f}%)")
