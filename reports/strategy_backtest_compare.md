# Main vs PR #28 on the same frozen dump

Both runs use the whitelist candles in `reports/hl_ohlcv_whitelist_2026-09-26.tar.gz` (downloaded 2026-09-26, no second fetch). Costs are the same: taker 4.50 bp per side + slip 1.00 bp per fill, plus funding when the hourly series covers the hold.

- **main** params: `reports/strategy_backtest.md`, trades in `reports/strategy_backtest_trades.csv`.
- **PR #28** (commit `1ca28c9`, branch `cursor/lt-cascade-trigger-refine-adab`, not merged): `reports/strategy_backtest_pr28.md`, trades in `reports/strategy_backtest_pr28_trades.csv`, config snapshot `reports/strategies_pr28.json`.

Trend LT, Range LT, and SuperTrend share the same decision clock (1h, 1h, 15m). Rocket and Waterfall do not: the main run steps every 5m, the #28 run every 1m, because #28's active scan is 1 minute. Their trade counts are not a pure filter comparison.

#28 is not merged into this branch. `data/config/strategies.json` is still the main file.

## Side by side

| plan | n main | n #28 | Δ n | hit main | hit #28 | avg net R main | avg net R #28 | Δ avg net R | PF main | PF #28 | max DD main | max DD #28 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| supertrend | 0 | 0 | 0 | — | — | — | — | — | — | — | — | — |
| trend_lt | 6 | 969 | +963 | 83.3% | 44.9% | +0.058 | −0.035 | −0.093 | 5.28 | 0.87 | 0.08 R | 58.2 R |
| range_lt | 39 | 195 | +156 | 33.3% | 40.0% | −0.366 | −0.152 | +0.214 | 0.43 | 0.73 | 15.7 R | 34.8 R |
| rocket | 2 | 3 | +1 | 50% | 0% | +0.588 | −0.876 | −1.464 | n/a | n/a | 0.27 R | 2.63 R |
| waterfall | 1 | 5 | +4 | 100% | 20% | +1.464 | −0.047 | −1.511 | n/a | 0.86 | 0 R | 1.62 R |

Profit factor is omitted by the runner when n < 5. Trend LT's main PF of 5.28 is six trades.

## Range LT

Same 1h clock, 2026-03-06 → 2026-09-26. Funding covered every trade in both runs.

| | main | #28 |
|---|---:|---:|
| n | 39 | 195 |
| hit rate (net R > 0) | 33.3% | 40.0% |
| avg net R | −0.366 | −0.152 |
| sum net R | −14.26 | −29.55 |
| profit factor | 0.43 | 0.73 |
| max DD | 15.7 R | 34.8 R |
| holdout avg net R | +0.696 (n=4) | −0.108 (n=50) |

The per-trade average is less negative under #28 (+0.214 R). The book still loses, and the loss in R units is larger (−29.5 R vs −14.3 R) because there are five times as many trades. n=195 is still under the audit floor of 200. The holdout slice, which was four trades on main, is 50 trades and still negative.

What changed in #28 for this plan: `adx_max` 18 → 23, `max_adx_slope` 0.4 → 1.0, `ema_slope_flat_max` 0.0004 → 0.0008. Signals went from 39 to 195 with zero hard vetoes in both runs, so the extra trades are the looser box filters, not a veto change.

## Trend LT

Same 1h clock. This is the plan the looser gates actually fill.

| | main | #28 |
|---|---:|---:|
| n | 6 | 969 |
| hit rate | 83.3% | 44.9% |
| avg net R | +0.058 | −0.035 |
| sum net R | +0.35 | −34.32 |
| profit factor | 5.28 | 0.87 |
| max DD | 0.08 R | 58.2 R |
| holdout n / avg net R | 2 / +0.016 | 306 / −0.060 |

Signals 21 → 995, hard vetoes 15 → 26. Dropping the 1h MIXED / MACD vetoes and keeping a 2R target when the swing trim would break `min_rr` is what creates the sample. n=969 clears 200 on this one frozen window. The point estimate and the holdout are both negative, and PF stays under 1.1. That does not clear the audit bar for an edge.

## Cascades

Rocket: 2 trades on SUI under main (avg net R +0.588) versus 3 trades under #28 (SUI, NEAR, ZEC), all losers, avg net R −0.876. Decisions 25,304 (5m) versus 126,524 (1m). Signals 4 → 9, hard vetoes 2 → 6.

Waterfall: 1 trade (OP, TP, +1.464 R) versus 5 trades, hit rate 20%, avg net R −0.047, PF 0.86. Signals 1 → 8.

Both samples are still a few days of 1m history. Do not read a hit-rate change off n ≤ 5.

## Verdict

On this dump, loosening Range LT does not make the average trade worse. Average net R improves from −0.366 to −0.152 and PF from 0.43 to 0.73, while the cumulative loss and the R drawdown get larger because the plan trades much more often. The average is still negative. Trend LT is the plan that degrades in the way a small lucky sample would: six trades at +0.058 R become 969 trades at −0.035 R. Neither result is a reason to turn HVH back on.
