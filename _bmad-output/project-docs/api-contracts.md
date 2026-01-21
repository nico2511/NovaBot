# API Contracts - NovaBot

This document provides a comprehensive catalog of the REST API endpoints exposed by the NovaBot backend.

## Base URL
The API is served by default on `http://localhost:8001`.

## Security
- **Header**: `X-API-Key`
- **Mechanism**: API Key validation is enforced for sensitive operations (via `backend/api_optimizations.py`).

---

## 🤖 Engine Control
Endpoints for managing the core trading engine.

### `GET /api/status`
Retrieves the current status of the bot, including open positions, PnL, and health metrics.
- **Response Model**: `BotStatus`
- **Key Fields**: `is_running`, `trading_enabled`, `daily_pnl`, `active_positions`, `open_positions`, `margin_usage`.

### `POST /api/engine/start`
Starts the trading engine.
- **Payload**: None
- **Response**: `{"status": "started", "message": "..."}`

### `POST /api/engine/stop`
Stops the trading engine.
- **Payload**: None
- **Response**: `{"status": "stopped", "message": "..."}`

### `POST /api/engine/panic`
🚨 **Panic Button**: Immediately stops the engine and attempts to close all open positions on the exchange.
- **Payload**: None
- **Response**: Summary of closure attempts per symbol.

---

## ⚙️ Settings Management
Endpoints for configuring bot behavior and risk parameters.

### `GET /api/settings/global`
Retrieves global settings (personas, risk profiles, leverage).
- **Response Model**: `GlobalSettingsModel`

### `POST /api/settings/global`
Updates global settings and syncs leverage to the exchange for the active symbol.
- **Payload**: `GlobalSettingsModel` json.

### `GET /api/settings/scanner`
Retrieves scanner configuration.
- **Response Model**: `ScannerSettingsModel`

---

## 🕵️ Scanner Opportunities
Provided by `backend/routes/scanner.py`.

### `GET /api/scanner/opportunities`
Scans the market for trading opportunities based on configured strategies.
- **Query Params**: `top_n` (default: 10)
- **Features**: Includes gamification filtering (restricts assets based on account equity).

### `GET /api/scanner/best`
Identifies the single best asset to trade right now.

---

## 📊 Market Data
Direct proxy/utility endpoints for market information.

### `GET /api/market/candles`
Fetches historical candles formatted for charts.
- **Params**: `symbol`, `interval` (default: 15m), `limit`.
