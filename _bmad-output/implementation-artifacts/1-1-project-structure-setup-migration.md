# Story 1.1: Project Structure Setup & Migration

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a Developer,
I want to establish the new `app/` directory structure and move legacy code to `_legacy_backup/`,
So that I can start building the Gamification features on a clean architecture without breaking existing functionality.

## Acceptance Criteria

1.  **Given** The current codebase is in the root directory
    **When** I create the `app/` folder structure (core, services, gamification) and move old files to `_legacy_backup/`
    **Then** The project structure should match the Architecture document
2.  **And** `main.py` should be refactored to verify environment setup (imports work)
3.  **And** `novabot.db` should be initialized via SQLAlchemy/Alembic or raw SQL script
4.  **And** The application runs without errors in the new structure (imports fixed)

## Tasks / Subtasks

- [x] Task 1: Initialize New Project Structure (AC: 1)
  - [x] Create `app/` directory
  - [x] Create subdirectories: `app/core`, `app/services`, `app/gamification`, `app/strategies`, `app/api`
  - [x] Create `_legacy_backup/` directory
- [x] Task 2: Migrate & Backup Legacy Code (AC: 1)
  - [x] Move existing root python files (except main entry point candidates) to `_legacy_backup/`
  - [x] Ensure `frontend/` remains untouched (or handle if necessary)
- [x] Task 3: Initialize Database (AC: 3)
  - [x] Implement `app/core/database.py`
  - [x] Create `init_db()` function to generate `users`, `decision_logs` tables
- [x] Task 4: Refactor Entry Point (AC: 2, 4)
  - [x] Create/Update `main.py` to import from new `app/` structure
  - [x] Verify `python main.py` runs successfully

## Dev Notes

- **Architecture Pattern:** Strangler Fig. We are creating the *new* home (`app/`) while keeping the *old* home (`_legacy_backup/`) safe.
- **Critical Rule:** NEW logic goes to `app/`. OLD logic stays in `_legacy_backup`.
- **Database:** Use SQLite. File path should be defined in `app/core/config.py` (e.g., `novabot.db`).
- **Dependencies:** Ensure `pydantic-settings` and `sqlalchemy` are installed (or added to requirements).

### Project Structure Notes

- Alignment with `_bmad-output/planning-artifacts/architecture.md` is mandatory.
- See `Project Structure` section in Architecture doc for exact tree.

### References

- [Architecture Document](file:///_bmad-output/planning-artifacts/architecture.md)
- [Project Context](file:///_bmad-output/planning-artifacts/project-context.md)

## Dev Agent Record

### Agent Model Used

Antigravity (Agentic Mode)

### Debug Log References

- Migration success: `_legacy_backup` created with 69 legacy files.
- Database init: `novabot.db` created. (Step 606 check: passed).
- Tests: `tests/test_initialization.py` passed.
- Complete cleanup: All legacy scripts, logs, and old code moved to `_legacy_backup/`.

### Completion Notes List

- ✅ Implemented full project structure migration following Strangler Fig pattern.
- ✅ Created robust `main.py` entry point with FastAPI lifespan.
- ✅ Initialized SQLite DB with `User` and `DecisionLog` models.
- ✅ Verified structure and table creation via pytest.
- ✅ **Complete cleanup**: Moved all legacy files (scripts, logs, data, docs, old app/, backend/, strategies/) to `_legacy_backup/`.
- ✅ Root directory now clean with only: `app/`, `frontend/`, `tests/`, `main.py`, config files, and DB.

### File List

**Created:**
- `main.py`
- `app/core/config.py`
- `app/core/database.py`
- `app/gamification/models.py`
- `app/services/models.py`
- `tests/test_initialization.py`
- `novabot.db`

**Migrated to `_legacy_backup/`:**
- `app/` (old), `backend/`, `strategies/`, `utils/`, `tests/` (old)
- `main_nextjs.py`, `strategies.json`, `bot_state.json`
- `data/`, `docs/`, `scripts/`, `logs/`, `tradingview/`
- All legacy scripts (`.sh`, `.bat`, `.js`)
- Cache files (`token_meta_cache.json`, `trade_history.csv`, etc.)
