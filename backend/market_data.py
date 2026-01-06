"""
Standalone market data service for FastAPI
Uses HyperLiquid API and calculates real indicators
"""
import pandas as pd
import numpy as np
from datetime import datetime
import aiohttp
from app.services.indicators import Indicators


async def get_hyperliquid_candles(symbol: str = "BTC", interval: str = "15m", limit: int = 100):
    """Fetch candles from HyperLiquid API"""
    try:
        url = 'https://api.hyperliquid.xyz/info'
        
        # Calculate time range
        end_time = int(datetime.now().timestamp() * 1000)
        # 15m = 900s, so limit candles * 900s
        start_time = end_time - (limit * 15 * 60 * 1000)
        
        payload = {
            "type": "candleSnapshot",
            "req": {
                "coin": symbol,
                "interval": interval,
                "startTime": start_time,
                "endTime": end_time
            }
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload) as resp:
                result_df = None
                
                candles = []  # Initialize to empty list to avoid UnboundLocalError
                
                if resp.status == 200:
                    candles = await resp.json()
                    
                    # RETRY WITH 'k' PREFIX (e.g. PEPE -> kPEPE) if empty
                    if not candles and not symbol.startswith("k"):
                         # Add exponential backoff for retry
                         import asyncio
                         await asyncio.sleep(0.5) 
                         
                         print(f"⚠️ No candles for {symbol}, trying k{symbol}...")
                         payload["req"]["coin"] = f"k{symbol}"
                         async with session.post(url, json=payload) as resp_retry:
                              if resp_retry.status == 200:
                                   candles = await resp_retry.json()
                                   
                if not candles:
                    return None
                
                # Convert to DataFrame
                df = pd.DataFrame(candles)
                df['time'] = pd.to_datetime(df['t'], unit='ms')
                df.set_index('time', inplace=True)
                
                # Convert to float
                for col in ['o', 'h', 'l', 'c', 'v']:
                    df[col] = df[col].astype(float)
                
                # Rename columns
                df.rename(columns={
                    'o': 'open',
                    'h': 'high',
                    'l': 'low',
                    'c': 'close',
                    'v': 'volume'
                }, inplace=True)
                
                return df.tail(limit)
                    
    except Exception as e:
        print(f"Error fetching HyperLiquid candles: {e}")
        return None


async def get_current_price(symbol: str = "BTC") -> float:
    """Get current price from HyperLiquid"""
    try:
        url = 'https://api.hyperliquid.xyz/info'
        payload = {"type": "allMids"}
        
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return float(data.get(symbol, 87000))
    except Exception as e:
        print(f"Error fetching price: {e}")
    
    return 87000.0


async def get_formatted_candles(symbol: str = "BTC", interval: str = "15m", limit: int = 100):
    """Get candles formatted for frontend chart (lightweight-charts)"""
    df = await get_hyperliquid_candles(symbol, interval, limit)
    if df is None or df.empty:
        return []
    
    # Format for lightweight-charts: { time: '2018-12-22', open: 75.16, high: 82.84, low: 36.16, close: 45.72 }
    # Requires timestamp in seconds
    candles = []
    for index, row in df.iterrows():
        # Timestamp is index
        ts = int(index.timestamp())
        candles.append({
            "time": ts,
            "open": float(row['open']),
            "high": float(row['high']),
            "low": float(row['low']),
            "close": float(row['close'])
        })
    return candles


async def get_open_interest(symbol: str = "BTC") -> float:
    """Get Open Interest for a symbol (Mock or Real)"""
    # Hyperliquid doesn't expose clean OI in public info endpoint easily without iteration
    # returns value in USD
    try:
        url = 'https://api.hyperliquid.xyz/info'
        payload = {"type": "metaAndAssetCtxs"}
        
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    # Find symbol index
                    universe = data[0]["universe"]
                    asset_ctxs = data[1]
                    
                    try:
                        idx = next(i for i, coin in enumerate(universe) if coin["name"] == symbol)
                        ctx = asset_ctxs[idx]
                        return float(ctx["openInterest"]) * float(ctx["oraclePx"])
                    except StopIteration:
                        return 0.0
    except Exception as e:
        print(f"Error fetching OI: {e}")
    return 0.0
