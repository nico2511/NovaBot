# Data Models - NovaBot

This document details the data architecture and persistence layer of NovaBot.

## Persistence Layer
The bot's state is persisted in a central JSON file: `bot_state.json`.

### `StateManager` (`app/core/state_manager.py`)
- **Atomic Operations**: Uses a temp file (`.tmp`) and backup (`.bak`) to ensure state is never corrupted during a crash.
- **Auto-Sync**: The bot automatically saves its state when critical parameters change (e.g., enabling trading, opening a position).
- **Migration Logic**: Handles legacy settings conversion (e.g., migrating single-value AI confidence to tri-level thresholds).

---

## 📄 `bot_state.json` Schema

### `active_trade`
Stores details of the currently open trade.
- `symbol`: e.g., "BTC", "ETH".
- `side`: "BUY" or "SELL".
- `entry`: Entry price.
- `size`: Quantity in base asset.
- `sl` / `tp`: Stop-Loss and Take-Profit prices.
- `oid`: Order ID (or "external_position" if adopted).
- `status`: e.g., "OPEN", "OPEN (ADOPTED)".

### `risk_state`
Cumulative session risk metrics.
- `daily_pnl`: Current session profit/loss.
- `open_positions`: Number of currently open positions.
- `is_stop_mode`: True if the bot has hit a global stop-loss.

### `scanner_settings`
Configuration for the market scanner.
- `enabled`: Global toggle.
- `interval`: Time between scans (minutes).
- `min_score`: Minimum threshold for an opportunity to be valid.
- `gamification_enabled`: Restricts asset universe based on equity level.

### `global_settings`
High-level bot behavior configuration.
- `max_positions`: Limit on simultaneous trades.
- `daily_stop_loss`: Maximum dollar loss before stopping.
- `bot_persona`: LLM persona for analysis (e.g., "Conservative Scalper").
- `ai_thresholds`: `{ "high": 101, "medium": 55, "low": 35 }`
- `default_leverage`: Leverage to use for new trades.

---

## 🔧 Other Data Files
- `strategies.json`: Central registry of all trading strategies and their parameters.
- `token_meta_cache.json`: Cache of Hyperliquid token metadata (decimals, full names).
- `daily_pnl_snapshot.json`: Historical daily performance data.
