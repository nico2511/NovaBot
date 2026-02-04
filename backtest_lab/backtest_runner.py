
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

# === STRATEGY: Elastic Nibbler ===
class ElasticNibblerBacktest(Strategy):
    # Params
    bb_period = 20
    bb_std = 2.2 # Strategy Default
    
    # Optimization Ranges
    rsi_min = 28
    rsi_max = 72
    adx_threshold = 25
    volume_multiplier = 1.5
    sl_atr_mult = 1.4
    tp_atr_mult = 2.0
    
    # Logic
    min_bb_width_pct = 0.5

    def init(self):
        pass

    def next(self):
        if len(self.data) < 50: return

        # Indicators
        price = self.data.Close[-1]
        high = self.data.High[-1]
        low = self.data.Low[-1]
        
        # BB
        bb_upper = self.data.BBU[-1]
        bb_lower = self.data.BBL[-1]
        bb_width_pct = (bb_upper - bb_lower) / price * 100
        
        # Dead Market Filter
        if bb_width_pct < self.min_bb_width_pct: return
        
        # ADX Safety
        adx = self.data.ADX[-1]
        if adx > self.adx_threshold: return
        
        # RSI
        rsi = self.data.RSI[-1]
        
        # ATR
        atr = self.data.ATR[-1]
        
        # Volume
        try:
             vol = self.data.Volume[-1]
             vol_avg = self.data.Vol_Avg[-1]
        except:
             vol = 0
             vol_avg = 0
             
        # Volume Validation
        # Spike > ratio AND not > 5x (panic but not cataclysmic)
        if vol_avg == 0: return
        vol_ratio = vol / vol_avg
        is_vol_spike = (vol_ratio > self.volume_multiplier) and (vol_ratio < 5.0)
        
        if not is_vol_spike: return

        # === LONG SETUP ===
        # Price < BB Lower AND RSI Low
        if price < bb_lower:
            if rsi < self.rsi_min:
                # Entry
                sl = price - (self.sl_atr_mult * atr)
                tp = price + (self.tp_atr_mult * atr) 
                
                if not self.position:
                    self.buy(sl=sl, tp=tp)

        # === SHORT SETUP ===
        # Price > BB Upper AND RSI High
        elif price > bb_upper:
            if rsi > self.rsi_max:
                # Entry
                sl = price + (self.sl_atr_mult * atr)
                tp = price - (self.tp_atr_mult * atr)
                
                if not self.position:
                    self.sell(sl=sl, tp=tp)


def prepare_data(df):
    print("🧹 Preparing 1m Data for Elastic Nibbler (Scalp)...")
    # Elastic Nibbler is 1m or 5m. Strategy defaults say 1m/5m. 
    # Let's test on 5m for better noise filtering, or strict 1m?
    # User data is 1m CSV.
    # Resample to 5m?
    df_tf = df.resample('5min').agg({
        'Open': 'first', 'High': 'max', 'Low': 'min', 'Close': 'last', 'Volume': 'sum'
    }).dropna()
    
    # Indicators
    df_tf.ta.bbands(length=20, std=2.2, append=True) # Note: std 2.2 as per Strategy
    df_tf.rename(columns={'BBL_20_2.2': 'BBL', 'BBM_20_2.2': 'BBM', 'BBU_20_2.2': 'BBU'}, inplace=True)
    
    df_tf['ATR'] = ta.atr(df_tf['High'], df_tf['Low'], df_tf['Close'], length=14)
    df_tf['ADX'] = ta.adx(df_tf['High'], df_tf['Low'], df_tf['Close'], length=14)['ADX_14']
    df_tf['RSI'] = ta.rsi(df_tf['Close'], length=14)
    df_tf['Vol_Avg'] = ta.sma(df_tf['Volume'], length=50)
    
    return df_tf.dropna()

def run():
    print("🚀 Starting Backtest: Elastic Nibbler...")
    
    data_path = "data/BTC_1m.csv"
    if not os.path.exists(data_path):
        print("❌ Data not found")
        return

    df = pd.read_csv(data_path, index_col=0, parse_dates=True)
    df_strategy = prepare_data(df)
    
    try:
        bt = Backtest(df_strategy, ElasticNibblerBacktest, cash=1_000_000, commission=.0006, exclusive_orders=True, finalize_trades=True)
    except TypeError:
        bt = Backtest(df_strategy, ElasticNibblerBacktest, cash=1_000_000, commission=.0006, exclusive_orders=True)
        
    print("🧬 Optimizing Elastic Nibbler...")
    stats = bt.optimize(
        rsi_min=[20, 24, 28, 32],
        rsi_max=[68, 72, 76, 80],
        adx_threshold=[20, 25, 30],
        sl_atr_mult=[1.0, 1.4, 1.8],
        tp_atr_mult=[1.5, 2.0, 2.5],
        volume_multiplier=[1.2, 1.5, 1.8, 2.0],
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
