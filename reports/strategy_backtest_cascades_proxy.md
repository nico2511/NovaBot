# PROXY causal backtest — Binance USDT-M, not Hyperliquid

LABEL: PROXY. These prices are Binance USDT-M perpetual klines from `data.binance.vision`. They are not the Hyperliquid dump and must not be compared as if they were the same market.

## Verdict (provisoire)

Pas d'edge sur cette fenêtre proxy, avec n encore sous 200. Rocket : n=122, hit 35,2 %, avg net R −0,109, PF 0,69, max DD 16,8 R. Waterfall : n=83, hit 31,3 %, avg net R −0,280, PF 0,32, max DD 23,2 R. Les deux holdouts (après le 18 Jul 2026) sont pires que la première partie. Ce n'est pas un walk-forward, et l'intervalle de confiance à n<200 peut encore contenir zéro. Le signe, lui, est négatif des deux côtés.

Fenêtre : 2026-03-01 → 2026-09-25, 25/25 coins de la whitelist (`COIN` → `COINUSDT`). Aucun coin sauté. Le fichier du 26 Sep 2026 n'était pas sur l'archive (404) ; 0 trou dans les 1m et 15m présents. Waterfall n'a pas tradé ARB ni BNB ; les bougies sont là, le plan n'a pas donné de signal.

Chase (mesuré, filtre #28 non appliqué) : médiane ~0,5 ATR au-delà du close 15m confirmé, environ 62–66 % des fills au-dessus de 0,35 ATR. Le délai d'horloge est court : médiane 5 min, max 10 min (pas de scan 5m). Le retard prix est réel ; l'attente calendaire ne dépasse pas deux pas de 5m.

Funding Binance (règlement 8h, 4h pour HYPE et TIA) s'arrête au 31 Aug 2026 : les fichiers journaliers de septembre sont en 404. Seulement ~26 % des trades contiennent un règlement dans le hold, et la moyenne après funding ne bouge pas (−0,109 / −0,280). Le coût de funding est donc presque absent, pas un coût HL horaire.

Params : `main`. PR #28 abandonnée, non appliquée. Cache local `data/ohlcv_proxy/` (~425 Mo, gitignoré). Rebuild : `python -m app.core.proxy_ohlcv`.

Params are `data/config/strategies.json` on this branch (based on `main`).
Main params only. Abandoned PR #28 was not applied. Rocket and waterfall use the main 5-minute decision step.
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

Symbols (example scanner whitelist, not the live top-K): BTC, ETH, SOL, ARB, OP, SUI, APT, AVAX, LINK, UNI, AAVE, ADA, NEAR, INJ, TIA, DOT, ATOM, LTC, BCH, XRP, BNB, TRX, HYPE, DOGE, ZEC.
Config file: `data/config/strategies.json`.

## PR #28

Not used. These numbers are **main** params (`data/config/strategies.json`). PR #28 is abandoned and was not applied. The 0.35 ATR figure in the chase section is only a reference line on the measured distribution.

## Results

| slice | n | hit rate (net R>0) | avg gross R | avg net R | sum net R | profit factor | max DD (R) | max time under water |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| rocket | 122 | 35.2% | -0.028 | -0.109 | -13.256 | 0.69 | 16.757 | 191.5d |
| waterfall | 83 | 31.3% | -0.180 | -0.280 | -23.244 | 0.32 | 23.244 | 205.9d |

### rocket

Status: enabled in strategies.json.
Decisions scanned: 2026-03-01T20:00:00+00:00 → 2026-09-25T23:55:00+00:00.
- BTC 1m: 300960 bars 2026-03-01T00:00:00+00:00 → 2026-09-25T23:59:00+00:00
- BTC 15m: 20064 bars 2026-03-01T00:00:00+00:00 → 2026-09-25T23:45:00+00:00

n=122 is below the audit minimum of 200. A confidence interval on mean R at this size still includes zero even when the point estimate does not.

Funding covered 31/122 trades. Avg net R after funding: -0.109. EOD marks: 0.
Exit reasons: sl=8, sl_gap=7, sl_trailed=15, thesis=73, tp=19. Exit candles: 1m=122.

By symbol

| slice | n | hit rate (net R>0) | avg gross R | avg net R | sum net R | profit factor | max DD (R) | max time under water |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| OP | 10 | 60.0% | 0.378 | 0.323 | 3.227 | 3.67 | 0.659 | 150.1d |
| LINK | 9 | 33.3% | -0.162 | -0.232 | -2.084 | 0.45 | 2.117 | 201.7d |
| ATOM | 8 | 62.5% | 0.415 | 0.326 | 2.606 | 2.50 | 0.785 | 77.4d |
| AVAX | 8 | 37.5% | -0.209 | -0.301 | -2.409 | 0.17 | 2.587 | 143.0d |
| DOT | 8 | 25.0% | -0.195 | -0.266 | -2.129 | 0.42 | 3.108 | 189.4d |
| NEAR | 8 | 37.5% | -0.111 | -0.166 | -1.327 | 0.56 | 2.778 | 163.5d |
| SOL | 8 | 37.5% | 0.077 | -0.017 | -0.139 | 0.95 | 1.485 | 162.1d |
| UNI | 7 | 42.9% | -0.050 | -0.120 | -0.843 | 0.70 | 1.358 | 157.1d |
| HYPE | 6 | 50.0% | 0.139 | 0.094 | 0.567 | 1.37 | 1.097 | 49.1d |
| SUI | 6 | 50.0% | -0.091 | -0.195 | -1.169 | 0.57 | 1.642 | 63.7d |
| ZEC | 6 | 33.3% | -0.137 | -0.196 | -1.175 | 0.55 | 2.622 | 164.9d |
| AAVE | 5 | 20.0% | -0.057 | -0.122 | -0.608 | 0.70 | 2.049 | 100.6d |
| TIA | 5 | 20.0% | -0.130 | -0.183 | -0.917 | 0.61 | 1.270 | 60.7d |
| APT | 4 | 50.0% | -0.078 | -0.200 | -0.801 | n/a (n<5) | 0.801 | 68.2d |
| ARB | 4 | 25.0% | 0.276 | 0.158 | 0.634 | n/a (n<5) | 0.795 | 47.4d |
| ADA | 3 | 0.0% | -0.477 | -0.550 | -1.650 | n/a (n<5) | 1.650 | 115.9d |
| INJ | 3 | 33.3% | 0.021 | -0.024 | -0.072 | n/a (n<5) | 1.512 | 136.3d |
| XRP | 3 | 0.0% | -0.414 | -0.595 | -1.785 | n/a (n<5) | 1.785 | 146.9d |
| BNB | 2 | 0.0% | -0.367 | -0.510 | -1.020 | n/a (n<5) | 1.020 | 132.0d |
| DOGE | 2 | 0.0% | -0.101 | -0.179 | -0.358 | n/a (n<5) | 0.358 | 46.8d |
| ETH | 2 | 0.0% | -0.315 | -0.412 | -0.823 | n/a (n<5) | 0.823 | 17.8d |
| LTC | 2 | 50.0% | -0.127 | -0.203 | -0.406 | n/a (n<5) | 0.411 | 59.2d |
| BCH | 1 | 0.0% | 0.000 | -0.132 | -0.132 | n/a (n<5) | 0.132 | 0.0d |
| BTC | 1 | 0.0% | 0.070 | -0.014 | -0.014 | n/a (n<5) | 0.014 | 0.0d |
| TRX | 1 | 0.0% | -0.174 | -0.429 | -0.429 | n/a (n<5) | 0.429 | 0.1d |

By regime at entry

| slice | n | hit rate (net R>0) | avg gross R | avg net R | sum net R | profit factor | max DD (R) | max time under water |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| TREND_BULL_STRONG | 122 | 35.2% | -0.028 | -0.109 | -13.256 | 0.69 | 16.757 | 191.5d |

Chronological holdout (no refit). Cut at 2026-07-18T14:36:40+00:00 — last third of the scanned span is the holdout.

| slice | n | hit rate (net R>0) | avg gross R | avg net R | sum net R | profit factor | max DD (R) | max time under water |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| earlier | 89 | 38.2% | -0.007 | -0.089 | -7.917 | 0.73 | 8.968 | 118.7d |
| holdout | 33 | 27.3% | -0.084 | -0.162 | -5.339 | 0.62 | 8.103 | 45.9d |

By entry month

| slice | n | hit rate (net R>0) | avg gross R | avg net R | sum net R | profit factor | max DD (R) | max time under water |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 2026-04 | 27 | 29.6% | -0.015 | -0.109 | -2.948 | 0.69 | 4.067 | 20.1d |
| 2026-05 | 21 | 52.4% | 0.173 | 0.105 | 2.205 | 1.39 | 1.824 | 13.5d |
| 2026-06 | 19 | 26.3% | -0.218 | -0.282 | -5.361 | 0.11 | 5.846 | 23.8d |
| 2026-09 | 16 | 37.5% | 0.085 | 0.022 | 0.350 | 1.06 | 3.425 | 11.6d |
| 2026-08 | 14 | 21.4% | -0.235 | -0.320 | -4.476 | 0.39 | 5.916 | 16.7d |
| 2026-07 | 13 | 38.5% | -0.033 | -0.146 | -1.904 | 0.49 | 3.555 | 27.0d |
| 2026-03 | 12 | 41.7% | -0.011 | -0.093 | -1.121 | 0.79 | 2.093 | 15.6d |

Diagnostics: decisions=1498800, signals=165, hard_veto=43, geometry_veto=0, bb_block=0, regime_skips=416042, weekend_skips=420000, cooldown_skips=5, direction_block=0, invalid_bracket=0, unresolved=0, errors=0.

Entry timing vs the confirmed 15m close (measured, not a filter):
- chase ATR: n=122, median 0.49, p75 0.81, p90 1.22, max 3.89. 62.3% of fills are more than 0.35 ATR past that close (the cap drafted in abandoned PR #28; it is not applied on this run).
- minutes after the 15m close: n=122, median 5, p90 10, max 10.

### waterfall

Status: enabled in strategies.json.
Decisions scanned: 2026-03-01T20:00:00+00:00 → 2026-09-25T23:55:00+00:00.
- BTC 1m: 300960 bars 2026-03-01T00:00:00+00:00 → 2026-09-25T23:59:00+00:00
- BTC 15m: 20064 bars 2026-03-01T00:00:00+00:00 → 2026-09-25T23:45:00+00:00

n=83 is below the audit minimum of 200. A confidence interval on mean R at this size still includes zero even when the point estimate does not.

Funding covered 22/83 trades. Avg net R after funding: -0.280. EOD marks: 0.
Exit reasons: sl=5, sl_gap=3, sl_trailed=15, thesis=54, tp=6. Exit candles: 1m=83.

By symbol

| slice | n | hit rate (net R>0) | avg gross R | avg net R | sum net R | profit factor | max DD (R) | max time under water |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| XRP | 9 | 22.2% | -0.416 | -0.565 | -5.087 | 0.02 | 5.175 | 190.9d |
| UNI | 7 | 28.6% | -0.166 | -0.223 | -1.563 | 0.56 | 1.712 | 175.2d |
| ETH | 6 | 50.0% | 0.268 | 0.188 | 1.126 | 1.62 | 0.798 | 92.2d |
| HYPE | 5 | 60.0% | 0.085 | 0.014 | 0.068 | 1.04 | 1.059 | 131.2d |
| ZEC | 5 | 40.0% | -0.251 | -0.365 | -1.825 | 0.05 | 1.872 | 114.0d |
| BCH | 4 | 25.0% | -0.431 | -0.553 | -2.212 | n/a (n<5) | 2.212 | 139.8d |
| BTC | 4 | 0.0% | -0.508 | -0.640 | -2.561 | n/a (n<5) | 2.561 | 110.1d |
| DOGE | 4 | 25.0% | -0.242 | -0.347 | -1.387 | n/a (n<5) | 1.427 | 156.3d |
| DOT | 4 | 50.0% | 0.108 | 0.052 | 0.207 | n/a (n<5) | 1.318 | 83.2d |
| INJ | 4 | 50.0% | -0.018 | -0.108 | -0.432 | n/a (n<5) | 0.546 | 84.7d |
| LTC | 4 | 25.0% | -0.054 | -0.195 | -0.781 | n/a (n<5) | 1.018 | 37.5d |
| SUI | 4 | 0.0% | -0.576 | -0.628 | -2.514 | n/a (n<5) | 2.514 | 134.3d |
| ADA | 3 | 66.7% | 0.390 | 0.336 | 1.009 | n/a (n<5) | 0.534 | 34.9d |
| SOL | 3 | 33.3% | -0.331 | -0.436 | -1.307 | n/a (n<5) | 1.367 | 189.2d |
| AAVE | 2 | 50.0% | 0.057 | 0.001 | 0.002 | n/a (n<5) | 0.044 | 132.4d |
| ATOM | 2 | 0.0% | -0.569 | -0.666 | -1.332 | n/a (n<5) | 1.332 | 15.3d |
| AVAX | 2 | 50.0% | -0.121 | -0.197 | -0.395 | n/a (n<5) | 0.479 | 49.5d |
| LINK | 2 | 0.0% | -0.189 | -0.262 | -0.524 | n/a (n<5) | 0.524 | 153.4d |
| NEAR | 2 | 0.0% | -0.487 | -0.573 | -1.145 | n/a (n<5) | 1.145 | 42.0d |
| OP | 2 | 0.0% | -0.558 | -0.595 | -1.189 | n/a (n<5) | 1.189 | 91.3d |
| TIA | 2 | 0.0% | -0.438 | -0.613 | -1.226 | n/a (n<5) | 1.226 | 94.2d |
| TRX | 2 | 50.0% | 0.036 | -0.184 | -0.368 | n/a (n<5) | 0.593 | 8.1d |
| APT | 1 | 100.0% | 0.426 | 0.192 | 0.192 | n/a (n<5) | 0.000 | 0.0d |

By regime at entry

| slice | n | hit rate (net R>0) | avg gross R | avg net R | sum net R | profit factor | max DD (R) | max time under water |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| TREND_BEAR_STRONG | 83 | 31.3% | -0.180 | -0.280 | -23.244 | 0.32 | 23.244 | 205.9d |

Chronological holdout (no refit). Cut at 2026-07-18T14:36:40+00:00 — last third of the scanned span is the holdout.

| slice | n | hit rate (net R>0) | avg gross R | avg net R | sum net R | profit factor | max DD (R) | max time under water |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| earlier | 47 | 38.3% | -0.155 | -0.237 | -11.162 | 0.40 | 11.162 | 134.8d |
| holdout | 36 | 22.2% | -0.213 | -0.336 | -12.082 | 0.23 | 12.319 | 64.5d |

By entry month

| slice | n | hit rate (net R>0) | avg gross R | avg net R | sum net R | profit factor | max DD (R) | max time under water |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 2026-08 | 15 | 20.0% | -0.306 | -0.432 | -6.484 | 0.03 | 6.484 | 24.1d |
| 2026-09 | 15 | 20.0% | -0.196 | -0.320 | -4.800 | 0.26 | 4.800 | 21.8d |
| 2026-06 | 13 | 46.2% | 0.180 | 0.118 | 1.530 | 1.35 | 1.767 | 13.0d |
| 2026-05 | 12 | 25.0% | -0.453 | -0.539 | -6.467 | 0.02 | 6.524 | 23.2d |
| 2026-07 | 11 | 18.2% | -0.178 | -0.267 | -2.932 | 0.36 | 3.491 | 25.3d |
| 2026-03 | 10 | 50.0% | -0.254 | -0.341 | -3.414 | 0.19 | 3.414 | 23.1d |
| 2026-04 | 7 | 57.1% | 0.026 | -0.097 | -0.676 | 0.51 | 0.961 | 24.7d |

Diagnostics: decisions=1498800, signals=130, hard_veto=47, geometry_veto=0, bb_block=0, regime_skips=416470, weekend_skips=419994, cooldown_skips=2, direction_block=0, invalid_bracket=0, unresolved=0, errors=0.

Entry timing vs the confirmed 15m close (measured, not a filter):
- chase ATR: n=83, median 0.47, p75 0.75, p90 1.11, max 1.66. 66.3% of fills are more than 0.35 ATR past that close (the cap drafted in abandoned PR #28; it is not applied on this run).
- minutes after the 15m close: n=83, median 5, p90 10, max 10.

## What this does not say

A positive average on a short window is not an edge. The audit kill lines (profit factor under 1.1 after costs, n under 200, hit rate under 40% for a 2R trend plan or under 58% for a 1R cascade) are only meaningful once n is large. Max drawdown here is in R units assuming 1R risk per trade added when each trade closes, not a percent of account equity.
