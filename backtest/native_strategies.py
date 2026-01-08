"""
Native Backtesting.py Strategies
Stratégies recréées nativement pour backtesting.py
Utilise les paramètres de strategies.json
"""

from backtesting import Strategy
import pandas as pd
import pandas_ta as ta
import numpy as np


def ta_wrapper(fun, series, **kwargs):
    """Wrapper pour convertir numpy array -> Series pour pandas_ta"""
    s = pd.Series(series)
    res = fun(s, **kwargs)
    if hasattr(res, "to_numpy"):
        return res.to_numpy()
    return np.array(res)


def ta_adx_wrapper(high, low, close, length):
    """Wrapper spécifique pour ADX qui retourne DataFrame"""
    h = pd.Series(high)
    l = pd.Series(low)
    c = pd.Series(close)
    res = ta.adx(h, l, c, length=length)
    if isinstance(res, pd.DataFrame):
        return res.iloc[:, 0].to_numpy()
    if hasattr(res, "to_numpy"):
        return res.to_numpy()
    return np.array(res)


def ta_atr_wrapper(high, low, close, length):
    """Wrapper pour ATR"""
    h = pd.Series(high)
    l = pd.Series(low)
    c = pd.Series(close)
    res = ta.atr(h, l, c, length=length)
    if hasattr(res, "to_numpy"):
        return res.to_numpy()
    return np.array(res)


class FiboPullbackStrategy(Strategy):
    """Fibo Pullback"""
    ema_period = 200
    swing_lookback = 10
    swing_confirmation_bars = 2
    adx_threshold = 25
    volume_multiplier = 1.5
    min_rr = 1.3
    
    def init(self):
        self.ema200 = self.I(ta_wrapper, ta.ema, self.data.Close, length=self.ema_period)
        self.adx = self.I(ta_adx_wrapper, self.data.High, self.data.Low, self.data.Close, length=14)
        self.volume_sma = self.I(ta_wrapper, ta.sma, self.data.Volume, length=20)
    
    def next(self):
        if len(self.data) < self.swing_lookback + self.ema_period: return
        if self.position: return
        
        try:
            # Force conversion to float/scalar
            price = float(self.data.Close[-1])
            ema200_val = float(self.ema200[-1])
            
            # Trend
            if price <= ema200_val: return
            
            # ADX
            adx_val = float(self.adx[-1])
            if np.isnan(adx_val) or adx_val < self.adx_threshold: return
            
            # Swing detection
            start, end = -(self.swing_lookback + self.swing_confirmation_bars), -self.swing_confirmation_bars
            highs = self.data.High[start:end]
            lows = self.data.Low[start:end]
            if len(highs) < 20: return
            
            swing_high = float(max(highs))
            swing_low = float(min(lows))
            
            if swing_high <= swing_low: return
            diff = swing_high - swing_low
            if diff / swing_low < 0.02: return
            
            # Fibo Zone
            fibo_50 = swing_high - (diff * 0.50)
            fibo_786 = swing_high - (diff * 0.786)
            
            current_low = float(self.data.Low[-1])
            current_high = float(self.data.High[-1])
            
            if not (current_low <= fibo_50 and current_high >= fibo_786): return
            
            # Volume
            current_vol = float(self.data.Volume[-1])
            vol_sma = float(self.volume_sma[-1])
            
            if current_vol < vol_sma * self.volume_multiplier: return
            
            sl = fibo_786 - (diff * 0.01)
            tp = swing_high
            
            if sl >= price: sl = price * 0.995
            if tp <= price: tp = price * 1.01
            
            if (price - sl) == 0: return
            if (tp - price) / (price - sl) < self.min_rr: return
            
            self.buy(sl=sl, tp=tp)
            
        except Exception as e:
            pass # Ignore errors to prevent crash

class SmartTrendStrategy(Strategy):
    """Smart Trend"""
    min_rr = 1.5
    ema_fast = 21
    ema_slow = 50
    adx_threshold = 25
    
    def init(self):
        self.ema_fast_line = self.I(ta_wrapper, ta.ema, self.data.Close, length=self.ema_fast)
        self.ema_slow_line = self.I(ta_wrapper, ta.ema, self.data.Close, length=self.ema_slow)
        self.adx = self.I(ta_adx_wrapper, self.data.High, self.data.Low, self.data.Close, length=14)
        self.atr = self.I(ta_atr_wrapper, self.data.High, self.data.Low, self.data.Close, length=14)
    
    def next(self):
        if self.position: return
        if len(self.data) < 100: return
        
        if np.isnan(self.adx[-1]) or self.adx[-1] < self.adx_threshold: return
        
        if self.ema_fast_line[-2] <= self.ema_slow_line[-2] and self.ema_fast_line[-1] > self.ema_slow_line[-1]:
            price = self.data.Close[-1]
            atr_val = self.atr[-1]
            if np.isnan(atr_val) or atr_val <= 0: return
            
            sl = price - (atr_val * 1.5)
            tp = price + (atr_val * 2.5)
            
            if sl >= price: sl = price * 0.99
            if tp <= price: tp = price * 1.01
            
            self.buy(sl=sl, tp=tp)


class ScalpEmaRsiStrategy(Strategy):
    """Scalp EMA RSI"""
    ema_fast = 9
    ema_slow = 21
    rsi_period = 14
    min_rr = 1.3
    
    def init(self):
        self.ema9 = self.I(ta_wrapper, ta.ema, self.data.Close, length=self.ema_fast)
        self.ema21 = self.I(ta_wrapper, ta.ema, self.data.Close, length=self.ema_slow)
        self.rsi = self.I(ta_wrapper, ta.rsi, self.data.Close, length=self.rsi_period)
        self.volume_sma = self.I(ta_wrapper, ta.sma, self.data.Volume, length=20)
        self.atr = self.I(ta_atr_wrapper, self.data.High, self.data.Low, self.data.Close, length=14)
    
    def next(self):
        if self.position: return
        if len(self.data) < 50: return
        if np.isnan(self.volume_sma[-1]) or self.data.Volume[-1] < self.volume_sma[-1] * 1.3: return
        
        if self.ema9[-2] <= self.ema21[-2] and self.ema9[-1] > self.ema21[-1]:
            if 50 < self.rsi[-1] < 70:
                price = self.data.Close[-1]
                atr_val = self.atr[-1]
                if np.isnan(atr_val) or atr_val <= 0: return
                
                sl = price - (atr_val * 1.2)
                tp = price + (atr_val * 1.8)
                
                if sl >= price: sl = price * 0.99
                if tp <= price: tp = price * 1.01
                
                self.buy(sl=sl, tp=tp)


class InstitutionalScalpStrategy(Strategy):
    """Institutional Scalp"""
    liq_grab_lookback = 10
    min_rr = 1.2
    
    def init(self):
        self.volume_sma = self.I(ta_wrapper, ta.sma, self.data.Volume, length=20)
        self.adx = self.I(ta_adx_wrapper, self.data.High, self.data.Low, self.data.Close, length=14)
    
    def next(self):
        if self.position: return
        if len(self.data) < 50: return
        if not np.isnan(self.adx[-1]) and self.adx[-1] > 25: return
        
        recent_lows = self.data.Low[-self.liq_grab_lookback:-1]
        
        if hasattr(recent_lows, 'to_numpy'):
            recent_lows = recent_lows.to_numpy()
            
        if len(recent_lows) == 0: return
        
        support = float(min(recent_lows))
        
        if self.data.Low[-1] < support and self.data.Close[-1] > support:
            if self.data.Volume[-1] > self.volume_sma[-1] * 1.5:
                price = self.data.Close[-1]
                sl = self.data.Low[-1] - (support - self.data.Low[-1]) * 0.2
                tp = price + (price - sl) * 2.0
                
                if sl >= price: sl = price * 0.995
                if tp <= price: tp = price * 1.01
                
                self.buy(sl=sl, tp=tp)


class BollingerBounceStrategy(Strategy):
    """Bollinger Bounce"""
    bb_period = 20
    bb_std = 2.0
    adx_threshold = 30
    min_rr = 1.5
    
    def init(self):
        # Calculate outside self.I first to handle DataFrame return safe
        close_series = pd.Series(self.data.Close)
        bb = ta.bbands(close_series, length=self.bb_period, std=self.bb_std)
        
        # Default empty arrays if calculation fails
        n = len(close_series)
        l, m, u = np.zeros(n), np.zeros(n), np.zeros(n)
        
        if isinstance(bb, pd.DataFrame):
            l = bb.iloc[:, 0].to_numpy()
            m = bb.iloc[:, 1].to_numpy()
            u = bb.iloc[:, 2].to_numpy()
            
        # Register inputs
        self.lower = self.I(lambda: l)
        self.mid = self.I(lambda: m)
        self.upper = self.I(lambda: u)
        
        self.adx = self.I(ta_adx_wrapper, self.data.High, self.data.Low, self.data.Close, length=14)
        self.atr = self.I(ta_atr_wrapper, self.data.High, self.data.Low, self.data.Close, length=14)
        
    def next(self):
        if self.position: return
        if np.isnan(self.adx[-1]) or self.adx[-1] > self.adx_threshold: return
        
        # Buy Lower
        if self.data.Low[-1] <= self.lower[-1] and self.data.Close[-1] > self.lower[-1]:
            price = self.data.Close[-1]
            atr_val = self.atr[-1]
            if np.isnan(atr_val) or atr_val <= 0: return

            sl = price - (atr_val * 1.5)
            tp = self.mid[-1]
            
            if sl >= price: sl = price * 0.995
            if tp <= price: tp = price * 1.01
            
            if (tp - price) / (price - sl) >= self.min_rr:
                self.buy(sl=sl, tp=tp)


class ElasticReversionStrategy(Strategy):
    """Elastic Reversion"""
    rsi_period = 14
    oversold_rsi = 20
    min_rr = 1.5
    
    def init(self):
        self.rsi = self.I(ta_wrapper, ta.rsi, self.data.Close, length=self.rsi_period)
        self.ema20 = self.I(ta_wrapper, ta.ema, self.data.Close, length=20)
        self.atr = self.I(ta_atr_wrapper, self.data.High, self.data.Low, self.data.Close, length=14)
        self.adx = self.I(ta_adx_wrapper, self.data.High, self.data.Low, self.data.Close, length=14)
        
    def next(self):
        if self.position: return
        if self.adx[-1] > 25: return
        
        if self.rsi[-1] < self.oversold_rsi:
            price = self.data.Close[-1]
            dist = self.ema20[-1] - price
            if dist > 0:
                atr_val = self.atr[-1]
                if np.isnan(atr_val) or atr_val <= 0: return
                
                sl = price - (atr_val * 2.0)
                tp = self.ema20[-1]
                
                if sl >= price: sl = price * 0.99
                if tp <= price: tp = price * 1.01
                
                self.buy(sl=sl, tp=tp)


class RSIPingPongStrategy(Strategy):
    """RSI Ping Pong"""
    rsi_period = 14
    rsi_oversold = 30
    min_rr = 1.5
    
    def init(self):
        self.rsi = self.I(ta_wrapper, ta.rsi, self.data.Close, length=self.rsi_period)
        self.adx = self.I(ta_adx_wrapper, self.data.High, self.data.Low, self.data.Close, length=14)
        self.atr = self.I(ta_atr_wrapper, self.data.High, self.data.Low, self.data.Close, length=14)
        
    def next(self):
        if self.position: return
        if self.adx[-1] > 25: return
        
        if self.rsi[-1] < self.rsi_oversold and self.rsi[-2] > self.rsi[-1]:
             atr_val = self.atr[-1]
             if np.isnan(atr_val) or atr_val <= 0: return
             
             sl = self.data.Low[-1] - atr_val
             tp = self.data.Close[-1] + (atr_val * 3)
             
             price = self.data.Close[-1]
             if sl >= price: sl = price * 0.99
             if tp <= price: tp = price * 1.01
             
             self.buy(sl=sl, tp=tp)


class DoubleBottomStrategy(Strategy):
    """Double Bottom"""
    min_rr = 1.3
    
    def init(self):
         self.ema200 = self.I(ta_wrapper, ta.ema, self.data.Close, length=200)
    
    def next(self):
        if self.position: return
        if len(self.data) < 50: return
        
        window = 20
        recent = self.data.Low[-window:]
        if len(recent) < window: return
        
        l1 = float(recent[0])
        l2 = float(recent[-1])
        mid_high = float(max(recent))
        
        if abs(l1 - l2) / l1 < 0.01:
            if mid_high > l1 * 1.02:
                sl = min(l1, l2) * 0.99
                tp = mid_high + (mid_high - sl)
                
                price = self.data.Close[-1]
                if sl >= price: sl = price * 0.99
                if tp <= price: tp = price * 1.01
                
                self.buy(sl=sl, tp=tp)


class BullFlagStrategy(Strategy):
    """Bull Flag"""
    min_rr = 1.3
    
    def init(self):
        self.ema20 = self.I(ta_wrapper, ta.ema, self.data.Close, length=20)
        self.volume_sma = self.I(ta_wrapper, ta.sma, self.data.Volume, length=20)
        
    def next(self):
        if self.position: return
        if len(self.data) < 30: return
        
        start_price = self.data.Close[-20]
        peak_price = float(max(self.data.High[-20:-5]))
        
        if (peak_price - start_price) / start_price > 0.03:
            curr_price = self.data.Close[-1]
            if curr_price < peak_price and curr_price > start_price:
                if np.isnan(self.volume_sma[-1]): return
                recent_vol = sum(self.data.Volume[-5:]) / 5
                if recent_vol < self.volume_sma[-1]:
                    if self.data.Close[-1] > self.ema20[-1]:
                        sl = float(min(self.data.Low[-5:]))
                        tp = peak_price + (peak_price - start_price)
                        
                        price = self.data.Close[-1]
                        if sl >= price: sl = price * 0.99
                        if tp <= price: tp = price * 1.01
                        
                        self.buy(sl=sl, tp=tp)


class SmartMeanReversionStrategy(Strategy):
    """Smart Mean Reversion"""
    rsi_period = 14
    roc_period = 10
    bb_period = 20
    bb_std = 2.0
    rsi_threshold = 30
    roc_floor = -15.0
    min_rr = 1.5
    
    def init(self):
        self.rsi = self.I(ta_wrapper, ta.rsi, self.data.Close, length=self.rsi_period)
        
        # Custom ROC implementation using Series pct_change since ta.roc might differ
        def roc_calc(close, length):
            return pd.Series(close).pct_change(periods=length) * 100
            
        self.roc = self.I(roc_calc, self.data.Close, length=self.roc_period)
        
        # Bollinger Bands
        close_series = pd.Series(self.data.Close)
        bb = ta.bbands(close_series, length=self.bb_period, std=self.bb_std)
        
        n = len(close_series)
        l, m, u = np.zeros(n), np.zeros(n), np.zeros(n)
        
        if isinstance(bb, pd.DataFrame):
            l = bb.iloc[:, 0].to_numpy()
            m = bb.iloc[:, 1].to_numpy()
            u = bb.iloc[:, 2].to_numpy()
            
        self.lower = self.I(lambda: l)
        self.mid = self.I(lambda: m)
        self.upper = self.I(lambda: u)
        
        self.adx = self.I(ta_adx_wrapper, self.data.High, self.data.Low, self.data.Close, length=14)

    def next(self):
        if self.position: return
        if len(self.data) < 50: return
        
        # Regime Check (Range Only)
        if not np.isnan(self.adx[-1]) and self.adx[-1] > 25: return
        
        # RSI Oversold
        if self.rsi[-1] >= self.rsi_threshold: return
        
        # Momentum Floor (Crash Protection)
        if self.roc[-1] < self.roc_floor: return
        
        # Bollinger Interaction
        if self.data.Close[-1] >= self.lower[-1]: return
        
        # Stabilization (Green candle relative to prev close)
        if self.data.Close[-1] <= self.data.Close[-2]: return
        
        # SL/TP Calculation
        recent_low = min(self.data.Low[-4:-1]) # Last 3 completed (excluding current building?) 
        # In backtesting.py next() runs on closed candle usually, so [-1] is 'current closed'.
        # The strategy logic says "Last 3 completed". If [-1] is the signal candle, we look at [-4:-1] relative to it?
        # Let's use [-3:] (last 3) relative to NOW.
        recent_low = min(self.data.Low[-3:]) 
        sl = recent_low * 0.995
        
        tp = self.mid[-1]
        
        price = self.data.Close[-1]
        
        if sl >= price: sl = price * 0.99
        if tp <= price: tp = price * 1.01
        
        if price - sl == 0: return
        
        rr = (tp - price) / (price - sl)
        if rr < self.min_rr: return
        
        self.buy(sl=sl, tp=tp)


# Mapping
STRATEGY_CLASSES = {
    "fibo_pullback": FiboPullbackStrategy,
    "smart_trend": SmartTrendStrategy,
    "scalp_ema_rsi": ScalpEmaRsiStrategy,
    "institutional_scalp": InstitutionalScalpStrategy,
    "bollinger_bounce": BollingerBounceStrategy,
    "elastic_reversion": ElasticReversionStrategy,
    "rsi_ping_pong": RSIPingPongStrategy,
    "double_bottom": DoubleBottomStrategy,
    "bull_flag": BullFlagStrategy,
    "smart_mean_reversion": SmartMeanReversionStrategy,
}
