# Deep Dive: Strategy Creation Subsystem

## 1. Overview
The Strategy Subsystem is the core trading logic engine of NovaBot. It uses a **Regime-Based Orchestration** model where a central engine determines the market environment (Trend, Range, Crash) and dynamically activates appropriate strategy modules.

**Target Area:** `strategies/` directory  
**Primary Engine:** `strategies/engine.py`  
**Base Contract:** `strategies/base.py`

## 2. File Inventory

| File | Purpose | Key Exports |
| :--- | :--- | :--- |
| **`strategies/base.py`** | Abstract Base Class defining the contract for all strategies. Includes helper methods for common analysis. | `BaseStrategy` (Class), `generate_signal()` (Abstract), `calculate_progress()`, `check_conditions()` |
| **`strategies/engine.py`** | The "Brain" that loads strategies, calculates global regime, injects indicators, and filters signals (Anti-Chasing, Global Risk). | `StrategyEngine` (Class), `analyze()` (Main Loop) |
| **`strategies/smart_trend.py`** | Reference implementation of a Multi-Timeframe (MTF) Trend strategy. | `StrategySmartTrend` (Class) |
| **`strategies.json`** | Configuration registry defining active strategies, parameters, and types. | JSON Schema (Strategies Config) |

## 3. Architecture & Data Flow

### The "Funnel" Architecture
Data flows through a strictly defined funnel:

1.  **Market Data Input**: `15m` candles (Context) + `1m` candles (Trigger) passed to `engine.analyze(df, extra_data)`.
2.  **Global Regime Detection** (`engine.py`):
    *   Calculates ADX & Slope.
    *   Determines Regime: `TREND`, `RANGE`, or `TREND_BEAR_STRONG` (Waterfall).
    *   **Waterfall Override**: If Price < EMA9 < EMA20 with consecutive red candles, force Bear Strong mode.
3.  **Strategy Selection**:
    *   Engine filters strategies based on `type` in `strategies.json` matching the current regime.
    *   *Example:* `type="trend"` strategies are ONLY executed if Regime is `TREND`.
4.  **Strategy Execution** (`generate_signal`):
    *   Selected strategies run their logic.
    *   Must return `dict` (signal data) or `None`.
5.  **Global Filters (Engine Level)**:
    *   **Direction Filter**: Checks `allow_longs`/`allow_shorts`.
    *   **Anti-Chasing (BB Filter)**: Rejects Buys near Upper Band / Sells near Lower Band.
    *   **Kill Switch**: Checks `should_panic_close` utility.
6.  **Output**: Aggregated Snapshot (Signal + Market State) returned to Bot/UI.

```mermaid
graph TD
    A[Market Data (15m + 1m)] --> B[Strategy Engine]
    B --> C{Global Regime?}
    C -- ADX > 25 --> D[TREND Mode]
    C -- ADX < 25 --> E[RANGE Mode]
    C -- Crash Pattern --> F[WATERFALL Mode]
    
    D --> G[Activate Trend Strats]
    E --> H[Activate Range/Reversion Strats]
    
    G --> I[Strategy.generate_signal()]
    H --> I
    
    I --> J{Global Filters}
    J -- Anti-Chase/Risk --> K[Final Signal]
```

## 4. Implementation Details

### Base Strategy Contract (`strategies/base.py`)
All strategies **must** inherit from `BaseStrategy`.

```python
class MyStrategy(BaseStrategy):
    def __init__(self, config=None):
        super().__init__(config)
        # Access params: self.params.get("key", default)

    def generate_signal(self, df, extra_data=None):
        # Must return dict or None
        pass
    
    def calculate_progress(self, df, extra_data=None):
        # Return int 0-100 for UI Progress Bar
        pass    

    def check_conditions(self, df, extra_data=None):
        # Return list of checks for UI Diagnostic Card
        pass
```

### AI Persona Integration
Strategies includes a text-based `AI_PERSONA` constant. This is **not** used for trading logic, but is injected into the LLM context (Analyst Service) to give the AI a "personality" when explaining the strategy's behavior to the user.

### Configuration (`strategies.json`)
The `type` field is critical.
*   `trend`: Active in `TREND`, `TREND_BEAR_STRONG`.
*   `range`: Active in `RANGE`.
*   `reversion`: Active in `RANGE` (typically).
*   `always_active`: Bypasses regime filter.

## 5. Critical Risks & Gotchas

> [!WARNING]
> **Global Filters Override Strategy Logic**
> Even if your strategy generates a valid signal, the `StrategyEngine` may reject it if the price is too close to Bollinger Bands (Anti-Chasing). Ensure your strategy doesn't rely on "breakout" logic that triggers exactly at the bands, or it will be blocked.

> [!IMPORTANT]
> **Data Requirements**
> Strategies often require `50+` candles. Always include a guard clause: `if len(df) < 50: return None`.

> [!TIP]
> **Regime Awareness**
> Do not put ADX checks inside your strategy if you define it as `type="trend"`. The Engine handles this efficiently. Only add strategy-specific filters (e.g. "Stricter ADX").

## 6. Verification Steps
Before enabling a new strategy:

1.  **Backtest**: Run `scripts/backtest_smart_trend_v3.py` (adapt it for your file) to verify logic.
2.  **UI Check**: Ensure `calculate_progress` returns valid 0-100 values (otherwise UI bar breaks).
3.  **JSON Config**: Validate JSON syntax in `strategies.json` (trailing commas are common errors).
4.  **Import**: Ensure the class is imported and instantiated in `strategies/engine.py`.

## 7. Related Code
*   `app/services/indicators.py`: Uses `pandas_ta` or custom implementations. Check this for available indicators.
*   `app/core/trade_recorder.py`: How signals are eventually tracked.
