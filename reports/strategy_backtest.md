# NovaBot per-strategy causal backtest

Params are `data/config/strategies.json` on this branch (based on `main`).
AI is not replayed. A signal that passes mechanical geometry and `check_hard_veto` is taken.

## Method

- Confirmed bars only. At decision time t the strategy sees bars with open time ≤ t; the last row is the forming bar and entries use `iloc[-2]`.
- Costs: taker 4.50 bp per side + slip 1.00 bp per fill (round trip), subtracted in R via `net_r` (same constants as `app/core/causal_backtest.py`). The fill price is the strategy signal price.
- Funding: hourly Hyperliquid `fundingHistory` when the cache covers the hold, as an extra R drag (`net_r_funding`). Positive funding is paid by longs.
- Exits: walk the finest candle interval that exists at the entry. Same-bar SL and TP counts as a stop. A gap through the stop fills at the open. R-ladder trailing and thesis tightens update the stop for the *next* bar, using the bar close. Thesis `CLOSE` flattens at that close. Still-open trades at the last bar are marked `eod`.
- One open trade per strategy per symbol. Books are independent across strategies (no shared `max_positions`, no scanner top-K). This is not a portfolio equity curve.
- `type: trend` plans are idle unless the 15m regime is TREND or a confirmed cascade, matching `StrategyEngine`. Weekend pause uses the bar time in Europe/Paris.
- Context depth defaults to 300 primary bars and 120 one-minute bars, in line with the live fetch in `_analyze_symbol_market`.
- Hard veto sees RSI, ADX, MACD histogram, confirmed volume ratio, and funding when present. Trend LT also gets a 1h/4h MTF line built like `_fetch_mtf_sentiment`. Missing funding or MTF does not veto (same fallback as live).
- Official `candleSnapshot` retains only the most recent 5000 candles per interval. That caps 1m near 3.5 days, 15m near 52 days, and 1h near 208 days. There is no multi-year OOS sample in this run.

Symbols (whitelist subset, not the live scanner board): BTC, ETH, SOL, HYPE, AVAX, LINK, DOGE, SUI.
Config file: `data/config/strategies.json`.

## PR #28

These numbers use **main** params. Draft PR #28 (`cursor/lt-cascade-trigger-refine-adab`) softens Trend LT / Range LT geometry and cascade 1m timing. It is not merged here. Re-run this command after that PR lands if you want the comparison; do not read this report as a test of #28.

## Results

| slice | n | hit rate (net R>0) | avg gross R | avg net R | sum net R | profit factor | max DD (R) | max time under water |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| supertrend | 0 | — | — | — | — | n/a (n<5) | — | — |
| trend_lt | 2 | 100.0% | 0.174 | 0.133 | 0.266 | n/a (n<5) | 0.000 | 0.0d |
| range_lt | 14 | 42.9% | -0.054 | -0.160 | -2.235 | 0.68 | 5.019 | 116.0d |
| rocket | 2 | 50.0% | 0.644 | 0.588 | 1.177 | n/a (n<5) | 0.273 | 0.3d |
| waterfall | 0 | — | — | — | — | n/a (n<5) | — | — |

### supertrend

Status: enabled in strategies.json.
Decisions scanned: 2026-09-23T06:45:00+00:00 → 2026-09-26T20:30:00+00:00.
- BTC 1m: 5080 bars 2026-09-23T07:49:00+00:00 → 2026-09-26T20:28:00+00:00
- BTC 15m: 5005 bars 2026-08-05T17:15:00+00:00 → 2026-09-26T20:15:00+00:00
- BTC 1h: 5001 bars 2026-03-02T12:00:00+00:00 → 2026-09-26T20:00:00+00:00
- BTC 4h: 5001 bars 2024-06-15T12:00:00+00:00 → 2026-09-26T20:00:00+00:00

No closed trades. Expectancy is unknown.

Diagnostics: decisions=2689, signals=0, hard_veto=0, geometry_veto=0, bb_block=0, regime_skips=1157, weekend_skips=0, cooldown_skips=0, direction_block=0, invalid_bracket=0, unresolved=0, errors=0.

### trend_lt

Status: enabled in strategies.json.
Decisions scanned: 2026-03-11T09:00:00+00:00 → 2026-09-26T20:00:00+00:00.
- BTC 1m: 5080 bars 2026-09-23T07:49:00+00:00 → 2026-09-26T20:28:00+00:00
- BTC 15m: 5005 bars 2026-08-05T17:15:00+00:00 → 2026-09-26T20:15:00+00:00
- BTC 1h: 5001 bars 2026-03-02T12:00:00+00:00 → 2026-09-26T20:00:00+00:00
- BTC 4h: 5001 bars 2024-06-15T12:00:00+00:00 → 2026-09-26T20:00:00+00:00

n=2 is too small to estimate expectancy. The audit minimum is 200 closed trades; this window cannot support a hit-rate claim.

Funding covered 2/2 trades. Avg net R after funding: 0.132. EOD marks: 0.
Exit reasons: sl_trailed=2. Exit candles: 1h=2.

By symbol

| slice | n | hit rate (net R>0) | avg gross R | avg net R | sum net R | profit factor | max DD (R) | max time under water |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| DOGE | 2 | 100.0% | 0.174 | 0.133 | 0.266 | n/a (n<5) | 0.000 | 0.0d |

By regime at entry

| slice | n | hit rate (net R>0) | avg gross R | avg net R | sum net R | profit factor | max DD (R) | max time under water |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| TREND | 2 | 100.0% | 0.174 | 0.133 | 0.266 | n/a (n<5) | 0.000 | 0.0d |

Chronological holdout (no refit). Cut at 2026-07-22T08:20:00+00:00 — last third of the scanned span is the holdout.

| slice | n | hit rate (net R>0) | avg gross R | avg net R | sum net R | profit factor | max DD (R) | max time under water |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| earlier | 2 | 100.0% | 0.174 | 0.133 | 0.266 | n/a (n<5) | 0.000 | 0.0d |
| holdout | 0 | — | — | — | — | n/a (n<5) | — | — |

By entry month

| slice | n | hit rate (net R>0) | avg gross R | avg net R | sum net R | profit factor | max DD (R) | max time under water |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 2026-05 | 2 | 100.0% | 0.174 | 0.133 | 0.266 | n/a (n<5) | 0.000 | 0.0d |

Diagnostics: decisions=38290, signals=10, hard_veto=8, geometry_veto=0, bb_block=0, regime_skips=0, weekend_skips=10880, cooldown_skips=0, direction_block=0, invalid_bracket=0, unresolved=0, errors=0.

### range_lt

Status: enabled in strategies.json.
Decisions scanned: 2026-03-06T06:00:00+00:00 → 2026-09-26T20:00:00+00:00.
- BTC 1m: 5080 bars 2026-09-23T07:49:00+00:00 → 2026-09-26T20:28:00+00:00
- BTC 15m: 5005 bars 2026-08-05T17:15:00+00:00 → 2026-09-26T20:15:00+00:00
- BTC 1h: 5001 bars 2026-03-02T12:00:00+00:00 → 2026-09-26T20:00:00+00:00
- BTC 4h: 5001 bars 2024-06-15T12:00:00+00:00 → 2026-09-26T20:00:00+00:00

n=14 is too small to estimate expectancy. The audit minimum is 200 closed trades; this window cannot support a hit-rate claim.

Funding covered 14/14 trades. Avg net R after funding: -0.156. EOD marks: 0.
Exit reasons: sl=3, sl_trailed=2, thesis=5, tp=4. Exit candles: 15m=2, 1h=12.

By symbol

| slice | n | hit rate (net R>0) | avg gross R | avg net R | sum net R | profit factor | max DD (R) | max time under water |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| DOGE | 6 | 66.7% | 0.627 | 0.516 | 3.097 | 2.99 | 0.839 | 48.7d |
| AVAX | 2 | 0.0% | -0.817 | -0.885 | -1.771 | n/a (n<5) | 1.771 | 42.0d |
| HYPE | 2 | 50.0% | -0.455 | -0.526 | -1.052 | n/a (n<5) | 1.093 | 16.0d |
| SUI | 2 | 50.0% | -0.412 | -0.534 | -1.069 | n/a (n<5) | 1.148 | 65.2d |
| BTC | 1 | 0.0% | -0.527 | -0.671 | -0.671 | n/a (n<5) | 0.671 | 0.1d |
| SOL | 1 | 0.0% | -0.617 | -0.769 | -0.769 | n/a (n<5) | 0.769 | 0.2d |

By regime at entry

| slice | n | hit rate (net R>0) | avg gross R | avg net R | sum net R | profit factor | max DD (R) | max time under water |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| RANGE | 14 | 42.9% | -0.054 | -0.160 | -2.235 | 0.68 | 5.019 | 116.0d |

Chronological holdout (no refit). Cut at 2026-07-20T15:20:00+00:00 — last third of the scanned span is the holdout.

| slice | n | hit rate (net R>0) | avg gross R | avg net R | sum net R | profit factor | max DD (R) | max time under water |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| earlier | 10 | 30.0% | -0.410 | -0.502 | -5.019 | 0.20 | 5.019 | 80.1d |
| holdout | 4 | 75.0% | 0.836 | 0.696 | 2.784 | n/a (n<5) | 0.769 | 26.9d |

By entry month

| slice | n | hit rate (net R>0) | avg gross R | avg net R | sum net R | profit factor | max DD (R) | max time under water |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 2026-07 | 6 | 50.0% | 0.079 | -0.012 | -0.072 | 0.97 | 2.506 | 20.8d |
| 2026-04 | 2 | 0.0% | -0.876 | -0.994 | -1.987 | n/a (n<5) | 1.987 | 3.2d |
| 2026-05 | 2 | 0.0% | -0.764 | -0.873 | -1.746 | n/a (n<5) | 1.746 | 1.1d |
| 2026-06 | 2 | 100.0% | 0.643 | 0.570 | 1.139 | n/a (n<5) | 0.000 | 0.0d |
| 2026-08 | 2 | 50.0% | 0.382 | 0.215 | 0.430 | n/a (n<5) | 0.769 | 0.7d |

Diagnostics: decisions=39274, signals=14, hard_veto=0, geometry_veto=0, bb_block=0, regime_skips=0, weekend_skips=11263, cooldown_skips=0, direction_block=0, invalid_bracket=0, unresolved=0, errors=0.

### rocket

Status: enabled in strategies.json.
Decisions scanned: 2026-09-23T06:40:00+00:00 → 2026-09-26T20:30:00+00:00.
- BTC 1m: 5080 bars 2026-09-23T07:49:00+00:00 → 2026-09-26T20:28:00+00:00
- BTC 15m: 5005 bars 2026-08-05T17:15:00+00:00 → 2026-09-26T20:15:00+00:00
- BTC 1h: 5001 bars 2026-03-02T12:00:00+00:00 → 2026-09-26T20:00:00+00:00
- BTC 4h: 5001 bars 2024-06-15T12:00:00+00:00 → 2026-09-26T20:00:00+00:00

n=2 is too small to estimate expectancy. The audit minimum is 200 closed trades; this window cannot support a hit-rate claim.

Funding covered 1/2 trades. Avg net R after funding: 0.588. EOD marks: 0.
Exit reasons: thesis=1, tp=1. Exit candles: 1m=2.

By symbol

| slice | n | hit rate (net R>0) | avg gross R | avg net R | sum net R | profit factor | max DD (R) | max time under water |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| SUI | 2 | 50.0% | 0.644 | 0.588 | 1.177 | n/a (n<5) | 0.273 | 0.3d |

By regime at entry

| slice | n | hit rate (net R>0) | avg gross R | avg net R | sum net R | profit factor | max DD (R) | max time under water |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| TREND_BULL_STRONG | 2 | 50.0% | 0.644 | 0.588 | 1.177 | n/a (n<5) | 0.273 | 0.3d |

Chronological holdout (no refit). Cut at 2026-09-25T15:53:20+00:00 — last third of the scanned span is the holdout.

| slice | n | hit rate (net R>0) | avg gross R | avg net R | sum net R | profit factor | max DD (R) | max time under water |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| earlier | 1 | 100.0% | 1.500 | 1.450 | 1.450 | n/a (n<5) | 0.000 | 0.0d |
| holdout | 1 | 0.0% | -0.213 | -0.273 | -0.273 | n/a (n<5) | 0.273 | 0.0d |

By entry month

| slice | n | hit rate (net R>0) | avg gross R | avg net R | sum net R | profit factor | max DD (R) | max time under water |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 2026-09 | 2 | 50.0% | 0.644 | 0.588 | 1.177 | n/a (n<5) | 0.273 | 0.3d |

Diagnostics: decisions=8074, signals=2, hard_veto=0, geometry_veto=0, bb_block=0, regime_skips=2373, weekend_skips=1587, cooldown_skips=0, direction_block=0, invalid_bracket=0, unresolved=0, errors=0.

### waterfall

Status: enabled in strategies.json.
Decisions scanned: 2026-09-23T06:40:00+00:00 → 2026-09-26T20:30:00+00:00.
- BTC 1m: 5080 bars 2026-09-23T07:49:00+00:00 → 2026-09-26T20:28:00+00:00
- BTC 15m: 5005 bars 2026-08-05T17:15:00+00:00 → 2026-09-26T20:15:00+00:00
- BTC 1h: 5001 bars 2026-03-02T12:00:00+00:00 → 2026-09-26T20:00:00+00:00
- BTC 4h: 5001 bars 2024-06-15T12:00:00+00:00 → 2026-09-26T20:00:00+00:00

No closed trades. Expectancy is unknown.

Diagnostics: decisions=8074, signals=0, hard_veto=0, geometry_veto=0, bb_block=0, regime_skips=2388, weekend_skips=1587, cooldown_skips=0, direction_block=0, invalid_bracket=0, unresolved=0, errors=0.

## What this does not say

A positive average on a short window is not an edge. The audit kill lines (profit factor under 1.1 after costs, n under 200, hit rate under 40% for a 2R trend plan or under 58% for a 1R cascade) are only meaningful once n is large. Max drawdown here is in R units assuming 1R risk per trade added when each trade closes, not a percent of account equity.
