# Strategy Guide — Bot = machine, Strategy = plan

NovaBot’s loop, orders, state, Discord, and **capital** `risk_profile` live in the bot.
Everything that decides *whether / how* to trade a setup belongs in the **strategy**:

| In the strategy | In the bot (machine) |
|-----------------|----------------------|
| `params` / `get_param` | Loop, HL entry/exit, state |
| `AI_PERSONA` / `get_ai_persona()` | `risk_profile` capital appetite (min R:R floor, lev, min conf) |
| `get_ai_validation_criteria()` | Discord, storage |
| `check_hard_veto()` | Trailing default if `manage_trade` returns `None` |
| `score_scan_candidate()` / scan TF | ScannerJob orchestrator (universe, merge, top-K) |
| `post_ai_adjust()` | Multi-position book (`trade_id`), top-K analysis |
| `generate_signal` / `add_indicators` | Timeline API (`GET /api/history/timeline`) |
| optional `manage_trade` | |

Reference: [`supertrend.py`](./supertrend.py) (15m) and [`trend_lt.py`](./trend_lt.py) (1h).

---

## SuperTrend (ST) vs Trend LT

| | **SuperTrend** | **Trend LT** |
|--|----------------|--------------|
| Key | `supertrend` | `trend_lt` |
| TF | 15m context + 1m trigger | 1h context + 1h reclaim |
| Setup | EMA200 + ST, pullback → reclaim | Same idea on 1h (progressive swings) |
| Engine `type` | `trend` (needs 15m TREND regime) | `always_active` (own 1h ADX filters) |
| Priority | Lower if both fire same tick | **Wins** over ST on same symbol/tick |

Do **not** soften ST filters to catch LT-style moves — use Trend LT instead.

---

## Multi-positions (HL-safe)

- Bookkeeping: `TradeBook` keyed by `trade_id` + symbol index (`app/core/trade_book.py`).
- `max_positions` configurable (live default **2**). Same-symbol concurrent stays off (HL nets one position per coin).
- `allow_same_symbol_concurrent=false` by default — Hyperliquid nets **one position per coin**.
- Same symbol + ST/LT: first entry wins the symbol slot; the other waits for flat.
- **Money management**: profile risk % / fixed margin / notional cap are **÷ `max_positions`**
  so N concurrent slots ≈ 1× the intended portfolio budget (not N×).

---

## Top-K analysis / strategy-owned scan

`ScannerJob` builds a liquid universe once, then each **enabled** strategy scores
candidates via `score_scan_candidate` on its `get_scan_timeframe()` (15m ST, 1h LT).
Boards are merged (union by symbol, max score). Sticky ∪ top-K
(`scanner_settings.analyze_top_k`, default **3**) feeds the trading loop.

- Scan = context TF only. SuperTrend **1m trigger** stays in `generate_signal` after focus.
- `active_symbol` is UI/scanner focus, not the only analyzed market.
- Sticky `looking_for_entry` is per `(strategy, symbol)` in `bot_state.json`.

---

## Timeline debug

`GET /api/history/timeline?symbol=&trade_id=&trace_id=&limit=`  
Aggregates signal analysis + trade history + activity log.  
Signal records include `trace_id` / `trade_id` when available.

---

## Checklist — add a new strategy

1. **Copy** [`_template_strategy.py`](./_template_strategy.py) → `ma_strategie.py`.
2. **Implement** the contract (persona, **TF-appropriate** `check_hard_veto`, optional `post_ai_adjust`, `generate_signal`, and `score_scan_candidate` if the strat should appear in the scanner).
3. **Register** in [`engine.py`](./engine.py):
   ```python
   from strategies.ma_strategie import StrategyMaStrategie
   self.strategies = {
       "supertrend": StrategySupertrend(...),
       "trend_lt": StrategyTrendLT(...),
       "ma_strategie": StrategyMaStrategie(strats_config.get("ma_strategie")),
   }
   ```
4. **Params JSON** in [`data/config/strategies.json`](../data/config/strategies.json) and [`app/core/defaults/strategies.default.json`](../app/core/defaults/strategies.default.json).
   - `type: "trend"` → ADX regime gate from 15m engine.
   - `type: "always_active"` → always evaluated (still apply your own filters).
   - Non-15m: set `"timeframe": "1h"` (skips engine 15m BB anti-chase; drives scan TF).
   - Optional `"scan_interval_minutes"` in params (else derived from timeframe).
   - Same-tick priority: `"signal_score_bonus": 100` (not hardcoded names in bot/engine).
5. **Tests**: veto + signal reject + scan score path (if scannable) under `tests/unit/`.
6. **Do not** put métier thresholds in `bot.py` or global scalp rules in `prompts.py`.

Agent skill: [`.cursor/skills/create-novabot-strategy/SKILL.md`](../.cursor/skills/create-novabot-strategy/SKILL.md).

---

## Contract (BaseStrategy)

See [`base.py`](./base.py).

- `get_ai_persona()` → string merged as **STRATEGY PERSONA (PRIMARY)** in AI validation.
- `get_ai_validation_criteria()` → criteria block in the user prompt (or `None` for generic).
- `check_hard_veto(side, ctx)` → reason string or `None`. Called **before** AI spend. **1 strategy = 1 veto plan** (do not blindly reuse ST 15m helpers for a 1h swing).
- `get_scan_timeframe()` / `get_scan_interval_minutes()` / `score_scan_candidate(df, symbol=, meta=)` → strategy-owned universe ranking (default: no scan).
- `post_ai_adjust(signal, ai_result, ctx)` → mutate AI result (e.g. trim TP) **before** R:R / volume hard gates.
- `get_min_volume_ratio_pct()` → post-AI WEAK_VOLUME floor (optional).
- `get_rr_epsilon()` → default `0.02` when comparing post-trim R:R to capital profile min.

Shared veto helpers (optional import): [`app/core/veto_checker.py`](../app/core/veto_checker.py) — **not** a global bot law.

---

## Anti-patterns

- `if strategy_id == "supertrend":` métier logic inside `ia.py` / `bot.py` / `scanner_job.py`
- Hardcoding scalp SL bands (0.8%–2.5%) in the global system prompt
- Softening SuperTrend (or any strat) vetoes “to get more trades” without changing that strat’s plan on purpose
- A single generic scanner score for all strategies
- Scattering the same threshold in scanner + strat + IA without a single `get_param` source
- Assuming `active_trades[symbol]` is the only open trade — use `trade_book` / `can_open_trade`

---

## Persona model

**1 strategy = 1 métier persona** (`AI_PERSONA`).  
UI “personas” (Conservative Scalper / …) are **capital temperaments** only; they must not override strategy geometry.
