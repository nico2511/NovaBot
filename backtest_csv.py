"""
Backtest institutional_scalp using local CSV data
"""
import pandas as pd
import json
import sys
sys.path.append('.')

from backtest.backtest_engine import BacktestEngine

# Load BTC data from CSV
print("\n🎯 BACKTESTING: institutional_scalp (CSV DATA)")
print("="*60)

print("\n📊 Loading BTC data from CSV...")
df_btc = pd.read_csv('data/historical/BTC_15m.csv')
df_btc['timestamp'] = pd.to_datetime(df_btc['timestamp'])
df_btc.set_index('timestamp', inplace=True)

print(f"✅ Loaded {len(df_btc)} candles")
print(f"📅 Period: {df_btc.index[0]} → {df_btc.index[-1]}")

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

# Run backtest on BTC
engine = BacktestEngine(initial_balance=1000.0)
results_btc = engine.run(df_btc, "BTC", config, verbose=False)

print("\n" + "="*60)
print("📊 BTC RESULTS (52 days)")
print("="*60)
stats = results_btc['stats']
print(f"Initial Balance: ${engine.initial_balance:.2f}")
print(f"Final Balance:   ${stats['final_balance']:.2f}")
print(f"Total PnL:       ${stats['total_pnl']:.2f}")
print(f"ROI:             {stats['roi_pct']:.2f}%")
print(f"Total Trades:    {stats['total_trades']}")
print(f"Winning Trades:  {stats['winning_trades']}")
print(f"Losing Trades:   {stats['losing_trades']}")
print(f"Win Rate:        {stats['win_rate']:.2f}%")
print(f"Avg Win:         ${stats['avg_win']:.2f}")
print(f"Avg Loss:        ${stats['avg_loss']:.2f}")
print(f"Total Fees:      ${stats['total_fees']:.2f}")
print("="*60)

# Load DOGE data
print("\n📊 Loading DOGE data from CSV...")
df_doge = pd.read_csv('data/historical/DOGE_15m.csv')
df_doge['timestamp'] = pd.to_datetime(df_doge['timestamp'])
df_doge.set_index('timestamp', inplace=True)

print(f"✅ Loaded {len(df_doge)} candles")
print(f"📅 Period: {df_doge.index[0]} → {df_doge.index[-1]}")

# Run backtest on DOGE
engine_doge = BacktestEngine(initial_balance=1000.0)
results_doge = engine_doge.run(df_doge, "DOGE", config, verbose=False)

print("\n" + "="*60)
print("📊 DOGE RESULTS (52 days)")
print("="*60)
stats_doge = results_doge['stats']
print(f"Initial Balance: ${engine_doge.initial_balance:.2f}")
print(f"Final Balance:   ${stats_doge['final_balance']:.2f}")
print(f"Total PnL:       ${stats_doge['total_pnl']:.2f}")
print(f"ROI:             {stats_doge['roi_pct']:.2f}%")
print(f"Total Trades:    {stats_doge['total_trades']}")
print(f"Winning Trades:  {stats_doge['winning_trades']}")
print(f"Losing Trades:   {stats_doge['losing_trades']}")
print(f"Win Rate:        {stats_doge['win_rate']:.2f}%")
print(f"Avg Win:         ${stats_doge['avg_win']:.2f}")
print(f"Avg Loss:        ${stats_doge['avg_loss']:.2f}")
print(f"Total Fees:      ${stats_doge['total_fees']:.2f}")
print("="*60)

# Summary
print("\n" + "="*60)
print("📊 SUMMARY")
print("="*60)
btc_emoji = "✅" if stats['roi_pct'] > 0 else "❌"
doge_emoji = "✅" if stats_doge['roi_pct'] > 0 else "❌"
print(f"{btc_emoji} BTC:  ROI {stats['roi_pct']:+.2f}% | Trades: {stats['total_trades']} | Win Rate: {stats['win_rate']:.1f}%")
print(f"{doge_emoji} DOGE: ROI {stats_doge['roi_pct']:+.2f}% | Trades: {stats_doge['total_trades']} | Win Rate: {stats_doge['win_rate']:.1f}%")
print("="*60)

# Save results
results_combined = {
    'config': config,
    'btc': {
        'stats': stats,
        'trades': [{k: str(v) for k, v in t.items()} for t in results_btc['trades']]
    },
    'doge': {
        'stats': stats_doge,
        'trades': [{k: str(v) for k, v in t.items()} for t in results_doge['trades']]
    }
}

with open("backtest_institutional_scalp_csv.json", "w") as f:
    json.dump(results_combined, f, indent=2)

print("\n💾 Results saved to: backtest_institutional_scalp_csv.json")
print("\n✅ Backtest complete!")
