# Source Tree Analysis - NovaBot

Annotated directory structure for the NovaBot project.

```text
novabot/
├── app/                 # 🤖 Core Bot Logic
│   ├── core/            # Bot context, risk manager, state persistence
│   ├── services/        # Hyperliquid, AI, Indicators, Discord services
│   └── utils/           # Shared utility functions
├── backend/             # 🌐 FastAPI Management API
│   ├── routes/          # API Route definitions (Scanner, etc.)
│   ├── api.py           # Main FastAPI entry point
│   └── market_data.py   # Standalone market data service for UI
├── frontend-v3/         # 💻 Next.js Dashboard
│   ├── app/             # App Router pages and layouts
│   ├── components/      # UI components (Trading dashboard, settings)
│   └── lib/             # API client and SWR hooks
├── strategies/          # 🎯 Trading Strategy Implementation
│   ├── engine.py        # Strategy coordinator and regime selector
│   └── *.py             # Individual strategy logic (Bollinger, RSI, etc.)
├── data/                # 📂 Local data storage (Logs, history)
├── docs/                # 📖 Historical project documentation
├── _bmad-output/        # 🧠 BMAD Generated Docs & Artifacts
├── .env                 # Secret configuration
└── strategies.json      # Strategy parameter registry
```

## Key Files
- `main_integrated.py`: Main entry point for the combined Bot + API.
- `bot_state.json`: Single source of truth for the bot's runtime state.
- `requirements.txt`: Python package manifest.
- `frontend-v3/package.json`: Frontend dependency manifest.
- `ecosystem.config.js`: PM2 production configuration.
