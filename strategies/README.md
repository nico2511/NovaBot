# Strategy Guide — Bot = machine, Strategy = plan

NovaBot’s loop, orders, state, Discord, and **capital** `risk_profile` live in the bot.
Everything that decides *whether / how* to trade a setup belongs in the **strategy**:

| In the strategy | In the bot (machine) |
|-----------------|----------------------|
| `params` / `get_param` | Loop, HL entry/exit, state |
| `AI_PERSONA` / `get_ai_persona()` | `risk_profile` capital appetite (min R:R floor, lev, min conf) |
| `get_ai_validation_criteria()` | Discord, storage, scanner job |
| `check_hard_veto()` | Trailing default if `manage_trade` returns `None` |
| `post_ai_adjust()` | |
| `generate_signal` / `add_indicators` | |
| optional `manage_trade` | |

Reference implementation: [`supertrend.py`](./supertrend.py).

---

## Checklist — add a new strategy

1. **Copy** [`_template_strategy.py`](./_template_strategy.py) → `ma_strategie.py`.
2. **Implement** the contract methods (persona, veto, optional `post_ai_adjust`, `generate_signal`).
3. **Register** in [`engine.py`](./engine.py):
   ```python
   from strategies.ma_strategie import StrategyMaStrategie
   self.strategies = {
       "supertrend": StrategySupertrend(...),
       "ma_strategie": StrategyMaStrategie(strats_config.get("ma_strategie")),
   }
   ```
4. **Params JSON** in [`data/config/strategies.json`](../data/config/strategies.json) and [`app/core/defaults/strategies.default.json`](../app/core/defaults/strategies.default.json):
   ```json
   "ma_strategie": {
     "enabled": true,
     "type": "trend",
     "active": true,
     "timeframe": "15m",
     "params": { "...": "..." }
   }
   ```
   - `type: "trend"` participates in ADX regime (threshold = max of active trend strats’ `adx_threshold`).
5. **Tests**: at least veto + signal reject/approve paths under `tests/unit/`.
6. **Do not** put métier thresholds in `bot.py` or global scalp rules in `prompts.py`.

---

## Contract (BaseStrategy)

See [`base.py`](./base.py).

- `get_ai_persona()` → string merged as **STRATEGY PERSONA (PRIMARY)** in AI validation.
- `get_ai_validation_criteria()` → criteria block in the user prompt (or `None` for generic).
- `check_hard_veto(side, ctx)` → reason string or `None`. Called **before** AI spend.
- `post_ai_adjust(signal, ai_result, ctx)` → mutate AI result (e.g. trim TP) **before** R:R / volume hard gates.
- `get_min_volume_ratio_pct()` → post-AI WEAK_VOLUME floor (optional).
- `get_rr_epsilon()` → default `0.02` when comparing post-trim R:R to capital profile min.

Shared veto helpers (optional import): [`app/core/veto_checker.py`](../app/core/veto_checker.py) — **not** a global bot law.

---

## Anti-patterns

- `if strategy_id == "supertrend":` métier logic inside `ia.py` / `bot.py`
- Hardcoding scalp SL bands (0.8%–2.5%) in the global system prompt
- Softening SuperTrend (or any strat) vetoes “to get more trades” without changing that strat’s plan on purpose
- Scattering the same threshold in scanner + strat + IA without a single `get_param` source

---

## Persona model

**1 strategy = 1 métier persona** (`AI_PERSONA`).  
UI “personas” (Conservative Scalper / …) are **capital temperaments** only; they must not override strategy geometry.
