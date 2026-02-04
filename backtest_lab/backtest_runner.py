
import sys
import os
import pandas as pd
from backtesting import Backtest, Strategy
from backtesting.lib import resample_apply

# PATCH: Fix pandas-ta importlib.metadata issue in Python 3.10+
import importlib
try:
    import importlib.metadata
except ImportError:
    pass

if not hasattr(importlib, 'metadata'):
    importlib.metadata = importlib.metadata

import pandas_ta as ta

# Add project root to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

class SmartTrendBacktest(Strategy):
    # Public parameters for optimization
    ema_fast = 21
    ema_slow = 50
    rsi_min = 30
    rsi_max = 70
    pullback_tolerance = 0.02
    rr_ratio = 1.5
    sl_atr_mult = 0.35
    volume_multiplier = 1.3
    
    def init(self):
        # All indicators are pre-calculated in prepare_data
        # We access them via self.data.ColumnName in next()
        pass

    def next(self):
        if len(self.data) < 100: return

        # Access Pre-Calc Indicators directly
        ema21 = self.data.EMA_21_15m[-1]
        ema50 = self.data.EMA_50_15m[-1]
        rsi15 = self.data.RSI_15m[-1]
        atr15 = self.data.ATR_15m[-1]
        rsi1 = self.data.RSI_1m[-1] # New column we need to add
        # Reconstruct 15m price roughly (using last closed 15m value is safer for backtest to avoid lookahead)
        
        # Reconstruct 15m price roughly (using last closed 15m value is safer for backtest to avoid lookahead)
        # Actually resample_apply usually gives the current interval's incomplete value or last closed. 
        # By default backtesting.py resample uses "agg" which might peek? 
        # Standard robust backtest: Use values valid at Open of this bar.
        
        # --- LOGIC PORT FROM smart_trend.py ---
        
        # Filter: RSI 15m
        if not (self.rsi_min < rsi15 < self.rsi_max):
            return

        # Trend Check
        long_trend = ema21 > ema50 # Simplification of "Close > EMA50" for backtest readability first
        short_trend = ema21 < ema50
        
        # Pullback Zone (using current 1m price to check proximity)
        price = self.data.Close[-1]
        
        # LONG SETUP
        if long_trend:
            upper_zone = ema21 * (1 + self.pullback_tolerance)
            lower_zone = ema21 * (1 - self.pullback_tolerance)
            
            if lower_zone <= price <= upper_zone:
                # 1m TRIGGER: RSI < 70
                if rsi1 < 70: 
                    # Entry
                    if not self.position:
                        sl_price = price - (self.sl_atr_mult * atr15)
                        tp_price = price + (self.rr_ratio * (price - sl_price))
                        self.buy(sl=sl_price, tp=tp_price)
                        
        # SHORT SETUP
        elif short_trend:
            upper_zone = ema21 * (1 + self.pullback_tolerance)
            lower_zone = ema21 * (1 - self.pullback_tolerance)
            
            if lower_zone <= price <= upper_zone:
                if rsi1 > 30:
                    if not self.position:
                        sl_price = price + (self.sl_atr_mult * atr15)
                        tp_price = price - (self.rr_ratio * (sl_price - price))
                        self.sell(sl=sl_price, tp=tp_price)



def prepare_data(df):
    # Pre-calculate ALL indicators here
    
    # 1. 15m Indicators (Resampled then Reindexed)
    df_15m = df.resample('15min').agg({'Open': 'first', 'High': 'max', 'Low': 'min', 'Close': 'last'})
    
    # EMAs
    ema21_15m = ta.ema(df_15m['Close'], length=21)
    ema50_15m = ta.ema(df_15m['Close'], length=50)
    # RSI
    rsi_15m = ta.rsi(df_15m['Close'], length=14)
    # ATR
    atr_15m = ta.atr(df_15m['High'], df_15m['Low'], df_15m['Close'], length=14)
    
    # Reindex everything to 1m
    df['EMA_21_15m'] = ema21_15m.reindex(df.index).ffill().bfill()
    df['EMA_50_15m'] = ema50_15m.reindex(df.index).ffill().bfill()
    df['RSI_15m'] = rsi_15m.reindex(df.index).ffill().bfill()
    df['ATR_15m'] = atr_15m.reindex(df.index).ffill().bfill()
    
    # 2. 1m Indicators
    df['RSI_1m'] = ta.rsi(df['Close'], length=14).bfill() # bfill needed for start
    
    return df

def run():
    print("🚀 Starting Backtest & OPTIMIZATION...")
    
    # Load Data
    data_path = "data/BTC_1m.csv"
    if not os.path.exists(data_path):
        print(f"❌ Data not found at {data_path}. Run fetch_data.py first.")
        return

    df = pd.read_csv(data_path, index_col=0, parse_dates=True)
    df = prepare_data(df)
    
    # Run Backtest
    # Cash 1,000,000 to ensure we can buy 1 BTC even at $100k+
    try:
        # User reported warning suggesting finalize_trades=True
        # We pass it to init as requested.
        # exclusive_orders=True is also good.
        bt = Backtest(df, SmartTrendBacktest, cash=1_000_000, commission=.0006, exclusive_orders=True, finalize_trades=True)
    except TypeError:
        # Fallback if param doesn't exist (e.g. older version)
        print("⚠️ 'finalize_trades' not supported in this version. Falling back.")
        bt = Backtest(df, SmartTrendBacktest, cash=1_000_000, commission=.0006, exclusive_orders=True)
    
    print("🧬 Running Genetic Algorithm (Deep Search 300 iters)...")
    # Switch to Random Search (max_tries) to avoid Grid Search hanging on Windows
    stats = bt.optimize(
        pullback_tolerance=[0.005, 0.01, 0.015, 0.02, 0.025, 0.03],
        rr_ratio=[1.0, 1.25, 1.5, 1.75, 2.0, 2.5, 3.0],
        sl_atr_mult=[0.3, 0.5, 0.8, 1.0, 1.5, 2.0],
        rsi_min=[20, 25, 30, 35, 40],
        rsi_max=[60, 65, 70, 75, 80],
        maximize='Profit Factor',
        constraint=lambda p: p.rsi_min < p.rsi_max,
        max_tries=300,
        random_state=42
    )
    
    print("\n🏆 OPTIMIZATION RESULTS:")
    print(stats)
    print("\n💎 BEST PARAMETERS:")
    print(stats._strategy)

if __name__ == "__main__":
    run()
