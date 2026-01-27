# API Contracts - Backend

| Method | Endpoint | Description | Auth | Status |
| :--- | :--- | :--- | :--- | :--- |
| **GET** | `/api/status` | Get current bot status (positions, PnL, logs) | No | Active |
| **POST** | `/api/engine/start` | Start the trading engine | No | Active |
| **POST** | `/api/engine/stop` | Stop the trading engine | No | Active |
| **POST** | `/api/engine/restart` | Restart the trading engine | No | Active |
| **POST** | `/api/engine/panic` | **PANIC**: Stop engine and close all positions | No | Active |
| **POST** | `/api/trading/enable` | Enable live trading execution | No | Active |
| **POST** | `/api/trading/disable` | Disable live trading execution | No | Active |
| **POST** | `/api/switch_symbol` | Switch active trading symbol | No | Active |
| **GET** | `/api/settings/global` | Get global bot settings | No | Active |
| **POST** | `/api/settings/global` | Update global bot settings | No | Active |
| **GET** | `/api/settings/scanner` | Get scanner settings | No | Active |
| **GET** | `/api/analysis/` | Get multi-timeframe market analysis | No | Active |
| **GET** | `/api/scanner/opportunities` | Get top trading opportunities | No | Disabled* |
| **GET** | `/api/scanner/best` | Get single best asset | No | Disabled* |

_*Scanner routes appear to be commented out in `api.py` registration._

## Endpoint Details

### Status & Control

#### `GET /api/status`
Returns the full state of the bot.
**Response (`BotStatus`):**
```json
{
  "is_running": true,
  "trading_enabled": true,
  "active_symbol": "BTC",
  "active_trade": null,
  "daily_pnl": 150.50,
  "active_positions": 1,
  "margin_usage": 12.5,
  "market_analysis": { ... },
  "open_positions": [ ... ]
}
```

#### `POST /api/switch_symbol`
**Body:**
```json
{ "symbol": "ETH" }
```

### Analysis
#### `GET /api/analysis/`
Returns market sentiment and position advice.
**Response:**
```json
{
  "symbol": "BTC",
  "market_sentiment": { "1h": "BULLISH", ... },
  "positions_analysis": [ ... ],
  "global_advice": "HOLD"
}
```
