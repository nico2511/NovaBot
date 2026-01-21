# Story 5.2: Enhanced AI Rationale (Metadata Visualization)

Status: done

## Story

As a Serene Investor,
I want the "Copilot" card to show specific indicator values (RSI, ADX) that caused a decision,
So that I have full transparency on the AI's logic.

## Acceptance Criteria

1. **Metadata Parsing**: Extract `metadata` (e.g., `{ "rsi": 75, "adve_mode": "TREND" }`) from the latest log entry.
2. **Visual Badges**: Display indicator values as small badges or tags within the `CopilotCard`.
3. **Semantic Coloring**: 
    - Profit-inducing factors (e.g., strong trend) in Emerald.
    - Risk/Veto factors (e.g., high RSI) in Amber/Rose.
4. **Fallback State**: Show a generic "Waiting for data..." message if no metadata is available.

## Tasks / Subtasks

- [ ] Update `CopilotCard` to accept metadata #frontend
    - [ ] Extend component props to include optional metadata
- [ ] Implement Badge Mapping #frontend
    - [ ] Create a utility to map metadata keys to human-readable labels and colors
- [ ] Integrate with Backend Data #frontend
    - [ ] Ensure `useBotStatus` or log fetching provides the necessary metadata
- [ ] Style Refinements #frontend
    - [ ] Ensure badges follow the "Dark Void" theme

## Dev Notes

### Architecture Constraints
- **Data Source**: Usually comes from the `latest_log` or a specific AI rationale field in `/api/status`.

### Source Tree Components
- [MODIFY] `frontend-v3/components/CopilotCard.tsx`
- [MODIFY] `frontend-v3/hooks/useBotStatus.ts`
