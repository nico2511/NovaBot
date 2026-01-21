# Story 2.3: Global System Alerting

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## User Story

As a User,
I want to know immediately if the bot is in a stopped or error state,
So that I don't mistakenly believe I am being protected when I am not.

## Acceptance Criteria

- [x] Persistent Status Bar #frontend
    - [x] Display a fixed banner when status is `STOPPED` or `ERROR`
    - [x] Banner is visible on all pages
    - [x] Banner color indicates severity (Red for Stopped, Orange for Error)
- [x] Visual Cues #frontend
    - [x] Top border "Pulse Line" changes color based on status
    - [x] Animations/Throbber for active states
- [x] Integration #frontend
    - [x] Connect to shared bot status
    - [x] Ensure banner disappears when bot is RUNNING

## Dev Notes

- Extract status fetching to a reusable hook `useBotStatus` to be used by both the Dashboard and the Global Banner.
- Use `layout.tsx` to ensure the banner is persistent across all future pages (like Logs).
- Use Shadcn/UI Alert or a custom sticky banner component.
