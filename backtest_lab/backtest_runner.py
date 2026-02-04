
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

# === STRATEGY: Institutional Scalp ===
class InstitutionalScalpBacktest(Strategy):
    # Params
    lookback = 20
    
    # Optimization Ranges
    volume_multiplier = 1.25
    wick_ratio = 0.35
    min_rr = 1.2
    sl_atr_mult = 0.5
    adx_limit = 60
    
    def init(self):
        # We need to manually track rolling window for recent High/Low
        # backtesting library 'self.data' is full series, but we access via [-1]
        pass
        
    def next(self):
        if len(self.data) < 50: return

        # Current Candle
        price = self.data.Close[-1]
        high = self.data.High[-1]
        low = self.data.Low[-1]
        open_ = self.data.Open[-1]
        
        # Lookback Window (excluding current)
        # We need recent High/Low from [-lookback-1 : -1]
        # self.data.High returns np array
        highs = self.data.High[-self.lookback-1 : -1]
        lows = self.data.Low[-self.lookback-1 : -1]
        
        recent_high = max(highs)
        recent_low = min(lows)
        
        # ADX Safety
        adx = self.data.ADX[-1]
        if adx > self.adx_limit: return
        
        # Atr
        atr = self.data.ATR[-1]
        
        # Volume Check
        try:
             vol = self.data.Volume[-1]
             vol_avg = self.data.Vol_Avg[-1]
        except:
             vol = 0
             vol_avg = 0
        
        # We need Volume Spike ON THE TRIGGER CANDLE (Current)
        # Use completed candle logic? backtesting 'next' runs on confirmed candle usually.
        # But if we treat [-1] as "Just Closed", we compare vol[-1] to avg.
        
        volume_ok = True
        if vol_avg > 0 and vol < vol_avg * self.volume_multiplier:
            volume_ok = False
            
        # Candle Stats
        candle_range = high - low
        if candle_range == 0: return
        
        upper_wick = (high - max(price, open_)) / candle_range
        lower_wick = (min(price, open_) - low) / candle_range
        
        # === BULLISH GRAB ===
        # 1. Sweep Low: Low < Recent Low
        # 2. Close Back Inside: Close > Recent Low
        if low < recent_low and price > recent_low:
             # 3. Wick Rejection
             if lower_wick >= self.wick_ratio:
                 # 4. Volume Spike
                 if volume_ok:
                     # Entry
                     sl = low - (self.sl_atr_mult * atr)
                     tp = price + (2.0 * atr) 
                     
                     # Check RR
                     risk = price - sl
                     reward = tp - price
                     if risk > 0 and (reward/risk) >= self.min_rr:
                         if not self.position:
                             self.buy(sl=sl, tp=tp)

        # === BEARISH GRAB ===
        # 1. Sweep High: High > Recent High
        # 2. Close Back Below: Close < Recent High
        elif high > recent_high and price < recent_high:
            # 3. Wick Rejection
            if upper_wick >= self.wick_ratio:
                # 4. Volume Spike
                if volume_ok:
                    # Entry
                    sl = high + (self.sl_atr_mult * atr)
                    tp = price - (2.0 * atr)
                    
                    risk = sl - price
                    reward = price - tp
                    if risk > 0 and (reward/risk) >= self.min_rr:
                         if not self.position:
                             self.sell(sl=sl, tp=tp)


def prepare_data(df):
    print("🧹 Preparing 15m Data for Institutional Scalp...")
    df_15m = df.resample('15min').agg({
        'Open': 'first', 'High': 'max', 'Low': 'min', 'Close': 'last', 'Volume': 'sum'
    }).dropna()
    
    # Indicators
    df_15m['ATR'] = ta.atr(df_15m['High'], df_15m['Low'], df_15m['Close'], length=14)
    df_15m['ADX'] = ta.adx(df_15m['High'], df_15m['Low'], df_15m['Close'], length=14)['ADX_14']
    df_15m['Vol_Avg'] = ta.sma(df_15m['Volume'], length=20)
    
    return df_15m.dropna()

def run():
    print("🚀 Starting Backtest: Institutional Scalp...")
    
    data_path = "data/BTC_1m.csv"
    if not os.path.exists(data_path):
        print("❌ Data not found")
        return

    df = pd.read_csv(data_path, index_col=0, parse_dates=True)
    df_strategy = prepare_data(df)
    
    try:
        bt = Backtest(df_strategy, InstitutionalScalpBacktest, cash=1_000_000, commission=.0006, exclusive_orders=True, finalize_trades=True)
    except TypeError:
        bt = Backtest(df_strategy, InstitutionalScalpBacktest, cash=1_000_000, commission=.0006, exclusive_orders=True)
        
    print("🧬 Optimizing Institutional Scalp...")
    stats = bt.optimize(
        wick_ratio=[0.25, 0.3, 0.35, 0.4, 0.45],
        volume_multiplier=[1.0, 1.25, 1.5, 2.0],
        sl_atr_mult=[0.3, 0.5, 0.8, 1.0],
        min_rr=[1.0, 1.2, 1.5, 2.0],
        lookback=[10, 20, 30, 50],
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
