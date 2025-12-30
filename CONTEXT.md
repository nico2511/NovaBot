# Project Context: Hyperliquid AI Trading Bot

## 1. Project Overview
This project is an advanced algorithmic trading bot designed for the **Hyperliquid** DEX. It features a hybrid architecture combining a **Python (FastAPI)** backend for trading logic, a **Next.js (React)** frontend for monitoring, and **Gemini AI** for market analysis.

## 2. Technical Stack & Architecture

### Backend (Python)
- **Framework**: FastAPI (Port 8001).
- **Engine**: `hl-bot-engine` process managed by PM2.
- **Core Libs**: `pandas` (Data), `hyperliquid-python-sdk` (Exchange), `google-generativeai` (AI).
- **Persistence**: 
  - `bot_state.json`: Settings & Trading State (Atomic write).
  - `token_meta_cache.json`: Exchange Metadata (Decimals/Rules) cached 24h+ to avoid Rate Limits.

### Frontend (Next.js)
- **Framework**: Next.js 14 App Router (Port 3000).
- **UI**: Tailwind CSS, Lucide Icons, Real-time Dashboard.
- **Features**: Real-time Chart (Lightweight Charts), Strategy Monitor, Gamification Widget.

## 3. Key Features & Security

### 🛡️ Security & Risk Management
- **Hard Stop Loss / Take Profit**: Trigger orders are placed **directly on the exchange** immediately after opening a position. This protects funds even if the bot crashes or loses connection.
- **Gamification Levels**: Strict asset filtering. "Goblin" users (low balance) are restricted to Whitelisted Memecoins (Safe List). Fallback logic ensures forbidden assets (BTC/ETH) are never traded in case of API failure.
- **Rate Limit Protection**: 
   - Scanner results cached for 5 minutes.
   - Metadata (Decimals) cached on disk.
   - Optimized `useSWR` intervals on frontend.

### 🤖 AI & Strategy
- **Gemini AI**: Provides market sentiment and signal validation.
- **Strategies**: `ScalpEmaRsi` (Main), `InstitutionalScalp`, `SwingTrendPullback`. Logic ported from TradingView pine prototypes.

## 4. Commands Reference

```bash
# 🚀 START (PM2)
npx pm2 start ecosystem.config.js

# 🔄 RESTART Backend (Safe)
npx pm2 restart hl-bot-engine

# 📜 LOGS (Check errors or trades)
npx pm2 logs hl-bot-engine --lines 100

# 🛠️ FORCE METADATA UPDATE (If "Invalid Size" errors persist)
python3 force_cache.py (Script to create if needed)
```

## 5. Current Status (Dec 30, 2025)

### ✅ Completed & Stable
- **Execution**: Market orders + Hard Trigger Orders (SL/TP) on Hyperliquid.
- **Scanner**: Auto-switch to best opportunity + Gamification Filters.
- **Optimization**: Metadata Caching drastically reduces API calls (fixes 429 errors).
- **UI**: Full dashboard with multi-tabs (Overview, Strategies, Signals, Scanner).

### 🚧 Roadmap (Optimization)
- [ ] **Position Sizing**: Add "% of Balance" mode (currently Fixed USDC only).
- [ ] **Backtest UI**: Visual interface for running Python backtests.
- [ ] **Trailing Stop**: Implement Hard Trailing Stop logic (Move SL on exchange).
