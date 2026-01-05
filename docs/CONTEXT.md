# Project Context: Hyperliquid AI Trading Bot

## 1. Project Overview
This project is an advanced algorithmic trading bot designed for the **Hyperliquid** DEX. It features a hybrid architecture combining a **Python (FastAPI)** backend for trading logic and a **Next.js (React)** frontend for monitoring and control. The system integrates **OpenRouter (Llama 3.1 8B)** for professional market analysis, signal validation, and trade commentary, with a strong focus on autonomous resilience, AI-driven decision making, and user experience.

**Current Status:** 🟢 **Production Ready (Beta)**
**Last Critical Update:** Jan 5, 2026 (Phase 2 Optimization)

---

## 2. Technical Stack & Architecture

### Backend (Python)
- **Framework**: FastAPI (runs on port 8001).
- **Process Management**: `PM2` manages the `hl-bot-engine` process.
- **Data Handling**: `pandas` for OHLCV manipulation and indicator calculation.
- **Exchange Integration**: Custom `HyperliquidService` wrapping the `hyperliquid-python-sdk`.
- **AI Integration**: `OpenRouter` (meta-llama/llama-3.1-8b-instruct) for professional market analysis.
- **State Management**: JSON-based atomic persistence (`bot_state.json`) for crash recovery.

### Frontend (Next.js)
- **Framework**: Next.js 14 (App Router).
- **UI Library**: Tailwind CSS, Lucide Icons.
- **Communication**: Polling based API calls to the backend (Status, Settings, Logs).

---

## 3. Key Technical Decisions & Features

### A. Trade Execution & Safety (Robustness)
- **Zero Repainting Protocol**: All strategies strictly use `iloc[-2]` (last completed candle) for decision making. No look-ahead bias.
- **"Funnel" Strategy Architecture**: Every strategy follows a 3-step validation: `Regime Filter (ADX)` -> `Setup` -> `Trigger`.
- **Robust Order Parsing**: Custom parser handles both Dict and String statuses from Hyperliquid to prevent "Phantom Positions".
- **API Rate Limit Handling**: Exponential Backoff retry logic (1s, 2s, 4s) to gracefully handle HTTP 429 errors.
- **Position Verification**: Double-check with exchange API (`has_position`) after every order fill.
- **Log Rotation**: Automated rotation (10MB / 2 days) to prevent disk saturation.

### B. Strategy Engine & AI
#### Professional AI Analysis
- **Strategic Validation**: AI reviews every entry signal against 15+ datapoints (Market bias, Volume, RSI, Volatility).
- **Risk Assessment**: Real-time analysis of active trades with "Hold/Close" recommendations based on technical structure.

#### Quantitative Standards (The "Senior Quant" Standard)
- **Regime Filters**:
  - **Trend Strategies**: Require `ADX > 20/25` (e.g., `scalp_ema_rsi`, `bull_flag`).
  - **Range/Reversal Strategies**: Require `ADX < 25` OR `ADX > 15` (to avoid dead markets) (e.g., `institutional_scalp`, `double_top`).
- **Volume Validation**: All chart patterns require Volume > SMA(20) on the signal candle.
- **Event-Based Triggers**: Elimination of "State" logic (e.g., "is aligned") in favor of "Event" logic (e.g., "crossover") to prevent signal spam.

### C. Notifications & UX
- **Real-time Dashboard**: Live PnL, Active Strategy, AI Thinking process.
- **Discord Alerts**: Instant notifications for Trades, AI Warnings, and System Events.
- **Config Limits**: UI-based control for Max Leverage, Position Size, and Margin Type.

---

## 4. Current Status (As of Jan 5, 2026)

### ✅ Completed & Stable
- **Core Engine**: Stable loop (10s interval) with robust error handling.
- **Strategy Suite**: 11 Strategies fully optimized and standardized (Zero Repainting).
- **Safety Nets**: Kill Switches (ADX breakout), Stop Loss (Hard + Soft), Take Profit.
- **Logging**: Clean, rotated logs with clear emojis for event tracking.

### 🚧 Recent Major Improvements (Phase 2 - Jan 5, 2026)

#### 1. Strategic Core Rewrite
- **Batch Fix**: Corrected `institutional_scalp`, `bull_flag`, and patterns to use strict `iloc[-2]` logic.
- **Regime Injection**: Added ADX Guard Clauses to ALL 11 strategies.
- **Spam Kill**: Refactored `scalp_ema_rsi` to Event-Based logic.

#### 2. Critical Bug Fixes
- **Phantom Position**: Fixed `AttributeError` on order status parsing that caused the bot to lose track of trades.
- **Rate Limits**: Implemented backoff logic to solve HTTP 429 errors.

#### 3. Protocol Establishment
- Created `docs/strategy_standards.md`: The "Bible" for adding new strategies.

---

## 5. Recent Commits (Last 5)

### 1. docs: Add strategy_standards.md protocol
**Commit**: `Jan 5, 2026`
- Established strict "Funnel" and "Anti-Repainting" protocols for the project.

### 2. fix(repainting): Standardize rsi_ping_pong and smart_mean_reversion
**Commit**: `Jan 5, 2026`
- Converted last 2 strategies to `iloc[-2]` standards.
- 100% of strategies are now compliant.

### 3. fix(batch): Fix repainting + add ADX regime filters to 5 strategies
**Commit**: `Jan 5, 2026`
- Batch update for `institutional_scalp`, `bull_flag`, `double_top`, `double_bottom`, `head_shoulders`.
- Added Volume Spike filters on confirmed candles.

### 4. fix(critical): Change ScalpEmaRsi to event-based logic + PM2 logrotate
**Commit**: `Jan 5, 2026`
- Solved signal spamming issue.
- Added log rotation scripts.

### 5. fix(api): Add exponential backoff for rate limits
**Commit**: `Jan 5, 2026`
- Solved HTTP 429 crashes with retry logic.

---

## 6. How to Run
```bash
# Start everything
npx pm2 start ecosystem.config.js

# View Logs (Rotated)
npx pm2 logs hl-bot-engine

# Pull latest changes and restart
git pull
npx pm2 restart hl-bot-engine
```
