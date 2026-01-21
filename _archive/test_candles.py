import requests
import time

url = "http://localhost:8001/api/market/candles?symbol=SUI&interval=15m&limit=10"
print(f"Checking {url}...")

try:
    response = requests.get(url)
    if response.status_code == 200:
        data = response.json()
        print(f"✅ Success! Received {len(data)} candles.")
        if len(data) > 0:
            print(f"Sample: {data[0]}")
    else:
        print(f"❌ Error: {response.status_code} - {response.text}")
except Exception as e:
    print(f"❌ Connection failed: {e}")
