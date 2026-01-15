# Source Tree Analysis

## Project Structure Overview
This project follows a **Monolithic Python Backend** structure.
- **Root**: `c:\Users\User\Desktop\novabot`
- **Core Framework**: FastAPI, Python 3.1x
- **Key Directories**: `app/` (Application Logic), `backend/` (API Interface), `strategies/` (Trading Logic)

## Annotated Directory Tree

```
novabot/
├── app/                         # Core Application Logic
│   ├── core/                    # System-level modules
│   │   ├── config.py            # Environment configuration
│   │   ├── state_manager.py     # JSON persistence engine (bot_state.json)
│   │   ├── risk_manager.py      # PnL & max drawdown protection
│   │   └── prompts.py           # AI Persona system prompts
│   ├── services/                # Business Logic Services
│   │   ├── hyperliquid_service.py # Exchange adapter
│   │   ├── ia.py                # AI analysis engine
│   │   └── indicators.py        # Pandas-based TA library
│   └── utils/                   # Shared internal utilities
├── backend/                     # REST API Layer (FastAPI)
│   ├── api.py                   # Main API entry point (Endpoints)
│   ├── bot_bridge.py            # Connector between API and Bot Engine
│   └── routes/                  # Modular route handlers (e.g. scanner)
├── strategies/                  # Trading Strategies (Algorithmic Logic)
│   ├── base.py                  # BaseStrategy abstract class
│   ├── engine.py                # Strategy execution engine
│   ├── smart_trend.py           # "Sniper" Trend Strategy
│   ├── bollinger_bounce.py      # "Shield" Mean Reversion Strategy
│   ├── elastic_reversion.py     # "Elasticity Guard" Strategy
│   ├── institutional_scalp.py   # "Banker" Liquidity Hunter Strategy
│   └── ... (others)
├── docs/                        # Project Documentation
│   ├── STRATEGIES.md            # Strategy Logic Documentation
│   └── TRADING_PROFILES.md      # AI Persona Profiles
├── utils/                       # DevOps & Maintenance Scripts
│   ├── fetch_prod_logs.sh       # Log retrieval script
│   └── tests/                   # Unit tests
├── .env                         # Secrets (API Keys) - DO NOT COMMIT
├── ecosystem.config.js          # PM2 Process Manager config
├── start_integrated.sh          # Main startup script (Linux/WSL)
├── main_nextjs.py               # Application Entry Point (Bot Loop)
└── bot_state.json               # Runtime State Persistence
```

## Critical Folders

### `app/core/`
**Purpose**: The "brain" of the bot configuration.
- Contains the `StateManager` which is the single source of truth for the bot's runtime state.
- Holds `config.py` which loads all sensitive `.env` variables.

### `strategies/`
**Purpose**: The "heart" of the trading logic.
- Each file here (e.g., `smart_trend.py`) represents a distinct trading behavior.
- Strategies inherit from `base.py` and are orchestrated by `engine.py`.

### `backend/`
**Purpose**: The "mouth" of the system (External Interface).
- Exposes the internal state to the Frontend via REST API.
- Handles manual overrides (`api.py` endpoints like `/close_trade`).

## Entry Points

1.  **Application Start**: `main_nextjs.py`
    - Initializes services, connects to Hyperliquid, and starts the `StrategyEngine` loop.
2.  **API Start**: `backend/api.py` (via Uvicorn)
    - Starts the web server to listen for frontend requests.
3.  **Deployment**: `start_integrated.sh`
    - Orchestrates the launch of both the Python Bot and the API server suitable for production.
