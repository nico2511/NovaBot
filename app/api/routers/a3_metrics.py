"""A3 EMA-Trend 4H paper observation metrics (read-only)."""
from __future__ import annotations

import os

from fastapi import APIRouter, Depends

from app.api.auth import require_api_key
from app.core.a3_paper_journal import A3PaperJournal

router = APIRouter(
    prefix="/api/strategy/a3-ema-trend-4h",
    tags=["a3"],
    dependencies=[Depends(require_api_key)],
)

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))


@router.get("/paper-metrics")
def get_a3_paper_metrics():
    """Drawdown, profit factor, slippage vs paper stop criteria (spec A3)."""
    journal = A3PaperJournal(ROOT)
    return journal.snapshot()
