
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

# === STRATEGY: Elastic Reversion ===
class ElasticReversionBacktest(Strategy):
    # Optimization Ranges
    ema_period = 20
    rsi_overbought = 75
    rsi_oversold = 25
    adx_threshold = 60
    min_rr = 1.5
    bb_std = 2.5
    
    def init(self):
        pass

    def next(self):
        if len(self.data) < 50: return

        # Indicators
        price = self.data.Close[-1]
        ema_20 = self.data.EMA_20[-1]
        rsi = self.data.RSI[-1]
        adx = self.data.ADX[-1]
        bb_upper = self.data.BBU[-1]
        bb_lower = self.data.BBL[-1]
        
        # Trend / Extremes Filter
        # Usually reversion works when ADX is VERY high (overextended)
        if adx < self.adx_threshold: return

        # === LONG ===
        if price < bb_lower and rsi < self.rsi_oversold:
            if not self.position:
                sl = price * 0.99
                tp = ema_20 # Target EMA 20 as mean
                
                risk = price - sl
                reward = tp - price
                if risk > 0 and (reward / risk) >= self.min_rr:
                    self.buy(sl=sl, tp=tp)

        # === SHORT ===
        elif price > bb_upper and rsi > self.rsi_overbought:
            if not self.position:
                sl = price * 1.01
                tp = ema_20
                
                risk = sl - price
                reward = price - tp
                if risk > 0 and (reward / risk) >= self.min_rr:
                    self.sell(sl=sl, tp=tp)


def prepare_data(df):
    print("🧹 Preparing 15m Data for Elastic Reversion...")
    df_15m = df.resample('15min').agg({
        'Open': 'first', 'High': 'max', 'Low': 'min', 'Close': 'last', 'Volume': 'sum'
    }).dropna()
    
    # Indicators
    df_15m['EMA_20'] = ta.ema(df_15m['Close'], length=20)
    df_15m.ta.bbands(length=20, std=2.5, append=True)
    df_15m.rename(columns={'BBU_20_2.5': 'BBU', 'BBL_20_2.5': 'BBL'}, inplace=True)
    df_15m['ADX'] = ta.adx(df_15m['High'], df_15m['Low'], df_15m['Close'], length=14)['ADX_14']
    df_15m['RSI'] = ta.rsi(df_15m['Close'], length=14)
    
    return df_15m.dropna()

def run():
    print("🚀 Starting Backtest: Elastic Reversion (1 MONTH)...")
    
    data_path = "data/BTC_1m.csv"
    if not os.path.exists(data_path):
        print("❌ Data not found")
        return

    df = pd.read_csv(data_path, index_col=0, parse_dates=True)
    df_strategy = prepare_data(df)
    
    try:
        bt = Backtest(df_strategy, ElasticReversionBacktest, cash=1_000_000, commission=.0006, exclusive_orders=True, finalize_trades=True)
    except TypeError:
        bt = Backtest(df_strategy, ElasticReversionBacktest, cash=1_000_000, commission=.0006, exclusive_orders=True)
        
    print("🧬 Optimizing Elastic Reversion...")
    stats = bt.optimize(
        adx_threshold=[50, 60, 70],
        rsi_overbought=[70, 75, 80],
        rsi_oversold=[20, 25, 30],
        bb_std=[2.2, 2.5, 3.0],
        maximize='Profit Factor',
        max_tries=50,
        random_state=42
    )

    print("\n📊 RESULTS:")
    print(stats)
    print("\n💎 BEST PARAMETERS:")
    print(stats._strategy)

if __name__ == "__main__":
    run()
