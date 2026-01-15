# Data Models & Persistence

## Overview
The project uses a **JSON-based persistence** mechanism via `app/core/state_manager.py` and `backend/api.py`. There is no traditional SQL database. State is stored in `bot_state.json`.

## Core Models

### 1. Bot State (`bot_state.json`)
Primary state file for the bot engine.
- **File:** `c:\Users\User\Desktop\novabot\bot_state.json`
- **Access:** `app/core/state_manager.py` (Write), `backend/api.py` (Read/Write Standalone)

#### Schema Structure:
```json
{
  "active_trade": {
    "symbol": "BTC",
    "side": "BUY",
    "entry": float,
    "sl": float,
    "tp": float,
    "size": float,
    "timestamp": "ISO8601",
    "ai_analysis": {...} // Optional
  },
  "trading_enabled": boolean,
  "is_running": boolean,
  "active_symbol": "BTC",
  "execution_mode": "Manual (Phantom) | Auto (Hyperliquid)",
  "risk_state": {
    "daily_pnl": float,
    "open_positions": int,
    "is_stop_mode": boolean,
    "stop_reason": string
  },
  "sidebar_settings": {
    "leverage": int,
    "size_value": float,
    "execution_mode": string,
    "scanner": {
      "enabled": boolean,
      "interval": int,
      "min_score": int
    }
  },
  "last_updated": "datetime string"
}
```

### 2. Trade History
- **Source:** Hyperliquid API (`get_trade_history`)
- **Cache:** In-memory `_trade_history_cache` in `api.py` (60s TTL)
- **Local CSV:** `trade_history.csv` (used for download endpoint/backup)

### 3. Token Metadata (`token_meta_cache.json`)
- **File:** `token_meta_cache.json`
- **Purpose:** Caches Hyperliquid exchange metadata (precision, max_leverage, universe).
- **TTL:** 24 hours (Checked in `backend/market_data.py` or `hyperliquid_service.py`)

## Pydantic Models (`backend/api.py`)
Used for API validation and serialization.

### `BotStatus`
```python
class BotStatus(BaseModel):
    is_running: bool
    trading_enabled: bool
    active_symbol: str
    execution_mode: str
    active_trade: Optional[Dict[str, Any]]
```
