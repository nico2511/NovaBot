"""In-memory / file-backed A3 paper observation journal (no exchange orders)."""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.core.a3_ema_trend_logic import compute_paper_stop_flags

logger = logging.getLogger(__name__)

DEFAULT_JOURNAL_NAME = "a3_paper_journal.json"


class A3PaperJournal:
    def __init__(self, base_dir: Path):
        self.path = Path(base_dir) / "data" / "state" / DEFAULT_JOURNAL_NAME
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def _load(self) -> Dict[str, Any]:
        if not self.path.is_file():
            return {
                "equity_start": 10000.0,
                "closed_trades": [],
                "open_positions": {},
                "alerts_sent": {},
            }
        try:
            return json.loads(self.path.read_text())
        except Exception:
            logger.warning("A3 paper journal corrupt — resetting")
            return {
                "equity_start": 10000.0,
                "closed_trades": [],
                "open_positions": {},
                "alerts_sent": {},
            }

    def _save(self, data: Dict[str, Any]) -> None:
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, indent=2))
        tmp.replace(self.path)

    def metrics(self) -> Dict[str, Any]:
        data = self._load()
        flags = compute_paper_stop_flags(
            data.get("closed_trades") or [],
            equity_start=float(data.get("equity_start") or 10000.0),
        )
        return {
            "strategy": "a3_ema_trend_4h",
            "trade_count": flags.trade_count,
            "open_positions": len(data.get("open_positions") or {}),
            "max_drawdown_pct": round(flags.max_drawdown_pct, 4),
            "profit_factor": round(flags.profit_factor, 4),
            "avg_slippage_pct_per_side": round(flags.avg_slippage_pct_per_side, 6),
            "stop_criteria": {
                "drawdown_gt_20pct": flags.drawdown_breach,
                "pf_lt_1_after_150_trades": flags.profit_factor_breach,
                "avg_slippage_gt_0_1pct_per_side": flags.slippage_breach,
            },
            "any_stop_triggered": (
                flags.drawdown_breach
                or flags.profit_factor_breach
                or flags.slippage_breach
            ),
        }

    def record_closed_trade(self, trade: Dict[str, Any]) -> None:
        data = self._load()
        closed: List[dict] = list(data.get("closed_trades") or [])
        closed.append(trade)
        data["closed_trades"] = closed[-5000:]
        self._save(data)

    def snapshot(self) -> Dict[str, Any]:
        data = self._load()
        data["metrics"] = self.metrics()
        return data
