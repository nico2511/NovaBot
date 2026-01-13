# Story 1.2: Tier Calculation Engine

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a Trader,
I want the system to calculate my Tier (Nebula/Protostar/Supernova) based on my Equity,
So that I receive the correct status and privileges.

## Acceptance Criteria

1.  **Given** A User has an Equity balance (mock or real)
    **When** The `TierCalculator.calculate(equity)` service is called
    **Then** It returns the correct Enum (NEBULA if < 100, PROTOSTAR if < 500, SUPERNOVA if > 500)
2.  **And** The logic handles edge cases (0 equity, exactly 100) according to PRD

## Tasks / Subtasks

- [x] Task 1: Create Tier Enum (AC: 1)
  - [x] Create `app/gamification/enums.py`
  - [x] Define `TierEnum` with NEBULA, PROTOSTAR, SUPERNOVA
  - [x] Add tier thresholds as constants
- [x] Task 2: Implement TierCalculator Service (AC: 1, 2)
  - [x] Create `app/gamification/tier_calculator.py`
  - [x] Implement `calculate(equity: float) -> TierEnum` method
  - [x] Handle edge cases (0, negative, exactly 100, exactly 500)
- [x] Task 3: Add Unit Tests (AC: 1, 2)
  - [x] Create `tests/test_tier_calculator.py`
  - [x] Test all tier boundaries
  - [x] Test edge cases

## Dev Notes

- **Business Logic:** 
  - Equity < 100 → NEBULA
  - 100 ≤ Equity < 500 → PROTOSTAR
  - Equity ≥ 500 → SUPERNOVA
- **Edge Cases:** Handle 0, negative values (default to NEBULA), exact boundary values.
- **Architecture:** Pure business logic, no database dependency yet.

### Project Structure Notes

- New file: `app/gamification/enums.py`
- New file: `app/gamification/tier_calculator.py`
- Test file: `tests/test_tier_calculator.py`

### References

- [PRD](file:///_bmad-output/planning-artifacts/prd.md) - FR1: Tier Calculation
- [Architecture Document](file:///_bmad-output/planning-artifacts/architecture.md)
- [Project Context](file:///_bmad-output/planning-artifacts/project-context.md)

## Dev Agent Record

### Agent Model Used

Antigravity (Claude 4.5 Sonnet)

### Debug Log References

- TierEnum created with 3 tiers and thresholds
- TierCalculator implemented with static method
- All 7 unit tests passed (0.05s)

### Completion Notes List

- ✅ Created `TierEnum` with NEBULA, PROTOSTAR, SUPERNOVA values
- ✅ Implemented `TierCalculator.calculate()` with proper business logic
- ✅ Handled all edge cases: zero, negative, exact boundaries (100, 500)
- ✅ Comprehensive test coverage: 7 tests covering all scenarios
- ✅ All tests passed successfully

### File List

- `app/gamification/enums.py`
- `app/gamification/tier_calculator.py`
- `tests/test_tier_calculator.py`
