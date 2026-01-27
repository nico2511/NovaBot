---
stepsCompleted: [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13]
inputDocuments:
  - prd.md
  - product-brief-novabot-2026-01-13.md
  - project-context.md
  - docs/TRADING_PROFILES.md
  - docs/personas_and_risks.md
---

# UX Design Specification: Novabot

**Author:** Nicolas
**Date:** 2026-01-17
**Status:** Validated

---

## 1. Executive Summary

### Project Vision
NovaBot is not a typical trading tool; it is a "serenity machine". The goal is to transform crypto trading into a passive and reliable activity. The key is **trust**: the user must know in < 2 seconds if everything is fine ("Morning Coffee Standard").

### Target Users
1. **The Serene Investor (Nicolas)**: Wants yield without stress. Checks the dashboard upon waking up. Wants to see "Green" and no alerts.
2. **The Operator (Nicolas)**: In case of issues or on weekends, wants to understand *why* a decision was made (Explainable AI Logs).

### Key Design Challenges
1. **Glanceability**: Health status (PnL, Running, Position) must be readable instantly on mobile.
2. **Explainability (Trust)**: The "Why" of the trade (or refusal) by AI must be accessible without digging into raw technical logs.
3. **Panic Management**: In case of a crash, the bot must reassure immediately ("I am paused, capital secured") rather than displaying errors.

### Design Opportunities
* **"Calm Tech" Interface**: Dark, soothing UI that only alerts in case of real necessity.
* **AI Insight Cards**: Highlight the bot's reasoning as a "Co-pilot" that speaks human.


## 2. Core User Experience

### Defining Experience: The "Morning Check"
The core loop is simple and binary.
*   **Concept**: In < 5 seconds, I know if my day is starting well.
*   **Analogy**: Like checking the weather.
*   **Mental Model**: "Has the bot worked? Am I rich?" (Expects binary "Good/Bad").

### Experience Mechanics
1.  **Initiation**: Open PWA (No login friction).
2.  **Interaction**: Zero clicks. Passive consumption.
3.  **Feedback**:
    *   🟢 **Green**: All good.
    *   🟠 **Orange**: Warning (non-critical).
    *   🔴 **Red**: Action required immediately.
4.  **Completion**: Close app. Feeling of "Duty done".

### Critical Success Moments
**The Crash Test**: Market drops 10%. User opens app in panic.
*   **Success**: See "⚠️ Volatile Market - Positions Closed - Capital Secured". Immediate relief.
*   **Failure**: See Error 500 or red PnL without explanation.

### Experience Principles
*   **Principle #1: Silence is Golden**: If the bot says nothing, everything is fine.
*   **Principle #2: Radical Trust**: Always explain money loss in human terms.
*   **Principle #3: Glanceability**: Critical info never requires scrolling.

### Success Criteria (Metrics)
*   **Speed**: < 200ms to see status.
*   **Clarity**: No ambiguity. "Running" vs "Stopped" visible from 1m away.
*   **Trust**: If it's green, it's TRULY green.


## 3. Desired Emotional Response

### Primary Emotional Goal
**Serenity (Peace of Mind)**: "I sleep soundly". The user should not feel excitement (casino mode) nor fear (panic mode). Just calm satisfaction.

### Emotional Journey
*   **Discovery**: Curiosity ("It's clean, looks pro").
*   **Action (Morning Check)**: Satisfaction ("Ah, it ran, cool").
*   **Problem (Crash)**: Relief ("Phew, lucky I had the bot").

### Design Implications
*   **Colors**: No aggressive red for normal losses. Use neutral tones or orange. Red is reserved for *system errors*.
*   **Wording**: Factual, reassuring, professional tone. Never alarmist.


## 4. UX Pattern Analysis

### Inspiration: HyperLiquid (DEX)
*   **Why it works**: Dense, dark, professional. "Feels like trading".
*   **Key Pattern**: Tabular interface and high information density. No unnecessary white space.

### Transferable Patterns
*   **Tab Navigation**: Context switching without losing state (Chart -> Logs -> Config).
*   **Data-Density**: Displaying critical metrics (RSI, ADX, Vol) in compact cards.
*   **Status Pills**: Instant visibility of system state ("ONLINE", "BULLISH").
*   **The Deafening Silence**: Notify ONLY if critical.

### Anti-Patterns to Avoid
*   **Marketing Fluff**: No massive headers or white space.
*   **Blocking Modals**: Never block visibility of status.
*   **Black Box Logic**: "Trade taken" is insufficient; need "Reasoning".


## 5. Design Direction & Strategy

### Chosen Direction: "One Brain, Two Faces"
*   **Desktop (The Cockpit)**: 3-column dense layout for deep analysis. "Control Tower" vibe.
*   **Mobile (The Companion)**: Tab-based navigation (Home, Graph, Brain). Optimized for "Morning Check" thumb-scrolling.

### Platform Strategy
*   **Mobile First (Absolute Priority)**: Acts as a pocket companion. Desktop is for deep analysis (weekend).
*   **Responsive Web App (PWA)**: Universal access, installable on mobile home screen.

### Navigation Strategy
*   **Mobile**: Bottom Navigation Bar (Home, Dashboard, Settings).
*   **Desktop**: Collapsible Sidebar.
*   **Signature Element**: "Pulse Line" - A sticky top border (Green/Orange) indicating bot health instantly.


## 6. Design System & Visual Foundation

### Technology Stack
*   **Core**: **Tailwind CSS** (Layout, Typography, Colors, Animation).
*   **Components**: **Shadcn/UI** (Selective import for complex interactive elements like Dialogs, Selects, Calendars).
*   **Rationale**: Lightweight bundle, high control for "HyperLiquid" aesthetics.

### Visual Theme: "Dark Void"
*   **Backgrounds**: `bg-neutral-950` (#0a0a0a) for main, `bg-neutral-900` for cards.
*   **Borders**: `border-neutral-800` (Subtle structure).
*   **Accents**:
    *   🟢 `text-emerald-400`: Profit / Long / Running (Softer than standard green).
    *   🔴 `text-rose-500`: Loss / Short / Error.
    *   🔵 `text-blue-400`: Neutral Info / Active Tab.

### Typography System
*   **UI/Headings**: `Inter` (Clean, neutral).
*   **Data/Code**: `JetBrains Mono` or `Geist Mono` (Financial terminal feel).

### Spacing & Layout
*   **Density**: Compact (`p-2`, `gap-2`). High information per pixel.
*   **Grid**: Fluid 12-column foundation.

## 7. UX Consistency Patterns

### Status Density
**Rule**: "If it fits in a badge, don't write a sentence."
*   **Use**: `[🟢 RUNNING]` instead of "The bot is currently running".

### Safe Action Patterns
**Rule**: "If it costs money, it demands confirmation."
*   **Pause**: Toggle Switch (Immediate).
*   **Emergency Stop**: Red Dialog + Confirmation (Intentional Friction).

### Progressive Disclosure
**Rule**: "First WHAT, then WHY."
*   **L1 (Glance)**: PnL (+100$).
*   **L2 (Overview)**: Asset Breakdown.
*   **L3 (Deep Dive)**: AI Logs & Technical Data.


## 8. Responsive Design & Accessibility

### Responsive Strategy
*   **Mobile (< 768px)**: Vertical Stack, Bottom Nav. Thumb-friendly zones (bottom 30%).
*   **Tablet (< 1024px)**: Hybrid, Icon Sidebar.
*   **Desktop (> 1024px)**: Full Control Tower, 3-Column.

### Accessibility Standards
*   **Contrast**: AA Compliant (Emerald-400/Rose-500 on Neutral-900).
*   **State Indicators**: Never rely on color alone (Use Icons + Text).
