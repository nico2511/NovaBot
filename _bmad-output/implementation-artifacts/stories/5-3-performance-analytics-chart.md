# Story 5.3: Performance Analytics Chart

## User Story
As an Operator,
I want to see a history of PnL performance over time,
So that I can evaluate the strategy's consistency.

## Prerequisites
- [x] Backend `POST /api/history/equity` or similar endpoint to fetch historical PnL data.
- [x] Basic charting library setup (Lightweight Charts used in Epic 1).

## Tasks
- [ ] **Data Fetching**:
    - [ ] Create `useEquityHistory` hook using SWR to fetch data from `/api/history/equity`.
    - [ ] Verify the backend endpoint returns timestamped equity snapshots.
- [ ] **Chart Component**:
    - [ ] Create `PerformanceChart.tsx` using `lightweight-charts`.
    - [ ] Configure it as a Line Series (or Area Series) for equity curve.
    - [ ] Add support for dynamic meaningful colors (Green if profitable, Red if drawdown).
    - [ ] Implement responsiveness for mobile view.
- [ ] **Integration**:
    - [ ] Add the `PerformanceChart` to a new "Analytics" tab or section in the main dashboard.
    - [ ] Add generic "Timeframe" controls (24H, 7D, 30D, ALL) if backend supports filtering.

## Acceptance Criteria
- [ ] Line chart showing cumulative PnL over the last 7 days/30 days.
- [ ] Toggle between different timeframes.
- [ ] Tooltip showing details on hover.
- [ ] Chart handles "no data" or "loading" states gracefully.
