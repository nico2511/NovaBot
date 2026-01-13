# Story 4.1: Migrate Hyperliquid Service

Status: done

## Story

As a Developer,
I want to migrate the HyperliquidService to the new architecture,
So that trading functionality is integrated with the gamification system.

## Acceptance Criteria

1.  **Given** The HyperliquidService exists in `_legacy_backup/`
    **When** I migrate it to `app/trading/`
    **Then** All imports are updated to use new `app/` structure
2.  **And** The service maintains all existing functionality
3.  **And** WebSocket manager integration is preserved

## Tasks / Subtasks

- [x] Task 1: Create Trading Module (AC: 1)
  - [x] Create `app/trading/` directory
  - [x] Create `app/trading/__init__.py`
- [x] Task 2: Copy Hyperliquid Service (AC: 1, 2)
  - [x] Copy from `_legacy_backup/app/services/hyperliquid_service.py`
  - [x] Update imports to use `app.core.config`
  - [x] Preserve WebSocket manager
- [x] Task 3: Copy WebSocket Manager (AC: 3)
  - [x] Copy `app/utils/websocket_manager.py`
  - [x] Copy `app/utils/retry_decorator.py`
- [x] Task 4: Manual Testing (AC: 2, 3)
  - [x] Test candle fetching
  - [x] Test WebSocket connection
  - [x] Verify no import errors

## Dev Notes

- **File Size:** 1036 lines (large file)
- **Dependencies:** hyperliquid-python-sdk, eth_account
- **WebSocket:** Managed separately, keep integration
- **No logic changes:** Pure copy + import updates

### Project Structure Notes

- New directory: `app/trading/`
- New file: `app/trading/hyperliquid_service.py`
- New file: `app/trading/websocket_manager.py`
- New file: `app/trading/retry_decorator.py`

### References

- [Epic 4 Migration Plan](file:///C:/Users/User/.gemini/antigravity/brain/79cf2554-791d-4819-a5a4-2c8ab667e31a/epic4-migration-plan.md)
- [Legacy Service](file:///c:/Users/User/Desktop/novabot/_legacy_backup/app/services/hyperliquid_service.py)

## Dev Agent Record

### Agent Model Used

Antigravity (Claude 4.5 Sonnet)

### Debug Log References

- Created `app/trading/` directory
- Copied 3 files from legacy (1036+ lines total)
- Updated imports to use `app.trading.*`
- No import errors detected

### Completion Notes List

- ✅ Created trading module structure
- ✅ Copied HyperliquidService (1036 lines)
- ✅ Copied WebSocketPriceManager
- ✅ Copied retry decorators
- ✅ Updated all imports to new structure
- ✅ Preserved all existing functionality

### File List

- `app/trading/__init__.py` (NEW)
- `app/trading/hyperliquid_service.py` (NEW - 1036 lines)
- `app/trading/websocket_manager.py` (NEW)
- `app/trading/retry_decorator.py` (NEW)
