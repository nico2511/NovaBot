#!/usr/bin/env python3
"""
DOGE Backtest - Test RSIReversal on Memecoin
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from backtest.backtest_engine import BacktestEngine
from strategies.engine import StrategyEngine
from app.core.risk_manager import RiskManager

def strategy_wrapper(df_slice, exchange, symbol):
    """Wrapper using real StrategyEngine"""
    risk_manager = RiskManager()
    engine = StrategyEngine(risk_manager)
    
    result = engine.analyze(df_slice)
    
    if result.get('signals'):
        signal = result['signals'][0]
        
        balance = exchange.get_account_balance()
        equity = balance['equity']
        
        raw_size = risk_manager.calculate_position_size(
            price=signal['price'],
            sl_price=signal['sl'],
            equity=equity,
            method="risk_pct",
            risk_per_trade_pct=0.01
        )
        
        # Cap position to 50% of equity
        max_position_value = equity * 0.5
        max_size = max_position_value / signal['price']
        size = min(raw_size, max_size)
        
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
    print("🐕 DOGE BACKTEST - RSIReversal Test")
    print("="*60)
    
    INITIAL_BALANCE = 1000.0
    DATA_FILE = "data/historical/DOGE_15m.csv"
    SYMBOL = "DOGE"
    
    if not os.path.exists(DATA_FILE):
        print(f"❌ Data file not found: {DATA_FILE}")
        sys.exit(1)
    
    engine = BacktestEngine(initial_balance=INITIAL_BALANCE)
    
    print(f"\n🚀 Starting backtest on {SYMBOL}...")
    print(f"📊 Strategy: All Enabled (RSIReversal + GoldenCross EMA 9/21)")
    print(f"💰 Risk per trade: 1% of equity")
    print()
    
    try:
        stats = engine.run(
            data_csv_path=DATA_FILE,
            strategy_func=strategy_wrapper,
            symbol=SYMBOL,
            warmup_candles=50
        )
        
        import json
        with open("backtest_results_DOGE.json", "w") as f:
            json.dump(stats, f, indent=2)
        
        print(f"\n💾 Results saved to: backtest_results_DOGE.json")
        
    except Exception as e:
        print(f"\n❌ Backtest failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
