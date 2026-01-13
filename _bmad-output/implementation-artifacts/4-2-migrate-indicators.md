# Story 4.2: Migrate Indicators Service

Status: done

## Story

As a Developer,
I want to migrate the Indicators service to the new architecture,
So that technical indicators are available for strategy calculations.

## Acceptance Criteria

1.  **Given** The Indicators service exists in `_legacy_backup/`
    **When** I migrate it to `app/trading/`
    **Then** All indicators (RSI, EMA, SMA, ATR, ADX, Bollinger) are available
2.  **And** No import changes needed (pure Pandas implementation)
3.  **And** TaAdapter compatibility layer is preserved

## Tasks / Subtasks

- [x] Task 1: Copy Indicators Service (AC: 1, 2, 3)
  - [x] Copy from `_legacy_backup/app/services/indicators.py`
  - [x] No changes needed (pure Pandas)
- [x] Task 2: Update Trading Module Init (AC: 1)
  - [x] Export indicators in `__init__.py`
- [x] Task 3: Verify Indicators (AC: 1)
  - [x] Test RSI calculation
  - [x] Test EMA calculation
  - [x] Verify TaAdapter works

## Dev Notes

- **File Size:** 103 lines (small, simple)
- **Dependencies:** pandas, numpy only
- **No changes needed:** Pure Pandas implementation
- **Compatibility:** TaAdapter mimics pandas_ta

### Project Structure Notes

- New file: `app/trading/indicators.py`
- Modified: `app/trading/__init__.py`

### References

- [Epic 4 Migration Plan](file:///C:/Users/User/.gemini/antigravity/brain/79cf2554-791d-4819-a5a4-2c8ab667e31a/epic4-migration-plan.md)
- [Legacy Indicators](file:///c:/Users/User/Desktop/novabot/_legacy_backup/app/services/indicators.py)

## Dev Agent Record

### Agent Model Used

Antigravity (Claude 4.5 Sonnet)

### Debug Log References

- Copied indicators.py (103 lines)
- No import changes needed
- Pure Pandas implementation preserved

### Completion Notes List

- ✅ Copied Indicators service (103 lines)
- ✅ All 6 indicators available (RSI, EMA, SMA, ATR, ADX, Bollinger)
- ✅ TaAdapter compatibility layer preserved
- ✅ No changes needed (pure Pandas)

### File List

- `app/trading/indicators.py` (NEW - 103 lines)
- `app/trading/__init__.py` (MODIFIED)
