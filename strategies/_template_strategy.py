"""
Copy-paste skeleton for a new NovaBot strategy.

NOT registered in StrategyEngine — rename, implement, then follow
strategies/README.md (register + JSON params + tests).

The strategy IS the plan: params, AI persona, hard veto, post-AI geometry,
and generate_signal all live here. The bot stays a dumb machine.
"""
from __future__ import annotations

from typing import Any, Dict, Optional

from strategies.base import BaseStrategy


class StrategyTemplate(BaseStrategy):
    AI_PERSONA = """
    CODENAME: "TEMPLATE"

    ROLE:
    Describe how the AI should judge THIS strategy's setups.

    RULES OF ENGAGEMENT:
    1. ...
    """

    def get_ai_validation_criteria(self) -> Optional[str]:
        return """=== VALIDATION CRITERIA (TEMPLATE) ===
Approve when your strategy-specific confluence holds.
Reject on weak volume / bad R:R / clear counter-trend as you define them.
"""

    def check_hard_veto(self, signal: str, market_context: dict) -> Optional[str]:
        # Own your TF — do not blindly reuse SuperTrend 15m helper thresholds for a 1h plan.
        # Option A: shared helpers with YOUR thresholds (subclass or wrap)
        # from app.core import veto_checker
        # return veto_checker.check_hard_veto(signal, market_context)
        #
        # Option B: custom rules — return a reason string or None
        return None

    def get_scan_timeframe(self) -> str:
        return super().get_scan_timeframe()

    def get_scan_interval_minutes(self) -> float:
        return super().get_scan_interval_minutes()

    def score_scan_candidate(self, df, *, symbol: str, meta=None):
        # Return None to skip the scanner, or {"score": float, "bias": "LONG"|"SHORT", ...}
        return None

    def post_ai_adjust(
        self,
        signal: Dict[str, Any],
        ai_result: Dict[str, Any],
        market_context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        # Optional: trim TP to structure, nudge SL, etc.
        return ai_result

    def get_min_volume_ratio_pct(self) -> Optional[float]:
        return float(self.get_param("min_volume_ratio_pct", 50.0) or 50.0)

    def supports_trade_thesis(self) -> bool:
        # Set True when the open-trade plan can break (box breakout, ST flip, …)
        return False

    def get_thesis_timeframe(self) -> str:
        return super().get_thesis_timeframe()

    def evaluate_trade_thesis(self, trade, current_price, *, df, extra_data=None):
        # Return ThesisVerdict from app.core.trade_thesis, or None to skip this tick.
        # Persist plan fields on the signal (e.g. range_high/range_low) — bot stores them in trade.metadata.
        return None

    def add_indicators(self, df):
        # Add columns your signal logic needs
        return df

    def generate_signal(self, df, extra_data=None):
        """
        Return None (via _reject) or a dict:
          {"signal": "BUY"|"SELL", "price": float, "sl": float, "tp": float, "comment": str}
        """
        if df is None or getattr(df, "empty", True):
            return self._reject("No data")
        return self._reject("Template strategy — not implemented")
