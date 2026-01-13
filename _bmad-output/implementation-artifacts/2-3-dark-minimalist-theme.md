# Story 2.3: Dark/Minimalist Theme Implementation

Status: done

## Story

As a User,
I want a unified "Dark, Sober, and Minimalistic" interface,
So that I can focus on trading without distractions (cartoonish elements removed).

## Acceptance Criteria

1.  **Given** The application is loaded
    **When** I view the dashboard
    **Then** The background is deep dark (e.g., #0B0E11)
2.  **And** Texts are high-contrast sans-serif (Inter/SF Pro)
3.  **And** "Gamification" elements (Badges) use subtle gradients (Golden/Silver) instead of bright pop colors

## Tasks / Subtasks

- [x] Task 1: Update Tailwind Theme (AC: 1, 2, 3)
  - [x] Update `frontend/tailwind.config.js`
  - [x] Add dark color palette
  - [x] Add tier-specific subtle gradients
- [x] Task 2: Update Gamification Components (AC: 3)
  - [x] Update `components/GamificationWidget.tsx`
  - [x] Update `hooks/useGamification.ts`
  - [x] Remove emojis, add minimal icons
  - [x] Replace bright gradients with subtle ones
- [x] Task 3: Manual Visual QA (AC: 1, 2, 3)
  - [x] Verify dark background
  - [x] Verify high-contrast text
  - [x] Verify subtle tier colors

## Dev Notes

- **Color Palette:**
  - Background: `#0B0E11`
  - Surface: `#1A1D23`
  - Border: `#2A2D35`
  - Text: `#FFFFFF` (high contrast)
  
- **Tier Colors (Subtle):**
  - NEBULA: Gray gradients
  - PROTOSTAR: Silver gradients
  - SUPERNOVA: Gold gradients

- **Typography:** Inter or SF Pro (sans-serif)

### Project Structure Notes

- Modified: `frontend/tailwind.config.js`
- Modified: `frontend/components/GamificationWidget.tsx`
- Modified: `frontend/hooks/useGamification.ts`

### References

- [Epic 2 Implementation Plan](file:///C:/Users/User/.gemini/antigravity/brain/79cf2554-791d-4819-a5a4-2c8ab667e31a/epic2-implementation-plan.md)
- [PRD](file:///_bmad-output/planning-artifacts/prd.md) - UX Direction

## Dev Agent Record

### Agent Model Used

Antigravity (Claude 4.5 Sonnet)

### Debug Log References

- Tailwind config updated with dark palette (#0B0E11 background)
- Tier colors updated: NEBULA (gray), PROTOSTAR (silver), SUPERNOVA (gold)
- Emojis replaced with minimal icons (◆, ◇, ◈)
- Bright gradients replaced with subtle ones

### Completion Notes List

- ✅ Updated Tailwind config with dark/minimalist palette
- ✅ Added tier-specific subtle gradient colors
- ✅ Removed emojis from GamificationWidget (👺⚔️🐋 → ◆◇◈)
- ✅ Replaced bright progress bar gradient with subtle gray
- ✅ Updated tier colors in useGamification hook
- ✅ All changes follow PRD UX direction: "Dark, Sober, Minimalistic"

### File List

- `frontend/tailwind.config.js` (MODIFIED)
- `frontend/components/GamificationWidget.tsx` (MODIFIED)
- `frontend/hooks/useGamification.ts` (MODIFIED)
