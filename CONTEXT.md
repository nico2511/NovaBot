# Project Context: Hyperliquid AI Trading Bot

## 1. Project Overview
This project is an advanced algorithmic trading bot designed for the **Hyperliquid** DEX. It features a hybrid architecture combining a **Python (FastAPI)** backend for trading logic, a **Next.js (React)** frontend for monitoring, and **Gemini AI** for market analysis.

## 2. Technical Stack & Architecture

### Backend (Python)
- **Framework**: FastAPI (Port 8001).
- **Engine**: `hl-bot-engine` process managed by PM2.
- **Core Libs**: `pandas` (Data), `hyperliquid-python-sdk` (Exchange), `google-generativeai` (AI).
- **Persistence**: Atomic JSON storage (`bot_state.json`) for crash recovery.

### Frontend (Next.js)
- **Framework**: Next.js 14 App Router (Port 3000).
- **UI**: Tailwind CSS, Lucide Icons, Real-time Dashboard.

## 3. Developer Resources & Documentation (in `/docs`)

For a developer or AI agent resuming work, these files are the **Source of Truth**:

- **`SETUP_GUIDE.md`**: 📥 **START HERE**. Step-by-step guide to clone, install, and configure the bot on a fresh machine (Linux/Mac).
- **`STRATEGIES.md`**: 🧠 Technical breakdown of active Python strategies (Logic, Indicators, Signals).
- **`BACKTESTING.md`**: 📊 Methodology and historical results of the Python strategies.
- **`SECURITY_WARNING.md`**: 🔒 Critical security rules (Private Keys handling, `.env` exclusions).
- **`THEME.md`**: 🎨 UI Design System reference (Colors, Components).

## 4. Strategy Development Workflow

We follow a rigorous **Prototype -> Implement -> Verify** workflow:

### A. Prototyping (TradingView / Pine Script)
All strategies are first coded and visually backtested on TradingView to validate the logic.
The `tradingview/` folder contains these prototypes:

| Script File | Strategy | Description |
|:---|:---|:---|
| `scalp_ema_v3.pine` | **ScalpEMA** | Quick scalps based on EMA crossovers + RSI confirmation. (Active in Python) |
| `rsi_reversal_v3.pine` | **RSI Reversal** | Counter-trend strategy for overbought/oversold conditions. |
| `golden_cross_v2.pine` | **Golden Cross** | Typical 50/200 MA trend following. |
| `bollinger_breakout_v2.pine` | **Bollinger** | Volatility breakout logic. |
| `head_shoulders.pine` | **Chart Patterns** | Pattern recognition prototype (Head & Shoulders). |
| `double_top_bottom.pine` | **Chart Patterns** | Pattern recognition prototype (Double Top/Bottom). |

### B. Implementation (Python)
Validated logic is ported to `strategies/definitions.py`.
- **Indicators**: Calculated using `pandas` (Vectorized) for performance.
- **Logic**: Implemented in `check_buy_signal` / `check_sell_signal`.

### C. Execution (Hyperliquid)
Real trading handles complexities not present in backtests:
- **Precision**: Dynamic rounding based on `info.meta()` (`szDecimals`, `maxPriceDecimals`).
- **Latency**: 30s grace period after entry.
- **Sync**: Startup leverage synchronization.

## 5. Current Status (Dec 28, 2025)

### ✅ Completed & Stable
- **Real Execution**: Market orders active with dynamic precision.
- **Risk Management**: Risk Manager rejects invalid trades; SL/TP executes immediately.
- **Persistence**: Bot State and Settings survive restarts.
- **AI Analysis**: Active for Signal Validation and Startup Checks.

### 🚧 Roadmap
- [ ] **AI Optimization**: Implement caching for AI analysis to save API quota.
- [ ] **Position Sizing**: Add "% of Balance" mode (currently Fixed USDC only).
- [ ] **Backtest UI**: Visual interface for running Python backtests.

## 6. Commands Reference

```bash
# 🚀 START (PM2)
npx pm2 start ecosystem.config.js

# 🔄 RESTART Backend
npx pm2 restart hl-bot-engine

# 📜 LOGS
npx pm2 logs hl-bot-engine --lines 100

# 🧪 RUN BACKTEST (Terminal)
python3 backtest_sequential.py
```
