# Story 1.3: "Morning Stats" UI Implementation

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a Serene Investor,
I want to see my Daily PnL and Bot Status immediately upon opening the app,
So that I can verify everything is fine in under 2 seconds.

## Acceptance Criteria

1. **Status Pill Display**: Shows "RUNNING" (green) or "STOPPED" (red) based on bot status.
2. **PnL Card Display**: Large, prominent display of daily PnL with color coding (green if > 0, red/orange if < 0).
3. **Data Polling**: Uses SWR or React Query to poll `/api/status` every 1 second.
4. **Connection Error Handling**: Shows "CONNECTION LOST" warning banner if API is unreachable.
5. **Performance**: Initial render < 2 seconds, smooth updates without flicker.
6. **Responsive Design**: Works on mobile (primary) and desktop.

## Tasks / Subtasks

- [x] Install Data Fetching Library #frontend
    - [x] Install SWR (`npm install swr`)
    - [x] Create API client utility
- [x] Create Status Pill Component #frontend
    - [x] Display running/stopped state with color coding
    - [x] Use Tailwind classes for styling
- [x] Create PnL Card Component #frontend
    - [x] Display daily PnL with large, readable text
    - [x] Apply profit (green) / loss (red) color based on value
    - [x] Show active positions count
- [x] Integrate API Polling #frontend
    - [x] Create SWR hook for `/api/status` endpoint
    - [x] Configure 1-second refresh interval
    - [x] Handle loading and error states
- [x] Add Connection Error Banner #frontend
    - [x] Show warning when API fetch fails
    - [x] Auto-hide when connection restored
- [x] Update Main Page #frontend
    - [x] Replace placeholder with dashboard components
    - [x] Test responsive layout

## Dev Notes

### Architecture Constraints
- **API Endpoint**: `GET http://localhost:8001/api/status` (from Story 1.1)
- **Data Structure**: `{ is_running: bool, daily_pnl: float, active_positions: int, last_updated: string }`
- **Styling**: Use custom Tailwind colors (`profit`, `loss`, `void`) from Story 1.2
- **Performance**: Optimize re-renders, use React.memo where needed

### Source Tree Components
- [NEW] `frontend-v3/lib/api.ts` (API client)
- [NEW] `frontend-v3/components/StatusPill.tsx`
- [NEW] `frontend-v3/components/PnLCard.tsx`
- [MODIFY] `frontend-v3/app/page.tsx`

### References
- [Story 1.1]: Backend API `/api/status` endpoint
- [Story 1.2]: Tailwind theme configuration
- [UX Design]: "Morning Check" under 2 seconds

## Dev Agent Record

### Agent Model Used
- Sm (Scrum Master)

### Completion Notes List
- Installed SWR for data fetching with 1-second polling interval.
- Created API client (`lib/api.ts`) with TypeScript types matching backend.
- Built StatusPill component with green/red color coding for running/stopped states.
- Built PnLCard component with dynamic color (profit=green, loss=red, neutral=gray).
- Integrated SWR polling in main page with loading, error, and success states.
- Added fixed connection error banner that appears when API is unreachable.
- Implemented responsive design for mobile and desktop.
- Build successful - all TypeScript types validated.

### File List
- `frontend-v3/lib/api.ts` (Created)
- `frontend-v3/components/StatusPill.tsx` (Created)
- `frontend-v3/components/PnLCard.tsx` (Created)
- `frontend-v3/app/page.tsx` (Modified)
