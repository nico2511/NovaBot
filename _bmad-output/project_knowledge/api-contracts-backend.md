# API Contracts (Backend)

## Overview | Vue d'ensemble
The API is built with **FastAPI** (`backend/api.py`) and exposes REST endpoints for:
- Bot Status & Control (Start/Stop, Enable/Disable)
- Market Data (Candles, Metrics, Metadata)
- Trade Management (Active Trade, Close, SL/TP)
- Settings & Logs
- Integration with Next.js Frontend

**Base URL:** `http://localhost:8001` (Default)

## Endpoints

### 🟢 Status & Control

#### `GET /api/status`
Get the current status of the bot.
- **Response:** `BotStatus` (JSON)
  ```json
  {
    "is_running": boolean,
    "trading_enabled": boolean,
    "active_symbol": string,
    "execution_mode": string,
    "active_trade": object | null
  }
  ```

#### `POST /api/engine/start`
Start the trading engine loop.
- **Response:** `{"status": "started", "message": "..."}`

#### `POST /api/engine/stop`
Stop the trading engine loop.
- **Response:** `{"status": "stopped", "message": "..."}`

#### `POST /api/trading/enable`
Enable live trading execution (Hyperliquid).
- **Response:** `{"status": "enabled", "message": "..."}`

#### `POST /api/trading/disable`
Disable live trading (Phantom mode).
- **Response:** `{"status": "disabled", "message": "..."}`

---

### 📊 Market Data

#### `GET /api/candles`
Get historical candles for charts.
- **Query Params:**
  - `limit`: int (default 200)
  - `symbol`: string (optional)
  - `strategy`: string (optional)
- **Response:** `{"candles": [{time, open, high, low, close, volume, ...indicators}]}`

#### `GET /api/market/data`
Get comprehensive real-time market data with computed indicators.
- **Response:**
  ```json
  {
    "symbol": "BTC",
    "price": 100000.0,
    "regime": "TREND",
    "rsi": 55.0,
    "adx": 25.0,
    "trends": { "15m": {...}, "1h": {...} },
    "active_strategies": [...],
    "signals": [...]
  }
  ```

#### `GET /api/market_metrics` (Scanner Optimized)
- **Query Params:** `symbol`
- **Response:** Light metrics payload for scanner (RSI, ADX, RVOL).

#### `GET /api/meta`
Get exchange metadata (precision, etc.).

---

### 💰 Trade Management

#### `GET /api/active_trade`
Get details of the currently active trade (including AI analysis).

#### `POST /api/close_trade`
Manually close the active position.
- **Requires:** `verify_api_key` dependency

#### `POST /api/recalibrate_stops`
Trigger recalibration of SL/TP based on current volatility.

#### `POST /api/force_breakeven`
Force move SL to Break Even.

#### `POST /api/execute_manual_trade`
Execute a manual trade.
- **Body:** `{"symbol": "BTC", "action": "BUY", "price":..., "sl":..., "tp":...}`

---

### ⚙️ Settings & System

#### `GET /api/settings`
Get current sidebar settings.

#### `POST /api/settings`
Update settings (persisted to `bot_state.json`).

#### `GET /api/logs`
Get recent logs (last 50).

#### `GET /api/trade_history`
Get trade history from Hyperliquid (Cached 60s).

#### `POST /api/toggle_gamification`
Enable/Disable UI gamification.
