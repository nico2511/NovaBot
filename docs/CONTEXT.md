# Project Context: Hyperliquid AI Trading Bot

## 1. Project Overview
This project is an advanced algorithmic trading bot designed for the **Hyperliquid** DEX. It features a hybrid architecture combining a **Python (FastAPI)** backend for trading logic and a **Next.js (React)** frontend for monitoring and control. The system integrates **Gemini AI** for market analysis and trade commentary, with a strong focus on autonomous resilience and user experience.

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
- **Dynamic Leverage Sync**: The bot strictly enforces the user-defined leverage (e.g., x3, x5) by sending a specific update command to Hyperliquid **immediately before** every manual trade execution. This prevents accidental "default leverage (x1/x20)" mishaps.
- **Smart Order Sizing**: Inputs in USDC are dynamically converted to token quantities based on real-time prices, with rounding logic that respects Hyperliquid's distinct `szDecimals` requirements for each asset.
- **Just-In-Time (JIT) Adoption**: Before alerting the user for a "Manual Validation" signal, the bot performs a final check against the exchange. If the position already exists, it silently adopts it instead of spamming the user.
- **Grace Period**: A 30-second buffer after trade entry prevents the "Position Vanished" safety check from accidentally closing trades before they appear on the exchange API.

### B. Strategy Engine & AI
- **Modular Design**: Strategies (e.g., `ScalpEmaRsi`, `W Patten`) are defined in `strategies/definitions.py`.
- **Regime Detection**: The engine first determines the market regime (TREND vs RANGE) via ADX/EMA.
- **AI Circuit Breaker**: To handle API rate limits (Gemini 429 Errors), a circuit breaker pauses AI requests for **10 minutes** upon detection, preventing log floods and ensuring quota recovery.
- **AI Analysis Cache**: Analyses are cached with symbol-specific keys (`position_analysis_BTC`) to ensure consistent display across the backend and frontend.

### C. Notifications & UX
- **Smart Silence**: The Opportunity Scanner is automatically muted when a trade is active to prevent distraction ("Marché Calme" alerts are suppressed).
- **Integrated Intelligence**: AI Risk Analysis (Risk Level, Reasoning, Recommendations) is displayed directly within the **Active Trade** card, eliminating the need to switch tabs.
- **Discord Alerts**: Real-time notifications for Entries, Exits, AI Risk warnings, and Bot Sync events.

## 4. Current Status (As of Dec 30, 2025)

### ✅ Completed & Stable
- **Execution**: Real trading is verified active with precise sizing and leverage enforcement.
- **AI Resilience**: Circuit Breaker active; "Ask AI" functionality restored; Analysis display fixed.
- **Notifications**: "Double Notification" issue resolved via JIT adoption; Scanner silence implemented.
- **Persistence**: Settings (Symbol, Leverage, Trading Mode) persist across restarts.
- **Interface**: Full dashboard with Chart, Logs, Manual Controls, and Integrated AI Analysis.

### 🚧 Recent Critical Fixes (Fixed)
- **Notification Spam**: Fixed by supressing Scanner alerts during active trades.
- **Leverage Mismatch**: Fixed by forced `update_leverage` call before execution.
- **AI Display**: Fixed by harmonizing cache keys between `main_nextjs.py` and `api.py`.

## 5. Roadmap & Remaining Tasks

### Short Term (Optimization)
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

# Restart Backend only (for logic updates)
npx pm2 restart hl-bot-engine

# Restart Frontend only (for UI updates)
npx pm2 restart hl-frontend

# View Logs
npx pm2 logs hl-bot-engine
```
