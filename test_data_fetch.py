"""
Debug script to check if data is being fetched correctly
"""
from app.services.hyperliquid_service import hyperliquid_service

# Test data fetch
print("Testing data fetch for BTC...")
df = hyperliquid_service.get_candles("BTC", "15m", limit=100)

if df is None or df.empty:
    print("❌ NO DATA RECEIVED!")
else:
    print(f"✅ Received {len(df)} candles")
    print(f"\nFirst 5 rows:")
    print(df.head())
    print(f"\nLast 5 rows:")
    print(df.tail())
    print(f"\nData types:")
    print(df.dtypes)
    print(f"\nPrice range:")
    print(f"  Min: ${df['close'].min():.2f}")
    print(f"  Max: ${df['close'].max():.2f}")
    print(f"  Current: ${df['close'].iloc[-1]:.2f}")
