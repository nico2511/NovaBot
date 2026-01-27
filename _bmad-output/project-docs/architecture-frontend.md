# Architecture: Frontend - NovaBot

This document details the frontend architecture for the NovaBot management interface.

## Tech Stack
- **Framework**: Next.js 14 (App Router)
- **Language**: TypeScript
- **Styling**: Tailwind CSS
- **Data Fetching**: SWR (Stale-While-Revalidate)
- **Charts**: TradingView Lightweight Charts
- **UI Components**: Radix UI (Headless) + Custom Polish

---

## 🏗️ UI Architecture
The frontend is designed for real-time monitoring and low-latency interaction.

### State Management (SWR)
The frontend uses **SWR** to sync with the Python backend.
- **Polling**: Critial endpoints (`/api/status`, `/api/market/candles`) are polled at short intervals (1s - 5s).
- **Optimistic Updates**: UI toggles (e.g., Enable Trading) reflect immediately while the backend confirms.

### Key Contexts & Hooks
- **Market Data**: Centralized fetching of candles and indicators.
- **Bot State**: Global context for bot status (running, trading enabled, active symbol).

---

## 🎨 Component Library
The UI is divided into modular, highly reactive components:

- **Trading Dashboard**:
    - `ActivePosition.tsx`: Real-time PnL, SL/TP levels, and "Panic Close" button.
    - `MarketAnalysis.tsx`: Visual gauges for RSI, ADX, and Market Regime.
    - `ControlButtons.tsx`: Start/Stop engine and Live Trading toggle.
- **Configuration**:
    - `AdvancedSettings.tsx`: Form-based editor for Global Settings (Personas/Risk).
    - `ConfigPanel.tsx`: Quick settings for the scanner and active symbol.
- **Data Visualization**:
    - `PriceChart.tsx`: Integration with `lightweight-charts` for technical analysis.
    - `EquityChart.tsx`: Performance history visualization.

---

## 📂 App Structure
- `/app`: App router pages (`page.tsx`, `logs/page.tsx`).
- `/components`: Reusable UI modules.
- `/lib`: Utility functions and SWR configurations.
- `/hooks`: Custom React hooks for bot state management.
