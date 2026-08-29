# NovaBot strategy & risk review (small-bankroll)

**Date:** 2026-08-29  
**Scope:** code + committed config in this repo.  
**Account used for arithmetic:** ~87 USDC (owner-stated; **not** read from an exchange).  
**No trades placed. No secrets committed. No live PnL invented.**

## Evidence status

| Source | Result |
|--------|--------|
| Live API `http://10.10.20.79:3001/health` | **Unreachable.** `curl -m 8` timed out (exit 28). No retry (RFC1918 from this cloud VM). |
| `/api/logs`, `/api/history/bot/trades`, `/api/history/bot/trades/stats`, `/api/history/timeline`, `/api/signal-analysis` | Not fetched (host unreachable). |
| `data/state`, `logs/`, `trade_history.csv`, signal-analysis dumps, `daily_pnl_snapshot.json`, `bot_state.json` | **Absent from the working tree.** `.gitignore` excludes `data/*` (except `data/config/`), `logs/`, `bot_state.json`, `daily_pnl_snapshot.json`. |
| Git history | Config + code only. No committed fill log or PnL snapshot. |

**This analysis is code-only** plus the committed files `data/config/strategies.json` and `data/config/user_settings.json`. Fill rate, win rate, and realized PnL cannot be verified from here.

---

## 1. How strategies are selected and combined

Verified in `strategies/engine.py`, `app/core/scanner_job.py`, `app/core/bot.py`, `strategies/README.md`.

### Engine regime (15m primary frame)

1. ADX(14) on the confirmed 15m bar (`iloc[-2]`). Slope = ADX[-2] − ADX[-3].
2. **TREND** if ADX > regime threshold **and** slope ≥ −3; else **RANGE**.
3. Regime threshold is `max(adx_threshold)` across enabled trend / always_active strats, else `market_regime.adx_threshold` (22). After this PR only SuperTrend still contributes `adx_threshold=22` (Trend LT uses 20 but is `always_active`).
4. Live 15m **waterfall** (double red, lower lows, price < EMA9 < EMA20) forces `TREND_BEAR_STRONG`.
5. Else live 15m **rocket** (double green, higher highs, price > EMA9 > EMA20) forces `TREND_BULL_STRONG`.

### Who runs on a tick

| `type` | When evaluated |
|--------|----------------|
| `trend` (supertrend, rocket, waterfall) | Only in `TREND`, `TREND_BEAR_STRONG`, or `TREND_BULL_STRONG` |
| `always_active` (trend_lt, range_lt) | Every tick (own 1h filters) |

Important: a bear cascade still **activates every `type=trend` strat**, including rocket (long-only). Rocket should not emit a BUY there, but SuperTrend can still fire opposite to waterfall on the same symbol. Same-symbol concurrency is blocked by `TradeBook` (`allow_same_symbol_concurrent=false`). Cross-symbol stacking is not.

Same-tick winner is **highest `score`**. Score starts at 50, plus optional AI confidence, plus `signal_score_bonus`:

| Strategy | bonus (was) |
|----------|-------------|
| waterfall / rocket | 120 |
| trend_lt | 100 |
| range_lt | 50 |
| supertrend | 0 |

Engine 15m Bollinger anti-chase applies to SuperTrend only (rocket/waterfall set `skip_bb_anti_chase`; 1h TFs skip it).

Weekend pause (`app/core/weekend_pause.py`) idles **rocket + waterfall** by default Saturday 06:00 → Monday 06:00 Europe/Paris (`enabled` defaults true even without a `weekend_pause` block). SuperTrend / LT keep running.

### Scanner + analysis loop

- Each **enabled** strategy scores the whitelist on its own TF (`score_scan_candidate`). Boards merge by symbol (max score wins).
- `auto_switch: false` does **not** stop analysis. Top-K (`analyze_top_k` default **3**) symbols with score ≥ `min_score` (70) are analyzed every loop; sticky `looking_for_entry` symbols are **appended**.
- `_strategies_for_analysis` only runs lanes that scored that symbol ≥ min_score (or are armed). So rocket/waterfall do not have to emit on a SuperTrend-only hit — but they **do** compete for the 3 analysis slots via the merged board.
- Scan cadences: rocket/waterfall **5m**, SuperTrend **15m**, LT **60m**. **Hunch:** 5m cascade lanes + bonus 120 will occupy top-K on volatile days and starve the slower book. Not proven without live scanner snapshots.

Funding (`funding_filter_enabled: true`) is a **universe** filter in `app/services/supertrend_scanner.py`: drop a coin if funding > 0.0011 **or** < −0.0045, regardless of intended side. It is not a per-signal veto inside `generate_signal`.

---

## 2. How risk_profile / veto / AI gate entries

```
generate_signal → engine filters (side, 15m BB)
  → TradeBook / max_positions / daily stop
  → strategy.check_hard_veto()          # before AI spend
  → ia.validate_signal()                # strategy AI_PERSONA is PRIMARY
  → required_ai_confidence()
  → post_ai_adjust + mechanical min R:R + volume floor
  → risk_pct sizing + profile leverage on the exchange
```

### Risk profile is the real risk knob (not the UI persona)

Verified in `app/core/risk_profiles.py`, `app/core/bot.py` (`_resolve_trade_leverage`, sizing ~L3262), `app/core/prompts.py`.

| Preset | min R:R (AI gate) | risk_pct (sizing) | max_leverage (live) | min_conf |
|--------|-------------------|-------------------|---------------------|----------|
| Capital Preservation First | 1.5 | **1.5%** | **3x** | 62 |
| Balanced Growth | 1.3 | **3.5%** | **5x** | 55 |
| High Volatility Hunter | 1.0 | **7.0%** | **10x** | 48 |

Account `risk_defaults.risk_profile` is only a **fallback** when a strategy omits `risk_profile`. Live book had Balanced Growth (ST / Trend LT) and HV Hunter (rocket / waterfall). Account default “Capital Preservation First” did **not** apply to those four.

`bot_persona: "Conservative Scalper"` is **capital temperament text** in the system prompt. `strategies/README.md` and `prompts.py` say it must not override strategy geometry. Strategy `AI_PERSONA` is injected as **PRIMARY**. Conservative Scalper does **not** shrink size.

### `default_leverage` does not cap live trades

Verified: `bot._resolve_trade_leverage` returns `get_max_leverage(profile)` only. `clamp_leverage()` exists and is **unused** for live sizing (`risk_profiles.py` docstring + `config.py` comment: “Account UI fallback only”).

So `default_leverage: 2` (now 1 in this PR) **does not** put 1x/2x on Hyperliquid. SuperTrend/Trend LT were **5x**; rocket/waterfall were **10x**. Isolated margin type is still read from `risk_defaults.default_margin_type`.

### Daily stop and position cap (portfolio ceilings)

`RiskManager` (`app/core/risk_manager.py`): halt when `daily_pnl <= -daily_stop_loss`; block when `open_positions >= max_positions`. These are the only account-level brakes. They do **not** cap per-trade notional.

Was: `daily_stop_loss: 30` on ~87 USDC ≈ **34% of the account per day**. This PR sets **6** (~7%).

### Sizing math (code, assumed equity 87)

Live path is `method="risk_pct"` with profile `risk_pct`, then **÷ `max_positions`**.

Notional ≈ `(equity × risk_pct / 100 / max_positions) / sl_distance_pct`.

There is **no $10 notional cap**. Account cap is `equity × MAX_NOTIONAL_CAP_MULTIPLIER` (50) ÷ slots ≈ **$2,175/slot** — irrelevant here. Hyperliquid floor is `MIN_POSITION_NOTIONAL_USD = 12` (`app/core/constants.py`). A true “$10 max” is **below the exchange minimum**; $12 is the practical floor.

Illustrative notionals at **equity 87** (not live fills):

| Book | risk/trade | SL 0.4% | SL 0.8% | SL 1.2% | SL 2.0% |
|------|------------|---------|---------|---------|---------|
| HV Hunter, max_pos=2 | 3.5% = $3.05 | **$761** | $381 | $254 | $152 |
| Balanced, max_pos=2 | 1.75% = $1.52 | $381 | $190 | $127 | $76 |
| Preservation, max_pos=1 (this PR) | 1.5% = $1.31 | $326 | $163 | $109 | $65 |

Tighter stops (rocket/waterfall `min_sl_pct=0.4`, `sl_atr_mult=0.5`) **increase** notional under risk-% sizing. Owner target “~$10 / 1x” is **not reachable from JSON alone**. Needs a hard notional clamp in `RiskManager` / `bot.py`, and `clamp_leverage(profile, account default_leverage)` if 1x is a hard cap.

Fallback when SL is missing: `DEFAULT_SIZE_USDC=20` margin × profile leverage ÷ slots (e.g. HV 10x → $100 notional/slot before the 50× cap).

### Veto and AI

- **Hard veto** is strategy-owned (`check_hard_veto`). SuperTrend reuses `app/core/veto_checker.py` (RSI 80/30, ADX runaway 75, volume < 50%). Others have their own bars (below).
- AI system prompt uses **strategy** risk-profile min R:R / min_conf / max SL%, plus UI persona as temperament.
- After approve: `required_ai_confidence`. Balanced/Preservation HIGH still needs **75**. HV Hunter HIGH is relaxed to **medium bar (55 / user 60)** so 65–72% cascade approvals can trade (`risk_profiles.required_ai_confidence`).
- Then IA `_enforce_hard_constraints`: profile min R:R (after `post_ai_adjust` TP trim) and strategy volume floor.

User `conf_threshold_medium: 60` is already stricter than the code default 55.

---

## 3. Per-strategy thresholds (fill rate vs quality on ~87 USDC)

Params from `data/config/strategies.json` (unchanged numbers except enable/profile flags in this PR).

### SuperTrend (15m, `type=trend`) — **keep, profile → Preservation**

| Param | Value | Effect |
|-------|-------|--------|
| `adx_threshold` | 22 | Needs 15m TREND; also raises engine regime floor |
| `min_adx_slope` | −0.35 | Drops dying trends |
| `max_rsi_long` / `min_rsi_short` | 60 / 40 | Chase filter |
| `rsi_neutral_low/high` | 46–54 | Dead-zone skip (stop-hunt) |
| `max_extension_atr` | 1.4 | No mid-impulse chase |
| `require_pullback` | true | 1m must tag ST within `pullback_touch_atr` 1.0 over 30 bars |
| `require_recent_flip` | false | Does not demand a fresh ST flip |
| `min_rr` | 2.0 | Geometry; AI floor is profile 1.5 after this PR |
| `sl_atr_mult` / `min_sl_pct` | 2.0 / 0.8% | Wide-ish ST stop → smaller risk-% notional than cascades |
| `cooldown_minutes` | 15 | Fill cooldown |
| `min_volume_ratio_pct` | 50 | Veto + post-AI |
| `scan_interval_minutes` | 15 | Matches scanner poll |

Quality is already fairly tight (pullback + RSI + ADX slope). Main risk on this account is **sizing** (was 3.5%/5x), not loose entries.

### Trend LT (1h, `always_active`) — **keep, profile → Preservation**

| Param | Value | Effect |
|-------|-------|--------|
| `adx_threshold` | 20 | Slightly easier than ST 22; own 1h series |
| `min_adx_slope` | −0.5 | Looser than ST |
| `max_rsi_long` / `min_rsi_short` | 65 / 35 | Wider than ST |
| `max_extension_atr` | 2.0 | Allows more extension |
| `require_pullback` | true | 1h ST tag within 1.2 ATR, lookback 12 |
| `min_rr` | 2.0 | Same as ST |
| `sl_atr_mult` / `min_sl_pct` | 2.0 / **1.2%** | Wider min SL than ST → smaller notional |
| `cooldown_minutes` | 60 | Low frequency |
| `scan_interval_minutes` | 60 | Quiet lane |
| Veto RSI / ADX | 85 / 20 / runaway 85 | Swing-calibrated (not ST 15m helper) |

Best match for a small book: fewer signals, wider stops, same thesis as SuperTrend. Complements ST; they can still compete for the single slot (`max_positions=1`).

### Range LT (1h fade, `always_active`) — **disabled in this PR**

| Param | Value | Why it fights the trend book |
|-------|-------|------------------------------|
| `adx_max` | 18 | Wants **low** 1h ADX; Trend LT wants **≥20**. Same coin is mostly exclusive; **different coins** can still take both slots (was max_pos=2). |
| `ema_slope_flat_max` | 0.0004 | Flat EMA50 |
| `min/max_range_pct` | 2–12 | Box must exist |
| `edge_frac` | 0.28 | Close must be at the box edge |
| `sl_atr_mult` / `min_sl_pct` | **0.4 / 0.4%** | Tight fade stop → **large** risk-% notional |
| `veto_rsi_long_max` / `short_min` | 58 / 42 | Tight fade veto |
| `veto_adx_trend` | 28 | Blocks if 1h ADX already trending |
| `cooldown` / scan | 60 / 60 | Low freq |

Thesis is fade; Trend LT is continuation. Do not run both on this capital.

### Waterfall (15m short cascade) — **disabled**

| Param | Value | Risk on $87 |
|-------|-------|-------------|
| `risk_profile` | High Volatility Hunter | 7% / 10x |
| `min_rr` | 1.0 | Profile AI floor also 1.0 |
| `sl_atr_mult` / `min_sl_pct` | 0.5 / 0.4% | Tight SL → huge notional |
| `cooldown_minutes` | 10 | Fast re-entry |
| `scan_interval_minutes` | 5 | Dominates merge |
| `signal_score_bonus` | 120 | Beats ST/LT on same tick |
| `veto_rsi_oversold` | 18 | Allows deep RSI shorts |
| `volume_spike_pct` | 120 | Soft volume / spike mix |
| `require_1m_confirm` | true | Good |
| `skip_bb_anti_chase` | true | Engine BB will not save a chase |

### Rocket (15m long cascade) — **disabled**

Mirror of waterfall (`veto_rsi_overbought` 82). Same HV sizing, 5m scan, bonus 120. Can occupy top-K while waterfall occupies another coin (long vs short on two names).

---

## 4. Ordered recommendations

Applied in this PR (config only; no engine rewrite):

1. **`daily_stop_loss` 30 → 6** (`user_settings.json`). 30 USDC/day is about a third of ~87. 6 ≈ 7%. If you want a hard “two losers and stop”, use **4–5** after you see typical $ at risk.
2. **`max_positions` 2 → 1.** One thesis. Avoids trend-vs-fade or rocket-vs-waterfall stacking. Note: risk-% is no longer split, so remaining strats were moved to Preservation (1.5%) to compensate.
3. **Disable `rocket` and `waterfall`.** HV Hunter + tight SL + 5m scan + bonus 120 is the worst fit for this bankroll.
4. **Disable `range_lt` while `trend_lt` is on.** Opposite 1h plans.
5. **Set `supertrend` and `trend_lt` `risk_profile` to `Capital Preservation First`.** This is the change that actually cuts leverage (5x→3x) and risk (3.5%→1.5%). The account default alone does not.

Still recommended, **not implemented** (needs a small code change, not a rewrite):

6. **Wire `clamp_leverage(profile_lev, account default_leverage)`** in `bot._resolve_trade_leverage`. Today `default_leverage: 1` is cosmetic. Tests already cover `clamp_leverage`.
7. **Add a hard per-trade notional cap (~$12, HL min).** Risk-% + ATR stops will still size $65–$160 on Preservation/1-slot. There is no JSON knob for “$10 max”.
8. If you want the quietest book after watching a week: **disable SuperTrend too** and run **Trend LT only** (60m scan, 60m cooldown). **Hunch:** fewer AI calls and less 15m noise. Not proven.

Optional tighten later (only if ST still feels busy; do **not** loosen vetoes to “get more trades”):

| Knob | Now | Conservative tweak | File |
|------|-----|--------------------|------|
| SuperTrend `adx_threshold` | 22 | 25 | `strategies.json` params |
| SuperTrend `cooldown_minutes` | 15 | 30 | same |
| SuperTrend `max_rsi_long` | 60 | 58 | same |
| Trend LT `adx_threshold` | 20 | 22 | same |
| Scanner `min_score` | 70 | keep | already selective |
| Scanner whitelist (~25) | keep | shrink later if you want | `user_settings.json` |
| `auto_switch` | false | keep false | same |

Do **not** drop SuperTrend `require_pullback` or Range/cascade `min_sl_pct` on this account (tighter SL = larger size).

---

## 5. What this PR changed vs what it did not

**Changed**

- `data/config/strategies.json`: rocket / waterfall / range_lt `enabled`+`active` false; ST + Trend LT `risk_profile` = Capital Preservation First. Thresholds themselves left intact.
- `data/config/user_settings.json`: `daily_stop_loss` 6, `max_positions` 1, `default_leverage` 1. No secrets added. File is listed in `.gitignore` but is already tracked.

**Not changed** (on purpose)

- `app/core/defaults/strategies.default.json` (product template).
- `risk_profiles.py` leverage/risk_pct tables.
- Engine / scanner / IA code.
- No `clamp_leverage` wiring, no $12 notional cap.

**Persona mismatch (explained, not a bug):** UI “Conservative Scalper” + account “Capital Preservation First” vs strategy presets Balanced / HV Hunter. Geometry and size follow the **strategy** preset. This PR aligns the remaining live strats with Preservation.

---

## 6. Merge / deploy notes

`user_settings.json` and `strategies.json` are live bot config. Merging this PR changes the **next process restart / settings reload** book: three strategies off, daily stop 6, one slot, Preservation sizing (still ~3x, still not $10 notionals until code grows a cap).

If the running host at 10.10.20.79 still has old in-memory settings, confirm via `/api/config/strategies-config` and `/api/status` **from that LAN** after deploy. This VM cannot see that API.
