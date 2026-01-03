"""
Backtest institutional_scalp strategy only
"""
import json
import sys
sys.path.append('.')

from backtest.backtest_engine import BacktestEngine
from app.services.hyperliquid_service import hyperliquid_service

# Create config with ONLY institutional_scalp enabled
config = {
    "market_regime": {
        "adx_threshold": 25,
        "timeframe": "15m"
    },
    "strategies": {
        "institutional_scalp": {
            "enabled": True,
            "type": "trend",
            "params": {
                "liq_grab_lookback": 20,
                "allow_longs": True,
                "allow_shorts": True
            }
        }
    }
}

print("\n🎯 BACKTESTING: institutional_scalp (ISOLATED)")
print("="*60)

# Test on BTC
print("\n📊 Fetching BTC data (30 days)...")
df_btc = hyperliquid_service.get_candles("BTC", "15m", limit=2880)

if df_btc is not None and not df_btc.empty:
    engine = BacktestEngine(initial_balance=1000.0)
    results_btc = engine.run(df_btc, "BTC", config, verbose=True)
    
    print("\n" + "="*60)
    print("📊 BTC SUMMARY")
    print("="*60)
    stats = results_btc['stats']
    print(f"ROI: {stats['roi_pct']:.2f}%")
    print(f"Win Rate: {stats['win_rate']:.2f}%")
    print(f"Total Trades: {stats['total_trades']}")
    print(f"Avg Win: ${stats['avg_win']:.2f}")
    print(f"Avg Loss: ${stats['avg_loss']:.2f}")
    print(f"Profit Factor: {stats.get('profit_factor', 0):.2f}")
    
    # Save results
    with open("backtest_institutional_scalp.json", "w") as f:
        json.dump({
            'config': config,
            'btc_stats': stats,
            'trades': [{k: str(v) for k, v in t.items()} for t in results_btc['trades']]
        }, f, indent=2)
    
    print("\n💾 Results saved to: backtest_institutional_scalp.json")
else:
    print("❌ Failed to fetch BTC data")

# Test on DOGE
print("\n📊 Fetching DOGE data (30 days)...")
df_doge = hyperliquid_service.get_candles("DOGE", "15m", limit=2880)

if df_doge is not None and not df_doge.empty:
    engine = BacktestEngine(initial_balance=1000.0)
    results_doge = engine.run(df_doge, "DOGE", config, verbose=True)
    
    print("\n" + "="*60)
    print("📊 DOGE SUMMARY")
    print("="*60)
    stats = results_doge['stats']
    print(f"ROI: {stats['roi_pct']:.2f}%")
    print(f"Win Rate: {stats['win_rate']:.2f}%")
    print(f"Total Trades: {stats['total_trades']}")
    print(f"Avg Win: ${stats['avg_win']:.2f}")
    print(f"Avg Loss: ${stats['avg_loss']:.2f}")
    print(f"Profit Factor: {stats.get('profit_factor', 0):.2f}")
else:
    print("❌ Failed to fetch DOGE data")

print("\n✅ Backtest complete!")
