---
stepsCompleted: ['step-01-validate', 'step-02-design', 'step-03-create', 'step-04-final-validation']
inputDocuments:
  - prd.md
  - architecture.md
  - ux-design-specification.md
---

# Novabot - Epic Breakdown

## Overview

This document provides the complete epic and story breakdown for Novabot, decomposing the requirements from the PRD, UX Design if it exists, and Architecture requirements into implementable stories.

## Requirements Inventory

### Functional Requirements

FR1: **Morning Check Dashboard**: Dashboard must display PnL, Running Status (Green/Red), and Active Positions in < 2 seconds.
FR2: **Panic Mode**: User must be able to pause/stop the bot ('Emergency Stop') and view capital security status immediately.
FR3: **AI Explanation**: Every trade (or signal rejection) must have an associated human-readable AI rationale displayed in the logs.
FR4: **Trading Engine Integration**: System must interface with Hyperliquid for real-time market data and trade execution via existing Python backend.
FR5: **Notifications**: Send Push/Discord/Telegram alerts for trades and daily PnL summaries.
FR6: **Mobile First**: UI must be optimized for mobile usage (Bottom Navigation, Thumb Zones, PWA installation).
FR7: **Log Drill-Down**: Ability to view detailed technical logs and AI reasoning layers (Progressive Disclosure).
FR8: **Safety Switch**: Mechanism to manually or automatically halt trading during volatility.

### NonFunctional Requirements

NFR1: **Resilience (Stateless Recovery)**: System must recover state from `bot_state.json` and Exchange reconciliation after any crash or restart.
NFR2: **Performance**: Dashboard First Contentful Paint (FCP) must be < 2 seconds.
NFR3: **Security**: API Keys stored only in local `.env`, never exposed to client side.
NFR4: **No Refactoring**: New development must NOT refactor existing Python backend logic (Immutable Backend Rule).
NFR5: **Reliability**: 99.9% uptime target (7/7 stability without manual intervention).
NFR6: **Accessibility**: High Contrast (AA) compliance for Dark Mode interface.

### Additional Requirements

**Technical (Architecture):**
- **Immutable Backend**: `app/` and `backend/` are Read-Only.
- **Frontend Stack**: Next.js 14, Tailwind CSS, Shadcn/UI.
- **Integration**: REST API Polling (1s interval) on `localhost:8001`, No Authentication.
- **State Management**: Server State Sync (SWR/React Query).
- **Naming Convention**: Frontend interfaces must mirror Python Backend `snake_case` types; UI state use `camelCase`.
- **Project Structure**: Strict adherence to `frontend-v3/` directory structure.

**UX (Design Specification):**
- **Theme**: "Dark Void" (Neutral-950 background, Emerald-400 profit, Rose-500 loss).
- **Navigation**: "One Brain, Two Faces" - Bottom Nav for Mobile, Sidebar for Desktop.
- **Patterns**: "Status Density" (Compact Pills), "Safe Actions" (Confirmation Dialogs for money ops).
- **Experience**: "Silence is Golden" - Alert only on critical issues.

### FR Coverage Map

FR1 (Morning Check): Epic 1 - Dashboard Core
FR2 (Panic Mode): Epic 2 - Safety & Control
FR3 (AI Explanation): Epic 3 - Trust & Logs
FR4 (Trading Engine): Epic 1 - API Connection
FR5 (Notifications): Epic 3 - Notifications (part of Trust/Monitoring)
FR6 (Mobile First): Epic 4 - Mobile Polish (and foundational in Epic 1)
FR7 (Log Drill-Down): Epic 3 - Logs Widget
FR8 (Safety Switch): Epic 2 - Panic Button

## Epic List

### Epic 1: The "Morning Check" (Core Value)
**Goal**: In < 2s, the user knows if they are profitable and safe. This covers 80% of daily usage.
**User Outcome**: "I can open the app, see a green status and positive PnL, and close it immediately with peace of mind."
**FRs covered**: FR1, FR4, FR6 (Partial), NFR2, NFR4.

### Epic 2: Safety & Control (Panic Mode)
**Goal**: Provide immediate manual control in case of market crash or bot malfunction.
**User Outcome**: "I can stop the bot and close positions instantly if I feel unsafe."
**FRs covered**: FR2, FR8, NFR3.

### Epic 3: Trust & Transparency (The "Why")
**Goal**: Transform the "Black Box" into a "Co-pilot" by explaining decisions in human terms.
**User Outcome**: "I understand why the bot took (or rejected) a trade without reading raw JSON."
**FRs covered**: FR3, FR7, NFR1, FR5.

### Epic 4: Mobile Polish (The Companion)
**Goal**: Ensure the app feels native and reliable on mobile devices.
**User Outcome**: "I can use the app with one hand, install it on my home screen, and it feels like a native app."
**FRs covered**: FR6 (Complete), NFR6.

## Epic 1: The "Morning Check" (Core Value)

**Goal:** In < 2s, the user knows if they are profitable and safe. This covers 80% of daily usage.

### Story 1.1: Backend API "Status" Endpoint

As a Frontend Developer,
I want a unified status API endpoint,
So that I can fetch all necessary dashboard data (PnL, Status, Positions) in a single request without auth.

**Acceptance Criteria:**

**Given** The python bot is running with `bot_state.json` populated
**When** I send a GET request to `/api/status`
**Then** It returns a JSON object with: `running` (bool), `daily_pnl` (float), `active_positions` (int), and `last_updated` (timestamp)
**And** The response time is < 50ms
**And** No authentication header is required (Open Access per Architecture)

### Story 1.2: Frontend Skeleton & PWA Setup

As a Mobile User,
I want to install the application on my phone's home screen,
So that I can access it instantly like a native app.

**Acceptance Criteria:**

**Given** A fresh Next.js 14 installation
**When** I visit the site on a mobile device and select "Add to Home Screen"
**Then** It installs with the correct icon and name "Novabot" (manifest.json)
**And** It opens in standalone mode (no browser URL bar)
**And** The UI defaults to "Dark Void" theme (Tailwind config)

### Story 1.3: "Morning Stats" UI Implementation

As a Serene Investor,
I want to see my Daily PnL and Bot Status immediately upon opening the app,
So that I can verify everything is fine in under 2 seconds.

**Acceptance Criteria:**

**Given** The app is opened
**When** The data loads from `/api/status`
**Then** I see a "Status Pill" (Green "RUNNING" or Red "STOPPED")
**And** I see a large PnL Card (Green text if > 0, Orange/Neutral if < 0)
**And** Use `SWR` or `React Query` to poll this data every 1 second
**And** If the API is unreachable, a "CONNECTION LOST" warning banner appears

## Epic 2: Safety & Control (Panic Mode)

**Goal:** Provide immediate manual control in case of market crash or bot malfunction.

### Story 2.1: Backend "Control" Endpoints

As a Frontend Developer,
I want REST endpoints to start and stop the bot's trading engine,
So that I can build a control interface for the user.

**Acceptance Criteria:**

**Given** The python bot is running
**When** I send a POST request to `/api/stop`
**Then** The bot immediately ceases looking for new trades
**And** `bot_state.json` is updated to reflect `trading_enabled=False`
**And** The existing "Stateless Recovery" logic honors this persistent state on restart

### Story 2.2: "Emergency Stop" UI Component

As a User in Panic,
I want a clearly visible "Emergency Stop" button,
So that I can halt the system requires double confirmation to avoid accidents.

**Acceptance Criteria:**

**Given** The dashboard is open and bot is RUNNING
**When** I click the "STOP TRADING" button
**Then** A confirmation dialog appears (Shadcn Dialog) asking "Are you sure? This will halt new trades."
**When** I confirm
**Then** The UI Optimistically updates status to "STOPPING..."
**And** A call is made to `POST /api/stop`
**And** Upon success, the UI updates to "STOPPED" (Red Pill)

### Story 2.3: Global System Alerting

As a User,
I want to know immediately if the bot is in a stopped or error state,
So that I don't mistakenly believe I am being protected when I am not.

**Acceptance Criteria:**

**Given** The bot status is `STOPPED` or `ERROR`
**When** I view any page of the app
**Then** A persistent "Status Bar" (Border or Banner) clearly indicates the danger state
**And** The "Pulse Line" (Top border) turns Red/Orange
**And** This state persists until I explicitly restart the bot via UI

## Epic 3: Trust & Transparency (The "Why")

**Goal:** Transform the "Black Box" into a "Co-pilot" by explaining decisions in human terms.

### Story 3.1: Backend "Logs & Rationale" Endpoint

As a Frontend Developer,
I want to retrieve structured logs from the backend,
So that I can display them in the UI with semantic highlighting (Error vs Info).

**Acceptance Criteria:**

**Given** The python bot is logging activities using `trade_recorder.py`
**When** I send a GET request to `/api/logs?limit=50`
**Then** It returns the last 50 log entries in JSON format
**And** Each entry contains: `timestamp`, `level` (INFO/ERROR), `message`, and optional `metadata` JSON object
**And** The `metadata` object contains AI reasoning tags (e.g. `{"veto": "RSI_HIGH"}`) if available

### Story 3.2: "AI Meaning" UI Card

As a Serene Investor,
I want to see the "Why" of the last significant action on the dashboard,
So that I understand the bot's decision without reading technical logs.

**Acceptance Criteria:**

**Given** The bot has recently taken an action or rejected a signal
**When** I look at the "Co-pilot" card on the dashboard
**Then** I see a human-readable summary (e.g., "Trade Rejected: Market Overbought (RSI 82)")
**And** This summary is derived from the latest log entry with `metadata`
**And** It uses a "Clean" UI style (Icon + Text) consistent with "Dark Void" theme

### Story 3.3: Detailed Logs Viewer ("Drill Down")

As an Operator,
I want to view the full history of bot actions,
So that I can audit behavior during weekends or investigations.

**Acceptance Criteria:**

**Given** I am on the dashboard
**When** I click "View Logs" or navigate to the Logs Tab
**Then** I see a scrollable list of recent logs
**And** Errors are highlighted in Red (`text-rose-500`)
**And** Info/Success messages are Green/Blue
**And** I can see the timestamp for every entry

## Epic 4: Mobile Polish (The Companion)

**Goal:** Ensure the app feels native and reliable on mobile devices.

### Story 4.1: PWA Configuration

As a Mobile User,
I want the app to behave like a native application,
So that I don't see browser chrome (URL bars) taking up valuable screen space.

**Acceptance Criteria:**

**Given** The application is deployed
**When** I inspect the `manifest.json`
**Then** It contains valid `start_url`, `display: standalone`, and high-res icons (192/512)
**And** The `viewport` meta tag prevents accidental zooming on inputs (`maximum-scale=1`)
**And** The Status Bar color matches the "Dark Void" theme background

### Story 4.2: Responsive Layout Strategy

As a User with multiple devices,
I want an interface optimized for the device I am currently holding,
So that I am not forced to use a "shrunken desktop site" on my phone.

**Acceptance Criteria:**

**Given** I am on a Mobile device (<768px)
**Then** The Sidebar is HIDDEN and the Bottom Navigation Bar is VISIBLE
**Given** I am on a Desktop device (>1024px)
**Then** The Sidebar is VISIBLE and the Bottom Navigation Bar is HIDDEN
**And** The layout shifts to a 3-column grid (Nav / Main Content / Logs)

### Story 4.3: Touch Optimization (Thumb Zone)

As a User on the go,
I want to interact with the app using one hand,
So that I can use it comfortably while holding a coffee.

**Acceptance Criteria:**

**Given** I am viewing the Dashboard on mobile
**Then** Critical actions (Panic Button) are located in the bottom 30% of the screen (Thumb Zone)
**And** All touch targets are at least 44x44 pixels
**And** Safe Area padding is applied to avoid overlap with iPhone Home Indicator

## Epic 5: Advanced Control & Insights (The Pro)
**Goal**: Provide deep control over bot behavior and clear performance metrics for advanced users.
**User Outcome**: "I can swap strategies mid-flight and see exactly why the AI is making specific decisions based on indicators."
**FRs covered**: FR3 (Enhanced), FR8 (Refined), FR7 (Drill-Down).

### Story 5.1: Strategy Selector
As a Trader,
I want to select the active trading strategy from the UI,
So that I can adapt to changing market conditions without editing config files.

**Acceptance Criteria:**
- [ ] Dropdown menu in the Settings panel listing all available strategies.
- [ ] Displays the current active strategy as selected.
- [ ] Changing selection calls `POST /api/settings/update`.
- [ ] UI shows a loading state during the update and confirmation toast on success.

### Story 5.2: Enhanced AI Rationale (Metadata Visualization)
As a Serene Investor,
I want the "Copilot" card to show specific indicator values (RSI, ADX) that caused a decision,
So that I have full transparency on the AI's logic.

**Acceptance Criteria:**
- [ ] "Copilot" card displays tags or badges for the primary indicators involved in the latest decision.
- [ ] Shows the specific value (e.g., "RSI: 75") if available in the log metadata.
- [ ] Color-coded badges (Emerald for positive, Amber for warning/veto).

### Story 5.3: Performance Analytics Chart
As an Operator,
I want to see a history of PnL performance over time,
So that I can evaluate the strategy's consistency.

**Acceptance Criteria:**
- [ ] Line chart showing cumulative PnL over the last 7 days/30 days.
- [ ] Toggle between different timeframes.
- [ ] Tooltip showing details on hover.

