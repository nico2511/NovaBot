"""
API endpoint for token scanner
"""

from fastapi import APIRouter
from app.services.token_scanner import HyperliquidScanner

router = APIRouter()

@router.get("/scanner/opportunities")
async def get_opportunities(top_n: int = 10):
    """Get top trading opportunities"""
    try:
        scanner = HyperliquidScanner()
        opportunities = scanner.scan(top_n=top_n)
        
        return {
            "success": True,
            "count": len(opportunities),
            "opportunities": opportunities
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
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
        details = opportunities[0] if opportunities else None
        
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
