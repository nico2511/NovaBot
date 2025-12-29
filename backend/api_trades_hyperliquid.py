@app.get("/api/trades/hyperliquid")
async def get_hyperliquid_trades(limit: int = 100):
    """Get trade history from Hyperliquid API"""
    try:
        from app.services.hyperliquid_service import hyperliquid_service
        
        trades = hyperliquid_service.get_trade_history(limit)
        
        return {
            "status": "success",
            "trades": trades,
            "source": "hyperliquid_api",
            "count": len(trades)
        }
    except Exception as e:
        print(f"Error in /api/trades/hyperliquid: {e}")
        import traceback
        traceback.print_exc()
        return {
            "status": "error",
            "message": str(e),
            "trades": []
        }
