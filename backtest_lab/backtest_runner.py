
import pandas as pd
import sys
import os
import importlib.metadata # Attempt to fix attribute error

# Add project root to path
sys.path.append(os.getcwd())

try:
    import pandas_ta as ta
except AttributeError:
    # Fallback for Python 3.12 issue with pandas_ta
    print("⚠️ Pandas TA import issue detected. Continuing...")
    import pandas_ta as ta

from backtesting import Backtest, Strategy

# === STRATEGY: Bollinger Bounce ===
class BollingerBounceBacktest(Strategy):
    # Params
    bb_period = 20
    bb_std = 2.0 # Match JSON default
    adx_period = 14
    atr_period = 14
    
    # Optimization Ranges
    adx_threshold = 22
    min_rr = 1.3
    sl_atr_mult = 0.8
    kill_zone_percent = 0.16
    min_candle_atr_mult = 1.0
    volume_multiplier = 1.2
    
    # RSI filters
    rsi_oversold = 35
    rsi_overbought = 65
    
    # Slope
    ema50_slope_max = 0.008

    def init(self):
        pass

    def next(self):
        # Need history
        if len(self.data) < 60: return

        # Indicators
        price = self.data.Close[-1]
        high = self.data.High[-1]
        low = self.data.Low[-1]
        open_ = self.data.Open[-1]
        
        # Bollinger
        bb_upper = self.data.BBU[-1]
        bb_lower = self.data.BBL[-1]
        bb_basis = self.data.BBM[-1]
        
        bb_width = bb_upper - bb_lower
        
        # Volatility Filter (Min Width)
        if bb_width / price < 0.003: return
        
        # ADX Check
        adx = self.data.ADX[-1]
        if adx >= self.adx_threshold: return
        
        # EMA Slope Check
        # calc slope over 5 bars
        if len(self.data.EMA_50) > 5:
            ema_now = self.data.EMA_50[-1]
            ema_prev = self.data.EMA_50[-6]
            slope = abs((ema_now - ema_prev) / ema_prev)
            if slope > self.ema50_slope_max: return
            
        # Kill Zone
        kill_size = bb_width * self.kill_zone_percent
        upper_zone = bb_upper - kill_size
        lower_zone = bb_lower + kill_size
        
        # RSI
        rsi = self.data.RSI[-1]
        
        # Candle Sig
        atr = self.data.ATR[-1]
        candle_range = high - low
        is_significant = candle_range >= (atr * self.min_candle_atr_mult)
        
        # Volume
        try:
             vol = self.data.Volume[-1]
             vol_avg = self.data.Vol_Avg[-1]
        except:
             vol = 0
             vol_avg = 0
        
        is_vol_ok = True
        if vol_avg > 0 and vol < vol_avg * self.volume_multiplier:
            is_vol_ok = False
            
        # === LONG ===
        # Price dipped into lower zone
        if low <= lower_zone:
            if rsi <= self.rsi_oversold:
                if is_significant and is_vol_ok:
                    # Trade
                    tp_padding = bb_width * 0.05
                    tp = bb_basis + tp_padding
                    sl = bb_lower - (atr * self.sl_atr_mult)
                    
                    risk = price - sl
                    reward = tp - price
                    
                    if risk > 0 and (reward/risk) >= self.min_rr:
                        if not self.position:
                            self.buy(sl=sl, tp=tp)
                            
        # === SHORT ===
        if high >= upper_zone:
            if rsi >= self.rsi_overbought:
                if is_significant and is_vol_ok:
                    # Trade
                    tp_padding = bb_width * 0.05
                    tp = bb_basis - tp_padding
                    sl = bb_upper + (atr * self.sl_atr_mult)
                    
                    risk = sl - price
                    reward = price - tp
                    
                    if risk > 0 and (reward/risk) >= self.min_rr:
                        if not self.position:
                            self.sell(sl=sl, tp=tp)


def prepare_data(df):
    print("🧹 Preparing 15m Data...")
    df_15m = df.resample('15min').agg({
        'Open': 'first', 'High': 'max', 'Low': 'min', 'Close': 'last', 'Volume': 'sum'
    }).dropna()
    
    # Indicators
    # BB
    df_15m.ta.bbands(length=20, std=2.0, append=True) # Adds BBL_20_2.0, BBM_..., BBU_...
    # Rename cols for easier access
    df_15m.rename(columns={'BBL_20_2.0': 'BBL', 'BBM_20_2.0': 'BBM', 'BBU_20_2.0': 'BBU'}, inplace=True)
    
    df_15m['EMA_50'] = ta.ema(df_15m['Close'], length=50)
    df_15m['ADX'] = ta.adx(df_15m['High'], df_15m['Low'], df_15m['Close'], length=14)['ADX_14']
    df_15m['RSI'] = ta.rsi(df_15m['Close'], length=14)
    df_15m['ATR'] = ta.atr(df_15m['High'], df_15m['Low'], df_15m['Close'], length=14)
    df_15m['Vol_Avg'] = ta.sma(df_15m['Volume'], length=20)
    
    return df_15m.dropna()

def run():
    print("🚀 Starting Backtest: Bollinger Bounce...")
    
    data_path = "data/BTC_1m.csv"
    if not os.path.exists(data_path):
        print("❌ Data not found")
        return

    df = pd.read_csv(data_path, index_col=0, parse_dates=True)
    df_strategy = prepare_data(df)
    
    try:
        bt = Backtest(df_strategy, BollingerBounceBacktest, cash=1_000_000, commission=.0006, exclusive_orders=True, finalize_trades=True)
    except TypeError:
        bt = Backtest(df_strategy, BollingerBounceBacktest, cash=1_000_000, commission=.0006, exclusive_orders=True)
        
    print("🧬 Optimizing Bollinger Bounce...")
    stats = bt.optimize(
        adx_threshold=[18, 20, 22, 25, 30],
        min_rr=[1.0, 1.3, 1.5, 2.0],
        sl_atr_mult=[0.5, 0.8, 1.0, 1.2],
        kill_zone_percent=[0.1, 0.16, 0.20],
        rsi_oversold=[30, 35, 40],
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
