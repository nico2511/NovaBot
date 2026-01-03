
import sys
import json
sys.path.append('.')

from app.services.hyperliquid_service import hyperliquid_service
from app.core.config import config

def inspect_account():
    print("🔍 Inspecting Hyperliquid Account State...\n")
    
    if not config.HL_ACCOUNT_ADDRESS:
        print("❌ No account address configured.")
        return

    # 1. Balance & Margin
    print("--- 💰 BALANCE ---")
    balance = hyperliquid_service.get_account_balance(force_refresh=True)
    if balance.get("status") == "success":
        equity = balance.get("total_equity", 0)
        margin_used = balance.get("margin_used", 0)
        available = balance.get("available_balance", 0)
        print(f"Equity:      ${equity:.2f}")
        print(f"Margin Used: ${margin_used:.2f}")
        print(f"Available:   ${available:.2f}")
        if equity > 0:
            print(f"Utilization: {(margin_used/equity)*100:.1f}%")
    else:
        print(f"Error fetching balance: {balance.get('message')}")

    # 2. Open Positions
    print("\n--- 📈 POSITIONS ---")
    positions = hyperliquid_service.get_positions()
    if positions:
        for p in positions:
            print(f"• {p['side']} {p['size']} {p['symbol']} @ ${p['entry_price']:.4f} (PnL: ${p['pnl']:.2f})")
    else:
        print("No open positions.")

    # 3. Open Orders
    print("\n--- 📝 OPEN ORDERS ---")
    try:
        open_orders = hyperliquid_service.info.open_orders(config.HL_ACCOUNT_ADDRESS)
        if open_orders:
            for o in open_orders:
                print(f"• [{o['oid']}] {o['side']} {o['sz']} {o['coin']} @ ${o['limitPx']} ({o['orderType']})")
                # Check if it's a resting limit or trigger
        else:
            print("No open orders.")
    except Exception as e:
        print(f"Error fetching orders: {e}")

if __name__ == "__main__":
    inspect_account()
