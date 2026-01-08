"""
Binance Historical Data Downloader
Télécharge plusieurs mois de données 15M depuis Binance
"""

import pandas as pd
from datetime import datetime, timedelta
import requests
import time
from pathlib import Path


def download_binance_klines(symbol, interval, start_date, end_date, output_file):
    """
    Télécharge les données historiques depuis Binance
    
    Args:
        symbol: Symbole Binance (ex: "BTCUSDT")
        interval: Intervalle (ex: "15m")
        start_date: Date début (YYYY-MM-DD)
        end_date: Date fin (YYYY-MM-DD)
        output_file: Fichier CSV de sortie
    """
    
    print(f"\n📥 Downloading {symbol} {interval} data from Binance...")
    print(f"   Period: {start_date} → {end_date}")
    
    # Convertir dates en timestamps
    start_ts = int(datetime.strptime(start_date, "%Y-%m-%d").timestamp() * 1000)
    end_ts = int(datetime.strptime(end_date, "%Y-%m-%d").timestamp() * 1000)
    
    # URL API Binance
    url = "https://api.binance.com/api/v3/klines"
    
    all_data = []
    current_ts = start_ts
    
    # Télécharger par chunks de 1000 candles
    while current_ts < end_ts:
        params = {
            "symbol": symbol,
            "interval": interval,
            "startTime": current_ts,
            "endTime": end_ts,
            "limit": 1000  # Max par requête
        }
        
        try:
            response = requests.get(url, params=params)
            response.raise_for_status()
            data = response.json()
            
            if not data:
                break
            
            all_data.extend(data)
            
            # Timestamp de la dernière candle
            current_ts = data[-1][0] + 1
            
            print(f"   Downloaded {len(all_data)} candles...", end="\r")
            
            # Rate limit Binance (1200 req/min)
            time.sleep(0.1)
            
        except Exception as e:
            print(f"\n❌ Error: {e}")
            break
    
    if not all_data:
        print("\n❌ No data downloaded!")
        return None
    
    # Convertir en DataFrame
    df = pd.DataFrame(all_data, columns=[
        'timestamp', 'Open', 'High', 'Low', 'Close', 'Volume',
        'close_time', 'quote_volume', 'trades', 'taker_buy_base',
        'taker_buy_quote', 'ignore'
    ])
    
    # Garder seulement OHLCV
    df = df[['timestamp', 'Open', 'High', 'Low', 'Close', 'Volume']]
    
    # Convertir types
    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
    df['Open'] = df['Open'].astype(float)
    df['High'] = df['High'].astype(float)
    df['Low'] = df['Low'].astype(float)
    df['Close'] = df['Close'].astype(float)
    df['Volume'] = df['Volume'].astype(float)
    
    # Set index
    df.set_index('timestamp', inplace=True)
    
    # Sauvegarder
    Path(output_file).parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(output_file)
    
    print(f"\n✅ Downloaded {len(df)} candles")
    print(f"   First: {df.index[0]}")
    print(f"   Last: {df.index[-1]}")
    print(f"💾 Saved to: {output_file}")
    
    return df


def main():
    """Point d'entrée principal"""
    
    print("\n" + "="*80)
    print("📊 BINANCE HISTORICAL DATA DOWNLOADER")
    print("="*80)
    
    # Configuration
    symbol = "BTCUSDT"  # Binance symbol
    interval = "15m"
    start_date = "2024-07-01"  # 6 mois de données
    end_date = "2025-01-08"
    output_file = "../data/BTC_15m_6months.csv"
    
    print(f"\nSymbol: {symbol}")
    print(f"Interval: {interval}")
    print(f"Period: {start_date} → {end_date}")
    print(f"Output: {output_file}")
    print("="*80)
    
    # Télécharger
    df = download_binance_klines(symbol, interval, start_date, end_date, output_file)
    
    if df is not None:
        print("\n" + "="*80)
        print("✅ DOWNLOAD COMPLETED")
        print("="*80)
        print(f"Total candles: {len(df)}")
        print(f"File size: {Path(output_file).stat().st_size / 1024 / 1024:.2f} MB")
        print("\n💡 To use in backtest:")
        print(f'   DATA_SOURCE = "csv"')
        print(f'   CSV_PATH = "{output_file}"')
        print("="*80 + "\n")


if __name__ == "__main__":
    main()
