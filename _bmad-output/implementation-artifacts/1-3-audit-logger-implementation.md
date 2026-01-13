# Story 1.3: Audit Logger Implementation

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a Compliance Officer (User),
I want every AI decision to be logged with a snapshot of all indicators,
So that I can audit "Why the IA said No" later.

## Acceptance Criteria

1.  **Given** A strategy makes a decision (Buy/Sell/Hold)
    **When** The `AuditService.log_decision()` is called
    **Then** A new row is inserted into `decision_logs` table
2.  **And** The row contains: Timestamp, StrategyName, AI_Persona, Verdict, Reasoning, AND a JSON Snapshot of all indicators
3.  **And** The operation is non-blocking (async)

## Tasks / Subtasks

- [x] Task 1: Create AuditService (AC: 1, 2, 3)
  - [x] Create `app/services/audit_service.py`
  - [x] Implement async `log_decision()` method
  - [x] Accept parameters: strategy_name, ai_persona, verdict, reasoning, indicators_snapshot
  - [x] Insert into `decision_logs` table using SQLAlchemy
- [x] Task 2: Add Unit Tests (AC: 1, 2, 3)
  - [x] Create `tests/test_audit_service.py`
  - [x] Test successful logging
  - [x] Test async operation
  - [x] Verify JSON snapshot storage

## Dev Notes

- **Critical Requirement:** MUST log ALL indicators at instant T (from project-context.md)
- **Database:** Use existing `decision_logs` table from `app/services/models.py`
- **Async:** Use SQLAlchemy async session or run in thread pool
- **JSON Storage:** `indicators_snapshot` column accepts JSON dict

### Project Structure Notes

- New file: `app/services/audit_service.py`
- Test file: `tests/test_audit_service.py`
- Uses existing: `app/services/models.py` (DecisionLog)

### References

- [PRD](file:///_bmad-output/planning-artifacts/prd.md) - NFR3: Auditability
- [Architecture Document](file:///_bmad-output/planning-artifacts/architecture.md)
- [Project Context](file:///_bmad-output/planning-artifacts/project-context.md) - User Indicator Audit requirement

## Dev Agent Record

### Agent Model Used

Antigravity (Claude 4.5 Sonnet)

### Debug Log References

- AuditService created with async and sync methods
- 4 unit tests passed (0.92s)
- JSON snapshot storage verified with complex nested objects

### Completion Notes List

- ✅ Created `AuditService` with both async and sync logging methods
- ✅ Implemented complete indicator snapshot storage as JSON
- ✅ Verdict normalization to uppercase
- ✅ Non-blocking async operation confirmed
- ✅ All tests passed: sync logging, async logging, JSON storage, verdict normalization

### File List

- `app/services/audit_service.py`
- `tests/test_audit_service.py`
