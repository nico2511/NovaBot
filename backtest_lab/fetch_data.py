import yfinance as yf
import pandas as pd
import os

def download_data(symbol="BTC-USD", period="5d", interval="1m", output_file="data/BTC_1m.csv"):
    print(f"📥 Downloading {symbol} ({period}, {interval})...")
    data = yf.download(symbol, period=period, interval=interval)
    
    if data.empty:
        print("❌ No data found.")
        return

    # Flatten columns if MultiIndex
    if isinstance(data.columns, pd.MultiIndex):
        data.columns = data.columns.droplevel(1)
        
    # Rename for backtesting compatibility
    data.rename(columns={
        "Open": "Open", 
        "High": "High", 
        "Low": "Low", 
        "Close": "Close", 
        "Volume": "Volume"
    }, inplace=True)
    
    os.makedirs(os.path.dirname(output_file), exist_ok=True)
    data.to_csv(output_file)
    print(f"✅ Data saved to {output_file} ({len(data)} rows)")

if __name__ == "__main__":
    download_data()
