"""
API endpoint for token scanner
"""

from fastapi import APIRouter
from app.services.token_scanner import HyperliquidScanner

router = APIRouter()

# Import sanitize helper from main API
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from backend.api import sanitize_for_json

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
