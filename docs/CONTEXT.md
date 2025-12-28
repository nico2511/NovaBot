# Project Context: Hyperliquid AI Trading Bot

## 1. Project Overview
This project is an advanced algorithmic trading bot designed for the **Hyperliquid** DEX. It features a hybrid architecture combining a **Python (FastAPI)** backend for trading logic and a **Next.js (React)** frontend for monitoring and control. The system integrates **Gemini AI** for market analysis and trade commentary.

## 2. Technical Stack & Architecture

### Backend (Python)
- **Framework**: FastAPI (runs on port 8001).
- **Process Management**: `PM2` manages the `hl-bot-engine` process.
- **Data Handling**: `pandas` for OHLCV manipulation and indicator calculation.
- **Exchange Integration**: Custom `HyperliquidService` wrapping the `hyperliquid-python-sdk`.
- **AI Integration**: `google-generativeai` for market regime analysis and signal checks.
- **State Management**: JSON-based atomic persistence (`bot_state.json`) for crash recovery.

### Frontend (Next.js)
- **Framework**: Next.js 14 (App Router).
- **UI Library**: Tailwind CSS, Lucide Icons.
- **Communication**: Polling based API calls to the backend (Status, Settings, Logs).

## 3. Key Technical Decisions & Features

### A. Trade Execution & Safety
- **Market Orders**: Chosen for immediate execution to avoid potential fill issues with unstable limit orders in fast markets.
- **Dynamic Precision**: implemented `_get_precision` to fetch `szDecimals` and `maxPriceDecimals` from exchange metadata. This prevents "dust" issues and "invalid size" rejections.
- **Grace Period**: A 30-second buffer after trade entry prevents the "Position Vanished" safety check from accidentally closing trades before they appear on the exchange API.
- **Sync-First Architecture**: The bot synchronizes its leverage (forces x5, for example) and active position with the exchange immediately upon startup.

### B. Strategy Engine
- **Modular Design**: Strategies (e.g., `ScalpEmaRsi`, `W Patten`) are defined in `strategies/definitions.py`.
- **Regime Detection**: The engine first determines the market regime (TREND vs RANGE) via ADX/EMA before selecting valid strategies.
- **AI Validation**: Signals are optionally cross-checked by Gemini AI for "sane" reasoning before execution.

### C. Resilience
- **Ghost Position Cleanup**: Strict logic to detect and close "phantom" positions (state says open, exchange says closed).
- **Discord Alerts**: Real-time notifications for Entries, Exits, AI Risk warnings, and Bot Sync events.

## 4. Current Status (As of Dec 28, 2025)

### ✅ Completed & Stable
- **Execution**: Real trading is verified active.
- **Precision**: Dynamic decimal handling is live.
- **Persistence**: Settings (Symbol, Leverage, Trading Mode) persist across restarts.
- **AI**: Integration active (despite library deprecation warnings, it works).
- **Interface**: Full dashboard with Chart, Logs, and Manual Controls ("Close Trade", "Switch Symbol").

### 🚧 Recent Critical Fixes (Fixed)
- **False SL Hit**: Caused by "dust" residues -> Fixed by precision upgrade.
- **Leverage Mismatch**: Fixed by forced sync on startup.
- **Silent Rejections**: Added detailed logging for Risk Manager rejections.

## 5. Roadmap & Remaining Tasks

### Short Term (Optimization)
- [ ] **AI Cache Optimization**: Reduce API calls by caching AI analysis for 5-15 minutes if price hasn't moved significantly.
- [ ] **Dynamic Position Sizing**: Implement "% of Balance" sizing (currently falls back to Fixed USDC).
- [ ] **Backtesting UI**: Integrate the backtest engine results directly into the Next.js dashboard.

### Long Term (Features)
- [ ] **Grid Strategy**: Add a grid trading module for Range markets.
- [ ] **Copy Trading**: Architecture allows for following a master wallet (future expansion).
- [ ] **Multi-Symbol Support**: Currently single-symbol focus; extending to multi-symbol monitoring would require refactoring `main_nextjs.py` loops.

## 6. How to Run
```bash
# Start everything
npx pm2 start ecosystem.config.js

# Restart Backend only
npx pm2 restart hl-bot-engine

# View Logs
npx pm2 logs hl-bot-engine
```
