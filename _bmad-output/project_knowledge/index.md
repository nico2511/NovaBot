# Project Knowledge Index

## Overview
This directory contains comprehensive documentation for the **NovaBot** project, generated via the `document-project` workflow (Deep Scan).

**Project Root**: `c:\Users\User\Desktop\novabot`
**Type**: Monolith Python Backend
**Scan Date**: 2026-01-13

## 📚 Documentation Map

### Core Architecture
- **[Source Tree Analysis](./source-tree-analysis.md)** breakdown of the project structure, directories, and file purposes.
- **[Component Inventory](./component-inventory-backend.md)**: List of key services (`HyperliquidService`, `IAService`), core modules, and strategies.
- **[Data Models](./data-models-backend.md)**: Documentation of `bot_state.json` schema, `BotStatus` objects, and persistence mechanisms.

### API & Interfaces
- **[API Contracts](./api-contracts-backend.md)**: Detailed reference for the FastAPI endpoints (Port 8001), including requesting market data and managing the bot.

### specific Guides
- **[Development Guide](./development-guide.md)**: Instructions for setting up the local dev environment, virtualenv, and running tests.
- **[Deployment Guide](./deployment-guide.md)**: Production deployment instructions using `start_integrated.sh` and PM2.

## 🔗 Related Resources
- [Project README](../../README.md)
- [Legacy Docs](../../docs/) (Original documentation folder)
