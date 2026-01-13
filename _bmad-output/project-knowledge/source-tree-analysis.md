# Source Tree Analysis

## Project Structure Overview

The project follows a **Multi-part** architecture with three distinct areas:
1. **Frontend**: A Next.js web application for the UI.
2. **Backend**: A Python API layer (FastAPI/Flask) handling requests.
3. **Core Bot**: The root-level Python application running the trading logic (`main_nextjs.py`).

## Detailed Directory Tree

```
novabot/
├── main_nextjs.py           # [CORE] Entry point for the Trading Bot
├── strategies.json          # [CONFIG] Active Strategy configurations
├── bot_state.json           # [DATA] Persistent bot state (positions, orders)
├── .env                     # [CONFIG] Environment variables (API Keys)
│
├── frontend/                # [PART: frontend] Web UI (Next.js)
│   ├── app/                 # Next.js App Router pages
│   ├── components/          # Reusable React components
│   ├── hooks/               # Custom React hooks
│   ├── public/              # Static assets
│   ├── package.json         # Frontend dependencies
│   └── next.config.js       # Next.js configuration
│
├── backend/                 # [PART: backend] API Server
│   ├── api.py               # [ENTRY] Main API server entry point
│   ├── bot_bridge.py        # Bridge between API and Core Bot
│   ├── market_data.py       # Market data fetching logic
│   └── routes/              # API Endpoint definitions
│
├── strategies/              # [LOGIC] Trading Strategy implementations
│   └── ...                  # Individual strategy files
│
├── logs/                    # [DATA] Application logs
├── docs/                    # [DOCS] Project documentation
└── _bmad/                   # [META] BMad Agent configuration
```

## Critical Folders & Files

### Core Bot (Root)
- **`main_nextjs.py`**: The heart of the bot. Likely contains the main event loop, websocket connections to Hyperliquid, and strategy execution engine.
- **`strategies/`**: Contains the logic for specific trading strategies. This is a critical area for modification.
- **`strategies.json`**: Controls which strategies are active and their parameters.

### Frontend
- **`frontend/app/`**: Defines the routes and pages of the dashboard.
- **`frontend/components/`**: UI elements like charts, order forms, and status indicators.

### Backend
- **`backend/api.py`**: Serves data to the frontend. Likely exposes endpoints for account status, history, and manual override.
- **`backend/bot_bridge.py`**: Crucial component connecting the stateless API to the stateful Bot process.

## Integration Points
- **Frontend ↔ Backend**: REST API calls (likely `fetch` or `axios` in `frontend/utils` or hooks).
- **Backend ↔ Core Bot**: Communication appears to be handled via `bot_bridge.py` or shared files (like `bot_state.json` or `trade_history.csv`), as Python processes are typically separate.
