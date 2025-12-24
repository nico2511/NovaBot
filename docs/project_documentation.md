# ⚡ HyperLiquid AI Trader - Project Definition

## 1. Project Overview
**Name:** HyperLiquid AI Trader
**Goal:** An autonomous trading bot connecting to the HyperLiquid DEX, enhanced by Google Gemini AI for market sentiment analysis and decision support.
**Current Version:** 2.0 (Post-Refactor)

## 2. Core Features
- **Real-Time Data:** Fetches live candle data from HyperLiquid API.
- **AI Market Analysis:** Uses Gemini 2.0 Flash to analyze market structure (Trend, Risk, Summary) based on OHLCV data.
- **Strategy Engine:** Modular strategy system supporting multiple concurrent strategies (e.g., Scalp EMA, Mean Reversion).
- **Risk Management:** Centralized risk checks (Max Positions, Daily Stop Loss, Exposure).
- **Dual Execution Mode:**
    - **Phantom (Manual):** Simulates trades for testing strategies without equity risk.
    - **Auto (Hyperliquid):** Live execution (requires explict 'ALLOW LIVE TRADING' confirmation).
- **Dashboard:** Streamlit-based UI with:
    - Interactive Plotly Charts (EMA, Price).
    - Split-view Logs & Signals.
    - Active Strategy & Market Regime Indicators.

## 3. Technology Stack
- **Language:** Python 3.10+
- **UI Framework:** Streamlit
- **Data Visualization:** Plotly
- **AI Model:** Google Gemini 2.0 Flash (via `google-genai` SDK)
- **Exchange API:** Hyperliquid Python SDK
- **Notification:** Discord Webhooks

## 4. Architecture & Design Patterns
- **Singleton Pattern:** The `BotContext` is a strict singleton (via `@st.cache_resource` factory) to manage global state (data, signals, logs) across Streamlit re-runs.
- **Background Threading:** A daemon thread `background_loop` handles data fetching and strategy processing to keep the UI responsive.
- **Service Layer:** 
    - `hyperliquid_service.py`: Exchange interactions (Candles, Orders).
    - `gemini_service.py`: AI prompting and response parsing.
    - `discord_service.py`: Remote logging.
- **Strategy Pattern:** Strategies inherit from `BaseStrategy` (in `strategies/definitions.py`) and are managed by `StrategyEngine`.

## 5. Current File Structure
```
PyBot/
├── main.py                 # Entry point, UI, and Main Loop
├── run.sh                  # Execution script
├── strategies.json         # Strategy configuration
├── .env                    # API Keys (Gemini, Hyperliquid, Discord)
├── app/
│   ├── core/
│   │   ├── risk_manager.py
│   │   └── config.py
│   ├── services/
│   │   ├── hyperliquid_service.py
│   │   ├── gemini_service.py
│   │   └── discord_service.py
│   └── ui/
│       ├── sidebar.py
│       └── charts.py
└── strategies/
    ├── engine.py           # Strategy selector & runner
    └── definitions.py      # Strategy logic classes
```

## 6. Latest Modifications (v2.0)
- **Fixed UI Duplication:** Resolved ghost rendering issues by enforcing clean singleton context.
- **Strategy Visibility:** Dashboard now displays the currently active strategy name.
- **Mobile Optimization:** Responsive metric layout (3+2 grid) and improved chart scaling.
- **Console Buffer:** Live system logs displayed directly in the UI.

## 7. Next Steps
- Implement concrete logic for all strategy classes (currently placeholders).
- Refine AI prompts for deeper technical analysis.
- Deployment via Docker.
