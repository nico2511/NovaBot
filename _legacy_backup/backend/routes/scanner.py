"""
API endpoint for token scanner
"""

from fastapi import APIRouter
from app.services.token_scanner import HyperliquidScanner
import numpy as np

router = APIRouter()

def sanitize_for_json(obj):
    """Convert numpy types to native Python types for JSON serialization"""
    if isinstance(obj, dict):
        return {k: sanitize_for_json(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [sanitize_for_json(item) for item in obj]
    elif isinstance(obj, (np.integer, np.int64, np.int32)):
        return int(obj)
    elif isinstance(obj, (np.floating, np.float64, np.float32)):
        return float(obj)
    elif isinstance(obj, (np.bool_, bool)):
        return bool(obj)
    elif isinstance(obj, np.ndarray):
        return obj.tolist()
    return obj

@router.get("/scanner/opportunities")
async def get_opportunities(top_n: int = 10):
    """Get top trading opportunities with gamification filtering"""
    try:
        from app.core.asset_gamification import AssetGamification
        from app.services.hyperliquid_service import hyperliquid_service
        
        scanner = HyperliquidScanner()
        
        # Get gamification whitelist
        whitelist = None
        try:
            balance_data = hyperliquid_service.get_account_balance()
            equity = balance_data.get("total_equity", 0) if balance_data.get("status") == "success" else 0
            gamification = AssetGamification(equity)
            whitelist = gamification.get_allowed_assets()
            print(f"🎮 Scanner API: Gamification Level {gamification.level.value} (${equity:.2f}) - {len(whitelist)} assets allowed")
        except Exception as e:
            print(f"⚠️ Gamification error in scanner API: {e}")
            whitelist = None  # Full access on error
        
        # Scan with whitelist
        opportunities = scanner.scan(top_n=top_n, whitelist=whitelist)
        
        # CRITICAL: Sanitize numpy types before JSON serialization
        opportunities = sanitize_for_json(opportunities)
        
        return {
            "success": True,
            "count": len(opportunities),
            "opportunities": opportunities
        }
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"❌ API Error in get_opportunities: {e}")
        return {
            "success": False, 
            "error": f"{str(e)}", 
            "trace": traceback.format_exc(),
            "opportunities": []
        }

@router.get("/scanner/best")
async def get_best_asset():
    """Get the single best asset to trade"""
    try:
        scanner = HyperliquidScanner()
        best_asset = scanner.get_best_asset()
        
        # Get full details
        opportunities = scanner.scan(top_n=1)
        details = sanitize_for_json(opportunities[0]) if opportunities else None
        
        return {
            "success": True,
            "best_asset": best_asset,
            "details": details
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "best_asset": "BTC"
        }
