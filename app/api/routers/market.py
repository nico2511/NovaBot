"""
Market Router - Market Data Endpoints
Handles candles, symbols, ticker, funding rates, open interest
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from typing import Optional
import logging
import pandas as pd
from app.api.auth import require_api_key

logger = logging.getLogger("MarketRouter")

router = APIRouter(prefix="/api/market", tags=["market"], dependencies=[Depends(require_api_key)])


@router.get("/candles")
def get_candles(
    symbol: str = Query(..., description="Trading symbol (e.g., BTC, ETH)"),
    interval: str = Query("15m", description="Candle interval (1m, 5m, 15m, 1h, 4h, 1d)"),
    limit: int = Query(200, description="Number of candles to fetch")
):
    """Get OHLCV candles for a symbol"""
    try:
        from app.services.hyperliquid_service import hyperliquid_service
        
        df = hyperliquid_service.get_candles(symbol, interval, limit)
        
        if df.empty:
            return {"candles": []}
        
        # Convert DataFrame to list of dicts
        candles = []
        for idx, row in df.iterrows():
            candles.append({
                "timestamp": int(idx.timestamp() * 1000),
                "open": float(row['open']),
                "high": float(row['high']),
                "low": float(row['low']),
                "close": float(row['close']),
                "volume": float(row['volume'])
            })
        
        return {"candles": candles}
    except Exception as e:
        logger.error(f"Error fetching candles for {symbol}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch candles: {str(e)}")


@router.get("/symbols")
def get_symbols():
    """Get list of available trading symbols"""
    try:
        from app.services.hyperliquid_service import hyperliquid_service
        
        meta = hyperliquid_service._fetch_metadata()
        if not meta:
            raise HTTPException(status_code=500, detail="Failed to fetch metadata")
        
        universe = meta.get("universe", [])
        symbols = [asset["name"] for asset in universe]
        
        return {"symbols": symbols, "count": len(symbols)}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching symbols: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch symbols: {str(e)}")


@router.get("/ticker")
def get_ticker(symbol: str = Query(..., description="Trading symbol")):
    """Get current ticker data for a symbol"""
    try:
        from app.services.hyperliquid_service import hyperliquid_service
        
        price = hyperliquid_service.get_current_price(symbol)
        
        return {
            "symbol": symbol,
            "price": price,
            "timestamp": int(pd.Timestamp.now(tz='UTC').timestamp() * 1000)
        }
    except Exception as e:
        logger.error(f"Error fetching ticker for {symbol}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch ticker: {str(e)}")


@router.get("/funding")
def get_funding(symbol: str = Query(..., description="Trading symbol")):
    """Get current funding rate for a symbol"""
    try:
        from app.services.hyperliquid_service import hyperliquid_service
        
        funding_rate = hyperliquid_service.get_funding_rate(symbol)
        
        return {
            "symbol": symbol,
            "funding_rate": funding_rate,
            "funding_rate_percent": funding_rate * 100,
            "timestamp": int(pd.Timestamp.now(tz='UTC').timestamp() * 1000)
        }
    except Exception as e:
        logger.error(f"Error fetching funding for {symbol}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch funding rate: {str(e)}")


@router.get("/oi")
def get_open_interest(symbol: str = Query(..., description="Trading symbol")):
    """Get open interest for a symbol"""
    try:
        from app.services.hyperliquid_service import hyperliquid_service
        
        oi = hyperliquid_service.get_open_interest(symbol)
        
        return {
            "symbol": symbol,
            "open_interest_usd": oi,
            "timestamp": int(pd.Timestamp.now(tz='UTC').timestamp() * 1000)
        }
    except Exception as e:
        logger.error(f"Error fetching OI for {symbol}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch open interest: {str(e)}")


@router.get("/orderbook")
def get_orderbook(
    symbol: str = Query(..., description="Trading symbol"),
    depth: int = Query(20, description="Orderbook depth")
):
    """Get orderbook for a symbol"""
    try:
        from app.services.hyperliquid_service import hyperliquid_service
        
        # Note: This would require implementing get_orderbook in hyperliquid_service
        # For now, return placeholder
        return {
            "symbol": symbol,
            "bids": [],
            "asks": [],
            "message": "Orderbook endpoint not yet implemented"
        }
    except Exception as e:
        logger.error(f"Error fetching orderbook for {symbol}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch orderbook: {str(e)}")
