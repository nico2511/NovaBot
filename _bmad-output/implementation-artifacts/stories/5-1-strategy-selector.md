# Story 5.1: Strategy Selector

Status: done

## Story

As a Trader,
I want to select the active trading strategy from the UI,
So that I can adapt to changing market conditions without editing config files.

## Acceptance Criteria

1. **Available Strategies List**: Fetch available strategies from the backend (or local config).
2. **Current Selection**: Display the currently active strategy as the default selection in a dropdown.
3. **Update Mechanism**: Selecting a new strategy triggers a `POST /api/settings/update` or equivalent.
4. **Loading & Feedback**: Show a loading spinner during update; show a toast notification on success/error.
5. **UI Location**: Placed within the "Settings" or "Advanced Settings" panel.

## Tasks / Subtasks

- [ ] Fetch Available Strategies #frontend
    - [ ] Add endpoint call to `lib/api.ts` (e.g., `GET /api/meta/strategies`)
    - [ ] Create a hook or state to store available strategies
- [ ] Create Dropdown Component #frontend
    - [ ] Use Shadcn/UI Select component
    - [ ] Populate with strategy names
- [ ] Implement Update Logic #frontend
    - [ ] Handle `onChange` event to call update API
    - [ ] Implement optimistic update or reload data after change
- [ ] Add Toasts for Feedback #frontend
    - [ ] Install/Configure Shadcn Toast if not present
    - [ ] Show success/error messages

## Dev Notes

### Architecture Constraints
- **API**: Check if backend supports `GET /api/meta/strategies` and `POST /api/settings/update`.
- **Consistency**: Use existing Shadcn theme.

### Source Tree Components
- [MODIFY] `frontend-v3/lib/api.ts`
- [MODIFY] `frontend-v3/components/ConfigPanel.tsx` (or similar)
- [NEW] `frontend-v3/components/StrategySelector.tsx`
