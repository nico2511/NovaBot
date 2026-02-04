
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

# === STRATEGY: Bollinger Middle Bounce ===
class BollingerMiddleBounceBacktest(Strategy):
    # Params
    bb_period = 20
    bb_std = 2.0
    
    # Optimization Ranges
    adx_threshold = 20
    rsi_min = 40
    min_rr = 1.5
    sl_buffer_pct = 0.008
    volume_multiplier = 1.2
    
    # EMAs
    ema_trend_short = 20
    ema_trend_long = 50

    def init(self):
        pass

    def next(self):
        if len(self.data) < 60: return

        # Indicators
        price = self.data.Close[-1]
        high = self.data.High[-1]
        low = self.data.Low[-1]
        open_ = self.data.Open[-1]
        
        # BB
        bb_upper = self.data.BBU[-1]
        bb_lower = self.data.BBL[-1]
        bb_mid = self.data.BBM[-1]
        
        # Trend EMAs
        ema_short = self.data.EMA_Short[-1]
        ema_long = self.data.EMA_Long[-1]
        
        # ADX
        adx = self.data.ADX[-1]
        if adx < self.adx_threshold: return
        
        # RSI
        rsi = self.data.RSI[-1]
        
        # Volume
        try:
             vol = self.data.Volume[-1]
             vol_avg = self.data.Vol_Avg[-1]
        except:
             vol = 0
             vol_avg = 0
             
        volume_ok = True
        if vol_avg > 0 and vol < vol_avg * self.volume_multiplier:
            volume_ok = False

        # === LONG ===
        # Trend: EMA Short > Long and Price > Long
        if ema_short > ema_long and price > ema_long:
            # Rejection of Low Band Crash?
            if price < bb_lower * 1.005: return 
            
            # Setup: Green Candle + Close > MB + Recent Touch
            is_green = price > open_
            closes_above_mb = price > bb_mid
            
            # Touch check (Current Low or Prev Low)
            prev_low = self.data.Low[-2]
            prev_mb = self.data.BBM[-2]
            
            touch_threshold = 1.006 
            recent_touch = (low <= bb_mid * touch_threshold) or (prev_low <= prev_mb * touch_threshold)
            
            if is_green and closes_above_mb and recent_touch and volume_ok:
                if rsi > self.rsi_min:
                    sl = low * (1 - self.sl_buffer_pct)
                    tp = bb_upper 
                    
                    risk = price - sl
                    
                    # Ensure decent RR, extend TP if needed or skip
                    tp_calc = price + (risk * self.min_rr)
                    
                    # We can use the MAX of Band Target or RR Target to ensure profitability
                    # Or conservatively use the Band if it provides enough RR, otherwise skip?
                    # Strategy says: "ideally target ... standard RR logic but check if Upper Band offers decent initial reward"
                    # Let's enforce Min RR. If Band is closer than RR target, we extend to RR target (hoping for breakout/continuation)
                    # or we skip.
                    # Given it's "Middle Bounce", we expect it to go to Upper Band.
                    # If Upper Band < RR Target, the trade is poor quality?
                    # Let's simply set TP = price + risk * RR to guarantee the math, assuming trend continuation.
                    
                    tp = tp_calc
                    
                    if not self.position:
                        self.buy(sl=sl, tp=tp)

        # === SHORT ===
        elif ema_short < ema_long and price < ema_long:
            # Rejection of Upper Band Spike?
            if price > bb_upper * 0.995: return
            if price < bb_lower * 1.005: return # Already at bottom
            
            # Setup: Red Candle + Close < MB + Recent Touch
            is_red = price < open_
            closes_below_mb = price < bb_mid
            
            prev_high = self.data.High[-2]
            prev_mb = self.data.BBM[-2]
            
            touch_threshold = 0.994 
            recent_touch = (high >= bb_mid * 0.994) or (prev_high >= prev_mb * 0.994)
            
            if is_red and closes_below_mb and recent_touch and volume_ok:
                if rsi < (100 - self.rsi_min):
                    sl = high * (1 + self.sl_buffer_pct)
                    
                    risk = sl - price
                    tp = price - (risk * self.min_rr)
                    
                    if not self.position:
                        self.sell(sl=sl, tp=tp)


def prepare_data(df):
    print("🧹 Preparing 15m Data for Bollinger Middle Bounce...")
    df_15m = df.resample('15min').agg({
        'Open': 'first', 'High': 'max', 'Low': 'min', 'Close': 'last', 'Volume': 'sum'
    }).dropna()
    
    # Indicators
    df_15m.ta.bbands(length=20, std=2.0, append=True)
    df_15m.rename(columns={'BBL_20_2.0': 'BBL', 'BBM_20_2.0': 'BBM', 'BBU_20_2.0': 'BBU'}, inplace=True)
    
    df_15m['EMA_Short'] = ta.ema(df_15m['Close'], length=20)
    df_15m['EMA_Long'] = ta.ema(df_15m['Close'], length=50)
    
    df_15m['ADX'] = ta.adx(df_15m['High'], df_15m['Low'], df_15m['Close'], length=14)['ADX_14']
    df_15m['RSI'] = ta.rsi(df_15m['Close'], length=14)
    df_15m['Vol_Avg'] = ta.sma(df_15m['Volume'], length=20)
    
    return df_15m.dropna()

def run():
    print("🚀 Starting Backtest: Bollinger Middle Bounce...")
    
    data_path = "data/BTC_1m.csv"
    if not os.path.exists(data_path):
        print("❌ Data not found")
        return

    df = pd.read_csv(data_path, index_col=0, parse_dates=True)
    df_strategy = prepare_data(df)
    
    try:
        bt = Backtest(df_strategy, BollingerMiddleBounceBacktest, cash=1_000_000, commission=.0006, exclusive_orders=True, finalize_trades=True)
    except TypeError:
        bt = Backtest(df_strategy, BollingerMiddleBounceBacktest, cash=1_000_000, commission=.0006, exclusive_orders=True)
        
    print("🧬 Optimizing Middle Bounce...")
    stats = bt.optimize(
        adx_threshold=[15, 20, 25, 30],
        min_rr=[1.5, 2.0, 2.5, 3.0],
        sl_buffer_pct=[0.005, 0.008, 0.01, 0.015],
        volume_multiplier=[0.8, 1.0, 1.2, 1.5],
        rsi_min=[30, 40, 50],
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
