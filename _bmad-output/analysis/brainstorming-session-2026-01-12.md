---
stepsCompleted: [1]
inputDocuments: ['app/core/asset_gamification.py', 'docs/CONTEXT.md', 'docs/STRATEGIES.md', 'docs/THEME.md']
session_topic: 'Refining Gamification Logic & Visuals around Portfolio Growth'
session_goals: '1. Validate/Enhance existing tier logic ($10-100, $100-500, $500+). 2. Define visual feedback for 15m strategy success. 3. Ensure modularity (toggleable features).'
selected_approach: 'ai-recommended'
techniques_used: ['SCAMPER Method', 'Persona Journey', 'Metaphor Mapping']
ideas_generated: []
context_file: ''
---

## Session Overview

**Topic:** Refining Gamification Logic & Visuals around Portfolio Growth
**Goals:**
1. Validate/Enhance existing tier logic ($10-100, $100-500, $500+)
2. Define visual feedback for 15m strategy success
3. Ensure modularity (toggleable features)

### Context Guidance
User emphasizes simplicity. Gamification is a layer on top of core trading performance.
Tiers are strict:
- Lvl 1: $10-$100
- Lvl 2: $100-$500
- Lvl 3: $500+
Strategy focus: 15m timeframe, 2-3h sessions, Range or Trend.

### Session Setup
Facilitator verified existing files (`asset_gamification.py`) and confirmed the "optional wrapper" nature of the feature. Focus will be on how to make the "Strategy Success" -> "Portfolio Growth" loop feel rewarding and clear in the UI.

# Brainstorming Session Results

**Facilitator:** Nicolas
**Date:** 2026-01-12

## Phase 1: Mechanics (SCAMPER) Results

**Key Decisions:**
1.  **Metric:** Real Balance (Equity) is the ONLY metric.
    *   *Implication:* Withdrawals reduce level.
    *   *Implication:* Losing trades reduce level.
2.  **Automation:** Zero manual tasks. Progression is purely a passive byproduct of profitable AI/Strategy execution.
3.  **Simplicity:** No XP, no skill points. Just $.

---

## Phase 2: Dynamics (Persona Journey) Results

**Key Scenario: The "Yo-Yo" Effect**
*   **Decision:** STRICT implementation.
*   **Rationale:** The gamification reflects *reality*. If you lose money, you lose access immediately. This adds genuine stakes to the trading. No artificial buffers.
*   **User Experience:** "Hardcore" mode. Encourages maintaining a safety margin above the threshold ($120, not just $101) to avoid accidental downgrades.

---

## Phase 3: Aesthetics (Metaphor Mapping) Results

**Chosen Theme: Space / Nova Evolution**
*   **Concept:** The portfolio "ignites" as it grows.
*   **Level 1 ($10-$100): "Nebula"**
    *   *Visuals:* Deep blues/purples, calm, misty transparency.
*   **Level 2 ($100-$500): "Protostar"**
    *   *Visuals:* Orange/Red accents, more pulsing activity (heat).
*   **Level 3 ($500+): "Supernova"**
    *   *Visuals:* Bright White/Cyan, radiating effects, intense glow.

---

## 🏁 Session Summary & Action Items

We have successfully defined the "Gamification" feature set for NovaBot.

### 1. The Rules (Mechanics)
*   **Progression Metric:** Pure Equity (Real Balance).
*   **Tiers:**
    *   $10 - $100 (Nebula) -> Access: Basic/Safe pairs.
    *   $100 - $500 (Protostar) -> Access: Extended pairs.
    *   $500+ (Supernova) -> Access: Full market / Risky pairs.
*   **Modularity:** Feature is a wrapper. Strategies run regardless, but *access* to execute them on certain coins is gatekept by this balance check.

### 2. The Experience (Dynamics)
*   **Strict Volatility:** No buffering. If balance drops below $100 to $99, user strictly downgrades to Nebula.
*   **Behavior:** Encourages users to build a "Safety Margin" (e.g., aim for $120) rather than riding the line.

### 3. The Look (Aesthetics)
*   **Space Theme:** UI accents (borders, badges, maybe background gradient) react to the current level.
*   **Feedback:** Visual reward for 15m strategy success is the "heating up" of the interface towards the next stellar stage.

### Next Steps
1.  **Draft PRD:** Formalize these rules into `docs/PRD.md`.
2.  **Mockup UI:** Create visual tests for the "Nebula" vs "Supernova" states.

