from hyperliquid.info import Info
import json

try:
    info = Info(skip_ws=True)
    market_data = info.meta_and_asset_ctxs()
    meta = market_data[0]
    contexts = market_data[1]

    for i, asset in enumerate(meta['universe']):
        if asset['name'] == 'BTC':
            print(f"--- Raw Context for BTC ---")
            print(json.dumps(contexts[i], indent=2))
            
            ctx = contexts[i]
            mark_px = float(ctx.get('markPx', 0))
            oi = ctx.get('openInterest', 'MISSING')
            print(f"\nCalculated:")
            print(f"Symbol: BTC")
            print(f"Mark Price: {mark_px}")
            print(f"Raw Open Interest: {oi}")
            if oi != 'MISSING':
                print(f"OI (USD): {float(oi) * mark_px}")
            break
except Exception as e:
    print(f"Error: {e}")
