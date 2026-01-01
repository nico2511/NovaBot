# Project Context: Hyperliquid AI Trading Bot

## 1. Project Overview
This project is an advanced algorithmic trading bot designed for the **Hyperliquid** DEX. It features a hybrid architecture combining a **Python (FastAPI)** backend for trading logic and a **Next.js (React)** frontend for monitoring and control. The system integrates **OpenRouter (Llama 3.1 8B)** for professional market analysis, signal validation, and trade commentary, with a strong focus on autonomous resilience, AI-driven decision making, and user experience.

## 2. Technical Stack & Architecture

### Backend (Python)
- **Framework**: FastAPI (runs on port 8001).
- **Process Management**: `PM2` manages the `hl-bot-engine` process.
- **Data Handling**: `pandas` for OHLCV manipulation and indicator calculation.
- **Exchange Integration**: Custom `HyperliquidService` wrapping the `hyperliquid-python-sdk`.
- **AI Integration**: `OpenRouter` (meta-llama/llama-3.1-8b-instruct) for professional market analysis, signal validation, and risk assessment.
- **State Management**: JSON-based atomic persistence (`bot_state.json`) for crash recovery.

### Frontend (Next.js)
- **Framework**: Next.js 14 (App Router).
- **UI Library**: Tailwind CSS, Lucide Icons.
- **Communication**: Polling based API calls to the backend (Status, Settings, Logs).

## 3. Key Technical Decisions & Features

### A. Trade Execution & Safety
- **Retry Logic with Exponential Backoff**: Orders are retried up to 3 times with exponential backoff (1s, 2s, 4s) to handle transient network issues.
- **Position Verification**: After order submission, the bot waits 2 seconds and verifies the position exists on Hyperliquid before considering the trade successful.
- **Dynamic Leverage Sync**: The bot strictly enforces the user-defined leverage (e.g., x3, x5) by sending a specific update command to Hyperliquid **immediately before** every manual trade execution.
- **Smart Order Sizing**: Inputs in USDC are dynamically converted to token quantities based on real-time prices, with rounding logic that respects Hyperliquid's distinct `szDecimals` requirements for each asset.
- **Just-In-Time (JIT) Adoption**: Before alerting the user for a "Manual Validation" signal, the bot performs a final check against the exchange. If the position already exists, it silently adopts it instead of spamming the user.
- **Grace Period**: A 30-second buffer after trade entry prevents the "Position Vanished" safety check from accidentally closing trades before they appear on the exchange API.
- **Force Close on Desync**: Manual close button now clears bot state even if Hyperliquid returns "No position found", preventing phantom trade issues.

### B. Strategy Engine & AI

#### Professional AI Analysis
- **Comprehensive Market Context**: AI receives 15+ data points including RSI, ATR, EMAs (20/50/200), volume ratios, swing levels, volatility percentiles, and position metrics.
- **Signal Validation**: Every trading signal is validated by AI before execution. The AI can approve, reject, or suggest adjustments to entry/SL/TP based on:
  - Signal alignment with market bias and technical indicators
  - Entry price logic (support/resistance, EMA levels)
  - SL/TP placement based on market structure
  - Volume confirmation
  - RSI extremes
  - Overall risk/reward favorability
- **Position Risk Analysis**: Active trades are analyzed with professional prompts including:
  - Current PnL and time in trade
  - Technical indicator states (RSI overbought/oversold, MACD, Bollinger Bands)
  - Distance from key EMAs
  - Support/resistance levels
  - Volume trends
  - Risk score (0-100) with reasoning
  - Optimal SL/TP suggestions based on technical levels

#### Strategy Execution
- **Modular Design**: Strategies (e.g., `ScalpEmaRsi`, `InstitutionalScalp`) are defined in `strategies/definitions.py`.
- **Regime Detection**: The engine first determines the market regime (TREND vs RANGE) via ADX/EMA.
- **AI Analysis Cache**: Analyses are cached with symbol-specific keys (`position_analysis_BTC`) to ensure consistent display across the backend and frontend.
- **30s Loop Interval**: Trading loop sleeps for 30 seconds between iterations to reduce API calls and prevent rate limiting.

### C. Notifications & UX
- **Smart Silence**: The Opportunity Scanner is automatically muted when a trade is active to prevent distraction ("Marché Calme" alerts are suppressed).
- **Integrated Intelligence**: AI Risk Analysis (Risk Level, Reasoning, Recommendations) is displayed directly within the **Active Trade** card.
- **Discord Alerts**: Real-time notifications for Entries, Exits, AI Risk warnings, and Bot Sync events.
- **Clarified Controls**: Settings buttons are now clearly separated:
  - 🤖 **STOP/START ENGINE**: Controls the trading loop
  - 💰 **ENABLE/DISABLE TRADING**: Authorizes trade execution
- **Conditional UI**: ActiveTrade component is hidden when no trade exists, reducing visual clutter.

## 4. Current Status (As of Dec 31, 2025)

### ✅ Completed & Stable
- **Execution**: Real trading is verified active with precise sizing, leverage enforcement, retry logic, and position verification.
- **AI Integration**: OpenRouter (Llama 3.1 8B) provides professional analysis with comprehensive market context.
- **Signal Validation**: AI approves/rejects every signal before execution with detailed reasoning.
- **Notifications**: "Double Notification" issue resolved via JIT adoption; Scanner silence implemented.
- **Persistence**: Settings (Symbol, Leverage, Trading Mode) persist across restarts.
- **Interface**: Full dashboard with Chart, Logs, Manual Controls, and Integrated AI Analysis.
- **Robustness**: Type-safe AI context preparation, force close on desync, retry logic with backoff.

### 🚧 Recent Major Improvements (Dec 31, 2025)

#### AI Enhancements
- **Professional Prompts**: Structured prompts with role definition, comprehensive context sections, and clear output requirements.
- **Rich Market Data**: AI receives RSI, ATR, EMAs, volume ratios, swing levels, volatility percentiles, PnL, time in trade, R/R ratios.
- **Signal Validation**: Pre-execution AI validation with approval/rejection logic and suggested adjustments.
- **Position Analysis**: Professional risk assessment with technical level-based SL/TP suggestions.

#### Execution Reliability
- **Retry Mechanism**: 3 attempts with exponential backoff (1s, 2s, 4s).
- **Position Verification**: 2-second wait + position check after order submission.
- **Error Handling**: Detailed logging at each step with clear error messages.

#### UI/UX Improvements
- **Clarified Settings**: Separated engine control from trading execution with clear labels.
- **Conditional Display**: ActiveTrade hidden when no trade exists.
- **Force Close**: Manual close clears bot state even on Hyperliquid errors.

## 5. Recent Commits (Last 5)

### 1. feat(trading): Add retry logic, timeout, and position verification to order execution
**Commit**: `6370579` | **Date**: 2025-12-31
- Added retry mechanism (3 attempts) with exponential backoff
- Implemented position verification after order submission
- Enhanced error handling with detailed logging
- **Files**: `app/services/hyperliquid_service.py` (+65, -27 lines)

### 2. fix(ai): Handle position_data type errors in _prepare_ai_context
**Commit**: `f7d5ed8` | **Date**: 2025-12-31
- Fixed type errors when extracting position data
- Added robust type checking with try/except blocks
- Handles both dict and direct value formats
- **Files**: `main_nextjs.py` (+26, -7 lines)

### 3. fix(ui): Clarify Settings buttons - STOP/START ENGINE vs ENABLE/DISABLE TRADING
**Commit**: `384aeed` | **Date**: 2025-12-31
- Renamed buttons for clarity (ENGINE vs TRADING)
- Separated controls into distinct sections
- Improved visual hierarchy
- **Files**: `frontend/components/Settings.tsx` (+32, -33 lines)

### 4. fix(ui): Hide ActiveTrade component when no trade exists
**Commit**: `9861f7a` | **Date**: 2025-12-31
- Added early return if no active trade
- Reduces visual clutter when waiting for signals
- **Files**: `frontend/components/ActiveTrade.tsx` (+5 lines)

### 5. feat(ai): Add AI signal validation before trade execution with approval/rejection logic
**Commit**: `de88359` | **Date**: 2025-12-31
- Implemented `validate_signal()` method in gemini_service
- Integrated AI validation into trading loop
- AI can approve, reject, or adjust signals
- Rejected signals are logged with reasoning
- **Files**: `app/services/gemini_service.py` (+70 lines), `main_nextjs.py` (+79 lines)

## 6. Roadmap & Remaining Tasks

### Short Term (Optimization)
- [ ] **Dynamic Position Sizing**: Implement "% of Balance" sizing (currently falls back to Fixed USDC).
- [ ] **Backtesting UI**: Integrate the backtest engine results directly into the Next.js dashboard.
- [ ] **Double Scan Fix**: Implement lock mechanism to prevent concurrent periodic and initial scans.

### Long Term (Features)
- [ ] **Grid Strategy**: Add a grid trading module for Range markets.
- [ ] **Copy Trading**: Architecture allows for following a master wallet (future expansion).
- [ ] **Multi-Symbol Support**: Currently single-symbol focus; extending to multi-symbol monitoring would require refactoring `main_nextjs.py` loops.
- [ ] **AI Model Comparison**: Test different models (Claude, GPT-4) for analysis quality.

## 7. How to Run
```bash
# Start everything
npx pm2 start ecosystem.config.js

# Restart Backend only (for logic updates)
npx pm2 restart hl-bot-engine

# Restart Frontend only (for UI updates)
npx pm2 restart hl-frontend

# View Logs
npx pm2 logs hl-bot-engine

# Pull latest changes and restart
git pull
npx pm2 restart hl-bot-engine
```

## 8. AI Integration Details

### OpenRouter Configuration
- **Provider**: OpenRouter
- **Model**: `meta-llama/llama-3.1-8b-instruct`
- **API Key**: Configured via `OPENROUTER_API_KEY` environment variable
- **Fallback**: Gemini (if OpenRouter fails)

### AI Functions
1. **`validate_signal()`**: Pre-execution signal validation with approval/rejection
2. **`analyze_position_risk()`**: Professional risk assessment for active trades
3. **`_prepare_ai_context()`**: Comprehensive market data collection helper

### Cache Strategy
- Signal validation: 1 minute TTL (time-sensitive)
- Position analysis: 5 minutes TTL
- Symbol-specific keys for consistency
