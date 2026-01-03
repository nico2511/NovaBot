"""
Script to download 1m historical data for SmartTrend backtest
"""
import sys
import pandas as pd
import os
sys.path.append('.')

from app.services.hyperliquid_service import hyperliquid_service

def download_1m_data(symbol: str, limit: int = 5000):
    print(f"\n📊 Downloading {symbol} 1m data (Limit: {limit})...")
    df = hyperliquid_service.get_candles(symbol, "1m", limit=limit)
    
    if df is not None and not df.empty:
        # Save to CSV
        output_path = f"data/historical/{symbol}_1m.csv"
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        
        df.to_csv(output_path)
        print(f"✅ Saved to {output_path} ({len(df)} rows)")
        
        # Verify timestamps
        print(f"   Range: {df.index[0]} -> {df.index[-1]}")
    else:
        print(f"❌ Failed to download {symbol} 1m data")

if __name__ == "__main__":
    download_1m_data("BTC", limit=5000)
    download_1m_data("DOGE", limit=5000)
