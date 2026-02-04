
import pandas as pd
import requests
import time
from datetime import datetime, timedelta

def download_data(symbol='BTC', days=30):
    print(f"📥 Downloading {days} days of {symbol} 1m data...")
    end_time = datetime.utcnow()
    start_time = end_time - timedelta(days=days)
    
    # Using Binance Public API for 1m klines (simplest for bulk)
    base_url = "https://api.binance.com/api/v3/klines"
    
    all_data = []
    current_start = int(start_time.timestamp() * 1000)
    final_end = int(end_time.timestamp() * 1000)
    
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
            
            print(f"  > Progress: {datetime.utcfromtimestamp(current_start/1000)}", end='\r')
            time.sleep(0.1) # Respect rate limits
            
        except Exception as e:
            print(f"\n❌ Error: {e}")
            break
            
    df = pd.DataFrame(all_data, columns=[
        'timestamp', 'Open', 'High', 'Low', 'Close', 'Volume', 
        'close_time', 'qav', 'num_trades', 'taker_base', 'taker_quote', 'ignore'
    ])
    
    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
    df.set_index('timestamp', inplace=True)
    
    # Convert types
    for col in ['Open', 'High', 'Low', 'Close', 'Volume']:
        df[col] = df[col].astype(float)
        
    output_path = "data/BTC_1m.csv"
    df[['Open', 'High', 'Low', 'Close', 'Volume']].to_csv(output_path)
    print(f"\n✅ Saved {len(df)} rows to {output_path}")

if __name__ == "__main__":
    download_data()
