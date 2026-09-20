"""Regression: BotContext.__init__ must resolve RiskManager (dropped in #21)."""
from __future__ import annotations

from unittest.mock import MagicMock


def test_risk_manager_imported_in_bot_module():
    import app.core.bot as bot_mod
    from app.core.risk_manager import RiskManager

    assert getattr(bot_mod, "RiskManager", None) is RiskManager


def test_botcontext_init_binds_risk_manager(monkeypatch):
    """Smoke: constructing BotContext must not NameError on RiskManager."""
    import app.core.bot as bot_mod
    from app.core.risk_manager import RiskManager

    monkeypatch.setattr(bot_mod, "bootstrap_active_symbol", lambda: "BTC")
    monkeypatch.setattr(bot_mod, "SafeOrderManager", MagicMock)
    monkeypatch.setattr(bot_mod, "PositionReconciler", MagicMock)
    monkeypatch.setattr(bot_mod.StrategyEngine, "__init__", lambda self, *_a, **_k: None)

    bot = bot_mod.BotContext()
    assert isinstance(bot.risk_manager, RiskManager)
