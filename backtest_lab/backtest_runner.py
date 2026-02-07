
import pandas as pd
import sys
import os
import importlib.metadata # Attempt to fix attribute error

# Add project root to path
sys.path.append(os.getcwd())

try:
    import pandas_ta as ta
except AttributeError:
    # Fallback
    print("⚠️ Pandas TA import issue detected. Continuing...")
    import pandas_ta as ta

from backtesting import Backtest, Strategy

from backtesting import Backtest
from backtest_lab.strategy_adapter import get_strategy_adapter
import argparse

def prepare_data(df, timeframe='15min'):
    print(f"🧹 Resampling data to {timeframe}...")
    df_resampled = df.resample(timeframe).agg({
        'Open': 'first', 'High': 'max', 'Low': 'min', 'Close': 'last', 'Volume': 'sum'
    }).dropna()
    return df_resampled

def run():
    parser = argparse.ArgumentParser()
    parser.add_argument("--strategy", default="ElasticReversionStrategy", help="Strategy class name (e.g. BollingerBounceStrategy)")
    parser.add_argument("--data", default="data/BTC_1m.csv", help="Path to CSV data file")
    parser.add_argument("--timeframe", default="15min", help="Resampling timeframe (e.g. 1min, 5min, 15min, 1h)")
    parser.add_argument("--optimize", action="store_true", help="Run optimization (only for legacy hardcoded strategies)")
    args = parser.parse_args()

    print(f"🚀 Starting Backtest: {args.strategy} (DATA: {args.data}, TF: {args.timeframe})...")
    
    if not os.path.exists(args.data):
        print(f"❌ Data not found: {args.data}")
        if os.path.exists("data"):
            files = [f for f in os.listdir("data") if f.endswith(".csv")]
            if files:
                print(f"Available datasets: {files}")
        return

    # Load and prepare data
    df = pd.read_csv(args.data, index_col=0, parse_dates=True)
    df_strategy = prepare_data(df, timeframe=args.timeframe)
    
    # Get the adapter for the requested strategy
    AdapterClass = get_strategy_adapter(args.strategy, original_df=df)
    
    try:
        bt = Backtest(df_strategy, AdapterClass, cash=1_000_000, commission=.0006, exclusive_orders=True, finalize_trades=True)
    except TypeError:
        bt = Backtest(df_strategy, AdapterClass, cash=1_000_000, commission=.0006, exclusive_orders=True)
        
    print(f"🏃 Running Backtest for {args.strategy}...")
    stats = bt.run()

    print("\n📊 RESULTS:")
    print(stats)
    
    if not stats['_trades'].empty:
        print("\n📝 Sample Trades:")
        print(stats['_trades'].head())

if __name__ == "__main__":
    run()
