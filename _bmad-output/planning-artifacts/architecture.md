---
stepsCompleted: ['step-01-init', 'step-02-context', 'step-03-starter', 'step-04-decisions', 'step-05-patterns', 'step-06-structure', 'step-07-validation', 'step-08-complete']
inputDocuments: [
  '_bmad-output/planning-artifacts/prd.md',
  '_bmad-output/project-knowledge/project-overview.md',
  '_bmad-output/project-knowledge/source-tree-analysis.md',
  'docs/CONTEXT.md',
  'docs/STRATEGIES.md',
  'docs/THEME.md'
]
workflowType: 'architecture'
project_name: 'novabot'
user_name: 'Nicolas'
date: '2026-01-12'
lastStep: 8
status: 'complete'
completedAt: '2026-01-12'
---

# Architecture Decision Document

_This document builds collaboratively through step-by-step discovery. Sections are appended as we work through each architectural decision together._

## Project Context Analysis

### Requirements Overview

**Functional Requirements:**
*   **Tier Calculation:** Logic based on Equity thresholds ($10/$100/$500) configurable.
*   **Access Control:** Gatekeeper mechanism to block strategies/pairs/leverage based on tier.
*   **UI Integration:** WebSocket updates for real-time tier reflection.
*   **Independence:** Strategies must remain agnostic of gamification logic.

**Non-Functional Requirements:**
*   **Latency:** < 5ms overhead on strategy loop (Critical).
*   **Reliability:** Fail-safe default (Block if API down).
*   **Isolation:** Clean separation of concerns (Gamification Module).

**Scale & Complexity:**
*   **Primary Domain:** Algorithmic Trading (Python Backend + Next.js Frontend).
*   **Complexity Level:** High (Concurrency, State Management, Financial Risk).
*   **Refactor Goal:** Move from flat structure to maintainable component-based architecture.

### Technical Constraints & Dependencies
*   **Hyperliquid SDK:** Source of truth for Equity and active trades.
*   **Python AsyncIO:** Core execution model.
*   **Process Separation:** `main_nextjs.py` (Bot) and `backend/api.py` (API) run separately but share data.

### Cross-Cutting Concerns Identified
*   **State Sharing:** How to sync "User Tier" between the disconnected Bot process and API process? (Shared Memory? File? DB?).
*   **Configuration:** Single source of truth for "Gamification Rules".

## Execution Environment Selection

### Strategy: "Strangler Fig" Migration (Option B)
**Decision:** We will NOT refactor in-place. We will create a new, clean structure and migrate functionality iteratively.
*   **Legacy Handling:** Current files moves to `_legacy_backup/`.
*   **New Core:** A fresh `novabot_v2/` (or root clean-up) structure.

### Base Architecture Pattern
**Backend/Core:** Standard Modular Python Application.
*   **Style:** Service-Oriented (Separation of API, Core Logic, and Strategies).
*   **Framework:** FastAPI (for API) + AsyncIO (for Bot Loop).

**Proposed Directory Structure (Target):**
```text
app/
  core/           # Config, EventLoop, GamificationEngine
  api/            # FastAPI Routes (Endpoints)
  services/       # MarketData, OrderExecution
  strategies/     # Trading Logic (Ported)
  models/         # Pydantic Schemas (Shared Types)
main.py           # Single Entry Point
```

## Core Architectural Decisions

### Decision Priority Analysis
**Critical Decisions (Block Implementation):**
*   **Database:** SQLite (Relational, Concurrent, No Ops overhead).
*   **Communication:** WebSocket (Native FastAPI).
*   **Config:** Pydantic (Type Safe).

### Data Architecture
*   **Engine:** SQLite (`novabot.db`).
*   **Schema Design:**
    *   `users`: Stores Tier, Equity history.
    *   `decision_logs`: **CRITICAL**. Stores every AI/Strategy decision (Timestamp, Indicators Snapshot, Persona Used, Verdict, Reasoning). Allows "Why did AI say No?" auditing.
    *   `positions`: Tracks active trades + state.

### Authentication & Security
*   **LocalAuth:** Simple Token/Key stored in `.env`, loaded via `pydantic-settings`. No complex OAuth needed for local single-user bot.

### API & Communication Patterns
*   **Pattern:** REST for Actions, WebSocket for State.
*   **Route Structure:** `api/v1/gamification`, `api/v1/history`.

### Frontend Architecture
*   **Framework:** Keep Next.js (Legacy connection or clean rebuild TBD by user constraint, assuming Clean Build per Step 3).
*   **State:** React Context + WebSocket Hook.

### Infrastructure & Deployment
*   **Docker:** Recommended for wrapping Python + Next.js dependencies together (Optional but Cleaner).

## Implementation Patterns & Consistency Rules

### Pattern Categories Defined

**Critical Conflict Points Identified:**
*   **Logic Location:** Prevent spaghetti code in `main.py`.
*   **Error Handling:** Prevent single strategy failure form crashing bot.
*   **Data Integrity:** Ensure AI decisions are auditable.

### Naming Patterns
*   **Database:** `snake_case`, Plural tables (`users`, `decision_logs`, `positions`).
*   **Python:** `snake_case` for functions/variables, `PascalCase` for Classes.
*   **API:** REST standard `POST /api/v1/gamification/tier`.
*   **Frontend:** `PascalCase` for Components, `camelCase` for props.

### Structure Patterns
*   **Service Layer Pattern:**
    *   **Rule:** ALL business logic (Tier calculation, Position sizing) MUST reside in `app/services/`.
    *   **Rule:** `main.py` is ONLY for orchestration/startup.
    *   **Rule:** `api/routes.py` is ONLY for request parsing and calling services.

### Format Patterns
*   **Interface Contracts:**
    *   **Rule:** Module communication MUST use `pydantic.BaseModel`. No passing `dict` or `json` directly.
    *   **Example:** `TierUpdate(user_id=1, new_tier="Supernova", reason="Equity > 500")`.

### Process Patterns
*   **Fail-Safe Enforcement:**
    *   **Pattern:** `@safe_execution` decorator on all Strategy `analyze()` methods.
    *   **Behavior:** Catches generic `Exception`, logs to SQLite, returns `signal=None`. Bot continues.

*   **AI Audit Logging:**
    *   **Pattern:** "Decision Traceability".
    *   **Requirement:** Every `Signal` generated involves a database write to `decision_logs` containing `{snapshot, persona, verdict, reason}`.

### Enforcement Guidelines
**All AI Agents MUST:**
1.  Use `structlog` or standard logging mapped to the SQLite audit table.
2.  Never import `main.py` into `services`. (Circular dependency prevention).
3.  Write logic in `app/services` first, then expose via API/Bot.

## Project Structure & Boundaries

### Complete Project Directory Structure
```text
novabot/
├── _legacy_backup/          # [MIGRATION] Old root files moved here
├── app/
│   ├── core/                # [INFRA] Config, Database
│   │   ├── config.py
│   │   ├── database.py
│   │   └── logging.py
│   ├── gamification/        # [MODULE] Gamification Domain
│   │   ├── engine.py        # Tier Calculation Logic
│   │   ├── gatekeeper.py    # Permission Checks
│   │   └── models.py        # Pydantic Schemas for Tiers
│   ├── services/            # [DOMAIN] Business Logic
│   │   ├── audit.py         # AI Decision Logging
│   │   ├── risk.py          # Position Sizing
│   │   └── hyperliquid.py   # Exchange Wrapper
│   ├── strategies/          # [LOGIC] Trading Algorithms
│   │   ├── base.py          # Abstract Base Class
│   │   └── implementations/ # Actual Strategy Files
│   ├── api/                 # [INTERFACE] HTTP/WebSocket
│   │   ├── dependencies.py
│   │   └── v1/
│   │       ├── router.py
│   │       └── endpoints/
│   └── main.py              # [ENTRY] Application Factory
├── frontend/                # [UI] Next.js Application
├── tests/                   # [QA] Pytest Suite
├── .env.example
├── pyproject.toml           # [META] Dependencies
└── alembic.ini              # [DB] Migrations (if needed)
```

### Architectural Boundaries
*   **API Boundary:** `app/api/` defines the contract. No logic here, only routing.
*   **Domain Boundary:** `app/gamification/` is self-contained. It exposes `check_access(user, strategy)` but knows nothing about *how* strategies work.
*   **Strategy Boundary:** `app/strategies/` are pure functions (or stateless classes). They receive `MarketData` and return `Signal`. They DO NOT execute orders directly.

### Requirements to Structure Mapping
*   **FR: Tier Calculation** -> `app/gamification/engine.py`
*   **FR: Access Control** -> `app/gamification/gatekeeper.py`
*   **FR: Audit Log** -> `app/services/audit.py` (Writing to `novabot.db`)

### Integration Points
*   **Bot <-> API:** Via `novabot.db` (SQLite) for state persistence and `asyncio.Event` (or Queue) for real-time signals inside the same process group (if running under one command) OR via generic DB polling if separate.
*   **Refinement:** We will run `main.py` as a SINGLE process that spawns the API server (`uvicorn`) and the Trading Loop (`asyncio.create_task`). This allows sharing memory/events directly without complex IPC.

### File Organization Patterns
*   **Configuration:** `app/core/config.py` uses `BaseSettings` to read `.env`.
*   **Tests:** `tests/test_gamification.py` to test logic without connecting to Hyperliquid.

## Architecture Validation Results

### Coherence Validation ✅
*   **Decision Compatibility:** "Strangler Fig" approach aligns with "Safe Refactor". Python/FastAPI/SQLite stack is standard and robust.
*   **Performance:** In-Process architecture (Single Entry Point) eliminates network latency for permission checks, ensuring < 5ms Requirement.

### Requirements Coverage Validation ✅
*   **Tier/Access:** Fully covered by `gamification` module boundaries.
*   **Audit/Traceability:** Covered by `decision_logs` table (User Request: "know why IA said no").
*   **Reliability:** Fail-safe decorators defined in Patterns section address NFRs.

### Architecture Completeness Checklist
*   [x] Project context analyzed
*   [x] Tech stack defined (Python 3.11+, FastAPI, SQLite)
*   [x] Directory structure mapped
*   [x] Implementation patterns (Error handling, Naming) defined

### Architecture Readiness Assessment
**Overall Status:** READY FOR IMPLEMENTATION
**Confidence Level:** High
**Next Step:** Execute the "Migration/Setup" Sprint (create folders, move files).

## Architecture Completion Summary

### Final Architecture Deliverables
*   **Decisions:** "Safe Refactor" (Strangler Fig), In-Process FastAPI, SQLite Audit.
*   **Patterns:** Service Layer, Pydantic contracts, Fail-Safe, Audit Logging.
*   **Structure:** Partitioned `app/` vs `_legacy_backup/`.
*   **Validation:** Metrics met (Latency & Traceability).

### Implementation Handoff
**AI Agents MUST:**
1.  **Read this document** `_bmad-output/planning-artifacts/architecture.md`.
2.  **Follow the Folder Structure** strictly.
3.  **Implement the Audit Log** for every strategy decision.

**Status:** READY FOR IMPLEMENTATION ✅
