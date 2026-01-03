
import sys
import time
sys.path.append('.')

from app.services.hyperliquid_service import hyperliquid_service
from app.core.config import config

def consolidate_doge():
    symbol = "DOGE"
    print(f"🧹 Consolidating orders for {symbol}...")
    
    # 1. Get Position
    positions = hyperliquid_service.get_positions()
    doge_pos = next((p for p in positions if p["symbol"] == symbol), None)
    
    if not doge_pos:
        print("❌ No DOGE position found to consolidate.")
        return

    size = doge_pos["size"]
    entry = doge_pos["entry_price"]
    side = doge_pos["side"]
    print(f"✅ Found Position: {size} {symbol} @ {entry}")

    # 2. Cancel Existing Orders
    print("🗑️ Cancelling all open orders...")
    hyperliquid_service.cancel_all_orders(symbol)
    time.sleep(1)

    # 3. Calculate New SL/TP (Consolidated)
    # Strategy: Use 2.5% SL and 4% TP from average entry (Standard fallback)
    # Or try to read from existing orders? Too risky if they vary.
    # Let's use the standard "Recovered" logic from main_nextjs.py
    
    sl_dist = entry * 0.025
    tp_dist = entry * 0.04
    
    if side == "BUY":
        sl_price = entry - sl_dist
        tp_price = entry + tp_dist
        is_buy_close = False
    else:
        sl_price = entry + sl_dist
        tp_price = entry - tp_dist
        is_buy_close = True
        
    print(f"🎯 New Levels: SL={sl_price:.4f}, TP={tp_price:.4f}")

    # 4. Place New Orders
    print(f"🚀 Placing new consolidated orders for {size} {symbol}...")
    res = hyperliquid_service.sync_sl_tp(
        symbol,
        side == "BUY", # is_buy (of position)
        size,
        sl_price,
        tp_price
    )
    
    print(f"✅ Result: {res}")

if __name__ == "__main__":
    consolidate_doge()
