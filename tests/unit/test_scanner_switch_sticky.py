"""Unit tests for ScannerJob auto-switch sticky near-entry behavior."""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import app.core.scanner_job as scanner_job_mod
from app.core.scanner_job import ScannerJob


def _job(active="ETH", armed=False, trades=None):
    st = SimpleNamespace(looking_for_entry=armed)
    engine = SimpleNamespace(strategies={"supertrend": st})
    bot = SimpleNamespace(
        active_symbol=active,
        active_trades=trades or {},
        max_positions=1,
        strategy_engine=engine,
        add_log=MagicMock(),
        switch_active_symbol=MagicMock(),
    )
    job = ScannerJob.__new__(ScannerJob)
    job.bot = bot
    return job


def _stub_side_effects(monkeypatch):
    monkeypatch.setattr(
        scanner_job_mod,
        "StateManager",
        SimpleNamespace(save_state=MagicMock()),
    )
    monkeypatch.setattr(
        scanner_job_mod,
        "discord_service",
        SimpleNamespace(send_log=MagicMock()),
    )


def test_keeps_armed_setup_within_armed_hysteresis(monkeypatch):
    _stub_side_effects(monkeypatch)
    job = _job(active="ETH", armed=True)
    best = {"symbol": "AAVE", "score": 91, "bias": "LONG", "adx": 28}
    opps = [best, {"symbol": "ETH", "score": 79}]
    # Gap 12 < armed hysteresis 35 → keep ETH
    assert job._maybe_auto_switch(best, opps) is None
    job.bot.switch_active_symbol.assert_not_called()


def test_switches_armed_setup_when_gap_exceeds_armed_hysteresis(monkeypatch):
    _stub_side_effects(monkeypatch)
    job = _job(active="ETH", armed=True)
    best = {"symbol": "AAVE", "score": 99, "bias": "LONG", "adx": 40}
    opps = [best, {"symbol": "ETH", "score": 60}]
    # Gap 39 >= armed hysteresis 35 → allow switch
    assert job._maybe_auto_switch(best, opps) == "AAVE"
    job.bot.switch_active_symbol.assert_called_once_with("AAVE")


def test_unarmed_uses_normal_hysteresis(monkeypatch):
    _stub_side_effects(monkeypatch)
    job = _job(active="ETH", armed=False)
    best = {"symbol": "AAVE", "score": 91, "bias": "LONG", "adx": 28}
    opps = [best, {"symbol": "ETH", "score": 79}]
    # Gap 12 >= 10 → switch when not armed
    assert job._maybe_auto_switch(best, opps) == "AAVE"


def test_no_switch_while_trade_open(monkeypatch):
    _stub_side_effects(monkeypatch)
    job = _job(active="ETH", armed=False, trades={"ETH": {"side": "BUY"}})
    best = {"symbol": "AAVE", "score": 99, "bias": "LONG", "adx": 40}
    assert job._maybe_auto_switch(best, [best]) is None
    job.bot.switch_active_symbol.assert_not_called()


def test_post_switch_cooldown_blocks_switch(monkeypatch):
    import time as time_mod

    _stub_side_effects(monkeypatch)
    job = _job(active="ETH", armed=False)
    job.last_switch_time = time_mod.time() - 60
    job.bot.scanner_settings = {"switch_cooldown_minutes": 30}
    best = {"symbol": "AAVE", "score": 99, "bias": "LONG", "adx": 40}
    opps = [best, {"symbol": "ETH", "score": 50}]
    assert job._maybe_auto_switch(best, opps) is None
    job.bot.switch_active_symbol.assert_not_called()
