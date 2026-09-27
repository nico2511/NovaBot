# NovaBot per-strategy causal backtest

Params are `data/config/strategies.json` on this branch (based on `main`).
PR #28 replay, commit 1ca28c9, same frozen 2026-09-26 dump, no fetch. Rocket and waterfall decision step is 1m to match the PR #28 active scan. The main report used a 5m cascade step.
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
Config file: `reports/strategies_pr28.json`.

## PR #28

These numbers are the PR #28 replay (commit `1ca28c9` on `cursor/lt-cascade-trigger-refine-adab`). The config snapshot is `reports/strategies_pr28.json`. Those strategy modules were loaded for this process only; they are not merged into this branch and `data/config/strategies.json` is unchanged. Rocket and waterfall decisions are every 1m, matching the PR #28 active scan. The main report stepped those two plans every 5m. Trend LT, Range LT, and SuperTrend use the same 1h / 1h / 15m clock as the main run. Comparison: `reports/strategy_backtest_compare.md`.

## Results

| slice | n | hit rate (net R>0) | avg gross R | avg net R | sum net R | profit factor | max DD (R) | max time under water |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| supertrend | 0 | — | — | — | — | n/a (n<5) | — | — |
| trend_lt | 969 | 44.9% | 0.021 | -0.035 | -34.323 | 0.87 | 58.206 | 110.6d |
| range_lt | 195 | 40.0% | -0.070 | -0.152 | -29.545 | 0.73 | 34.759 | 161.2d |
| rocket | 3 | 0.0% | -0.791 | -0.876 | -2.628 | n/a (n<5) | 2.628 | 2.4d |
| waterfall | 5 | 20.0% | 0.001 | -0.047 | -0.237 | 0.86 | 1.624 | 1.8d |

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

n=969 meets the audit minimum of 200. This is still one frozen-parameter window, not a refit walk-forward.

Funding covered 967/969 trades. Avg net R after funding: -0.037. EOD marks: 0.
Exit reasons: sl=82, sl_gap=115, sl_same_bar=1, sl_trailed=220, thesis=473, tp=78. Exit candles: 15m=215, 1h=726, 1m=28.

By symbol

| slice | n | hit rate (net R>0) | avg gross R | avg net R | sum net R | profit factor | max DD (R) | max time under water |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| BTC | 59 | 22.0% | -0.160 | -0.240 | -14.171 | 0.24 | 14.246 | 189.8d |
| ETH | 51 | 31.4% | -0.124 | -0.191 | -9.746 | 0.43 | 11.741 | 194.5d |
| SUI | 44 | 56.8% | 0.125 | 0.077 | 3.370 | 1.37 | 3.074 | 94.4d |
| ATOM | 43 | 44.2% | 0.093 | 0.035 | 1.486 | 1.15 | 4.894 | 169.0d |
| DOT | 42 | 50.0% | 0.120 | 0.068 | 2.870 | 1.25 | 3.681 | 106.1d |
| INJ | 42 | 52.4% | 0.133 | 0.090 | 3.799 | 1.41 | 3.521 | 104.8d |
| AVAX | 41 | 61.0% | 0.002 | -0.055 | -2.246 | 0.77 | 5.655 | 198.9d |
| AAVE | 39 | 64.1% | 0.156 | 0.114 | 4.431 | 1.59 | 2.743 | 81.3d |
| ADA | 39 | 46.2% | -0.023 | -0.081 | -3.153 | 0.72 | 5.707 | 97.1d |
| XRP | 39 | 38.5% | 0.165 | 0.097 | 3.779 | 1.50 | 2.521 | 72.8d |
| ARB | 38 | 50.0% | 0.140 | 0.096 | 3.666 | 1.46 | 4.243 | 110.5d |
| DOGE | 38 | 39.5% | -0.168 | -0.229 | -8.691 | 0.37 | 8.954 | 197.3d |
| OP | 38 | 44.7% | 0.013 | -0.029 | -1.093 | 0.89 | 5.146 | 197.0d |
| APT | 37 | 45.9% | 0.028 | -0.016 | -0.602 | 0.94 | 3.927 | 112.9d |
| LTC | 37 | 54.1% | 0.103 | 0.033 | 1.234 | 1.11 | 5.499 | 196.2d |
| TRX | 37 | 32.4% | 0.041 | -0.050 | -1.852 | 0.69 | 2.243 | 197.9d |
| UNI | 37 | 48.6% | 0.036 | -0.003 | -0.106 | 0.99 | 3.558 | 83.6d |
| TIA | 36 | 50.0% | -0.053 | -0.091 | -3.261 | 0.66 | 5.767 | 196.4d |
| BNB | 35 | 28.6% | -0.213 | -0.297 | -10.383 | 0.14 | 10.406 | 194.6d |
| SOL | 35 | 42.9% | -0.061 | -0.119 | -4.160 | 0.61 | 4.335 | 125.7d |
| NEAR | 34 | 50.0% | 0.015 | -0.028 | -0.963 | 0.87 | 5.240 | 147.3d |
| ZEC | 34 | 47.1% | 0.045 | 0.011 | 0.371 | 1.04 | 5.103 | 149.5d |
| BCH | 33 | 36.4% | 0.022 | -0.043 | -1.429 | 0.83 | 5.708 | 80.3d |
| HYPE | 31 | 54.8% | 0.010 | -0.034 | -1.057 | 0.86 | 3.129 | 76.5d |
| LINK | 30 | 43.3% | 0.176 | 0.119 | 3.581 | 1.45 | 4.204 | 104.4d |

By regime at entry

| slice | n | hit rate (net R>0) | avg gross R | avg net R | sum net R | profit factor | max DD (R) | max time under water |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| TREND | 969 | 44.9% | 0.021 | -0.035 | -34.323 | 0.87 | 58.206 | 110.6d |

Chronological holdout (no refit). Cut at 2026-07-22T08:20:00+00:00 — last third of the scanned span is the holdout.

| slice | n | hit rate (net R>0) | avg gross R | avg net R | sum net R | profit factor | max DD (R) | max time under water |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| earlier | 663 | 46.3% | 0.032 | -0.024 | -15.829 | 0.91 | 43.991 | 83.1d |
| holdout | 306 | 41.8% | -0.003 | -0.060 | -18.494 | 0.77 | 28.904 | 64.3d |

By entry month

| slice | n | hit rate (net R>0) | avg gross R | avg net R | sum net R | profit factor | max DD (R) | max time under water |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 2026-06 | 175 | 57.1% | 0.194 | 0.149 | 26.162 | 1.72 | 28.113 | 22.9d |
| 2026-05 | 154 | 50.6% | 0.060 | 0.002 | 0.300 | 1.01 | 9.671 | 11.4d |
| 2026-04 | 151 | 35.1% | -0.100 | -0.164 | -24.735 | 0.51 | 24.735 | 30.0d |
| 2026-07 | 140 | 36.4% | -0.034 | -0.097 | -13.561 | 0.68 | 14.585 | 27.8d |
| 2026-09 | 132 | 46.2% | -0.011 | -0.056 | -7.419 | 0.79 | 13.110 | 25.6d |
| 2026-08 | 121 | 43.0% | 0.036 | -0.028 | -3.421 | 0.88 | 10.720 | 20.1d |
| 2026-03 | 96 | 41.7% | -0.066 | -0.121 | -11.649 | 0.58 | 17.678 | 18.5d |

Diagnostics: decisions=119653, signals=995, hard_veto=26, geometry_veto=0, bb_block=0, regime_skips=0, weekend_skips=33770, cooldown_skips=0, direction_block=0, invalid_bracket=0, unresolved=0, errors=0.

### range_lt

Status: enabled in strategies.json.
Decisions scanned: 2026-03-06T06:00:00+00:00 → 2026-09-26T20:00:00+00:00.
- BTC 1m: 5099 bars 2026-09-23T07:49:00+00:00 → 2026-09-26T20:47:00+00:00
- BTC 15m: 5007 bars 2026-08-05T17:15:00+00:00 → 2026-09-26T20:45:00+00:00
- BTC 1h: 5001 bars 2026-03-02T12:00:00+00:00 → 2026-09-26T20:00:00+00:00
- BTC 4h: 5001 bars 2024-06-15T12:00:00+00:00 → 2026-09-26T20:00:00+00:00

n=195 is below the audit minimum of 200. A confidence interval on mean R at this size still includes zero even when the point estimate does not.

Funding covered 195/195 trades. Avg net R after funding: -0.149. EOD marks: 0.
Exit reasons: sl=65, sl_same_bar=2, sl_trailed=22, thesis=52, tp=53, tp_gap=1. Exit candles: 15m=28, 1h=166, 1m=1.

By symbol

| slice | n | hit rate (net R>0) | avg gross R | avg net R | sum net R | profit factor | max DD (R) | max time under water |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| OP | 16 | 37.5% | -0.127 | -0.187 | -2.989 | 0.68 | 3.721 | 75.8d |
| AVAX | 14 | 50.0% | 0.214 | 0.138 | 1.935 | 1.29 | 2.878 | 87.7d |
| DOGE | 12 | 58.3% | 0.455 | 0.355 | 4.258 | 1.98 | 2.449 | 50.1d |
| DOT | 12 | 33.3% | -0.311 | -0.384 | -4.610 | 0.39 | 6.387 | 156.9d |
| ARB | 11 | 36.4% | 0.027 | -0.032 | -0.348 | 0.95 | 5.985 | 83.7d |
| LTC | 10 | 30.0% | -0.302 | -0.404 | -4.040 | 0.36 | 4.043 | 132.5d |
| SOL | 10 | 50.0% | 0.146 | 0.058 | 0.585 | 1.13 | 3.803 | 88.0d |
| ADA | 9 | 44.4% | -0.065 | -0.137 | -1.232 | 0.75 | 2.615 | 116.6d |
| APT | 9 | 55.6% | 0.278 | 0.211 | 1.903 | 1.55 | 1.705 | 65.0d |
| SUI | 9 | 22.2% | -0.461 | -0.546 | -4.914 | 0.22 | 4.914 | 102.6d |
| XRP | 9 | 11.1% | -0.514 | -0.645 | -5.808 | 0.22 | 7.413 | 104.5d |
| ATOM | 8 | 50.0% | 0.032 | -0.053 | -0.426 | 0.89 | 1.986 | 61.2d |
| AAVE | 7 | 28.6% | -0.256 | -0.338 | -2.367 | 0.48 | 4.003 | 99.5d |
| HYPE | 7 | 42.9% | 0.021 | -0.044 | -0.309 | 0.91 | 2.573 | 123.4d |
| ZEC | 7 | 57.1% | -0.093 | -0.135 | -0.947 | 0.70 | 3.107 | 181.4d |
| UNI | 6 | 66.7% | 0.529 | 0.473 | 2.840 | 2.71 | 1.657 | 14.5d |
| BCH | 5 | 40.0% | 0.090 | 0.000 | 0.002 | 1.00 | 2.840 | 144.1d |
| BNB | 5 | 40.0% | -0.204 | -0.336 | -1.680 | 0.44 | 1.848 | 96.4d |
| BTC | 5 | 20.0% | -0.173 | -0.281 | -1.404 | 0.54 | 2.434 | 131.2d |
| LINK | 5 | 40.0% | -0.300 | -0.408 | -2.041 | 0.37 | 2.118 | 75.1d |
| NEAR | 5 | 20.0% | -0.456 | -0.528 | -2.638 | 0.32 | 2.638 | 45.8d |
| INJ | 4 | 50.0% | -0.084 | -0.137 | -0.548 | n/a (n<5) | 1.668 | 85.0d |
| TIA | 4 | 25.0% | -0.678 | -0.741 | -2.964 | n/a (n<5) | 3.036 | 57.2d |
| ETH | 3 | 66.7% | 0.200 | 0.118 | 0.354 | n/a (n<5) | 1.089 | 31.9d |
| TRX | 3 | 0.0% | -0.557 | -0.719 | -2.157 | n/a (n<5) | 2.157 | 112.9d |

By regime at entry

| slice | n | hit rate (net R>0) | avg gross R | avg net R | sum net R | profit factor | max DD (R) | max time under water |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| RANGE | 195 | 40.0% | -0.070 | -0.152 | -29.545 | 0.73 | 34.759 | 161.2d |

Chronological holdout (no refit). Cut at 2026-07-20T15:20:00+00:00 — last third of the scanned span is the holdout.

| slice | n | hit rate (net R>0) | avg gross R | avg net R | sum net R | profit factor | max DD (R) | max time under water |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| earlier | 145 | 39.3% | -0.090 | -0.167 | -24.143 | 0.70 | 32.105 | 96.4d |
| holdout | 50 | 42.0% | -0.013 | -0.108 | -5.401 | 0.80 | 10.980 | 61.3d |

By entry month

| slice | n | hit rate (net R>0) | avg gross R | avg net R | sum net R | profit factor | max DD (R) | max time under water |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 2026-07 | 52 | 42.3% | -0.039 | -0.120 | -6.239 | 0.77 | 11.236 | 30.5d |
| 2026-06 | 33 | 27.3% | -0.398 | -0.463 | -15.294 | 0.33 | 17.649 | 15.4d |
| 2026-04 | 29 | 37.9% | -0.025 | -0.106 | -3.071 | 0.82 | 8.375 | 14.4d |
| 2026-05 | 29 | 55.2% | 0.185 | 0.094 | 2.721 | 1.24 | 3.954 | 13.0d |
| 2026-08 | 24 | 41.7% | 0.001 | -0.103 | -2.470 | 0.81 | 6.554 | 25.9d |
| 2026-03 | 16 | 31.2% | -0.077 | -0.151 | -2.414 | 0.74 | 6.550 | 19.2d |
| 2026-09 | 12 | 41.7% | -0.160 | -0.232 | -2.778 | 0.58 | 5.102 | 20.9d |

Diagnostics: decisions=122728, signals=195, hard_veto=0, geometry_veto=0, bb_block=0, regime_skips=0, weekend_skips=35136, cooldown_skips=0, direction_block=0, invalid_bracket=0, unresolved=0, errors=0.

### rocket

Status: enabled in strategies.json.
Decisions scanned: 2026-09-23T06:13:00+00:00 → 2026-09-26T20:51:00+00:00.
- BTC 1m: 5099 bars 2026-09-23T07:49:00+00:00 → 2026-09-26T20:47:00+00:00
- BTC 15m: 5007 bars 2026-08-05T17:15:00+00:00 → 2026-09-26T20:45:00+00:00
- BTC 1h: 5001 bars 2026-03-02T12:00:00+00:00 → 2026-09-26T20:00:00+00:00
- BTC 4h: 5001 bars 2024-06-15T12:00:00+00:00 → 2026-09-26T20:00:00+00:00

n=3 is too small to estimate expectancy. The audit minimum is 200 closed trades; this window cannot support a hit-rate claim.

Funding covered 2/3 trades. Avg net R after funding: -0.877. EOD marks: 0.
Exit reasons: sl=2, thesis=1. Exit candles: 1m=3.

By symbol

| slice | n | hit rate (net R>0) | avg gross R | avg net R | sum net R | profit factor | max DD (R) | max time under water |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| NEAR | 1 | 0.0% | -1.000 | -1.142 | -1.142 | n/a (n<5) | 1.142 | 0.0d |
| SUI | 1 | 0.0% | -0.372 | -0.420 | -0.420 | n/a (n<5) | 0.420 | 0.0d |
| ZEC | 1 | 0.0% | -1.000 | -1.066 | -1.066 | n/a (n<5) | 1.066 | 0.0d |

By regime at entry

| slice | n | hit rate (net R>0) | avg gross R | avg net R | sum net R | profit factor | max DD (R) | max time under water |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| TREND_BULL_STRONG | 3 | 0.0% | -0.791 | -0.876 | -2.628 | n/a (n<5) | 2.628 | 2.4d |

Chronological holdout (no refit). Cut at 2026-09-25T15:58:20+00:00 — last third of the scanned span is the holdout.

| slice | n | hit rate (net R>0) | avg gross R | avg net R | sum net R | profit factor | max DD (R) | max time under water |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| earlier | 2 | 0.0% | -1.000 | -1.104 | -2.208 | n/a (n<5) | 2.208 | 0.3d |
| holdout | 1 | 0.0% | -0.372 | -0.420 | -0.420 | n/a (n<5) | 0.420 | 0.0d |

By entry month

| slice | n | hit rate (net R>0) | avg gross R | avg net R | sum net R | profit factor | max DD (R) | max time under water |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 2026-09 | 3 | 0.0% | -0.791 | -0.876 | -2.628 | n/a (n<5) | 2.628 | 2.4d |

Diagnostics: decisions=126524, signals=9, hard_veto=6, geometry_veto=0, bb_block=0, regime_skips=38271, weekend_skips=25257, cooldown_skips=8, direction_block=0, invalid_bracket=0, unresolved=0, errors=0.

### waterfall

Status: enabled in strategies.json.
Decisions scanned: 2026-09-23T06:13:00+00:00 → 2026-09-26T20:51:00+00:00.
- BTC 1m: 5099 bars 2026-09-23T07:49:00+00:00 → 2026-09-26T20:47:00+00:00
- BTC 15m: 5007 bars 2026-08-05T17:15:00+00:00 → 2026-09-26T20:45:00+00:00
- BTC 1h: 5001 bars 2026-03-02T12:00:00+00:00 → 2026-09-26T20:00:00+00:00
- BTC 4h: 5001 bars 2024-06-15T12:00:00+00:00 → 2026-09-26T20:00:00+00:00

n=5 is too small to estimate expectancy. The audit minimum is 200 closed trades; this window cannot support a hit-rate claim.

Funding covered 4/5 trades. Avg net R after funding: -0.047. EOD marks: 0.
Exit reasons: sl_gap=1, thesis=3, tp=1. Exit candles: 1m=5.

By symbol

| slice | n | hit rate (net R>0) | avg gross R | avg net R | sum net R | profit factor | max DD (R) | max time under water |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| NEAR | 2 | 0.0% | -0.358 | -0.383 | -0.766 | n/a (n<5) | 0.766 | 0.9d |
| AAVE | 1 | 0.0% | -0.796 | -0.858 | -0.858 | n/a (n<5) | 0.858 | 0.1d |
| ATOM | 1 | 0.0% | 0.014 | -0.077 | -0.077 | n/a (n<5) | 0.077 | 0.0d |
| OP | 1 | 100.0% | 1.500 | 1.464 | 1.464 | n/a (n<5) | 0.000 | 0.0d |

By regime at entry

| slice | n | hit rate (net R>0) | avg gross R | avg net R | sum net R | profit factor | max DD (R) | max time under water |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| TREND_BEAR_STRONG | 5 | 20.0% | 0.001 | -0.047 | -0.237 | 0.86 | 1.624 | 1.8d |

Chronological holdout (no refit). Cut at 2026-09-25T15:58:20+00:00 — last third of the scanned span is the holdout.

| slice | n | hit rate (net R>0) | avg gross R | avg net R | sum net R | profit factor | max DD (R) | max time under water |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| earlier | 5 | 20.0% | 0.001 | -0.047 | -0.237 | 0.86 | 1.624 | 1.8d |
| holdout | 0 | — | — | — | — | n/a (n<5) | — | — |

By entry month

| slice | n | hit rate (net R>0) | avg gross R | avg net R | sum net R | profit factor | max DD (R) | max time under water |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 2026-09 | 5 | 20.0% | 0.001 | -0.047 | -0.237 | 0.86 | 1.624 | 1.8d |

Diagnostics: decisions=126524, signals=8, hard_veto=3, geometry_veto=0, bb_block=0, regime_skips=37883, weekend_skips=25257, cooldown_skips=0, direction_block=0, invalid_bracket=0, unresolved=0, errors=0.

## What this does not say

A positive average on a short window is not an edge. The audit kill lines (profit factor under 1.1 after costs, n under 200, hit rate under 40% for a 2R trend plan or under 58% for a 1R cascade) are only meaningful once n is large. Max drawdown here is in R units assuming 1R risk per trade added when each trade closes, not a percent of account equity.
