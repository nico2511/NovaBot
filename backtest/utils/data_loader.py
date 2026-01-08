"""
Data Loader Utility
Charge les données historiques pour backtest 15M
"""

import pandas as pd
import yfinance as yf
from pathlib import Path


def load_data(symbol, start_date, end_date, timeframe="15m", source="yfinance", csv_path=None):
    """
    Charge les données OHLCV pour backtest
    
    Args:
        symbol: Symbole (ex: "BTC/USDT")
        start_date: Date début (YYYY-MM-DD)
        end_date: Date fin (YYYY-MM-DD)
        timeframe: Timeframe (15m par défaut)
        source: Source ("yfinance", "csv")
        csv_path: Chemin CSV si source="csv"
    
    Returns:
        DataFrame avec Open, High, Low, Close, Volume
    """
    
    if source == "yfinance":
        return _load_yfinance(symbol, start_date, end_date, timeframe)
    elif source == "csv":
        return _load_csv(csv_path)
    else:
        raise ValueError(f"Unknown data source: {source}")


def _load_yfinance(symbol, start_date, end_date, timeframe):
    """Charge depuis yfinance"""
    
    # Convertir BTC/USDT → BTC-USD
    if "/" in symbol:
        base, quote = symbol.split("/")
        if quote == "USDT":
            quote = "USD"
        symbol_yf = f"{base}-{quote}"
    else:
        symbol_yf = symbol
    
    print(f"[INFO] Downloading {symbol_yf} {timeframe} data...")
    print(f"   Period: {start_date} -> {end_date}")
    
    ticker = yf.Ticker(symbol_yf)
    df = ticker.history(start=start_date, end=end_date, interval=timeframe)
    
    if df.empty:
        raise ValueError(f"No data for {symbol_yf}")
    
    df = df[["Open", "High", "Low", "Close", "Volume"]]
    
    print(f"[INFO] Loaded {len(df)} candles ({df.index[0]} -> {df.index[-1]})")
    
    return df


def _load_csv(csv_path):
    """Charge depuis CSV"""
    
    if not Path(csv_path).exists():
        raise FileNotFoundError(f"CSV not found: {csv_path}")
    
    df = pd.read_csv(csv_path, index_col=0, parse_dates=True)
    df = df[["Open", "High", "Low", "Close", "Volume"]]
    
    print(f"[INFO] Loaded {len(df)} candles from CSV")
    
    return df


def validate_data(df):
    """Valide les données"""
    
    required = ["Open", "High", "Low", "Close", "Volume"]
    missing = [col for col in required if col not in df.columns]
    
    if missing:
        raise ValueError(f"Missing columns: {missing}")
    
    if df.isnull().any().any():
        raise ValueError("NaN values found in data")
    
    # Vérifier logique OHLC
    if (df["High"] < df["Low"]).any():
        raise ValueError("Invalid data: High < Low")
    
    print("[INFO] Data validation passed")
    
    return True
