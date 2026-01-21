# Project Documentation Index - NovaBot

Welcome to the comprehensive documentation for **NovaBot**, a hybrid (Python/Next.js) algorithmic trading bot for Hyperliquid.

## 📌 Project Overview
- **Type**: Multi-part Monorepo
- **Primary Language**: Python 3.10+ / TypeScript
- **Architecture**: Service-Oriented (Bot + API + Frontend)
- **Primary Domain**: Algorithmic Trading (DeFi)

---

## 🗺️ Documentation Map

### 🏗️ Architecture & Core Logic
- [**Bot Core Architecture**](./architecture-bot_core.md)
  *Trading loops, Risk management, Atomic execution.*
- [**Frontend Architecture**](./architecture-frontend.md)
  *Next.js structure, SWR state management, UI components.*
- [**Data Models & Persistence**](./data-models.md)
  *Schema for `bot_state.json` and StateManager logic.*

### 🎯 Strategy & API
- [**Strategy Catalog**](./strategy-catalog.md)
  *Detailed breakdown of all 9 trading strategies.*
- [**API Contracts**](./api-contracts.md)
  *REST endpoints for engine control and management.*

### 🛠️ Development & Operations
- [**Source Tree Analysis**](./source-tree-analysis.md)
  *Annotated folder structure and key file map.*
- [**Development Guide**](./development-guide.md)
  *Prerequisites, setup, and deployment instructions.*

---

## 📂 Existing Documentation (External)
- [Project Context](../project-context.md)
- [Historical Docs](../docs/README.md)
- [Trading Profiles](../docs/TRADING_PROFILES.md)

---

## 📈 Getting Started
To get the project running locally, refer to the [Development Guide](./development-guide.md).
For a high-level vision, see the [Project Overview](../_bmad-output/planning-artifacts/product-brief-novabot-2026-01-13.md).
