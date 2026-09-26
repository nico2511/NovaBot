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

Symbols (example scanner whitelist, not the live top-K): BTC, ETH, SOL, ARB, OP, SUI, APT, AVAX, LINK, UNI, AAVE, ADA, NEAR, INJ, TIA, DOT, ATOM, LTC, BCH, XRP, BNB, TRX, HYPE, DOGE, ZEC.
Config file: `data/config/strategies.json`.

## PR #28

These numbers use **main** params. Draft PR #28 (`cursor/lt-cascade-trigger-refine-adab`) softens Trend LT / Range LT geometry and cascade 1m timing. It is not merged here. Re-run this command after that PR lands if you want the comparison; do not read this report as a test of #28.

## Results

| slice | n | hit rate (net R>0) | avg gross R | avg net R | sum net R | profit factor | max DD (R) | max time under water |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| supertrend | 0 | — | — | — | — | n/a (n<5) | — | — |
| trend_lt | 6 | 83.3% | 0.102 | 0.058 | 0.350 | 5.28 | 0.082 | 111.2d |
| range_lt | 39 | 33.3% | -0.268 | -0.366 | -14.262 | 0.43 | 15.658 | 185.3d |
| rocket | 2 | 50.0% | 0.644 | 0.588 | 1.177 | n/a (n<5) | 0.273 | 0.3d |
| waterfall | 1 | 100.0% | 1.500 | 1.464 | 1.464 | n/a (n<5) | 0.000 | 0.0d |

### supertrend

Status: enabled in strategies.json.
Decisions scanned: 2026-09-23T06:15:00+00:00 → 2026-09-26T20:45:00+00:00.
- BTC 1m: 5099 bars 2026-09-23T07:49:00+00:00 → 2026-09-26T20:47:00+00:00
- BTC 15m: 5007 bars 2026-08-05T17:15:00+00:00 → 2026-09-26T20:45:00+00:00
- BTC 1h: 5001 bars 2026-03-02T12:00:00+00:00 → 2026-09-26T20:00:00+00:00
- BTC 4h: 5001 bars 2024-06-15T12:00:00+00:00 → 2026-09-26T20:00:00+00:00

No closed trades. Expectancy is unknown.

Diagnostics: decisions=8437, signals=1, hard_veto=1, geometry_veto=0, bb_block=0, regime_skips=3516, weekend_skips=0, cooldown_skips=0, direction_block=0, invalid_bracket=0, unresolved=0, errors=0.

### trend_lt

Status: enabled in strategies.json.
Decisions scanned: 2026-03-11T09:00:00+00:00 → 2026-09-26T20:00:00+00:00.
- BTC 1m: 5099 bars 2026-09-23T07:49:00+00:00 → 2026-09-26T20:47:00+00:00
- BTC 15m: 5007 bars 2026-08-05T17:15:00+00:00 → 2026-09-26T20:45:00+00:00
- BTC 1h: 5001 bars 2026-03-02T12:00:00+00:00 → 2026-09-26T20:00:00+00:00
- BTC 4h: 5001 bars 2024-06-15T12:00:00+00:00 → 2026-09-26T20:00:00+00:00

n=6 is too small to estimate expectancy. The audit minimum is 200 closed trades; this window cannot support a hit-rate claim.

Funding covered 6/6 trades. Avg net R after funding: 0.056. EOD marks: 0.
Exit reasons: sl_gap=1, sl_trailed=4, thesis=1. Exit candles: 15m=2, 1h=4.

By symbol

| slice | n | hit rate (net R>0) | avg gross R | avg net R | sum net R | profit factor | max DD (R) | max time under water |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| DOGE | 2 | 100.0% | 0.174 | 0.133 | 0.266 | n/a (n<5) | 0.000 | 0.0d |
| DOT | 1 | 100.0% | 0.078 | 0.032 | 0.032 | n/a (n<5) | 0.000 | 0.0d |
| INJ | 1 | 100.0% | 0.044 | 0.020 | 0.020 | n/a (n<5) | 0.000 | 0.0d |
| TIA | 1 | 100.0% | 0.134 | 0.114 | 0.114 | n/a (n<5) | 0.000 | 0.0d |
| TRX | 1 | 0.0% | 0.010 | -0.082 | -0.082 | n/a (n<5) | 0.082 | 0.4d |

By regime at entry

| slice | n | hit rate (net R>0) | avg gross R | avg net R | sum net R | profit factor | max DD (R) | max time under water |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| TREND | 6 | 83.3% | 0.102 | 0.058 | 0.350 | 5.28 | 0.082 | 111.2d |

Chronological holdout (no refit). Cut at 2026-07-22T08:20:00+00:00 — last third of the scanned span is the holdout.

| slice | n | hit rate (net R>0) | avg gross R | avg net R | sum net R | profit factor | max DD (R) | max time under water |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| earlier | 4 | 100.0% | 0.117 | 0.079 | 0.317 | n/a (n<5) | 0.000 | 0.0d |
| holdout | 2 | 50.0% | 0.072 | 0.016 | 0.032 | n/a (n<5) | 0.082 | 25.7d |

By entry month

| slice | n | hit rate (net R>0) | avg gross R | avg net R | sum net R | profit factor | max DD (R) | max time under water |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 2026-05 | 3 | 100.0% | 0.130 | 0.095 | 0.285 | n/a (n<5) | 0.000 | 0.0d |
| 2026-04 | 1 | 100.0% | 0.078 | 0.032 | 0.032 | n/a (n<5) | 0.000 | 0.0d |
| 2026-08 | 1 | 0.0% | 0.010 | -0.082 | -0.082 | n/a (n<5) | 0.082 | 0.4d |
| 2026-09 | 1 | 100.0% | 0.134 | 0.114 | 0.114 | n/a (n<5) | 0.000 | 0.0d |

Diagnostics: decisions=119653, signals=21, hard_veto=15, geometry_veto=0, bb_block=0, regime_skips=0, weekend_skips=34000, cooldown_skips=0, direction_block=0, invalid_bracket=0, unresolved=0, errors=0.

### range_lt

Status: enabled in strategies.json.
Decisions scanned: 2026-03-06T06:00:00+00:00 → 2026-09-26T20:00:00+00:00.
- BTC 1m: 5099 bars 2026-09-23T07:49:00+00:00 → 2026-09-26T20:47:00+00:00
- BTC 15m: 5007 bars 2026-08-05T17:15:00+00:00 → 2026-09-26T20:45:00+00:00
- BTC 1h: 5001 bars 2026-03-02T12:00:00+00:00 → 2026-09-26T20:00:00+00:00
- BTC 4h: 5001 bars 2024-06-15T12:00:00+00:00 → 2026-09-26T20:00:00+00:00

n=39 is below the audit minimum of 200. A confidence interval on mean R at this size still includes zero even when the point estimate does not.

Funding covered 39/39 trades. Avg net R after funding: -0.366. EOD marks: 0.
Exit reasons: sl=15, sl_trailed=4, thesis=11, tp=9. Exit candles: 15m=11, 1h=28.

By symbol

| slice | n | hit rate (net R>0) | avg gross R | avg net R | sum net R | profit factor | max DD (R) | max time under water |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| DOGE | 6 | 66.7% | 0.627 | 0.516 | 3.097 | 2.99 | 0.839 | 48.7d |
| LTC | 6 | 33.3% | -0.122 | -0.236 | -1.417 | 0.57 | 2.634 | 132.5d |
| XRP | 4 | 25.0% | -0.480 | -0.597 | -2.386 | n/a (n<5) | 3.312 | 56.1d |
| AAVE | 2 | 0.0% | -1.000 | -1.085 | -2.170 | n/a (n<5) | 2.170 | 8.8d |
| APT | 2 | 50.0% | 0.044 | -0.005 | -0.010 | n/a (n<5) | 1.066 | 71.3d |
| AVAX | 2 | 0.0% | -0.817 | -0.885 | -1.771 | n/a (n<5) | 1.771 | 42.0d |
| BCH | 2 | 50.0% | 0.109 | 0.021 | 0.041 | n/a (n<5) | 1.052 | 47.8d |
| DOT | 2 | 0.0% | -0.779 | -0.875 | -1.750 | n/a (n<5) | 1.750 | 100.8d |
| HYPE | 2 | 50.0% | -0.455 | -0.526 | -1.052 | n/a (n<5) | 1.093 | 16.0d |
| OP | 2 | 0.0% | -1.000 | -1.068 | -2.136 | n/a (n<5) | 2.136 | 83.8d |
| SUI | 2 | 50.0% | -0.412 | -0.534 | -1.069 | n/a (n<5) | 1.148 | 65.2d |
| UNI | 2 | 50.0% | -0.459 | -0.517 | -1.033 | n/a (n<5) | 1.070 | 71.0d |
| ATOM | 1 | 0.0% | -1.000 | -1.135 | -1.135 | n/a (n<5) | 1.135 | 0.2d |
| BTC | 1 | 0.0% | -0.527 | -0.671 | -0.671 | n/a (n<5) | 0.671 | 0.1d |
| NEAR | 1 | 0.0% | -1.000 | -1.070 | -1.070 | n/a (n<5) | 1.070 | 0.1d |
| SOL | 1 | 0.0% | -0.617 | -0.769 | -0.769 | n/a (n<5) | 0.769 | 0.2d |
| ZEC | 1 | 100.0% | 1.103 | 1.041 | 1.041 | n/a (n<5) | 0.000 | 0.0d |

By regime at entry

| slice | n | hit rate (net R>0) | avg gross R | avg net R | sum net R | profit factor | max DD (R) | max time under water |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| RANGE | 39 | 33.3% | -0.268 | -0.366 | -14.262 | 0.43 | 15.658 | 185.3d |

Chronological holdout (no refit). Cut at 2026-07-20T15:20:00+00:00 — last third of the scanned span is the holdout.

| slice | n | hit rate (net R>0) | avg gross R | avg net R | sum net R | profit factor | max DD (R) | max time under water |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| earlier | 22 | 22.7% | -0.492 | -0.579 | -12.745 | 0.21 | 12.745 | 121.5d |
| holdout | 17 | 47.1% | 0.021 | -0.089 | -1.517 | 0.83 | 4.157 | 54.8d |

By entry month

| slice | n | hit rate (net R>0) | avg gross R | avg net R | sum net R | profit factor | max DD (R) | max time under water |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 2026-07 | 12 | 25.0% | -0.438 | -0.531 | -6.372 | 0.28 | 6.451 | 28.5d |
| 2026-08 | 8 | 50.0% | 0.107 | -0.025 | -0.203 | 0.95 | 2.229 | 12.6d |
| 2026-06 | 7 | 28.6% | -0.439 | -0.515 | -3.606 | 0.24 | 4.704 | 28.2d |
| 2026-05 | 4 | 25.0% | -0.292 | -0.398 | -1.591 | n/a (n<5) | 2.807 | 22.3d |
| 2026-09 | 4 | 50.0% | -0.088 | -0.158 | -0.631 | n/a (n<5) | 0.984 | 7.9d |
| 2026-04 | 3 | 33.3% | -0.217 | -0.316 | -0.947 | n/a (n<5) | 1.987 | 3.7d |
| 2026-03 | 1 | 0.0% | -0.828 | -0.914 | -0.914 | n/a (n<5) | 0.914 | 0.1d |

Diagnostics: decisions=122728, signals=39, hard_veto=0, geometry_veto=0, bb_block=0, regime_skips=0, weekend_skips=35190, cooldown_skips=0, direction_block=0, invalid_bracket=0, unresolved=0, errors=0.

### rocket

Status: enabled in strategies.json.
Decisions scanned: 2026-09-23T06:15:00+00:00 → 2026-09-26T20:50:00+00:00.
- BTC 1m: 5099 bars 2026-09-23T07:49:00+00:00 → 2026-09-26T20:47:00+00:00
- BTC 15m: 5007 bars 2026-08-05T17:15:00+00:00 → 2026-09-26T20:45:00+00:00
- BTC 1h: 5001 bars 2026-03-02T12:00:00+00:00 → 2026-09-26T20:00:00+00:00
- BTC 4h: 5001 bars 2024-06-15T12:00:00+00:00 → 2026-09-26T20:00:00+00:00

n=2 is too small to estimate expectancy. The audit minimum is 200 closed trades; this window cannot support a hit-rate claim.

Funding covered 2/2 trades. Avg net R after funding: 0.588. EOD marks: 0.
Exit reasons: thesis=1, tp=1. Exit candles: 1m=2.

By symbol

| slice | n | hit rate (net R>0) | avg gross R | avg net R | sum net R | profit factor | max DD (R) | max time under water |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| SUI | 2 | 50.0% | 0.644 | 0.588 | 1.177 | n/a (n<5) | 0.273 | 0.3d |

By regime at entry

| slice | n | hit rate (net R>0) | avg gross R | avg net R | sum net R | profit factor | max DD (R) | max time under water |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| TREND_BULL_STRONG | 2 | 50.0% | 0.644 | 0.588 | 1.177 | n/a (n<5) | 0.273 | 0.3d |

Chronological holdout (no refit). Cut at 2026-09-25T15:58:20+00:00 — last third of the scanned span is the holdout.

| slice | n | hit rate (net R>0) | avg gross R | avg net R | sum net R | profit factor | max DD (R) | max time under water |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| earlier | 1 | 100.0% | 1.500 | 1.450 | 1.450 | n/a (n<5) | 0.000 | 0.0d |
| holdout | 1 | 0.0% | -0.213 | -0.273 | -0.273 | n/a (n<5) | 0.273 | 0.0d |

By entry month

| slice | n | hit rate (net R>0) | avg gross R | avg net R | sum net R | profit factor | max DD (R) | max time under water |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 2026-09 | 2 | 50.0% | 0.644 | 0.588 | 1.177 | n/a (n<5) | 0.273 | 0.3d |

Diagnostics: decisions=25304, signals=4, hard_veto=2, geometry_veto=0, bb_block=0, regime_skips=7633, weekend_skips=5061, cooldown_skips=0, direction_block=0, invalid_bracket=0, unresolved=0, errors=0.

### waterfall

Status: enabled in strategies.json.
Decisions scanned: 2026-09-23T06:15:00+00:00 → 2026-09-26T20:50:00+00:00.
- BTC 1m: 5099 bars 2026-09-23T07:49:00+00:00 → 2026-09-26T20:47:00+00:00
- BTC 15m: 5007 bars 2026-08-05T17:15:00+00:00 → 2026-09-26T20:45:00+00:00
- BTC 1h: 5001 bars 2026-03-02T12:00:00+00:00 → 2026-09-26T20:00:00+00:00
- BTC 4h: 5001 bars 2024-06-15T12:00:00+00:00 → 2026-09-26T20:00:00+00:00

n=1 is too small to estimate expectancy. The audit minimum is 200 closed trades; this window cannot support a hit-rate claim.

Funding covered 1/1 trades. Avg net R after funding: 1.464. EOD marks: 0.
Exit reasons: tp=1. Exit candles: 1m=1.

By symbol

| slice | n | hit rate (net R>0) | avg gross R | avg net R | sum net R | profit factor | max DD (R) | max time under water |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| OP | 1 | 100.0% | 1.500 | 1.464 | 1.464 | n/a (n<5) | 0.000 | 0.0d |

By regime at entry

| slice | n | hit rate (net R>0) | avg gross R | avg net R | sum net R | profit factor | max DD (R) | max time under water |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| TREND_BEAR_STRONG | 1 | 100.0% | 1.500 | 1.464 | 1.464 | n/a (n<5) | 0.000 | 0.0d |

Chronological holdout (no refit). Cut at 2026-09-25T15:58:20+00:00 — last third of the scanned span is the holdout.

| slice | n | hit rate (net R>0) | avg gross R | avg net R | sum net R | profit factor | max DD (R) | max time under water |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| earlier | 1 | 100.0% | 1.500 | 1.464 | 1.464 | n/a (n<5) | 0.000 | 0.0d |
| holdout | 0 | — | — | — | — | n/a (n<5) | — | — |

By entry month

| slice | n | hit rate (net R>0) | avg gross R | avg net R | sum net R | profit factor | max DD (R) | max time under water |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 2026-09 | 1 | 100.0% | 1.500 | 1.464 | 1.464 | n/a (n<5) | 0.000 | 0.0d |

Diagnostics: decisions=25304, signals=1, hard_veto=0, geometry_veto=0, bb_block=0, regime_skips=7648, weekend_skips=5061, cooldown_skips=0, direction_block=0, invalid_bracket=0, unresolved=0, errors=0.

## What this does not say

A positive average on a short window is not an edge. The audit kill lines (profit factor under 1.1 after costs, n under 200, hit rate under 40% for a 2R trend plan or under 58% for a 1R cascade) are only meaningful once n is large. Max drawdown here is in R units assuming 1R risk per trade added when each trade closes, not a percent of account equity.
