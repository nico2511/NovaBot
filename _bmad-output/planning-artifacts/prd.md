---
stepsCompleted: ['step-01-init', 'step-02-discovery', 'step-03-success', 'step-04-journeys', 'step-05-domain', 'step-06-innovation', 'step-07-project-type', 'step-08-scoping', 'step-09-functional', 'step-10-nonfunctional']
inputDocuments: [
  '_bmad-output/analysis/brainstorming-session-2026-01-12.md',
  '_bmad-output/project-knowledge/project-overview.md',
  '_bmad-output/project-knowledge/source-tree-analysis.md',
  'docs/CONTEXT.md',
  'docs/STRATEGIES.md',
  'docs/THEME.md'
]
workflowType: 'prd'
documentCounts:
  briefCount: 0
  researchCount: 0
  brainstormingCount: 1
  projectDocsCount: 5
classification:
  projectType: 'Fintech Application / Trading Bot'
  domain: 'Finance / Crypto'
  complexity: 'High'
  projectContext: 'brownfield'

## Success Criteria

### User Success
1.  **Instant Clarity:** The trader understands their current level (Nebula/Protostar/Supernova) instantly from visual cues (colors, borders) without needing to consult a manual.
2.  **Motivation:** The "hardcore" drop mechanism encourages users to build and maintain a safety margin, creating a "survival" game loop.

### Business Success
1.  **Engagement:** Users strive to reach the "Supernova" tier ($500+), driving portfolio growth.
2.  **Risk Management:** The system naturally filters low-balance users from high-risk strategies, protecting them (and the bot's reputation).

### Technical Success
1.  **Real-time Enforcement:** Level changes (up or down) are reflected in <100ms.
2.  **Security:** Access to restricted strategies is blocked server-side, not just hidden in UI.



## Product Scope

### MVP - Minimum Viable Product
*   **Strict Tiers Logic:** $10 (Nebula) / $100 (Protostar) / $500 (Supernova).
*   **Access Control:** Backend enforcement of strategy/pair restrictions based on level.
*   **Visual Theme:** "Space Evolution" UI (Colors/Badges) in Next.js.
*   **Real-time Updates:** Reactive to Equity changes via WebSocket/Polling.

### Growth Features (Post-MVP)
*   **Leaderboard:** Ranking based on PnL% within each tier.
*   **Social Share:** "I reached Supernova!" generated images.

### Vision (Future)
*   A fully immersive "Trading Game" where the UI evolves into a cockpit dashboard as the user levels up.

## User Journeys

### Journey 1: The Ascension (Success Path)
**Persona:** Luca (The Scalper)
**Context:** Starts with $80 (Nebula Tier).
1.  **Action:** Luca configures the bot on safe pairs (BTC/ETH) allowed by Nebula tier.
2.  **Progression:** After a week of consistent small wins, his equity crosses **$100.01**.
3.  **System Response:** The UI immediately shifts theme from "Nebula Blue" to "Protostar Orange". A visual unlock animation plays.
4.  **Result:** Luca sees new strategies (e.g., SOL/BNB Momentum) become clickable in the "Strategies" tab. He feels rewarded and validated.

### Journey 2: The Fall (Edge Case)
**Persona:** Luca (The Scalper)
**Context:** Has $105 (Protostar Tier), riding the line.
1.  **Event:** A sudden market wick hits a stop-loss. Equity drops to **$98**.
2.  **System Response:** Visual theme strictly reverts to "Nebula Blue" (Darker). Active strategies dependent on Protostar tier are instantly paused.
3.  **Reaction:** Luca sees the immediate consequence. He realizes he needs a safety margin.
4.  **Resolution:** He deposits $20 to reach $118, restoring access and learning the lesson of capital preservation.

### Journey Requirements Summary
*   **Real-time State Monitoring:** Frontend must listen to Equity updates constantly.
*   **Dynamic Theme Switching:** UI components must support "Hot Swapping" of themes.
*   **Conditional Logic:** Strategy buttons must be able to be Disabled/Hidden based on tier state.

## Domain-Specific Requirements

### Compliance & Regulatory
*   **Local Execution:** Bot runs locally/on user VPS. No external user data transmission (GDPR N/A).
*   **Exchange API Rules:** Must respect Hyperliquid API rate limits even when checking balance frequently.

### Technical Constraints
*   **Latency Criticality:** "Check Balance" -> "Authorize Trade" loop must be optimized to not miss market opportunities.
*   **State Integrity:** The "Level" must be recalculated dynamically from the *source of truth* (Exchange via API), never cached stale data.

### Risk Mitigations
*   **API Failure Fallback:** If balance check fails (API down), **Default to Deny** (Secure Fail state) prevents unauthorized trading.
*   **Slippage Protection:** Market orders blocked if visual tier hasn't updated yet? (Addressed by Pre-Trade Check).

## Fintech & Bot Architecture Requirements

### State Management Strategy
*   **Stateless Boot:** The system MUST NOT persist user tier in local files (`bot_state.json`).
*   **Recalculation:** On every startup (and periodic interval), the bot must fetch `Account Summary` from Hyperliquid API and derive the Tier state freshly.
*   **Fail-Safe:** If API is unreachable at boot, the system defaults to "Unverified" state (All trading blocked) until a successful fetch occurs.

### Currency & Precision
*   **Base Asset:** USDC is the only denominator for Tier calculation (Total Equity).
*   **Precision:** Standard 2 decimal places for UI display, but full precision for backend comparison.

### Concurrency
*   **Async Loop:** The "Gamification Watchdog" runs as an independent async task, separate from the "Strategy Execution" loop, updating a shared `BotState` object.

## Project Scoping & Phased Development

### MVP Strategy & Philosophy
**Approach:** "Core First" - Prioritize backend integrity and security before visual polish.
**Critical Requirement:** **Non-Interference**. The new Gamification layer must NOT degrade the performance of existing strategies or cause regression bugs in the core trading loop.

### MVP Feature Set (Phase 1)
1.  **Backend consolidation:** Review and refactor `main_nextjs.py` to ensure `GamificationEngine` integrates cleanly without blocking the main loop.
2.  **Core Logic:** Implement the `check_tier()` function based on API Equity.
3.  **Enforcement:** Add the "Gatekeeper" check in `Strategy.execute()` methods.
4.  **Basic UI:** Simple badge display in Frontend (No themes yet).

### Phase 2: UX "Delight"
1.  **Dynamic Themes:** Implementation of Nebula/Protostar/Supernova themes.
2.  **Visual Feedback:** Animations for level changes.

### Phase 3: Social & Expansion
1.  **Leaderboards:** Global ranking (Optional).
2.  **Social Sharing:** Exportable PnL cards.

### Risk Mitigation Strategy
*   **Regression Testing:** Before Phase 2, a complete suite of tests must verify that "Gamification ON" does not alter the *logic* of trading signals (only access).
*   **Toggle Switch:** A global `ENABLE_GAMIFICATION=False` flag must exist to instantly disable the feature if issues arise.

## Functional Requirements

### 1. Tier Calculation (Core)
*   **FR1:** The system must calculate the user's Tier based on Total Equity (USDC).
*   **FR2:** The specific monetary thresholds ($10/$100/$500) must be configurable in constants/config.
*   **FR3:** The Tier status must be refreshed from the API at startup and at least every 60 seconds.

### 2. Access Control (Permissions)
*   **FR4 (Token Gating):** The system must enforce an **Allowlist of Pairs** specific to each Tier.
    *   *Capability:* If a Strategy signals a trade for a coin NOT in the current Tier's allowlist, the trade is rejected.
*   **FR5 (Risk Gating):** The system must enforce **Max Leverage** or **Max Position Size** limits specific to each Tier.
    *   *Capability:* Higher tiers unlock higher leverage/exposure.
*   **FR6 (Strategy Independence):** The Strategy Logic (e.g., EMA Crossover) remains strictly independent. It generates signals blindly; the Gamification Layer acts as a final "Policy Filter" before execution.

### 3. User Interface (Frontend)
*   **FR7:** The UI must display the user's current Tier (Badge/Icon).
*   **FR8:** The UI must visually indicate which pairs/strategies are "Locked" for the current tier (e.g., Padlock icon).
*   **FR9:** The UI theme (Colors/Borders) must reactively change based on the current Tier.

### 4. System Integrity
*   **FR10:** In case of API failure (cannot fetch balance), the system must default to a "Safe Mode" (No new trades allowed) to prevent unverified execution.
*   **FR11:** Open positions entered under a higher tier must be allowed to close naturally (TP/SL) even if the user downgrades tiers mid-trade.

## Non-Functional Requirements

### Performance
*   **NFR1 (Critical Latency):** The "Gatekeeper" check (Permission to trade) must add **< 5ms** overhead to the strategy execution loop.
*   **NFR2 (UI Responsiveness):** Level changes detected by backend must be reflected in the Frontend within **1 second** (via WebSocket).

### Security & Reliability
*   **NFR3 (Fail-Safe Default):** If the Gamification Module crashes or becomes unresponsive, the system must default to a **"Secure State"** (Trading Blocked) rather than failing open.
*   **NFR4 (Auto-Recovery):** The async loop must incorporate error boundaries to catch exceptions and attempt auto-restart without crashing the main bot process.

### Maintainability
*   **NFR5 (Isolation):** Gamification logic must be encapsulated in `app/core/gamification/`. It must NOT modify the internal logic of `strategies/*.py` files, interacting only via defined interfaces (decorators or status checks).
---

# Product Requirements Document - novabot

**Author:** Nicolas
**Date:** 2026-01-12
