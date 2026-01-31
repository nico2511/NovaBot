import aiohttp
import asyncio
import json
import time

async def probe():
    url = 'https://api.hyperliquid.xyz/info'
    
    end_time = int(time.time() * 1000)
    start_time = end_time - (3600 * 1000 * 24) # 24 hours
    
    payload = {
        "type": "fundingHistory",
        "coin": "BTC",
        "startTime": start_time,
        "endTime": end_time
    }
    
    print("Sending payload:", payload)
    
    async with aiohttp.ClientSession() as session:
        async with session.post(url, json=payload) as resp:
            print(f"Status: {resp.status}")
            if resp.status == 200:
                data = await resp.json()
                if data and len(data) > 0:
                    print("First record keys:", data[0].keys())
                    print("First record sample:", data[0])
                else:
                    print("No data returned.")
            else:
                print("Error:", await resp.text())

if __name__ == "__main__":
    asyncio.run(probe())
