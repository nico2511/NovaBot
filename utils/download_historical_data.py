#!/usr/bin/env python3
"""
Download Historical Data from Hyperliquid
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.hyperliquid_service import hyperliquid_service
import pandas as pd
from datetime import datetime

def download_historical_data(symbol: str = "BTC", interval: str = "15m", days: int = 90):
    """
    Télécharge les données historiques depuis Hyperliquid.
    
    Args:
        symbol: Symbole du token
        interval: Intervalle (15m, 1h, 4h, 1d)
        days: Nombre de jours d'historique
    """
    print(f"📥 Downloading {symbol} {interval} data ({days} days)...")
    
    # Calculer le nombre de bougies
    candles_per_day = {
        "1m": 1440,
        "15m": 96,
        "1h": 24,
        "4h": 6,
        "1d": 1
    }
    
    limit = candles_per_day.get(interval, 96) * days
    
    # Télécharger
    df = hyperliquid_service.get_candles(symbol, interval, limit)
    
    if df.empty:
        print("❌ No data received")
        return False
    
    # Reset index to make timestamp a column if it's in index
    if 'timestamp' not in df.columns and df.index.name == 'timestamp':
        df = df.reset_index()
    
    # Rename columns to standard format (t → timestamp, etc.)
    column_mapping = {
        't': 'timestamp',
        'T': 'close_time',
        's': 'symbol',
        'i': 'interval'
    }
    df = df.rename(columns=column_mapping)
    
    # Ensure timestamp is datetime
    if 'timestamp' in df.columns:
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
    
    # Select only required columns for backtest
    required_cols = ['timestamp', 'open', 'high', 'low', 'close', 'volume']
    available_cols = [col for col in required_cols if col in df.columns]
    df = df[available_cols]
    
    # Sauvegarder
    output_dir = "data/historical"
    os.makedirs(output_dir, exist_ok=True)
    
    output_file = f"{output_dir}/{symbol}_{interval}.csv"
    df.to_csv(output_file, index=False)
    
    print(f"✅ Downloaded {len(df)} candles")
    print(f"📅 Period: {df['timestamp'].iloc[0]} → {df['timestamp'].iloc[-1]}")
    print(f"💾 Saved to: {output_file}")
    
    return True

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Download historical data for backtesting")
    parser.add_argument("--symbol", default="BTC", help="Symbol to download (default: BTC)")
    parser.add_argument("--interval", default="15m", choices=["1m", "15m", "1h", "4h", "1d"], help="Candle interval")
    parser.add_argument("--days", type=int, default=90, help="Number of days to download (default: 90)")
    
    args = parser.parse_args()
    
    success = download_historical_data(args.symbol, args.interval, args.days)
    
    if success:
        print("\n✅ Data ready for backtest!")
        print(f"   Run: python backtest_launcher.py")
    else:
        print("\n❌ Download failed")
        sys.exit(1)
