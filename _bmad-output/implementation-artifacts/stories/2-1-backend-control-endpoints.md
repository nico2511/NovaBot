# Story 2.1: Backend "Control" Endpoints

Status: done

<!-- Note: This story documents existing backend functionality -->

## Story

As a Frontend Developer,
I want REST endpoints to start and stop the bot's trading engine,
So that I can build a control interface for the user.

## Acceptance Criteria

1. **Stop Endpoint**: `POST /api/engine/stop` immediately ceases looking for new trades.
2. **Start Endpoint**: `POST /api/engine/start` resumes trading operations.
3. **State Persistence**: `bot_state.json` is updated to reflect `trading_enabled` state.
4. **Stateless Recovery**: The persistent state is honored on bot restart.
5. **Response Format**: Returns JSON with `status` and `message` fields.

## Tasks / Subtasks

- [x] Verify `/api/engine/start` endpoint exists #backend
- [x] Verify `/api/engine/stop` endpoint exists #backend
- [x] Verify state persistence to `bot_state.json` #backend
- [x] Verify restart recovery logic #backend

## Dev Notes

### Architecture Constraints
- **Immutable Backend**: These endpoints already exist in `backend/api.py`.
- **State Management**: Uses `_execute_bot_action` helper for bot/standalone mode.
- **Persistence**: StateManager handles saving to `bot_state.json`.

### Source Tree Components
- [EXISTING] `backend/api.py` (Lines 300-317: start/stop endpoints)

### References
- [Architecture]: Stateless Recovery pattern
- [backend/api.py]: Existing implementation

## Dev Agent Record

### Agent Model Used
- Sm (Scrum Master)

### Completion Notes List
- Backend control endpoints already implemented in `backend/api.py`.
- `/api/engine/start` (line 300): Starts trading engine.
- `/api/engine/stop` (line 310): Stops trading engine.
- Both endpoints use `_execute_bot_action` for bot bridge integration.
- State persistence handled by StateManager.
- No code changes required - marking as done.

### File List
- `backend/api.py` (Existing - no changes)
