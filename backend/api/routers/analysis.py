"""
Analysis Router - Copilot & Market Analysis Endpoints
Serves AI-generated sentiment analysis and position advice
"""
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from typing import Optional
from backend.api.dependencies import get_bot_context
import logging
import json

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


class AskAIRequest(BaseModel):
    symbol: Optional[str] = None


@router.post("/ask-ai")
def ask_ai_trade_signal(data: AskAIRequest = None, bot=Depends(get_bot_context)):
    """
    On-demand AI trade check. Analyzes current market and tells you if a trade is possible.
    Returns a clear YES/NO with reasoning.
    """
    try:
        symbol = (data.symbol if data and data.symbol else None) or bot.active_symbol
        target_symbol = symbol.upper().strip()

        # 1. Get current market data
        from app.services.hyperliquid_service import hyperliquid_service

        current_price = hyperliquid_service.get_current_price(target_symbol)
        if not current_price or current_price <= 0:
            return {"symbol": target_symbol, "trade_possible": False, "direction": None, "reasoning": "Unable to fetch current price.", "confidence": 0}

        # 2. Fetch candles for analysis
        df_15m = hyperliquid_service.get_candles(target_symbol, interval="15m", limit=200)
        if df_15m is None or df_15m.empty or len(df_15m) < 50:
            return {"symbol": target_symbol, "trade_possible": False, "direction": None, "reasoning": "Not enough candle data for analysis.", "confidence": 0}

        # 3. Run strategy engine analysis
        try:
            df_1m = hyperliquid_service.get_candles(target_symbol, interval="1m", limit=100)
            for col in ['open', 'high', 'low', 'close', 'volume']:
                if col in df_15m.columns:
                    df_15m[col] = df_15m[col].astype(float)
                if df_1m is not None and not df_1m.empty and col in df_1m.columns:
                    df_1m[col] = df_1m[col].astype(float)
            
            result = bot.strategy_engine.analyze(df_15m, extra_data={"1m": df_1m, "symbol": target_symbol})
        except Exception as engine_err:
            logger.error(f"Strategy engine error: {engine_err}")
            result = {"regime": "UNKNOWN", "signals": [], "adx": 0, "rsi": 50}

        regime = result.get("regime", "UNKNOWN")
        adx = result.get("adx", 0)
        rsi = result.get("rsi", 50)
        signals = result.get("signals", [])

        # 4. Build market context for AI
        try:
            market_context = bot._prepare_ai_context() if target_symbol == bot.active_symbol else {
                "symbol": target_symbol,
                "current_price": current_price,
                "regime": regime,
                "rsi": rsi,
                "adx": adx,
            }
        except Exception:
            market_context = {
                "symbol": target_symbol,
                "current_price": current_price,
                "regime": regime,
                "rsi": rsi,
                "adx": adx,
            }

        # 5. Build prompt for quick trade assessment
        from app.services.ia import ia_service
        from app.core.config import config

        best_signal = signals[0] if signals else None
        signal_info = ""
        if best_signal:
            signal_info = f"""
Best Strategy Signal Detected:
- Direction: {best_signal.get('signal', 'N/A')}
- Strategy: {best_signal.get('strategy', 'N/A')}
- Score: {best_signal.get('score', 0)}
- Price: ${best_signal.get('price', 'N/A')}
"""

        prompt = f"""You are a trading analyst. Based on the current market data below, determine if a trade (LONG or SHORT) is possible RIGHT NOW on {target_symbol}.

=== CURRENT MARKET SNAPSHOT ===
Symbol: {target_symbol}
Current Price: ${current_price}
Market Regime: {regime}
ADX: {adx}
RSI: {rsi}
{signal_info}

=== ANALYSIS TASK ===
Analyze the conditions and answer:
1. Is there a viable trade setup RIGHT NOW (LONG or SHORT)?
2. Which direction (LONG/SHORT/NONE)?
3. Why or why not?

Be concise. Focus on actionable insight.

=== REQUIRED OUTPUT ===
Respond ONLY with valid JSON (no markdown):
{{
  "trade_possible": true|false,
  "direction": "LONG"|"SHORT"|null,
  "confidence": <0-100>,
  "reasoning": "1-2 sentence explanation in ENGLISH"
}}
"""

        ai_result = ia_service._call_ai_generic(prompt)
        raw = ai_result.get("raw_output", "{}")

        try:
            parsed = json.loads(ia_service.extract_json(raw))
        except Exception:
            parsed = {"trade_possible": False, "direction": None, "confidence": 0, "reasoning": "AI response could not be parsed."}

        return {
            "symbol": target_symbol,
            "trade_possible": parsed.get("trade_possible", False),
            "direction": parsed.get("direction"),
            "confidence": parsed.get("confidence", 0),
            "reasoning": parsed.get("reasoning", "No reasoning provided."),
            "regime": regime,
            "adx": round(adx, 1),
            "rsi": round(rsi, 1),
            "current_price": current_price
        }

    except Exception as e:
        logger.error(f"Error in ask-ai: {e}")
        return {"symbol": "ERROR", "trade_possible": False, "direction": None, "reasoning": f"Analysis failed: {str(e)}", "confidence": 0}
