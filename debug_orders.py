
import sys
import json
import traceback
sys.path.append('.')

from app.services.hyperliquid_service import hyperliquid_service
from app.core.config import config
from hyperliquid.utils.error import ClientError

def debug_account():
    print("🔍 DEBUG: Inspecting Account...\n")
    
    # 1. POSITIONS
    print("--- 1. POSITIONS ---")
    try:
        positions = hyperliquid_service.get_positions()
        if positions:
            for p in positions:
                print(f"✅ Position: {p['side']} {p['size']} {p['symbol']} (Entry: {p['entry_price']})")
        else:
            print("ℹ️ No open positions found.")
    except Exception as e:
        print(f"❌ Error fetching positions: {e}")

    # 2. OPEN ORDERS
    print("\n--- 2. OPEN ORDERS ---")
    try:
        # Direct access to info API
        open_orders = hyperliquid_service.info.open_orders(config.HL_ACCOUNT_ADDRESS)
        if open_orders:
            print(f"⚠️ Found {len(open_orders)} open orders:")
            for o in open_orders:
                print(f"   • [{o['oid']}] {o['side']} {o['sz']} {o['coin']} @ ${o['limitPx']}")
        else:
            print("✅ No open orders.")
    except ClientError as e:
        print(f"❌ API ClientError: {e}")
    except Exception as e:
        print(f"❌ General Error fetching orders: {e}")
        traceback.print_exc()

if __name__ == "__main__":
    debug_account()
