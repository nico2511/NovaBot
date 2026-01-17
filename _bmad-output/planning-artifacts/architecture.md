---
stepsCompleted: [1, 2, 3]
inputDocuments:
  - prd.md
  - ux-design-specification.md
  - product-brief-novabot-2026-01-13.md
  - project-context.md
workflowType: 'architecture'
project_name: 'novabot'
user_name: 'Nicolas'
date: '2026-01-17'
---

# Architecture Decision Document

_This document builds collaboratively through step-by-step discovery. Sections are appended as we work through each architectural decision together._

## Project Context Analysis

### Requirements Overview

**Functional Requirements:**
*   **Core Trading Engine**: Python-based monolithic loop (`BotContext`) managing 7+ strategies via `StrategyEngine`.
*   **AI Validation Layer**: DeepSeek v3.2 integration (`ia_service`) acting as a "Hard Veto" on all signals.
*   **Dashboard (Web App)**: Next.js PWA for monitoring PnL, "Running" status, and executing "Panic" actions.
*   **Notifications**: Discord/Telegram alerts for trades and daily summaries.

**Non-Functional Requirements:**
*   **Resilience (Critical)**: "Stateless Recovery" architecture. The bot must be able to crash and restart without losing position tracking (relies on `StateManager` and Exchange reconciliation).
*   **Performance**: "Morning Coffee Standard" requires < 2s dashboard load time.
*   **Security**: API Keys in `.env` only. No sensitive data exposed to client.

**Scale & Complexity:**
*   **Primary Domain**: Full-Stack (Python Backend + Next.js Frontend).
*   **Complexity Level**: Medium (Personal project but High Risk/Financial).
*   **Estimated Components**: 3 Core (Bot Engine, API Server, Frontend App).

### Technical Constraints & Dependencies

*   **Exchange**: Hyperliquid (DEX) - Strict API limits and specific object models.
*   **AI Provider**: OpenRouter - Potential latency/reliability issues to handle.
*   **Infrastructure**: Must run on VPS/Local Server (PM2 managed).
*   **Backend Legacy**: Must integrate with existing `app/core/bot.py` logic without rewriting the core loop.

### Cross-Cutting Concerns Identified

*   **Atomic State Management**: ensuring `bot_state.json` is always in sync with reality (Hyperliquid).
*   **Error Handling**: "Silence is Golden" (Project Principle) vs Detailed Logs for debugging.
*   **Shared Types**: Frontend needs to know Backend data structures (Trade objects, signals).

## Starter Template Evaluation

### Primary Technology Domain

**Full-Stack Web Application (Brownfield Hybrid)**
Existing Python Backend + New Next.js Frontend.

### Selected Starter: Custom Next.js PWA

**Rationale for Selection:**
*   **Performance:** Next.js App Router minimizes client-side JS, essential for the "<2s Morning Check".
*   **Mobile-First:** PWA support is native in Next.js, satisfying the "Mobile First" requirement without building a native app.
*   **Aesthetics:** Tailwind + Shadcn/UI allows rapid implementation of the "Hyperliquid-like" dark mode UI defined in UX specs.
*   **Type Safety:** TypeScript ensures data contracts between the Python API and Frontend are respected (via manual type definitions).

**Initialization Command:**

```bash
npx create-next-app@latest frontend-v3 --typescript --tailwind --eslint --app
cd frontend-v3
npx shadcn@latest init
```

**Architectural Decisions Provided by Starter:**

**Language & Runtime:**
*   **Frontend**: TypeScript / Node.js (Next.js)
*   **Backend**: Python 3.10+ (Existing)

**Styling Solution:**
*   **Tailwind CSS**: Utility-first for rapid layout.
*   **Shadcn/UI**: Headless components for accessible, clean UI elements (Dialogs, Inputs).

**Code Organization:**
*   `/app` (App Router): Page-based routing (`/dashboard`, `/settings`).
*   `/components`: Atomic UI components.
*   `/lib`: Shared utilities and API clients.

**Note:** The Frontend will treat the Python API as a "Headless CMS" for market data.
