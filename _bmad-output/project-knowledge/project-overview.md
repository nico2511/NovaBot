# Project Overview: NovaBot

**Generated:** 2026-01-12
**Status:** Brownfield / Legacy
**Architecture:** Multi-part (Bot Core + API + Web UI)

## Executive Summary
NovaBot is an algorithmic trading system designed for the **Hyperliquid** DEX. It features a Python-based core trading engine, a separate API layer for data access, and a modern Next.js web dashboard for monitoring and control. The system supports multiple trading strategies, persistent state management, and real-time market conceptualization.

## Technology Stack

| Component | Technology | Role |
|-----------|------------|------|
| **Core Bot** | Python 3.11+ | Main trading loop, Strategy execution, WebSocket handling |
| **Backend** | Python (FastAPI/Flask) | REST API to serve data to Frontend |
| **Frontend** | Next.js 14+ (App Router) | User Interface for monitoring and control |
| **Styling** | Tailwind CSS | UI Styling |
| **Data** | JSON / CSV | Simple file-based persistence (`bot_state.json`) |
| **Exchange** | Hyperliquid | Target DEX (via SDK/API) |

## Repository Structure at a Glance
The repository is a monorepo containing three distinct parts:
1. **Root**: Trading logic and strategies (`main_nextjs.py`, `strategies/`)
2. **Backend**: API Server (`backend/`)
3. **Frontend**: Web Dashboard (`frontend/`)

## Key Features (Inferred)
- **Multi-Strategy Support**: Configurable via `strategies.json`.
- **Live Monitoring**: Real-time position and order tracking via Web UI.
- **Resilience**: State persistence in `bot_state.json` to survive restarts.
- **Separation of Concerns**: Trading logic is decoupled from the UI via the API layer.

## Documentation Status
- [Source Tree Analysis](./source-tree-analysis.md) - **Available**
- [API Contracts](./api-contracts.md) - *(To be generated via Deep Scan)*
- [Component Inventory](./component-inventory.md) - *(To be generated via Deep Scan)*
- [Architecture (Full)](./architecture.md) - *(To be generated during Solutioning)*
