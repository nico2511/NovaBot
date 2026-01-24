<story id="STORY-ANALYSIS-01" name="Active Position & Market Analyst">
  <context>
    User wants a "Sidecar" analysis service to provide multi-timeframe sentiment and position advice without modifying the core bot loop.
    This service will be exposed via `GET /api/analysis`.
  </context>
  
  <tasks>
    <task id="1" name="Create Analyst Service">
        <description>
            Implement `app/services/analyst_service.py`.
            - Method `analyze_market_sentiment(symbol)`: fetch 5m, 1h, 4h candles via `get_hyperliquid_candles`. Calculate trend (EMA20/50), RSI. Return "BULLISH/BEARISH".
            - Method `analyze_position(pos)`: Evaluate provided position against current price/trends. Return advice string.
        </description>
        <files>
            <file>app/services/analyst_service.py</file>
        </files>
    </task>

    <task id="2" name="Create Analysis API Router">
        <description>
            Implement `backend/routes/analysis.py` using FastAPI.
            - Endpoint `GET /`:
                1. Fetch Real Positions via `hyperliquid_service.get_positions()`.
                2. For each pos, call `analyst_service.analyze_position`.
                3. Fetch `bot.active_symbol` (via bot_bridge or state) and call `analyst_service.analyze_market_sentiment`.
                4. Return aggregated JSON.
        </description>
        <files>
            <file>backend/routes/analysis.py</file>
        </files>
    </task>

    <task id="3" name="Register Router">
        <description>
            Modify `backend/api.py` to include the new router.
            - Import `backend.routes.analysis`
            - `app.include_router(analysis.router, prefix="/api/analysis")`
        </description>
        <files>
            <file>backend/api.py</file>
        </files>
    </task>
  </tasks>
</story>
