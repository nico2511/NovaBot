"""Scanner poll cadence vs fast strategy lanes."""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

from app.core.scanner_job import ScannerJob
from strategies.spark import StrategySpark


def test_effective_poll_capped_by_fast_lane():
    bot = MagicMock()
    spark = StrategySpark({"params": {"scan_interval_minutes": 3}})
    bot.strategy_engine = SimpleNamespace(
        strategies={"spark": spark},
        config={"spark": {"enabled": True, "active": True, "type": "trend"}},
    )
    bot._strategy_sticky = {}
    job = ScannerJob(bot)
    poll = job._effective_poll_minutes({"interval": 15})
    assert poll == 3.0


def test_lane_due_accelerates_when_any_symbol_sticky_armed():
    bot = MagicMock()
    spark = StrategySpark(
        {"params": {"scan_interval_minutes": 3, "scan_interval_active_minutes": 1.5}}
    )
    bot.strategy_engine = SimpleNamespace(strategies={"spark": spark}, config={})
    bot.active_symbol = "SOL"
    bot._strategy_sticky = {("spark", "ETH"): {"looking_for_entry": True}}
    job = ScannerJob(bot)
    ctx_interval = spark.get_scan_interval_minutes(
        scan_context={"sticky_armed": job._any_sticky_armed_for("spark")}
    )
    assert ctx_interval == 1.5
