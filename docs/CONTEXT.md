# Project Context: Hyperliquid AI Trading Bot

## 1. Project Overview
This project is an advanced algorithmic trading bot designed for the **Hyperliquid** DEX. It features a hybrid architecture combining a **Python (FastAPI)** backend for trading logic and a **Next.js (React)** frontend for monitoring and control. The system integrates **OpenRouter (Llama 3.1 8B)** for professional market analysis, signal validation, and trade commentary, with a strong focus on autonomous resilience, AI-driven decision making, and user experience.

**Current Status:** 🟢 **Production Ready (v2.1)**
**Last Critical Update:** Jan 10, 2026 (Strategy Optimization & Active Sync)

---

## 2. Technical Stack & Architecture

### Backend (Python)
- **Framework**: FastAPI (runs on port 8001).
- **Process Management**: `PM2` manages the `hl-bot-engine` process.
- **Data Handling**: `pandas` and `pandas_ta` (pure python implementation) for OHLCV manipulation.
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
- **Zero Repainting Protocol**: All strategies strictly use `iloc[-2]` (last completed candle) for decision making.
- **"Funnel" Strategy Architecture**: Every strategy follows a 3-step validation: `Regime Filter (ADX)` -> `Setup` -> `Trigger`.
- **Force Sync Protocol**: Manual "Push" mechanism to resynchronize bot state with exchange and trigger immediate AI analysis.
- **Atomic Position Tracking**: Automated adoption of "Orphan Positions" (trades opened while bot was off) into memory.

### B. Strategy Engine & AI
#### Professional AI Analysis
- **Strategic Validation**: AI reviews every entry signal against 15+ datapoints (Market bias, Volume, RSI, Volatility).
- **Risk Assessment**: Real-time analysis of active trades with "Hold/Close" recommendations.

#### Quantitative Standards (The "Senior Quant" Standard)
- **Smart Trailing Stop**:
  - **> 40%**: Break Even (+0.3%).
  - **> 60%**: Secure 20% Profit.
  - **> 75%**: Secure 40% Profit.
- **Regime Filters**:
  - **Trend**: ADX > 25 (Strict) for momentum based strategies.
  - **Range**: ADX < 25 + Bollinger Band "Kill Zone" logic.
- **Volume Validation**: Volume > 1.5x SMA(50) for trend entries.

### C. Notifications & UX
- **Real-time Dashboard**: Live PnL, Active Strategy, AI Thinking process.
- **Discord Alerts**: Instant notifications for Trades, AI Warnings, and System Events.
- **Interactive Control**: "Force Sync" button on frontend to handle state desynchronization manually.

---

## 4. Current Status (As of Jan 10, 2026)

### ✅ Completed & Stable
- **Core Engine**: Stable loop (10s interval) with robust error handling.
- **Strategy Suite**: 10 Strategies optimized (Bollinger V2 merged).
- **Safety Nets**: Master Trailing Stop Logic (Multi-tier), Kill Switches.
- **Logging**: Clean, rotated logs with clear emojis.

### 🚧 Recent Major Improvements (Phase 4 - Jan 10, 2026)

#### 1. Architecture Cleanup & Organization
- **Orphaned File Analysis**: Identified and organized 12+ orphaned files.
- **Project Structure**: Created `scripts/`, `tests/`, and `.archived/` directories.
- **Consolidation**: Merged orphaned `api_trades_hyperliquid.py` into main `backend/api.py`.

#### 2. Critical History & Logging Fixes
- **Hyperliquid Trade History**: Repaired `/api/trades/hyperliquid` endpoint.
- **Frontend Networking**: 
  - Fixed API Port Mismatch (Frontend 8000 -> Backend 8001).
  - Bypassed Next.js Proxy for critical endpoints (Direct Call to 8001) to solve Timeouts.
- **Service Logging**: Implemented `LogBridge` to correctly route WebSocket logs to UI.

#### 3. Bug Fixes
- **TypeScript & Build**: Fixed `Trade` interface (missing `size`) and Component syntax errors.
- **Port Configuration**: Aligned `.env.local` with actual Uvicorn port.

---

## 5. Recent Commits (Last 5)

### 1. fix(history): Repair Trade History Tab & Build
**Commit**: `Jan 10, 2026`
- Integrated orphaned history endpoint into `api.py`.
- Fixed Frontend Port (8001) and bypassed proxy for stability.
- Fixed TypeScript types and Component syntax.

### 2. refactor(cleanup): Organize orphaned files
**Commit**: `Jan 10, 2026`
- Moved scripts to `scripts/` and tests to `tests/`.
- Archived unused strategies.

### 3. fix(logging): Repair WebSocket Logging Bridge
**Commit**: `Jan 10, 2026`
- Implementing `LogBridge` to fix missing UI logs from WebSocket service.
- Fixed infinite recursion in logger fallback.

### 4. feat(trailing): Add 60% intermediate profit securing threshold
**Commit**: `Jan 10, 2026`
- Active trades now secure 20% of profit when reaching 60% of target.

### 5. fix(imports): Cleanup deleted V2 strategy references
**Commit**: `Jan 10, 2026`
- Removed `strategies.bollinger_bounce_v2` imports from `engine.py`.

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
