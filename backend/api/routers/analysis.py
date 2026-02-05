"""
Analysis Router - Copilot \u0026 Market Analysis Endpoints
Serves AI-generated sentiment analysis and position advice
"""
from fastapi import APIRouter, Depends
from backend.api.dependencies import get_bot_context
import logging

logger = logging.getLogger("AnalysisRouter")

router = APIRouter(prefix="/api/analysis", tags=["analysis"])

@router.get("/")
def get_analysis_data(symbol: str = None, bot=Depends(get_bot_context)):
    """
    Get consolidated analysis data for frontend Copilot.
    Prevent crashes by ensuring all expected keys exist.
    """
    try:
        # Use target symbol (priority) or bot's active symbol
        target_symbol = symbol or bot.active_symbol
        
        # Default empty structure to prevent Frontend crashes
        default_sentiment = {
            "sentiment": "NEUTRAL",
            "score": 50,
            "rsi": 50,
            "trend": "SIDEWAYS",
            "macd": {"value": 0, "crossover": "NEUTRAL", "hist": 0},
            "volume": {"status": "NORMAL", "value": 0},
            "details": "Waiting for analysis..."
        }

        response = {
            "symbol": target_symbol,
            "market_sentiment": {
                "5m": default_sentiment,
                "1h": default_sentiment,
                "4h": default_sentiment,
                "history": []
            },
            "positions_analysis": [],
            "global_advice": "HOLD",
            "market_data": {
                "funding_rate": 0.0,
                "open_interest": 0.0,
                "funding_rate_hourly_pct": 0.0
            }
        }

        # 0. Fetch Real-Time Market Data for the requested symbol
        try:
            from app.services.hyperliquid_service import hyperliquid_service
            
            # Funding (Already canonicalized inside the service)
            funding = hyperliquid_service.get_funding_rate(target_symbol)
            
            # Open Interest
            oi = hyperliquid_service.get_open_interest(target_symbol)
            
            response["market_data"] = {
                "funding_rate": funding, # Raw (e.g. 0.0001)
                "funding_rate_hourly_pct": funding * 100, # % (e.g. 0.01%)
                "open_interest": oi
            }
        except Exception as e:
            logger.error(f"Error fetching real-time market data: {e}")

        # 1. Populate Market Sentiment from AI Cache
        if hasattr(bot, 'ai_cache') and bot.ai_cache:
            # If target_symbol matches bot's active_symbol, return cached analysis
            if target_symbol == bot.active_symbol:
                market_data = bot.ai_cache.get('last_market_analysis')
                if market_data and isinstance(market_data, dict):
                    for key in ["5m", "1h", "4h", "history"]:
                        if key in market_data:
                            response["market_sentiment"][key] = market_data[key]
            else:
                # If it's a different symbol, we don't have analysis yet
                # We could trigger it, but for now we just return market data
                response["market_sentiment"]["1h"]["details"] = f"Switch bot focus to {target_symbol} for AI analysis."


        # 2. Populate Position Analysis from AI Cache
        pos_analysis = bot.ai_cache.get('last_position_analysis')
        if pos_analysis:
            # Frontend expects an array of analyses
            # If the cache stores a single dict for the active position, wrap it
            if isinstance(pos_analysis, dict):
                # Ensure it has the structure frontend expects
                # Structure seems to be: { symbol, size, analysis: { advice, color, reason, score } }
                response["positions_analysis"] = [pos_analysis]
            elif isinstance(pos_analysis, list):
                response["positions_analysis"] = pos_analysis

        # 3. Global Advice
        # Derive from 1h sentiment if not explicitly set
        sentiment_1h = response["market_sentiment"]["1h"].get("sentiment", "NEUTRAL")
        if sentiment_1h == "BULLISH":
             response["global_advice"] = "LOOK FOR LONGS"
        elif sentiment_1h == "BEARISH":
             response["global_advice"] = "LOOK FOR SHORTS"
        else:
             response["global_advice"] = "PATIENCE"

        return response

    except Exception as e:
        logger.error(f"Error fetching analysis data: {e}")
        # Return safe fallback
        return {
            "symbol": "ERROR",
            "market_sentiment": {
                "5m": default_sentiment,
                "1h": default_sentiment,
                "4h": default_sentiment,
                "history": []
            },
            "positions_analysis": [],
            "global_advice": "ERROR"
        }
