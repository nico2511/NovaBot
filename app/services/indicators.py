import pandas as pd
import numpy as np

class Indicators:
    """
    Pure Pandas implementation of classic technical indicators.
    No external TA library required.
    Designed to be as close as possible to original Wilder formulas.
    
    Version: 2026-01-17 (Corrected)
    - Added min_periods to avoid bias on early data
    - Safe division handling to prevent inf/nan
    - Wilder-style alpha smoothing (alpha=1/length)
    """

    @staticmethod
    def ema(series: pd.Series, length: int = 14, min_periods: int = None) -> pd.Series:
        """Exponential Moving Average (Wilder style - alpha=1/N)"""
        return series.ewm(
            alpha=1/length,
            adjust=False,
            min_periods=min_periods or length
        ).mean()

    @staticmethod
    def ema_std(series: pd.Series, length: int = 14, min_periods: int = None) -> pd.Series:
        """Standard Exponential Moving Average (TradingView style - alpha=2/(N+1))"""
        return series.ewm(
            span=length,
            adjust=False,
            min_periods=min_periods or length
        ).mean()

    @staticmethod
    def sma(series: pd.Series, length: int = 20) -> pd.Series:
        """Simple Moving Average"""
        return series.rolling(window=length).mean()

    @staticmethod
    def rsi(close: pd.Series, length: int = 14) -> pd.Series:
        """Relative Strength Index – Wilder original method"""
        delta = close.diff()
        gain = delta.where(delta > 0, 0).fillna(0)
        loss = -delta.where(delta < 0, 0).fillna(0)

        avg_gain = gain.ewm(alpha=1/length, adjust=False, min_periods=length).mean()
        avg_loss = loss.ewm(alpha=1/length, adjust=False, min_periods=length).mean()

        # Safe division: replace 0 with nan to avoid inf
        rs = avg_gain / avg_loss.replace(0, np.nan)
        rsi = 100 - (100 / (1 + rs))
        return rsi

    @staticmethod
    def atr(high: pd.Series, low: pd.Series, close: pd.Series, length: int = 14) -> pd.Series:
        """Average True Range – using EMA smoothing (common approximation)"""
        tr1 = high - low
        tr2 = (high - close.shift(1)).abs()
        tr3 = (low - close.shift(1)).abs()

        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        return tr.ewm(alpha=1/length, adjust=False, min_periods=length).mean()

    @staticmethod
    def adx(high: pd.Series, low: pd.Series, close: pd.Series, length: int = 14):
        """
        Average Directional Index +DI -DI
        Returns DataFrame with columns: 'ADX', 'DMP', 'DMN' (compatible with existing strategies)
        """
        # True Range
        tr = pd.concat([
            high - low,
            (high - close.shift(1)).abs(),
            (low - close.shift(1)).abs()
        ], axis=1).max(axis=1)

        atr = tr.ewm(alpha=1/length, adjust=False, min_periods=length).mean()

        # Directional Movement
        up = high.diff()
        down = -low.diff()

        plus_dm = up.where((up > down) & (up > 0), 0.0)
        minus_dm = down.where((down > up) & (down > 0), 0.0)

        plus_dm_s = plus_dm.ewm(alpha=1/length, adjust=False, min_periods=length).mean()
        minus_dm_s = minus_dm.ewm(alpha=1/length, adjust=False, min_periods=length).mean()

        plus_di = 100 * plus_dm_s / atr
        minus_di = 100 * minus_dm_s / atr

        # DX with safe division (avoid inf on flat markets)
        diff = (plus_di - minus_di).abs()
        denom = plus_di + minus_di
        dx = 100 * diff / denom.where(denom > 1e-9, np.nan)

        adx = dx.ewm(alpha=1/length, adjust=False, min_periods=length).mean()

        # Keep original column names for backward compatibility
        return pd.DataFrame({
            'ADX': adx,
            'DMP': plus_di,
            'DMN': minus_di
        }, index=high.index)

    @staticmethod
    def bbands(close: pd.Series, length: int = 20, std: float = 2.0):
        """Bollinger Bands"""
        middle = close.rolling(window=length).mean()
        sigma = close.rolling(window=length).std()
        upper = middle + std * sigma
        lower = middle - std * sigma

        # Keep original column names for backward compatibility
        return pd.DataFrame({
            'BBL': lower,
            'BBM': middle,
            'BBU': upper
        }, index=close.index)

    @staticmethod
    def macd(close: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9):
        """
        Moving Average Convergence Divergence
        Returns DataFrame with columns: 'MACD', 'MACDh', 'MACDs'
        """
        fast_ema = Indicators.ema(close, length=fast)
        slow_ema = Indicators.ema(close, length=slow)
        
        macd_line = fast_ema - slow_ema
        signal_line = Indicators.ema(macd_line, length=signal)
        histogram = macd_line - signal_line
        
        return pd.DataFrame({
            'MACD': macd_line,
            'MACDh': histogram,
            'MACDs': signal_line
        }, index=close.index)

    @staticmethod
    def supertrend(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 10, multiplier: float = 3.0):
        """
        Supertrend indicator.
        Returns DataFrame with columns: 'Supertrend', 'Direction' (1 for Bullish, -1 for Bearish)
        """
        # 1. ATR calculation
        atr = Indicators.atr(high, low, close, period)
        
        # 2. Median Price
        hl2 = (high + low) / 2
        
        # 3. Basic Bands
        basic_ub = hl2 + (multiplier * atr)
        basic_lb = hl2 - (multiplier * atr)
        
        # 4. Final Bands (Stateful)
        m = len(close)
        final_ub = np.zeros(m)
        final_lb = np.zeros(m)
        st = np.zeros(m)
        direction = np.zeros(m)
        
        # Initialize
        final_ub[0] = basic_ub.iloc[0]
        final_lb[0] = basic_lb.iloc[0]
        st[0] = basic_ub.iloc[0]
        direction[0] = -1
        
        # Loop for stateful logic (Final Bands & Supertrend)
        close_values = close.values
        basic_ub_values = basic_ub.values
        basic_lb_values = basic_lb.values
        
        for i in range(1, m):
            # Final Upper Band
            if (basic_ub_values[i] < final_ub[i-1]) or (close_values[i-1] > final_ub[i-1]):
                final_ub[i] = basic_ub_values[i]
            else:
                final_ub[i] = final_ub[i-1]
                
            # Final Lower Band
            if (basic_lb_values[i] > final_lb[i-1]) or (close_values[i-1] < final_lb[i-1]):
                final_lb[i] = basic_lb_values[i]
            else:
                final_lb[i] = final_lb[i-1]
                
            # Supertrend & Direction
            if st[i-1] == final_ub[i-1]:
                if close_values[i] > final_ub[i]:
                    st[i] = final_lb[i]
                    direction[i] = 1
                else:
                    st[i] = final_ub[i]
                    direction[i] = -1
            else:
                if close_values[i] < final_lb[i]:
                    st[i] = final_ub[i]
                    direction[i] = -1
                else:
                    st[i] = final_lb[i]
                    direction[i] = 1
                    
        return pd.DataFrame({
            'Supertrend': st,
            'Direction': direction
        }, index=close.index)


# ────────────────────────────────────────────────
#   API style pandas_ta (for strategy compatibility)
# ────────────────────────────────────────────────

class TaAdapter:
    def ema(self, close, length=14):
        return Indicators.ema(close, length)

    def ema_std(self, close, length=14):
        return Indicators.ema_std(close, length)

    def sma(self, close, length=20):
        return Indicators.sma(close, length)

    def rsi(self, close, length=14):
        return Indicators.rsi(close, length)

    def atr(self, high, low, close, length=14):
        return Indicators.atr(high, low, close, length)

    def adx(self, high, low, close, length=14):
        return Indicators.adx(high, low, close, length)

    def bbands(self, close, length=20, std=2.0):
        return Indicators.bbands(close, length, std)

    def macd(self, close, fast=12, slow=26, signal=9):
        return Indicators.macd(close, fast, slow, signal)

    def supertrend(self, high, low, close, period=10, multiplier=3.0):
        return Indicators.supertrend(high, low, close, period, multiplier)


# Singleton – usage: from app.services.indicators import ta; ta.rsi(df['close'])
ta = TaAdapter()
