# Story 1.2: Frontend Skeleton & PWA Setup

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a Mobile User,
I want to install the application on my phone's home screen,
So that I can access it instantly like a native app.

## Acceptance Criteria

1. **Native Installability**: App prompts or allows "Add to Home Screen" on mobile.
2. **Manifest Configuration**: `manifest.json` correctly configured with name "Novabot" and correct icons.
3. **Standalone Mode**: App opens without browser UI (URL bar, navigation controls).
4. **Theme Preference**: UI defaults to "Dark Void" theme (Neutral-950 background) and handling of `theme-color` meta tag.
5. **Tech Stack**: Uses Next.js 14 App Router, Tailwind CSS, and `next-pwa` (or equivalent).
6. **Project Structure**: Code resides in `frontend-v3/` (per constraints).

## Tasks / Subtasks

- [x] Initialize Next.js 14 Project #frontend
    - [x] Create `frontend-v3` directory using `create-next-app` (TypeScript, Tailwind, App Router)
    - [x] Clean up default boilerplate (page.tsx, globals.css)
- [x] Configure Tailwind Theme (Dark Void) #frontend
    - [x] Update `tailwind.config.ts` with project colors (Emerald-400, Rose-500, Neutral-950)
    - [x] Set global background color in `globals.css`
- [x] Configure PWA Capabilities #frontend
    - [x] Install `next-pwa` or `serwist/next`
    - [x] Configure `next.config.mjs` for PWA
    - [x] Create `manifest.json` and icons (use placeholder or generate)
    - [x] Add `viewport` and `theme-color` meta tags
- [x] Verify PWA Installability #frontend
    - [x] Test manifest recognition (Lighthouse or DevTools)

## Dev Notes

### Architecture Constraints
- **Directory**: ALL new frontend code must go into `frontend-v3/`. Do not touch `frontend/` (v2 legacy).
- **Styling**: Tailwind CSS is mandatory. Use `shadcn/ui` where applicable later, but core setups first.
- **PWA**: Critical for mobile-first usage. Ensure `display: standalone` is set.

### Source Tree Components
- [NEW] `frontend-v3/`
- [NEW] `frontend-v3/next.config.mjs`
- [NEW] `frontend-v3/public/manifest.json`

### References
- [UX Design]: "Dark Void" theme (Neutral-950).
- [Architecture]: Mobile-First PWA requirement.

## Dev Agent Record

### Agent Model Used
- Sm (Scrum Master)

### Completion Notes List
- Created Next.js 14 project in `frontend-v3/` with TypeScript, Tailwind, and App Router.
- Configured Dark Void theme with custom colors (profit: Emerald-400, loss: Rose-500, void: Neutral-950).
- Installed and configured `@ducanh2912/next-pwa` for PWA functionality.
- Created `manifest.json` with Novabot branding and standalone display mode.
- Added viewport and theme-color meta tags to layout.
- Build successful - service worker generated at `/sw.js`.

### File List
- `frontend-v3/` (Created)
- `frontend-v3/next.config.js` (Modified)
- `frontend-v3/tailwind.config.ts` (Modified)
- `frontend-v3/app/globals.css` (Modified)
- `frontend-v3/app/layout.tsx` (Modified)
- `frontend-v3/app/page.tsx` (Modified)
- `frontend-v3/public/manifest.json` (Created)
