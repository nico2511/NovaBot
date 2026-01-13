---
project_name: novabot
last_updated: 2026-01-12
rule_count: 15
optimized_for_llm: true
---

# Project Context & Critical Rules

## Technology Stack
- **Python:** 3.11+
- **API Framework:** FastAPI (Async/Await strict)
- **Database:** SQLite (No partial writes, use transactions)
- **Exchange SDK:** `hyperliquid-python-sdk` (Official)
- **Frontend:** Next.js (Legacy connection)
- **Validation:** Pydantic V2

## Critical Implementation Rules

### 1. Architectural Boundaries (Strangler Fig Pattern)
- **New Logic:** MUST go into `app/` folder.
- **Legacy Logic:** Moved to `_legacy_backup/`. DO NOT import from here in production code.
- **No Logic in Main:** `main.py` and `api/endpoints` must ONLY call Services.
- **Service Layer:** All business logic (Tier Calculation, Risk, etc.) resides in `app/services/`.

### 2. Fail-Safe & Reliability
- **Decorator Mandatory:** Every public method in `Strategies` or `Gamification` MUST use the `@safe_execution` decorator.
- **Bot Survival:** A single strategy crash must NEVER stop the main loop. Catch `Exception`, log error, return `None`/`False`.
- **Default Deny:** If Gamification Service is offline/erroring, Access is DENIED.

### 3. Audit & Observability (Decision Traceability)
- **Mandatory Logging:** Every Trading Signal (Buy/Sell/Hold) MUST be recorded in the `decision_logs` SQLite table.
- **Indicator Snapshot:** You MUST record a snapshot of ALL indicators at the instant T (e.g., `{"rsi": 35, "ema_trend": "up", "vol": 1.2M}`) along with the decision.
- **Reasoning:** The `reason` field is mandatory (e.g., "AI: Probability 85% > Threshold").

### 4. Naming Conventions and Coding Style
- **Python:** `snake_case` for variables/functions. `PascalCase` for Classes.
- **Async:** Use `async def` for all I/O (DB, API, Exchange).
- **Type Hints:** Strict Python type hints (`def foo(a: int) -> bool:`).
- **Configuration:** Use `pydantic-settings` to read `.env`. Do NOT use `os.getenv` directly in logic.

---

## Usage Guidelines

**For AI Agents:**
- Read this file before implementing any code.
- Follow ALL rules exactly as documented.
- When in doubt, prefer the more restrictive option (e.g., Default Deny).
- **CRITICAL:** The "Audit & Observability" rule #3 is non-negotiable for this User.

**For Humans:**
- Keep this file lean.
- Update when Architecture changes.
- Last Updated: 2026-01-12
