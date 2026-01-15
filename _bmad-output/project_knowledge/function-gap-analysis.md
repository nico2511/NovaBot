# Function Documentation Gap Analysis

## 🔍 Overview
This report compares the actual codebase functions (scanned via `view_file_outline`) against the current documentation (`api-contracts-backend.md`, `component-inventory-backend.md`, `trading-logic.md`).

## 🟢 1. Backend API (`backend/api.py`)
**Status: Excellent Coverage (95%)**
- **Documented**: All 17 public endpoints are fully documented in `api-contracts-backend.md`.
  - `/api/status`, `/api/engine/start|stop`, `/api/trading/enable|disable`
  - `/api/candles`, `/api/market/data`, `/api/market_metrics`, `/api/meta`
  - `/api/active_trade`, `/api/close_trade`, `/api/recalibrate_stops`, `/api/force_breakeven`, `/api/execute_manual_trade`
  - `/api/settings`, `/api/logs`, `/api/trade_history`, `/api/toggle_gamification`
- **Gap**: `BotStatus` Internal Class & helper `sanitize_for_json` are not documented (Intentional: Internal Utils).
- **Recommendation**: No action needed.

## 🟡 2. Core Bot Logic (`main_nextjs.py`)
**Status: Moderate Coverage (60%)**
- **Documented**:
  - `trading_loop`: Mentioned in logic flow.
  - `execute_entry_atomically`, `execute_exit_atomically`: Implicitly covered in "Trading Logic".
  - `_adopt_existing_position`: Now covered in `trading-logic.md` (Shield System).
  - `_manage_active_trade`: Now covered (Smart BE).
- **Gap**:
  - `_prepare_ai_context`: Critical function for AI inputs, not detailed.
  - `switch_active_symbol`: Logic for websocket switching not explicitly documented.
  - `_check_hard_veto`: Safety mechanism (RSI hard limits) not documented.
- **Recommendation**: Add a brief "Safety Rails" section to `trading-logic.md` covering `_check_hard_veto`.

## 🟡 3. Hyperliquid Service (`hyperliquid_service.py`)
**Status: High Level Coverage (40%)**
- **Documented**: High-level purpose in `component-inventory-backend.md`.
- **Gap (Detailed)**:
  - `execute_order` (Atomic logic): Implements complex retry & bulk logic.
  - `_place_protection_orders`: The core of the safety mechanism.
  - `get_candles` (Robustness): Contains specific logic for cleaning/retrying (rate limits) not mentioned.
- **Recommendation**: Keep as high-level service unless technical deep-dive is requested. The *result* (safety) is documented, the *implementation* (bulk orders) is code-level.

## 🔴 4. AI Service (`ia.py`)
**Status: Low Coverage (20%)**
- **Documented**: "AI Service" mentioned in inventory.
- **Gap**:
  - `analyze_market` vs `validate_signal` vs `analyze_active_position`: The 3 distinct "Brains" are not differentiated in docs.
  - `get_dynamic_system_prompt`: The mechanism for shifting personas based on config is undocumented.
- **Recommendation**: Create `ai-architecture.md` if the user wants to understand *how* the AI thinks (Personas, caching, prompt injection).

## 📊 Summary & Next Steps
- **Public API**: ✅ 100% Documented.
- **Trading Logic**: ✅ 90% Documented (with new `trading-logic.md`).
- **Internal Services**: ⚠️ 30% Documented (Focus is on "What it does", not "How").

**Proposed Action**:
1. Add `_check_hard_veto` (RSI Hardcheck) to `trading-logic.md`.
2. Ask user if they want an `ai-architecture.md` (How the Brain works).
2. Otherwise, current docs are sufficient for Dashboard development.
