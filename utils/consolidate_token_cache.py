"""
Consolidate Token Metadata Cache
Fetches metadata for ALL available tokens on Hyperliquid and saves to token_meta_cache.json
"""
import json
from app.services.hyperliquid_service import hyperliquid_service

def consolidate_token_cache():
    """Fetch and cache metadata for all Hyperliquid tokens"""
    print("🔍 Fetching all available tokens from Hyperliquid...")
    
    try:
        # Get all available tokens
        meta_info = hyperliquid_service.info.meta()
        universe = meta_info.get("universe", [])
        
        print(f"✅ Found {len(universe)} tokens")
        
        # Build comprehensive cache
        cache = {}
        for token_info in universe:
            symbol = token_info.get("name")
            if symbol:
                cache[symbol] = {
                    "szDecimals": token_info.get("szDecimals", 8),
                    "maxLeverage": token_info.get("maxLeverage", 20),
                    "onlyIsolated": token_info.get("onlyIsolated", False),
                    # Add any other useful metadata
                }
                print(f"  ✓ {symbol}: {cache[symbol]}")
        
        # Save to file
        cache_file = "token_meta_cache.json"
        with open(cache_file, "w") as f:
            json.dump(cache, f, indent=2)
        
        print(f"\n✅ Consolidated cache saved to {cache_file}")
        print(f"📊 Total tokens cached: {len(cache)}")
        
        return cache
        
    except Exception as e:
        print(f"❌ Error consolidating token cache: {e}")
        import traceback
        traceback.print_exc()
        return None

if __name__ == "__main__":
    consolidate_token_cache()
