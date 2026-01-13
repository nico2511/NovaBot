# Story 3.2: Admin Manual Override

Status: done

## Story

As a System Administrator,
I want to manually override a user's tier for debugging,
So that I can test tier-specific features without changing equity.

## Acceptance Criteria

1.  **Given** I am an admin
    **When** I call `POST /api/v1/admin/override-tier` with a tier
    **Then** The user's tier is overridden
2.  **And** The override persists until removed
3.  **And** I can remove the override with `DELETE /api/v1/admin/override-tier`

## Tasks / Subtasks

- [x] Task 1: Create Admin Endpoint (AC: 1, 2, 3)
  - [x] Create `app/api/routes/admin.py`
  - [x] Implement `POST /override-tier` endpoint
  - [x] Implement `DELETE /override-tier` endpoint
  - [x] Store override in database or config
- [x] Task 2: Update Tier Calculator (AC: 1, 2)
  - [x] Check for override before calculating tier
  - [x] Return override tier if exists
- [x] Task 3: Test Override (AC: 1, 2, 3)
  - [x] Test setting override
  - [x] Test removing override
  - [x] Verify tier calculation respects override

## Dev Notes

- **Security:** For now, no auth (dev environment). Add auth in production.
- **Storage:** Simple in-memory dict or SQLite table
- **Priority:** Override > Calculated tier

### Project Structure Notes

- New file: `app/api/routes/admin.py`
- Modified: `app/gamification/tier_calculator.py`
- Modified: `main.py` (add admin router)

### References

- [PRD](file:///_bmad-output/planning-artifacts/prd.md) - FR5: Admin Manual Override

## Dev Agent Record

### Agent Model Used

Antigravity (Claude 4.5 Sonnet)

### Debug Log References

- Admin routes created with override endpoints
- TierCalculator updated to check for override first
- In-memory storage used for dev (tier_override dict)
- Admin router registered in main app

### Completion Notes List

- ✅ Created admin routes (`POST`, `DELETE`, `GET /override-tier`)
- ✅ Updated TierCalculator to check override before calculation
- ✅ In-memory storage for tier overrides (dev environment)
- ✅ Admin router registered in main app
- ✅ Override priority: Admin Override > Calculated Tier

### File List

- `app/api/routes/admin.py` (NEW)
- `app/gamification/tier_calculator.py` (MODIFIED)
- `main.py` (MODIFIED)
