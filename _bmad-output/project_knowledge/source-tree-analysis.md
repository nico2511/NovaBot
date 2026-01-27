# Source Tree Analysis

**Project Classification:** Multi-part / Layered Monolith
**Root Path:** `C:\Users\User\Desktop\novabot`

## High-Level Structure
The project follows a layered architecture where the core logic, API interface, and trading strategies are separated but co-located, with a distinct frontend application.

```
novabot/
├── app/                 # [CORE] Main business logic and services
│   ├── core/            # State management, bot context, base classes
│   ├── services/        # External integrations (Hyperliquid, AI, Analyst)
│   └── utils/           # Helper functions
├── backend/             # [API LAYER] FastAPI application
│   ├── api.py           # Main entry point (Port 8001)
│   └── routes/          # API endpoints (analysis, scanner, etc.)
├── frontend-v3/         # [UI LAYER] Next.js 14 Dashboard
│   ├── app/             # App Router pages
│   └── components/      # React components
├── strategies/          # [TRADING LOGIC] pluggable strategy modules
│   ├── base.py          # Strategy base class
│   └── *.py             # Implementation files (smart_trend, bollinger, etc.)
├── scripts/             # [TOOLS] Backtesting and utility scripts
├── docs/                # [DOCS] Legacy documentation
└── start_integrated.sh  # [OPS] Master startup script
```

## Critical Directories

### `app/` (Core Logic)
Contains the "Brain" of the bot.
- Used by both the API (backend) and the independent strategy engine.
- Key Services: `hyperliquid_service`, `analyst_service`.

### `strategies/` (Strategy Plugins)
Modular trading strategies.
- Each file (e.g., `smart_trend.py`) implements a specific trading algorithm.
- Managed by `strategies/engine.py`.

### `backend/` (Interface)
- **Role**: Exposes bot state and control to the Frontend.
- **Entry**: `api.py`.

### `frontend-v3/` (User Interface)
- **Tech**: Next.js 14, Tailwind CSS.
- **Entry**: `npm run start` (via PM2).
