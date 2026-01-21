# Architecture: Bot Core Engine - NovaBot

This document describes the core logic and architectural flow of the NovaBot trading engine.

## High-Level Architecture
The bot is built around a central hub, the `BotContext`, which orchestrates several specialized services:

- **State Management**: `StateManager` ensures persistence of all settings and active trade data.
- **Risk Management**: `RiskManager` defines the safety boundaries (Daily SL, Max Positions).
- **Strategy Engine**: `StrategyEngine` manages the various trading strategies.
- **Service Layer**: Handles communication with Hyperliquid (execution), Discord (alerts), and AI Providers (validation).

---

## ⚡ Execution Flow: Atomic Trades
NovaBot emphasizes **atomicity** to prevent "orphan orders" or inconsistent states.

### Entry Flow (`execute_entry_atomically`)
1. **Veto Check**: Brief technical sanity check (RSI/ADX/Volume).
2. **Quota Check**: Verification against `max_positions`.
3. **Cancellation**: Cleanup of any pending orders for the symbol.
4. **Execution**: Concurrent submission of Limit/Market order with SL and TP.
5. **Verification**: Position polling for 5 seconds to confirm fill.
6. **Logging**: Full metadata snapshot (including entry indicators) saved to state.

### Exit Flow (`execute_exit_atomically`)
1. **Market Close**: Immediate submission of a closing order.
2. **Verification**: Confirmation that position size is 0.
3. **Cleanup**: Cancellation of remaining SL/TP orders on exchange.
4. **Recording**: Detailed trade statistics saved to `TradeRecorder`.

---

## 🛡️ Risk & Management
- **Smart Break-Even**: Automatically moves SL to entry + 0.2% profit after 60% of the target is reached.
- **Trailing Stops**: Locks in percentage of gains as the trade progresses toward TP.
- **External Sync**: Periodically polls the exchange to detect if a position was closed by SL/TP orders on the server-side, ensuring the bot's local state remains in sync.

---

## 🧠 AI Validation Context
When requesting AI validation, the bot provides a rich "Dynamic Context":
- **Trend Indicators**: ADX, EMA alignment, EMA slopes.
- **Volatility**: ATR and Bollinger Band width.
- **Volume**: Current vs 50-period average ratio.
- **Structure**: Fibonacci levels and Swing High/Low detection.
