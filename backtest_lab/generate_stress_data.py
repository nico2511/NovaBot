
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import os
import argparse

def generate_stress_data(type='crash', symbol='BTC', start_price=50000, duration_minutes=1440):
    print(f"🛠 Generating STRESS data: {type} for {symbol} starting at ${start_price}...")
    
    # Use timezone-aware UTC datetime
    from datetime import timezone
    base_time = datetime.now(timezone.utc)
    timestamps = [base_time - timedelta(minutes=duration_minutes-i) for i in range(duration_minutes)]
    prices = np.zeros(duration_minutes)
    prices[0] = start_price
    
    # Base volatility (noise)
    volatility = 0.0005 
    
    if type == 'crash':
        # Flash crash in the middle
        mid = duration_minutes // 2
        crash_start = mid - 30
        crash_end = mid + 30
        
        for i in range(1, duration_minutes):
            change = np.random.normal(0, volatility)
            if crash_start <= i <= mid:
                change -= 0.015 # Even steeper drop to trigger ADX/RSI
            elif mid < i <= crash_end:
                change += 0.005 # Partial recovery
            prices[i] = prices[i-1] * (1 + change)
            
    elif type == 'squeeze':
        # Short squeeze
        mid = duration_minutes // 2
        squeeze_start = mid - 10
        squeeze_end = mid + 50
        
        for i in range(1, duration_minutes):
            change = np.random.normal(0, volatility)
            if i < squeeze_start:
                change -= 0.0005 # Slow bleeder
            elif squeeze_start <= i <= squeeze_end:
                change += 0.008 # Explosive pump
            prices[i] = prices[i-1] * (1 + change)
            
    elif type == 'noise':
        # High frequency noise (mean reverting)
        volatility = 0.005
        for i in range(1, duration_minutes):
            prices[i] = prices[i-1] * (1 + np.random.normal(0, volatility))
            
    elif type == 'trend':
        # Strong uptrend with minor pullbacks
        for i in range(1, duration_minutes):
            change = np.random.normal(0.0002, volatility) # Positive drift
            prices[i] = prices[i-1] * (1 + change)
    else:
        print(f"❌ Unknown type: {type}")
        return

    df = pd.DataFrame({
        'timestamp': timestamps,
        'Open': prices,
        'High': prices * (1 + np.random.uniform(0, 0.001, duration_minutes)),
        'Low': prices * (1 - np.random.uniform(0, 0.001, duration_minutes)),
        'Close': prices, # Simplified for synthetic
        'Volume': np.random.uniform(10, 100, duration_minutes)
    })
    
    # Fix OHLC logic (Close should be between High and Low)
    df['Close'] = df['Open'] * (1 + np.random.normal(0, 0.0005, duration_minutes))
    df['High'] = df[['Open', 'Close']].max(axis=1) * (1 + np.random.uniform(0, 0.0005, duration_minutes))
    df['Low'] = df[['Open', 'Close']].min(axis=1) * (1 - np.random.uniform(0, 0.0005, duration_minutes))

    df.set_index('timestamp', inplace=True)
    
    os.makedirs("data", exist_ok=True)
    output_path = f"data/STRESS_{type}.csv"
    df.to_csv(output_path)
    print(f"✅ Generated {len(df)} rows to {output_path}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--type", choices=['crash', 'squeeze', 'noise', 'trend'], default='crash')
    parser.add_argument("--symbol", default="BTC")
    parser.add_argument("--price", type=float, default=50000)
    parser.add_argument("--duration", type=int, default=4320, help="Duration in minutes (default 3 days)")
    args = parser.parse_args()
    
    generate_stress_data(type=args.type, symbol=args.symbol, start_price=args.price, duration_minutes=args.duration)
