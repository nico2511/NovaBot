# Story 2.2: "Emergency Stop" UI Component

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a User in Panic,
I want a clearly visible "Emergency Stop" button,
So that I can halt the system with double confirmation to avoid accidents.

## Acceptance Criteria

1. **Button Visibility**: "STOP TRADING" button is prominently displayed when bot is RUNNING.
2. **Confirmation Dialog**: Clicking the button shows a confirmation dialog (Shadcn/UI Dialog).
3. **Dialog Content**: Clear message "Are you sure? This will halt new trades."
4. **Optimistic Update**: UI shows "STOPPING..." state immediately after confirmation.
5. **API Integration**: Calls `POST /api/engine/stop` from Story 2.1.
6. **Success State**: Upon success, StatusPill updates to "STOPPED" (red).
7. **Error Handling**: Shows error message if API call fails.
8. **Reverse Action**: "START TRADING" button appears when bot is STOPPED.

## Tasks / Subtasks

- [x] Install Shadcn/UI Dialog Component #frontend
    - [x] Initialize Shadcn/UI in project
    - [x] Install Dialog component
- [x] Create ControlButtons Component #frontend
    - [x] Show "STOP TRADING" button when running
    - [x] Show "START TRADING" button when stopped
    - [x] Use danger/success styling
- [x] Implement Confirmation Dialog #frontend
    - [x] Create confirmation dialog with Shadcn Dialog
    - [x] Add clear warning message
    - [x] Include Cancel and Confirm buttons
- [x] Integrate API Calls #frontend
    - [x] Add stop/start functions to API client
    - [x] Handle optimistic UI updates
    - [x] Handle loading and error states
- [x] Update Main Page #frontend
    - [x] Add ControlButtons below PnL Card
    - [x] Test user flow (click → confirm → update)

## Dev Notes

### Architecture Constraints
- **UI Library**: Use Shadcn/UI for Dialog component (consistent with UX spec).
- **API Endpoints**: `POST /api/engine/stop` and `POST /api/engine/start` (from Story 2.1).
- **Optimistic Updates**: Update UI immediately, revert on error.
- **Error Handling**: Use toast notifications for errors.

### Source Tree Components
- [NEW] `frontend-v3/components/ui/dialog.tsx` (Shadcn component)
- [NEW] `frontend-v3/components/ControlButtons.tsx`
- [MODIFY] `frontend-v3/lib/api.ts` (add stop/start functions)
- [MODIFY] `frontend-v3/app/page.tsx`

### References
- [Story 2.1]: Backend control endpoints
- [UX Design]: Shadcn/UI component library
- [Architecture]: Panic Mode requirement

## Dev Agent Record

### Agent Model Used
- Sm (Scrum Master)

### Completion Notes List
- Installed Shadcn/UI (new package, not deprecated shadcn-ui).
- Installed Dialog and Button components from Shadcn/UI.
- Created ControlButtons component with conditional rendering (stop/start).
- Implemented confirmation dialog with clear warning message.
- Added stopEngine() and startEngine() functions to API client.
- Integrated ControlButtons into main page below PnL Card.
- Used SWR mutate() for manual revalidation after API calls.
- Implemented loading states ("STOPPING...", "STARTING...").
- Added error handling with user-friendly error messages.

### File List
- `frontend-v3/lib/api.ts` (Modified - added stopEngine/startEngine)
- `frontend-v3/components/ControlButtons.tsx` (Created)
- `frontend-v3/components/ui/dialog.tsx` (Created by Shadcn)
- `frontend-v3/components/ui/button.tsx` (Created by Shadcn)
- `frontend-v3/app/page.tsx` (Modified - added ControlButtons)
