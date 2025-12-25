#!/usr/bin/env python3
"""Debug script to test Hyperliquid balance API"""

from app.core.config import config
from hyperliquid.info import Info
from hyperliquid.utils.constants import MAINNET_API_URL
import json

def test_balance():
    print("=" * 60)
    print("Testing Hyperliquid Balance API")
    print("=" * 60)
    
    # Check configuration
    print(f"\nAccount Address: {config.HL_ACCOUNT_ADDRESS}")
    print(f"Private Key configured: {'Yes' if config.HL_PRIVATE_KEY else 'No'}")
    
    # Initialize Info API
    info = Info(base_url=MAINNET_API_URL, skip_ws=True)
    
    try:
        # Fetch user state
        print(f"\nFetching user state for: {config.HL_ACCOUNT_ADDRESS}")
        user_state = info.user_state(config.HL_ACCOUNT_ADDRESS)
        
        # Print full response for debugging
        print("\n" + "=" * 60)
        print("FULL API RESPONSE:")
        print("=" * 60)
        print(json.dumps(user_state, indent=2))
        
        # Extract balance information
        print("\n" + "=" * 60)
        print("PARSED BALANCE INFO:")
        print("=" * 60)
        
        if user_state:
            # Check different possible fields
            margin_summary = user_state.get("crossMarginSummary", {})
            print(f"\nCross Margin Summary: {json.dumps(margin_summary, indent=2)}")
            
            account_value = float(margin_summary.get("accountValue", 0.0))
            total_margin_used = float(margin_summary.get("totalMarginUsed", 0.0))
            withdrawable = float(user_state.get("withdrawable", account_value))
            
            print(f"\nAccount Value: ${account_value:.2f}")
            print(f"Withdrawable: ${withdrawable:.2f}")
            print(f"Margin Used: ${total_margin_used:.2f}")
            
            # Check asset positions
            asset_positions = user_state.get("assetPositions", [])
            print(f"\nAsset Positions: {len(asset_positions)}")
            for pos in asset_positions:
                print(f"  - {json.dumps(pos, indent=4)}")
                
        else:
            print("❌ No user state returned!")
            
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_balance()
