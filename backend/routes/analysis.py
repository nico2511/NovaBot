from fastapi import APIRouter, Depends, HTTPException
from typing import List, Dict, Any
from app.services.analyst_service import analyst_service
from app.services.hyperliquid_service import hyperliquid_service

router = APIRouter(prefix="/analysis", tags=["analysis"])

@router.get("/", response_model=Dict[str, Any])
async def get_analysis():
    """
    Get multi-timeframe market analysis and active position insights.
    """
    try:
        # 1. Get Active Symbol (from Bot State if available, or default to BTC)
        # We try to get it from the bot_bridge if connected
        symbol = "BTC"
        
        # Try to import bot bridge dynamically to avoid circular imports at top level if not needed
        try:
            from backend.bot_bridge import bot_bridge
            if bot_bridge and bot_bridge.is_connected():
                bot = bot_bridge.get_bot_context()
                symbol = bot.active_symbol
        except ImportError:
            pass

        # 2. Analyze Market Sentiment
        market_sentiment = await analyst_service.analyze_market_sentiment(symbol)
        
        # 3. Analyze Active Positions
        positions_analysis = []
        try:
            positions = hyperliquid_service.get_positions()
            for pos in positions:
                if float(pos.get("size", 0)) != 0:
                    analysis = analyst_service.analyze_position(pos, market_sentiment)
                    positions_analysis.append({
                        "symbol": pos["symbol"],
                        "size": pos["size"],
                        "entryPrice": pos.get("entryPx"),
                        "pnl_roe": pos.get("returnOnEquity"),
                        "analysis": analysis
                    })
        except Exception as e:
            print(f"Error fetching positions for analysis: {e}")

        return {
            "symbol": symbol,
            "market_sentiment": market_sentiment,
            "positions_analysis": positions_analysis,
            "global_advice": market_sentiment.get("1h", {}).get("sentiment", "NEUTRAL")
        }
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
