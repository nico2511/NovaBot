
import pandas as pd
import requests
import time
import os
from datetime import datetime, timedelta

import argparse

PRESETS = {
    'crash_aug24': ('2024-08-04', '2024-08-06'),
    'dip_apr24': ('2024-04-12', '2024-04-14'),
    'etf_jan24': ('2024-01-09', '2024-01-11'),
    'election_nov24': ('2024-11-04', '2024-11-07')
}

def download_data(symbol='BTC', days=None, start_date=None, end_date=None, preset=None):
    if preset and preset in PRESETS:
        start_date, end_date = PRESETS[preset]
        print(f"📦 Using PRESET: {preset} ({start_date} to {end_date})")
    
    if start_date and end_date:
        start_dt = datetime.strptime(start_date, '%Y-%m-%d')
        end_dt = datetime.strptime(end_date, '%Y-%m-%d')
        suffix = f"_{start_date}_to_{end_date}"
    else:
        days = days or 30
        end_dt = datetime.utcnow()
        start_dt = end_dt - timedelta(days=days)
        suffix = ""

    print(f"📥 Downloading {symbol} 1m data from {start_dt} to {end_dt}...")
    
    # Using Binance Public API for 1m klines (simplest for bulk)
    base_url = "https://api.binance.com/api/v3/klines"
    
    all_data = []
    current_start = int(start_dt.timestamp() * 1000)
    final_end = int(end_dt.timestamp() * 1000)
    
    while current_start < final_end:
        params = {
            "symbol": f"{symbol}USDT",
            "interval": "1m",
            "startTime": current_start,
            "limit": 1000
        }
        
        try:
            response = requests.get(base_url, params=params)
            data = response.json()
            
            if not data:
                break
                
            all_data.extend(data)
            # Last candle timestamp + 1m
            current_start = data[-1][0] + 60000
            
            # Stop if we reached final_end
            if current_start >= final_end:
                break

            print(f"  > Progress: {datetime.utcfromtimestamp(current_start/1000)}", end='\r')
            time.sleep(0.1) # Respect rate limits
            
        except Exception as e:
            print(f"\n❌ Error: {e}")
            break
            
    if not all_data:
        print("❌ No data found for this range.")
        return

    df = pd.DataFrame(all_data, columns=[
        'timestamp', 'Open', 'High', 'Low', 'Close', 'Volume', 
        'close_time', 'qav', 'num_trades', 'taker_base', 'taker_quote', 'ignore'
    ])
    
    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
    df.set_index('timestamp', inplace=True)
    
    # Convert types
    for col in ['Open', 'High', 'Low', 'Close', 'Volume']:
        df[col] = df[col].astype(float)
        
    os.makedirs("data", exist_ok=True)
    output_path = f"data/{symbol}{suffix}_1m.csv"
    df[['Open', 'High', 'Low', 'Close', 'Volume']].to_csv(output_path)
    print(f"\n✅ Saved {len(df)} rows to {output_path}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--symbol", default="BTC")
    parser.add_argument("--days", type=int)
    parser.add_argument("--start", help="YYYY-MM-DD")
    parser.add_argument("--end", help="YYYY-MM-DD")
    parser.add_argument("--preset", help=f"Choose from: {list(PRESETS.keys())}")
    args = parser.parse_args()
    
    download_data(symbol=args.symbol, days=args.days, start_date=args.start, end_date=args.end, preset=args.preset)
