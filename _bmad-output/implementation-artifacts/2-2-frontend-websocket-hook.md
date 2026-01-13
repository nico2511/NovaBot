# Story 2.2: Frontend WebSocket Hook & API Migration

Status: done

## Story

As a Frontend Developer,
I want to use WebSocket for real-time gamification updates instead of polling,
So that the UI reflects tier changes instantly (< 1s).

## Acceptance Criteria

1.  **Given** The frontend is running
    **When** I connect to the backend
    **Then** A WebSocket connection is established to `ws://localhost:8000/ws/gamification`
2.  **And** The `useGamification` hook receives real-time tier updates
3.  **And** The API URL is corrected from `8001` to `8000`

## Tasks / Subtasks

- [x] Task 1: Update Environment Variables (AC: 3)
  - [x] Update `frontend/.env.local` (API URL 8001 → 8000)
  - [x] Add `NEXT_PUBLIC_WS_URL` for WebSocket
- [x] Task 2: Create WebSocket Hook (AC: 1)
  - [x] Create `frontend/hooks/useWebSocket.ts`
  - [x] Handle connection, reconnection, message handling
- [x] Task 3: Update Gamification Hook (AC: 2)
  - [x] Update `frontend/hooks/useGamification.ts`
  - [x] Add WebSocket support with polling fallback
  - [x] Test real-time updates
- [x] Task 4: Manual Testing (AC: 1, 2, 3)
  - [x] Start frontend and verify WebSocket connection
  - [x] Test real-time updates

## Dev Notes

- **WebSocket URL:** `ws://localhost:8000/ws/gamification`
- **Fallback:** Keep polling as fallback if WebSocket fails
- **Reconnection:** Auto-reconnect on disconnect with exponential backoff
- **Compatibility:** Use legacy endpoint during transition

### Project Structure Notes

- Modified: `frontend/.env.local`
- New file: `frontend/hooks/useWebSocket.ts`
- Modified: `frontend/hooks/useGamification.ts`

### References

- [Epic 2 Implementation Plan](file:///C:/Users/User/.gemini/antigravity/brain/79cf2554-791d-4819-a5a4-2c8ab667e31a/epic2-implementation-plan.md)
- [Story 2.1](file:///c:/Users/User/Desktop/novabot/_bmad-output/implementation-artifacts/2-1-websocket-compatibility-api.md)

## Dev Agent Record

### Agent Model Used

Antigravity (Claude 4.5 Sonnet)

### Debug Log References

- API URL corrected: 8001 → 8000
- WebSocket URL added to environment
- useWebSocket hook created with auto-reconnect (max 5 attempts, 3s interval)
- useGamification updated with WebSocket + polling fallback

### Completion Notes List

- ✅ Updated `.env.local` with correct API URL and WebSocket URL
- ✅ Created `useWebSocket` hook with auto-reconnect and error handling
- ✅ Updated `useGamification` to use WebSocket with polling fallback
- ✅ WebSocket connection status exposed via `isWebSocketConnected`
- ✅ Graceful degradation: falls back to polling if WebSocket fails

### File List

- `frontend/.env.local` (MODIFIED)
- `frontend/hooks/useWebSocket.ts` (NEW)
- `frontend/hooks/useGamification.ts` (MODIFIED)
