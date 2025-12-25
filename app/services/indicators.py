import pandas as pd
import numpy as np

class Indicators:
    """
    Pure Pandas implementation of technical indicators.
    Replaces pandas_ta dependency for better compatibility.
    """

    @staticmethod
    def ema(series: pd.Series, length: int = 14) -> pd.Series:
        """Exponential Moving Average"""
        return series.ewm(span=length, adjust=False).mean()

    @staticmethod
    def rsi(series: pd.Series, length: int = 14) -> pd.Series:
        """Relative Strength Index"""
        delta = series.diff()
        gain = (delta.where(delta > 0, 0)).fillna(0)
        loss = (-delta.where(delta < 0, 0)).fillna(0)
        
        avg_gain = gain.ewm(alpha=1/length, adjust=False).mean()
        avg_loss = loss.ewm(alpha=1/length, adjust=False).mean()
        
        rs = avg_gain / avg_loss
        return 100 - (100 / (1 + rs))

    @staticmethod
    def atr(high: pd.Series, low: pd.Series, close: pd.Series, length: int = 14) -> pd.Series:
        """Average True Range"""
        tr1 = high - low
        tr2 = (high - close.shift(1)).abs()
        tr3 = (low - close.shift(1)).abs()
        
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        # Using EMA smoothing for ATR (Wilder's smoothing is slightly different but EMA is standard proxy)
        return tr.ewm(alpha=1/length, adjust=False).mean()

    @staticmethod
    def adx(high: pd.Series, low: pd.Series, close: pd.Series, length: int = 14) -> pd.Series:
        """Average Directional Index"""
        # True Range
        tr1 = high - low
        tr2 = (high - close.shift(1)).abs()
        tr3 = (low - close.shift(1)).abs()
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        atr = tr.ewm(alpha=1/length, adjust=False).mean()

        # Directional Movement
        up_move = high - high.shift(1)
        down_move = low.shift(1) - low
        
        plus_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0.0)
        minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0.0)
        
        plus_dm_s = pd.Series(plus_dm, index=high.index).ewm(alpha=1/length, adjust=False).mean()
        minus_dm_s = pd.Series(minus_dm, index=high.index).ewm(alpha=1/length, adjust=False).mean()
        
        plus_di = 100 * (plus_dm_s / atr)
        minus_di = 100 * (minus_dm_s / atr)
        
        dx = 100 * np.abs((plus_di - minus_di) / (plus_di + minus_di))
        adx = dx.ewm(alpha=1/length, adjust=False).mean()
        
        return pd.concat([adx, plus_di, minus_di], axis=1, keys=['ADX', 'DMP', 'DMN'])

    @staticmethod
    def bbands(series: pd.Series, length: int = 20, std: float = 2.0):
        """Bollinger Bands"""
        middle = series.rolling(window=length).mean()
        sigma = series.rolling(window=length).std()
        upper = middle + (std * sigma)
        lower = middle - (std * sigma)
        return pd.DataFrame({'BBL': lower, 'BBM': middle, 'BBU': upper}, index=series.index)

# Create a 'ta' like object for compatibility
class TaAdapter:
    def rsi(self, close, length=14):
        return Indicators.rsi(close, length)
    
    def ema(self, close, length=14):
        return Indicators.ema(close, length)
    
    def atr(self, high, low, close, length=14):
        return Indicators.atr(high, low, close, length)
    
    def adx(self, high, low, close, length=14):
        return Indicators.adx(high, low, close, length)
    
    def bbands(self, close, length=20, std=2.0):
        return Indicators.bbands(close, length, std)

# Singleton to mimic pandas_ta module
ta = TaAdapter()
