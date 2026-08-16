---
name: create-novabot-strategy
description: >-
  Create or extend a NovaBot trading strategy that owns its plan (params, AI
  persona, hard veto, post_ai_adjust, generate_signal). Use when adding a new
  strategy, scaffolding from _template_strategy.py, registering in engine.py /
  strategies.json, writing strategy unit tests, or when the user mentions
  strategies/README.md, BaseStrategy, Trend LT, SuperTrend, or "nouvelle stratégie".
---

# Create NovaBot Strategy

**Source of truth:** read [`strategies/README.md`](../../../strategies/README.md) first, then this skill.

**Rule:** Bot = machine. Strategy = plan. Do **not** put métier thresholds in `bot.py`, `ia.py`, or scalp bands in `prompts.py`.

## Workflow checklist

Copy and complete:

```
- [ ] 1. Scaffold from strategies/_template_strategy.py → strategies/<key>.py
- [ ] 2. Implement contract (persona, criteria, veto, optional post_ai_adjust, generate_signal)
- [ ] 3. Register in strategies/engine.py
- [ ] 4. Add JSON to data/config/strategies.json AND app/core/defaults/strategies.default.json
- [ ] 5. Unit tests under tests/unit/ (persona/criteria, veto, reject path at minimum)
- [ ] 6. No métier if strategy_id == "..." in bot.py / ia.py
- [ ] 7. Params only via get_param(); sticky fields if multi-symbol armed state needed
- [ ] 8. If non-15m TF: set timeframe + skip_bb_anti_chase (or type always_active) so engine BB 15m does not false-reject
```

## Contract (required)

Subclass `strategies.base.BaseStrategy`. Implement:

| Method | Role |
|--------|------|
| `AI_PERSONA` / `get_ai_persona()` | 1 strategy = 1 métier persona (PRIMARY in AI) |
| `get_ai_validation_criteria()` | Criteria block or `None` |
| `check_hard_veto(side, ctx)` | Reason string or `None` — **before** AI spend |
| `post_ai_adjust(signal, ai, ctx)` | Geometry (e.g. trim TP) before R:R / volume gates |
| `generate_signal(df, extra_data)` | Return signal dict or `_reject(...)` → `None` |
| `get_param` / `get_min_volume_ratio_pct` | Live params; optional volume floor |

Optional: `manage_trade`. Shared helpers: `app.core.veto_checker` (not a global bot law).

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
  "params": { "...": "..." }
}
```

- `type: "trend"` → only when engine 15m regime is TREND / TREND_BEAR_STRONG  
- `type: "always_active"` → always evaluated; strategy must apply its own filters  
- Non-15m setups: set `"timeframe": "1h"` (engine skips 15m BB anti-chase). Prefer this over hardcoding the strategy name in the engine.  
- Cross-strategy priority on the same tick: set `"signal_score_bonus": 100` (Trend LT pattern) — **not** `if strategy == "…"` métier branches in the bot.

## Multi-symbol / sticky

If the strategy arms then waits (pullback), expose:

- `looking_for_entry`
- `entry_direction`
- `_last_entry_time`

The bot persists these per `(strategy_key, symbol)` in `bot_state.json`. Do not rely on a single global instance flag without sticky restore.

Same-symbol concurrent trades are blocked by default (Hyperliquid net position). Do not assume `active_trades[symbol]` is the only book API — use `trade_book` / `can_open_trade`.

## Tests (minimum)

Under `tests/unit/test_<key>.py`:

1. Persona + validation criteria present  
2. `check_hard_veto` blocks a clear bad context  
3. `generate_signal` rejects missing/insufficient data  

Reference: `tests/unit/test_strategy_contract.py`, `tests/unit/test_trend_lt.py`.

## Anti-patterns (reject these)

- Softening an existing strategy’s vetoes “to get more trades” — add a **new** strategy instead  
- `if strategy_id == "supertrend":` (or any key) métier logic in `bot.py` / `ia.py`  
- Hardcoded scalp SL bands in the global system prompt  
- Duplicating the same threshold in scanner + strat + IA without one `get_param` source  
- Putting capital temperament (UI personas) into strategy geometry  

## References

- Guide: [`strategies/README.md`](../../../strategies/README.md)  
- Template: [`strategies/_template_strategy.py`](../../../strategies/_template_strategy.py)  
- ST (15m): [`strategies/supertrend.py`](../../../strategies/supertrend.py)  
- LT (1h): [`strategies/trend_lt.py`](../../../strategies/trend_lt.py)  
- Base: [`strategies/base.py`](../../../strategies/base.py)  
