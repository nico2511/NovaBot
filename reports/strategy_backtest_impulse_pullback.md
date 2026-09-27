## A vs E (PROXY)

A = rocket (long) and waterfall (short) on `main` params, 5m decision clock, 15m regime gate.
E = `impulse_pullback` (enabled stays false in live JSON), 1m decision clock, no 15m regime gate.
Same cost model as the proxy harness: HL taker 4.50 bp/side + 1 bp slip, Binance prices.

| variante | plan | side | n | hit rate | avg net R | PF | max DD (R) | % chase>0.35 |
|---|---|---|---:|---:|---:|---:|---:|---:|
| A | rocket | long | 27 | 37.0% | 0.069 | 1.28 | 2.469 | 63.0% |
| A | waterfall | short | 15 | 26.7% | -0.262 | 0.43 | 4.174 | 73.3% |
| E | impulse_pullback | long | 1097 | 24.5% | -0.286 | 0.49 | 315.802 | 56.2% |
| E | impulse_pullback | short | 1063 | 23.9% | -0.287 | 0.48 | 309.000 | 52.7% |

Filtre (les deux côtés): n ≥ 40, hit ≥ 45% et +8 pts vs la baseline du même côté, avg net R ≥ 0, PF ≥ 1.1.

**Verdict: NON, ne pas merger.** Le filtre ne passe pas sur: long, short. Live `impulse_pullback` reste `enabled: false`.

Holdout (dernier tiers du calendrier, pas de refit):
- rocket long: holdout n=4, hit 50.0%, avg net R 0.255
- waterfall short: holdout n=6, hit 16.7%, avg net R -0.439
- impulse_pullback long: holdout n=429, hit 25.4%, avg net R -0.264
- impulse_pullback short: holdout n=423, hit 26.7%, avg net R -0.227

# PROXY causal backtest — Binance USDT-M, not Hyperliquid

LABEL: PROXY. These prices are Binance USDT-M perpetual klines from `data.binance.vision`. They are not the Hyperliquid dump and must not be compared as if they were the same market.
Params are `data/config/strategies.json` on this branch (based on `main`).
LABEL: PROXY. Compare A (rocket/waterfall, live baseline) vs E (impulse_pullback, off in strategies.json). Universe BTC ETH SOL BNB ARB OP.
AI is not replayed. A signal that passes mechanical geometry and `check_hard_veto` is taken.

## Method

- Confirmed bars only. At decision time t the strategy sees bars with open time ≤ t; the last row is the forming bar and entries use `iloc[-2]`.
- Costs: the NovaBot Hyperliquid model is applied to these proxy prices: taker 4.50 bp per side + slip 1.00 bp per fill (round trip), subtracted in R via `net_r`. Binance's own fee schedule is not used. The fill price is the strategy signal price. Spread beyond the 1 bp slip is not modeled.
- Funding: Binance USDT-M settlement rate (`last_funding_rate`, usually every 8h), summed over settlements inside the hold and converted to R the same way as `funding_drag_r`. This is not the Hyperliquid hourly rate. A hold with no settlement in the cache is uncovered and the funding drag is zero.
- Exits: walk the finest candle interval that exists at the entry. Same-bar SL and TP counts as a stop. A gap through the stop fills at the open. R-ladder trailing and thesis tightens update the stop for the *next* bar, using the bar close. Thesis `CLOSE` flattens at that close. Still-open trades at the last bar are marked `eod`.
- One open trade per strategy per symbol. Books are independent across strategies (no shared `max_positions`, no scanner top-K). This is not a portfolio equity curve.
- `type: trend` plans are idle unless the 15m regime is TREND or a confirmed cascade, matching `StrategyEngine`. Weekend pause uses the bar time in Europe/Paris.
- Context depth defaults to 300 primary bars and 120 one-minute bars, in line with the live fetch in `_analyze_symbol_market`.
- Hard veto sees RSI, ADX, MACD histogram, confirmed volume ratio, and funding when present. Trend LT also gets a 1h/4h MTF line built like `_fetch_mtf_sentiment`. Missing funding or MTF does not veto (same fallback as live).
- Source: Binance USDT-M perpetual klines, symbol map `COIN` → `COINUSDT`, files under `data/ohlcv_proxy/`. Months 2026-03 through 2026-08 plus daily files 2026-09-01 through 2026-09-26 when the archive has them. A coin with no 1m file is skipped and listed in `reports/proxy_ohlcv_manifest.json`.
- Proxy gaps vs Hyperliquid: different mark price, different funding clock (8h vs 1h), different spreads, and listing dates that are Binance's. A missing minute is counted in the manifest `gaps` field. Do not read this as a Hyperliquid fill.

Symbols (example scanner whitelist, not the live top-K): BTC, ETH, SOL, BNB, ARB, OP.
Config file: `/workspace/data/config/strategies.json`.

## PR #28

These numbers use **main** params. Draft PR #28 (`cursor/lt-cascade-trigger-refine-adab`) softens Trend LT / Range LT geometry and cascade 1m timing. It is not merged here. Re-run this command after that PR lands if you want the comparison; do not read this report as a test of #28.

## Results

| slice | n | hit rate (net R>0) | avg gross R | avg net R | sum net R | profit factor | max DD (R) | max time under water |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| rocket | 27 | 37.0% | 0.156 | 0.069 | 1.864 | 1.28 | 2.469 | 119.4d |
| waterfall | 15 | 26.7% | -0.169 | -0.262 | -3.931 | 0.43 | 4.174 | 108.7d |
| impulse_pullback (disabled) | 2160 | 24.2% | -0.012 | -0.286 | -618.784 | 0.49 | 622.534 | 208.0d |

### rocket

Status: enabled in strategies.json.
Decisions scanned: 2026-03-01T20:00:00+00:00 → 2026-09-26T23:55:00+00:00.
- BTC 1m: 302400 bars 2026-03-01T00:00:00+00:00 → 2026-09-26T23:59:00+00:00
- BTC 15m: 20160 bars 2026-03-01T00:00:00+00:00 → 2026-09-26T23:45:00+00:00

n=27 is too small to estimate expectancy. The audit minimum is 200 closed trades; this window cannot support a hit-rate claim.

Funding covered 5/27 trades. Avg net R after funding: 0.069. EOD marks: 0.
Exit reasons: sl_gap=3, sl_trailed=4, thesis=14, tp=6. Exit candles: 1m=27.

By symbol

| slice | n | hit rate (net R>0) | avg gross R | avg net R | sum net R | profit factor | max DD (R) | max time under water |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| OP | 10 | 60.0% | 0.378 | 0.323 | 3.227 | 3.67 | 0.659 | 150.1d |
| SOL | 8 | 37.5% | 0.077 | -0.017 | -0.139 | 0.95 | 1.485 | 162.1d |
| ARB | 4 | 25.0% | 0.276 | 0.158 | 0.634 | n/a (n<5) | 0.795 | 47.4d |
| BNB | 2 | 0.0% | -0.367 | -0.510 | -1.020 | n/a (n<5) | 1.020 | 132.0d |
| ETH | 2 | 0.0% | -0.315 | -0.412 | -0.823 | n/a (n<5) | 0.823 | 17.8d |
| BTC | 1 | 0.0% | 0.070 | -0.014 | -0.014 | n/a (n<5) | 0.014 | 0.0d |

By regime at entry

| slice | n | hit rate (net R>0) | avg gross R | avg net R | sum net R | profit factor | max DD (R) | max time under water |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| TREND_BULL_STRONG | 27 | 37.0% | 0.156 | 0.069 | 1.864 | 1.28 | 2.469 | 119.4d |

Chronological holdout (no refit). Cut at 2026-07-19T06:36:40+00:00 — last third of the scanned span is the holdout.

| slice | n | hit rate (net R>0) | avg gross R | avg net R | sum net R | profit factor | max DD (R) | max time under water |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| earlier | 23 | 34.8% | 0.124 | 0.037 | 0.845 | 1.13 | 2.132 | 49.1d |
| holdout | 4 | 50.0% | 0.338 | 0.255 | 1.019 | n/a (n<5) | 0.352 | 25.1d |

By entry month

| slice | n | hit rate (net R>0) | avg gross R | avg net R | sum net R | profit factor | max DD (R) | max time under water |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 2026-04 | 8 | 25.0% | 0.185 | 0.077 | 0.618 | 1.28 | 1.211 | 13.0d |
| 2026-06 | 5 | 20.0% | -0.365 | -0.421 | -2.103 | 0.01 | 2.132 | 17.9d |
| 2026-05 | 4 | 50.0% | 0.306 | 0.225 | 0.900 | n/a (n<5) | 0.587 | 18.3d |
| 2026-07 | 4 | 25.0% | 0.097 | -0.004 | -0.014 | n/a (n<5) | 1.383 | 12.6d |
| 2026-03 | 2 | 100.0% | 0.792 | 0.722 | 1.444 | n/a (n<5) | 0.000 | 0.0d |
| 2026-08 | 2 | 50.0% | -0.063 | -0.161 | -0.323 | n/a (n<5) | 0.352 | 6.8d |
| 2026-09 | 2 | 50.0% | 0.739 | 0.671 | 1.342 | n/a (n<5) | 0.121 | 8.2d |

Diagnostics: decisions=361440, signals=31, hard_veto=4, geometry_veto=0, bb_block=0, regime_skips=98172, weekend_skips=102240, cooldown_skips=2, direction_block=0, invalid_bracket=0, unresolved=0, errors=0.

Entry timing vs the confirmed 15m close (measured, not a filter):
- chase ATR: n=27, median 0.46, p75 0.77, p90 1.07, max 3.89. 63.0% of fills are more than 0.35 ATR past that close (the cap drafted in abandoned PR #28; it is not applied on this run).
- minutes after the 15m close: n=27, median 5, p90 10, max 10.

### waterfall

Status: enabled in strategies.json.
Decisions scanned: 2026-03-01T20:00:00+00:00 → 2026-09-26T23:55:00+00:00.
- BTC 1m: 302400 bars 2026-03-01T00:00:00+00:00 → 2026-09-26T23:59:00+00:00
- BTC 15m: 20160 bars 2026-03-01T00:00:00+00:00 → 2026-09-26T23:45:00+00:00

n=15 is too small to estimate expectancy. The audit minimum is 200 closed trades; this window cannot support a hit-rate claim.

Funding covered 1/15 trades. Avg net R after funding: -0.262. EOD marks: 0.
Exit reasons: sl=1, sl_trailed=2, thesis=10, tp=2. Exit candles: 1m=15.

By symbol

| slice | n | hit rate (net R>0) | avg gross R | avg net R | sum net R | profit factor | max DD (R) | max time under water |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| ETH | 6 | 50.0% | 0.268 | 0.188 | 1.126 | 1.62 | 0.798 | 92.2d |
| BTC | 4 | 0.0% | -0.508 | -0.640 | -2.561 | n/a (n<5) | 2.561 | 110.1d |
| SOL | 3 | 33.3% | -0.331 | -0.436 | -1.307 | n/a (n<5) | 1.367 | 189.2d |
| OP | 2 | 0.0% | -0.558 | -0.595 | -1.189 | n/a (n<5) | 1.189 | 91.3d |

By regime at entry

| slice | n | hit rate (net R>0) | avg gross R | avg net R | sum net R | profit factor | max DD (R) | max time under water |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| TREND_BEAR_STRONG | 15 | 26.7% | -0.169 | -0.262 | -3.931 | 0.43 | 4.174 | 108.7d |

Chronological holdout (no refit). Cut at 2026-07-19T06:36:40+00:00 — last third of the scanned span is the holdout.

| slice | n | hit rate (net R>0) | avg gross R | avg net R | sum net R | profit factor | max DD (R) | max time under water |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| earlier | 9 | 33.3% | -0.064 | -0.144 | -1.297 | 0.69 | 1.743 | 95.1d |
| holdout | 6 | 16.7% | -0.326 | -0.439 | -2.634 | 0.02 | 2.634 | 25.0d |

By entry month

| slice | n | hit rate (net R>0) | avg gross R | avg net R | sum net R | profit factor | max DD (R) | max time under water |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 2026-06 | 5 | 40.0% | 0.310 | 0.249 | 1.244 | 1.76 | 0.890 | 4.9d |
| 2026-09 | 5 | 20.0% | -0.305 | -0.411 | -2.055 | 0.03 | 2.055 | 19.7d |
| 2026-03 | 2 | 50.0% | -0.433 | -0.533 | -1.066 | n/a (n<5) | 1.126 | 0.9d |
| 2026-05 | 1 | 0.0% | -0.556 | -0.677 | -0.677 | n/a (n<5) | 0.677 | 0.1d |
| 2026-07 | 1 | 0.0% | -0.704 | -0.798 | -0.798 | n/a (n<5) | 0.798 | 0.0d |
| 2026-08 | 1 | 0.0% | -0.431 | -0.579 | -0.579 | n/a (n<5) | 0.579 | 0.1d |

Diagnostics: decisions=361440, signals=23, hard_veto=8, geometry_veto=0, bb_block=0, regime_skips=98315, weekend_skips=102240, cooldown_skips=1, direction_block=0, invalid_bracket=0, unresolved=0, errors=0.

Entry timing vs the confirmed 15m close (measured, not a filter):
- chase ATR: n=15, median 0.43, p75 0.85, p90 1.11, max 1.66. 73.3% of fills are more than 0.35 ATR past that close (the cap drafted in abandoned PR #28; it is not applied on this run).
- minutes after the 15m close: n=15, median 5, p90 10, max 10.

### impulse_pullback

Status: disabled in strategies.json.
Decisions scanned: 2026-03-01T20:00:00+00:00 → 2026-09-26T23:59:00+00:00.
- BTC 1m: 302400 bars 2026-03-01T00:00:00+00:00 → 2026-09-26T23:59:00+00:00
- BTC 15m: 20160 bars 2026-03-01T00:00:00+00:00 → 2026-09-26T23:45:00+00:00

n=2160 meets the audit minimum of 200. This is still one frozen-parameter window, not a refit walk-forward.

Funding covered 107/2160 trades. Avg net R after funding: -0.286. EOD marks: 0.
Exit reasons: sl=373, sl_gap=2, sl_trailed=54, thesis=1262, tp=468, tp_gap=1. Exit candles: 1m=2160.

By symbol

| slice | n | hit rate (net R>0) | avg gross R | avg net R | sum net R | profit factor | max DD (R) | max time under water |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| SOL | 463 | 24.2% | -0.040 | -0.315 | -145.775 | 0.46 | 148.892 | 206.4d |
| BNB | 437 | 18.1% | 0.001 | -0.274 | -119.892 | 0.43 | 121.117 | 208.0d |
| ETH | 418 | 27.3% | 0.066 | -0.209 | -87.492 | 0.59 | 91.393 | 200.2d |
| BTC | 378 | 20.1% | -0.016 | -0.291 | -110.107 | 0.42 | 110.107 | 207.0d |
| ARB | 291 | 26.5% | -0.109 | -0.381 | -110.918 | 0.45 | 115.797 | 205.0d |
| OP | 173 | 37.6% | 0.014 | -0.258 | -44.598 | 0.64 | 45.270 | 207.5d |

By regime at entry

| slice | n | hit rate (net R>0) | avg gross R | avg net R | sum net R | profit factor | max DD (R) | max time under water |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| TREND | 1697 | 24.4% | -0.020 | -0.294 | -498.931 | 0.48 | 502.053 | 207.7d |
| RANGE | 463 | 23.5% | 0.016 | -0.259 | -119.852 | 0.51 | 121.632 | 207.9d |

Chronological holdout (no refit). Cut at 2026-07-19T06:39:20+00:00 — last third of the scanned span is the holdout.

| slice | n | hit rate (net R>0) | avg gross R | avg net R | sum net R | profit factor | max DD (R) | max time under water |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| earlier | 1308 | 23.0% | -0.039 | -0.313 | -409.627 | 0.45 | 410.852 | 137.6d |
| holdout | 852 | 26.1% | 0.028 | -0.245 | -209.157 | 0.55 | 211.682 | 68.2d |

By entry month

| slice | n | hit rate (net R>0) | avg gross R | avg net R | sum net R | profit factor | max DD (R) | max time under water |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 2026-09 | 384 | 28.4% | 0.021 | -0.251 | -96.404 | 0.57 | 98.929 | 25.3d |
| 2026-07 | 363 | 23.4% | 0.002 | -0.273 | -99.192 | 0.48 | 99.192 | 30.7d |
| 2026-06 | 317 | 21.5% | -0.125 | -0.400 | -126.659 | 0.37 | 126.659 | 29.5d |
| 2026-08 | 311 | 23.8% | 0.017 | -0.258 | -80.088 | 0.51 | 80.088 | 28.8d |
| 2026-03 | 284 | 26.4% | 0.001 | -0.274 | -77.862 | 0.52 | 79.428 | 29.4d |
| 2026-05 | 265 | 20.0% | -0.050 | -0.324 | -85.875 | 0.41 | 85.875 | 28.9d |
| 2026-04 | 236 | 25.0% | 0.052 | -0.223 | -52.704 | 0.57 | 53.930 | 29.8d |

Diagnostics: decisions=1807200, signals=3059, hard_veto=899, geometry_veto=0, bb_block=0, regime_skips=0, weekend_skips=510572, cooldown_skips=3804, direction_block=0, invalid_bracket=0, unresolved=0, errors=0.

Entry timing vs the confirmed 15m close (measured, not a filter):
- chase ATR: n=2160, median 0.38, p75 0.57, p90 0.80, max 2.98. 54.4% of fills are more than 0.35 ATR past that close (the cap drafted in abandoned PR #28; it is not applied on this run).
- minutes after the 15m close: n=2160, median 7, p90 13, max 14.

## What this does not say

A positive average on a short window is not an edge. The audit kill lines (profit factor under 1.1 after costs, n under 200, hit rate under 40% for a 2R trend plan or under 58% for a 1R cascade) are only meaningful once n is large. Max drawdown here is in R units assuming 1R risk per trade added when each trade closes, not a percent of account equity.
