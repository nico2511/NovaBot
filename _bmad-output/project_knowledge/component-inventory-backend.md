# Component Inventory (Backend)

## Services (`app/services/`)
- **`hyperliquid_service.py`**: Core wrapper for Hyperliquid Python SDK. Handles authentication, orders, market data.
- **`ia.py`**: AI Service integrating OpenRouter. Handles `analyze_market` and `validate_signal` with caching and personas.
- **`indicators.py`**: Technical indicators (RSI, EMA, ADX, ATR, BB) implemented in pure Pandas (replacing `pandas-ta`).

## Core (`app/core/`)
- **`config.py`**: Environment variable loading (`.env`).
- **`state_manager.py`**: Handles atomic read/write of `bot_state.json`.
- **`risk_manager.py`**: Manages daily PnL limits, max positions, and stop-loss logic.
- **`asset_gamification.py`**: Gamification logic (XP, Levels) based on equity.
- **`scanner_job.py`**: Background job for scanning tokens (logic likely moved/shared with backend).
- **`trade_recorder.py`**: Logs trades to CSV/JSON.

## Strategies (`strategies/`)
Active strategies implementing a common interface (typically `generate_signal`):
1. **`smart_trend.py`**
2. **`bollinger_bounce.py`**
3. **`elastic_reversion.py`**
4. **`institutional_scalp.py`**
5. **`scalp_ema_rsi.py`**
6. **`smart_mean_reversion.py`**

## Backend Main (`backend/`)
- **`api.py`**: FastAPI entry point.
- **`bot_bridge.py`**: Interface allowing the API to control the running bot instance.
- **`market_data.py`**: Helper functions for ensuring data availability using Hyperliquid SDK.
