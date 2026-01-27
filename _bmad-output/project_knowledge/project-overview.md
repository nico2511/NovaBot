# Project Overview

**Project Name:** NovaBot
**Classification:** Multi-part Trading System
**Primary Language:** Python (Backend) / TypeScript (Frontend)

## Executive Summary
NovaBot is a sophisticated automated trading system designed for the HyperLiquid DEX. It features a modular architecture where core logic, trading strategies, and user interface are decoupled.
- **Bot Engine**: Python-based, strategy-agnostic core.
- **Analyst Service**: Real-time market sentiment analysis using multi-timeframe candles.
- **Dashboard**: Modern Next.js web interface for real-time monitoring and control.

## Technology Stack

| Layer | Technology | Primary Libraries |
| :--- | :--- | :--- |
| **Backend API** | Python / FastAPI | `fastapi`, `uvicorn`, `pydantic` |
| **Core Logic** | Python | `pandas`, `numpy`, `aiohttp` |
| **Exchange** | HyperLiquid SDK | `hyperliquid-python-sdk`, `eth-account` |
| **Frontend** | Next.js 14 | `react`, `tailwindcss`, `lucide-react` |
| **Ops** | PM2 / Bash | `pm2` |

## Architecture Type
**Layered Monolith / Service-Based**
While the repository is a monolith, the code is structured into distinct layers:
1.  **UI Layer** (`frontend-v3`): Consumes the API.
2.  **API Layer** (`backend`): Exposes state and controls.
3.  **Service Layer** (`app`): Business logic and external integrations.
4.  **Strategy Layer** (`strategies`): Pluggable trading logic.

## Documentation Map
- **[Source Tree Analysis](./source-tree-analysis.md)**: Detailed directory breakdown.
- **[API Contracts](./api-contracts-backend.md)**: Backend API reference.
- **[Data Models](./data-models-backend.md)**: Core objects and settings.
- **[Frontend Components](./component-inventory-frontend.md)**: UI Component catalog.
- **[Development Guide](./development-guide.md)**: Setup and deployment instructions.
