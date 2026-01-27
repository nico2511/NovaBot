# Data Models - Backend

## Core Domain Models

### `BotStatus`
Represents the real-time snapshot of the bot's health and activity. Used in API responses.

| Field | Type | Description |
| :--- | :--- | :--- |
| `is_running` | `bool` | Master switch state of the engine |
| `trading_enabled` | `bool` | Whether new trades can be opened |
| `active_symbol` | `str` | Currently traded symbol (e.g., "BTC") |
| `daily_pnl` | `float` | Realized + Unrealized PnL for the day |
| `active_positions` | `int` | Count of open positions |
| `margin_usage` | `float` | Estimated margin usage percentage |
| `market_analysis` | `dict` | Nested analysis data (sentiment, advice) |
| `open_positions` | `list` | List of position details from Hyperliquid |

### `GlobalSettingsModel`
Configuration for bot behavior, persisted in `user_settings.json`.

| Field | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `max_positions` | `int` | `1` | Max concurrent positions |
| `daily_stop_loss` | `float` | `50.0` | Max daily loss before hard stop |
| `trading_timeframe` | `str` | `"15m"` | Candle timeframe for analysis |
| `bot_persona` | `str` | `"Conservative Scalper"` | AI personality profile |
| `risk_profile` | `str` | `"Capital Preservation"` | Risk management strictness |
| `default_leverage` | `int` | `1` | Leverage applied to trades |

## Persistence

### `BotState` (Internal Class)
Manages in-memory state and persistence to `bot_state.json`.

**File:** `bot_state.json`
**Key Fields:**
- `is_running`
- `trading_enabled`
- `active_symbol`
- `notifications`
- `operations`
- `risk_defaults`
- `ai_config`

This file serves as the recovery point if the bot restarts.
