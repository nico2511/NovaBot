"""
Optimization Script for Institutional Scalp Strategy
Iterates through parameter combinations to find profitable configurations.
"""
import pandas as pd
import json
import sys
import itertools
from copy import deepcopy
import time

sys.path.append('.')

from backtest.backtest_engine import BacktestEngine

# 1. Load Data (Once)
print("📊 Loading Data...")
try:
    df_btc = pd.read_csv('data/historical/BTC_15m.csv')
    df_btc['timestamp'] = pd.to_datetime(df_btc['timestamp'])
    df_btc.set_index('timestamp', inplace=True)
    
    df_doge = pd.read_csv('data/historical/DOGE_15m.csv')
    df_doge['timestamp'] = pd.to_datetime(df_doge['timestamp'])
    df_doge.set_index('timestamp', inplace=True)
    print("✅ Data Loaded")
except Exception as e:
    print(f"❌ Error loading data: {e}")
    sys.exit(1)

# 2. Define Parameter Ranges
# Total Combinations: 4 * 3 * 3 * 3 * 2 = 216 (A bit high, let's trim if needed)
# Revised for SPEED: 2 * 2 * 2 * 1 * 1 = 8 combinations
PARAMS = {
    # Narrow down to most likely effective range
    "liq_grab_lookback": [20, 30], 
    "sl_atr_mult": [0.5, 1.0],
    "tp_atr_mult": [2.0, 3.0],
    
    # Fix these for now
    "adx_threshold": [25],
    "direction": ["BOTH"]
}

# 3. Base Config
BASE_CONFIG = {
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
                "allow_shorts": True,
                # New params to be supported
                "sl_atr_mult": 0.5,
                "tp_atr_mult": 2.0
            }
        }
    }
}

def run_optimization():
    results = []
    
    # Generate all combinations
    keys = PARAMS.keys()
    combinations = list(itertools.product(*PARAMS.values()))
    total_runs = len(combinations)
    
    print(f"🚀 Starting Optimization: {total_runs} combinations x 2 Assets...")
    
    start_time = time.time()
    
    for i, combo in enumerate(combinations):
        # Unpack params
        param_dict = dict(zip(keys, combo))
        
        # Setup Config
        run_config = deepcopy(BASE_CONFIG)
        
        # Set Global ADX
        run_config["market_regime"]["adx_threshold"] = param_dict["adx_threshold"]
        
        # Set Strategy Params
        strat_params = run_config["strategies"]["institutional_scalp"]["params"]
        strat_params["liq_grab_lookback"] = param_dict["liq_grab_lookback"]
        strat_params["sl_atr_mult"] = param_dict["sl_atr_mult"]
        strat_params["tp_atr_mult"] = param_dict["tp_atr_mult"]
        
        if param_dict["direction"] == "LONG_ONLY":
            strat_params["allow_longs"] = True
            strat_params["allow_shorts"] = False
        else:
            strat_params["allow_longs"] = True
            strat_params["allow_shorts"] = True

        # Run BTC
        engine_btc = BacktestEngine(initial_balance=1000.0)
        res_btc = engine_btc.run(df_btc, "BTC", run_config, verbose=False)
        stats_btc = res_btc['stats']
        
        # Run DOGE
        engine_doge = BacktestEngine(initial_balance=1000.0)
        res_doge = engine_doge.run(df_doge, "DOGE", run_config, verbose=False)
        stats_doge = res_doge['stats']
        
        # Record Result
        results.append({
            "params": param_dict,
            "btc": {
                "roi": stats_btc['roi_pct'],
                "win_rate": stats_btc['win_rate'],
                "trades": stats_btc['total_trades']
            },
            "doge": {
                "roi": stats_doge['roi_pct'],
                "win_rate": stats_doge['win_rate'],
                "trades": stats_doge['total_trades']
            }
        })
        
        if i % 10 == 0:
            print(f"   Progress: {i}/{total_runs}...")

    duration = time.time() - start_time
    print(f"✅ Optimization Complete in {duration:.2f}s")
    
    # 4. Find Best
    print("\n🏆 TOP RESULTS (Sorted by Total ROI)")
    
    # Calculate combined ROI
    for r in results:
        r["total_roi"] = r["btc"]["roi"] + r["doge"]["roi"]
        
    # Sort
    sorted_results = sorted(results, key=lambda x: x["total_roi"], reverse=True)
    
    # Display Top 5
    for i in range(min(5, len(sorted_results))):
        res = sorted_results[i]
        p = res["params"]
        print(f"\n#{i+1}: Total ROI {res['total_roi']:.2f}%")
        print(f"   Params: Lookback={p['liq_grab_lookback']}, SL={p['sl_atr_mult']}x, TP={p['tp_atr_mult']}x, ADX={p['adx_threshold']}, Dir={p['direction']}")
        print(f"   BTC:  {res['btc']['roi']:+.2f}% (WR {res['btc']['win_rate']:.1f}%, {res['btc']['trades']} tr)")
        print(f"   DOGE: {res['doge']['roi']:+.2f}% (WR {res['doge']['win_rate']:.1f}%, {res['doge']['trades']} tr)")

    # Save to JSON
    with open("optimization_results.json", "w") as f:
        json.dump(sorted_results, f, indent=2)

if __name__ == "__main__":
    run_optimization()
