---
name: create-novabot-strategy
description: >-
  Create or extend a NovaBot trading strategy that owns its plan (params, AI
  persona, hard veto, scan ranking, post_ai_adjust, generate_signal,
  evaluate_trade_thesis). Use when adding a new strategy, scaffolding from
  _template_strategy.py, registering in engine.py / strategies.json, writing
  strategy unit tests, or when the user mentions strategies/README.md,
  BaseStrategy, Trend LT, SuperTrend, scanner, trade thesis, or "nouvelle stratégie".
---

# Create NovaBot Strategy

**Source of truth:** read [`strategies/README.md`](../../../strategies/README.md) first, then this skill.

**Rule:** Bot = machine. Strategy = plan. Do **not** put métier thresholds in `bot.py`, `ia.py`, `scanner_job.py`, or scalp bands in `prompts.py`.

## Workflow checklist

Copy and complete:

```
- [ ] 1. Scaffold from strategies/_template_strategy.py → strategies/<key>.py
- [ ] 2. Implement contract (persona, criteria, TF-appropriate veto, optional post_ai_adjust, generate_signal)
- [ ] 3. If scannable: get_scan_timeframe / get_scan_interval_minutes / score_scan_candidate
- [ ] 4. In-trade thesis: supports_trade_thesis + get_thesis_timeframe + evaluate_trade_thesis (+ persist plan fields on signal → trade.metadata)
- [ ] 5. Register in strategies/engine.py
- [ ] 6. Add JSON to data/config/strategies.json AND app/core/defaults/strategies.default.json
- [ ] 7. Unit tests (persona/criteria, veto, signal reject, scan score if scannable, thesis DEAD/WEAK path)
- [ ] 8. No métier if strategy_id == "..." in bot.py / ia.py / scanner_job.py
- [ ] 9. Params only via get_param(); sticky fields if multi-symbol armed state needed
- [ ] 10. If non-15m TF: set timeframe (drives scan TF + skips engine 15m BB anti-chase)
```

## Contract (required)

Subclass `strategies.base.BaseStrategy`. Implement:

| Method | Role |
|--------|------|
| `AI_PERSONA` / `get_ai_persona()` | 1 strategy = 1 métier persona (PRIMARY in AI) |
| `get_ai_validation_criteria()` | Criteria block or `None` |
| `check_hard_veto(side, ctx)` | Reason string or `None` — **before** AI spend; **own the TF** |
| `post_ai_adjust(signal, ai, ctx)` | Geometry (e.g. trim TP) before R:R / volume gates |
| `generate_signal(df, extra_data)` | Return signal dict or `_reject(...)` → `None` |
| `get_param` / `get_min_volume_ratio_pct` | Live params; optional volume floor |

### Scan hooks (if the strategy should rank the universe)

| Method | Role |
|--------|------|
| `get_scan_timeframe()` | Context TF for ranking (`15m`, `1h`, …) — from config by default |
| `get_scan_interval_minutes()` | Lane refresh cadence (params or derived from TF) |
| `score_scan_candidate(df, *, symbol, meta)` | `None` skip, or `{score, bias, …}` |

`ScannerJob` builds the liquid universe and merges boards. Strategies only score.
**Do not** fetch 1m (or other trigger TF) inside the scan job — fine triggers stay in `generate_signal` after a symbol is focused.

### Veto ownership

- **1 strategy = 1 veto plan.** Do not copy-paste SuperTrend 15m helper thresholds for a 1h swing.
- `app.core.veto_checker` is an **optional toolbox**, never a global bot law.
- Softening an existing strategy’s vetoes “to get more trades” → add a **new** strategy instead.

Optional: `manage_trade`.

### In-trade thesis (when the plan can invalidate while open)

| Method | Role |
|--------|------|
| `supports_trade_thesis()` | `True` when the strategy monitors open-trade plan health |
| `get_thesis_timeframe()` | OHLCV TF for checks (default: scan TF) |
| `evaluate_trade_thesis(trade, price, *, df, extra_data)` | Return `ThesisVerdict` or `None` if data/plan context missing |

The **bot** fetches candles and applies actions (BE tighten, soft close). **Rules live in the strategy** — never `if strategy == "supertrend"` in `bot.py`.

Persist entry plan context on the signal so it survives on the trade:

```python
# signal dict — bot copies these into trade.metadata at entry
{"signal": "SELL", "price": 3.31, "sl": 3.33, "tp": 3.23,
 "range_high": 3.32, "range_low": 3.18, "comment": "..."}
```

Pure helpers: `app/core/trade_thesis.py` (`evaluate_supertrend_thesis`, `evaluate_range_lt_thesis`, …).

Signal dict shape:

```python
{"signal": "BUY"|"SELL", "price": float, "sl": float, "tp": float, "comment": str}
```

## Register

**engine.py** — add import + entry in `self.strategies` keyed by stable id (`snake_case`).

**JSON** (both files must stay in sync):

```json
"<key>": {
  "enabled": true,
  "type": "trend",
  "active": true,
  "timeframe": "15m",
  "signal_score_bonus": 0,
  "params": { "scan_interval_minutes": 15, "...": "..." }
}
```

- `type: "trend"` → only when engine 15m regime is TREND / TREND_BEAR_STRONG  
- `type: "always_active"` → always evaluated; strategy must apply its own filters  
- Non-15m setups: set `"timeframe": "1h"` (engine skips 15m BB anti-chase; scan uses that TF).  
- Cross-strategy priority on the same tick: set `"signal_score_bonus": 100` (Trend LT pattern) — **not** `if strategy == "…"` métier branches in the bot.

## Multi-symbol / sticky

If the strategy arms then waits (pullback), expose:

- `looking_for_entry`
- `entry_direction`
- `_last_entry_time`
- `_last_signal_bar` (same-bar anti-spam; fill cooldown is separate)

The bot persists these per `(strategy_key, symbol)` in `bot_state.json`.

Same-symbol concurrent trades are blocked by default (Hyperliquid net position). Use `trade_book` / `can_open_trade`.

## Tests (minimum)

Under `tests/unit/test_<key>.py`:

1. Persona + validation criteria present  
2. `check_hard_veto` blocks a clear bad context (thresholds **for this TF**)  
3. `generate_signal` rejects missing/insufficient data  
4. If scannable: `score_scan_candidate` reject + score path on synthetic OHLCV  
5. If `supports_trade_thesis`: thesis DEAD on plan break (synthetic OHLCV + trade metadata)

Reference: `tests/unit/test_strategy_contract.py`, `tests/unit/test_trend_lt.py`, `tests/unit/test_strategy_scan.py`.

## Anti-patterns (reject these)

- Softening an existing strategy’s vetoes “to get more trades” — add a **new** strategy instead  
- `if strategy_id == "supertrend":` (or any key) métier logic in `bot.py` / `ia.py` / `scanner_job.py`  
- A single generic scanner score for all strategies  
- Fetching trigger TF (e.g. 1m) across the whole universe in the scan job  
- Hardcoded scalp SL bands in the global system prompt  
- Duplicating the same threshold in scanner + strat + IA without one `get_param` source  
- Putting capital temperament (UI personas) into strategy geometry  

## References

- Guide: [`strategies/README.md`](../../../strategies/README.md)  
- Template: [`strategies/_template_strategy.py`](../../../strategies/_template_strategy.py)  
- ST (15m): [`strategies/supertrend.py`](../../../strategies/supertrend.py)  
- LT (1h): [`strategies/trend_lt.py`](../../../strategies/trend_lt.py)  
- Base: [`strategies/base.py`](../../../strategies/base.py)  
- Scanner job: [`app/core/scanner_job.py`](../../../app/core/scanner_job.py)  
