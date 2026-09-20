---
name: audit-novabot-strategy
description: >-
  Audit NovaBot / Hyperliquid strategy logic (entry, exit, sizing, filters,
  in-strategy risk). Use when the user asks for a strategy audit, quant review,
  capital-risk review, backtest/statistical validation, or mentions this skill's
  response structure. Ignore infrastructure unless it changes the plan.
---

# Audit NovaBot Strategy (Hyperliquid)

**Scope:** strategy logic only (entry, exit, sizing, filters, thesis, internal risk).
Ignore API / WS / keys unless they change fills, SL placement, or look-ahead.

**Source of truth:** read the strategy file, `data/config/strategies.json`,
`strategies/engine.py` selection, `app/core/risk_profiles.py`, and
`app/core/trade_thesis.py` helpers used by that plan.

Worked example (book-wide, 2026-09-19): [`strategies/AUDIT.md`](../../../strategies/AUDIT.md).

Pick a **mode** from the user request (default = standard):

| Mode | When |
|------|------|
| `standard` | Default audit (structure below) |
| `capital` | Review before deploying real capital — harsher, loss-first |
| `stats` | Backtest / statistical validation — no live-capital advice without sample math |

If the user asks for several modes, run all of them. Never be complacent: a weak or undefined edge is a finding, not a vibe.

## Standard structure (mandatory)

### 1. Résumé exécutif
- Note globale /10
- Type (trend following, mean reversion, breakout, scalping, funding, cascade…)
- Risque global: Faible / Moyen / Élevé / Très élevé
- Verdict: « Stratégie viable » | « À retravailler » | « Trop dangereuse en l’état »

### 2. Analyse de la logique
- Entrée long / short
- Sortie (TP, SL, signal inverse, time, thesis)
- Sizing et levier
- Filtres (volume, vol, funding, TF, …)
- Positions multiples / pyramiding

### 3. Points faibles (table gravité)
`Critique | Élevé | Moyen | Faible` × Problème × Impact × Correction

Prioritize what can **lose money fast**. Non-robust hypotheses → **Critique**.

### 4. Stress / régimes
Forte tendance, range, haute vol / gaps, funding extrême, faible liquidité, whipsaw.
State **edge** vs **fragile** per regime.

### 5. Améliorations (priorité)
Entrée/sortie, risk, filtres, robustesse. Concrete, not vague.

### 6. Checklist Hyperliquid

| Critère | Statut | Commentaire |
|---------|--------|-------------|
| Logique d’entrée claire et non ambiguë | | |
| Logique de sortie complète | | |
| Position sizing cohérent | | |
| Protection contre liquidation | | |
| Gestion du funding rate | | |
| Robustesse aux fakeouts | | |
| Absence de look-ahead bias | | |
| Edge identifiable | | |

## Capital mode (extra, loss-first)

Answer these before any praise:

1. Worst 1-hour path: how much of equity can this plan vaporize (SL skip, 10x, cascade live bar)?
2. What is the **kill condition** (disable the strategy) — not “be careful”?
3. Is min R:R after fees + funding still > 1 after structural TP trim?
4. Does live-bar detection (`use_live=True` / `iloc[-1]`) turn fakeouts into fills?
5. If every enabled strategy can fire the same day, is portfolio risk additive?

Verdict language: deploy / paper only / disable.

## Stats mode (extra, validation)

Do not claim an edge without stating what would falsify it.

Required:
- Hypothesis (1 sentence)
- Minimum sample (trades, not days) for a stable hit-rate
- Walk-forward / OOS split
- Costs: HL taker round-trip, funding/hour × expected hold, slippage on thin alts
- Look-ahead checklist: confirmed bar (`iloc[-2]`) vs forming bar; SuperTrend/ADX computed on a frame that includes the live candle
- Regime conditional expectancy (trend vs range vs cascade)
- Kill metrics: max DD, profit factor after costs, time-under-water

If no backtest exists: say **unvalidated** and list the exact experiment to run. Do not invent win rates.

## Output rules

- Direct, quantitative, French if the user wrote in French.
- Per-strategy scores when auditing the whole book; plus a **portfolio** score if several strats are enabled together.
- Propose corrections with file/param names (`strategies/rocket.py`, `min_rr`, `use_live`).
- Do not “soften vetoes to get more trades” — that is an anti-pattern (see create-novabot-strategy skill).
