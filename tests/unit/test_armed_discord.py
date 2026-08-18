"""Dedicated Discord notifications for armed (looking_for_entry) setups."""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

from app.core.bot import BotContext


def _bot():
    bot = BotContext.__new__(BotContext)
    bot._strategy_sticky = {}
    bot._last_armed_discord_sig = None
    bot.strategy_engine = SimpleNamespace(
        config={
            "supertrend": {"timeframe": "15m"},
            "trend_lt": {"timeframe": "1h"},
        },
        strategies={},
    )
    bot.add_log = MagicMock()
    return bot


def test_collect_armed_setups_sorted():
    bot = _bot()
    bot._strategy_sticky = {
        ("supertrend", "SOL"): {
            "looking_for_entry": True,
            "entry_direction": "SHORT",
            "wait_reason": "No pullback to 15m ST",
        },
        ("trend_lt", "BTC"): {
            "looking_for_entry": True,
            "entry_direction": "LONG",
        },
        ("supertrend", "ETH"): {"looking_for_entry": False},
    }
    setups = bot._collect_armed_setups()
    assert [s["symbol"] for s in setups] == ["BTC", "SOL"]
    assert setups[0]["strategy"] == "trend_lt"
    assert setups[1]["wait_reason"] == "No pullback to 15m ST"


def test_armed_discord_on_new_setup(monkeypatch):
    send = MagicMock()
    monkeypatch.setattr("app.core.bot.discord_service.send_alert", send)
    bot = _bot()
    bot._strategy_sticky = {
        ("supertrend", "NEAR"): {
            "looking_for_entry": True,
            "entry_direction": "LONG",
            "wait_reason": "No pullback to 15m ST within 30m",
        }
    }
    bot._maybe_notify_armed_discord()
    send.assert_called_once()
    title = send.call_args[0][0]
    description = send.call_args[0][1]
    assert "ARMED" in title
    assert "NEAR" in description
    assert "supertrend" in description
    assert "No pullback" in description


def test_armed_discord_dedup_same_snapshot(monkeypatch):
    send = MagicMock()
    monkeypatch.setattr("app.core.bot.discord_service.send_alert", send)
    bot = _bot()
    bot._strategy_sticky = {
        ("trend_lt", "AVAX"): {
            "looking_for_entry": True,
            "entry_direction": "SHORT",
        }
    }
    bot._maybe_notify_armed_discord()
    bot._maybe_notify_armed_discord()
    send.assert_called_once()


def test_armed_discord_on_direction_change(monkeypatch):
    send = MagicMock()
    monkeypatch.setattr("app.core.bot.discord_service.send_alert", send)
    bot = _bot()
    bot._strategy_sticky = {
        ("trend_lt", "AVAX"): {
            "looking_for_entry": True,
            "entry_direction": "LONG",
        }
    }
    bot._maybe_notify_armed_discord()
    bot._strategy_sticky[("trend_lt", "AVAX")]["entry_direction"] = "SHORT"
    bot._maybe_notify_armed_discord()
    assert send.call_count == 2


def test_armed_discord_silent_on_full_disarm(monkeypatch):
    send = MagicMock()
    monkeypatch.setattr("app.core.bot.discord_service.send_alert", send)
    bot = _bot()
    bot._strategy_sticky = {
        ("supertrend", "XRP"): {
            "looking_for_entry": True,
            "entry_direction": "SHORT",
        }
    }
    bot._maybe_notify_armed_discord()
    bot._strategy_sticky[("supertrend", "XRP")]["looking_for_entry"] = False
    bot._maybe_notify_armed_discord()
    assert send.call_count == 1


def test_save_strategy_sticky_stores_wait_reason(monkeypatch):
    monkeypatch.setattr("app.core.bot.discord_service.send_alert", MagicMock())
    bot = _bot()
    strat = SimpleNamespace(
        looking_for_entry=True,
        entry_direction="LONG",
        _last_entry_time=None,
        _last_signal_bar=None,
        last_rejection_reason="Waiting for 1h rejection close",
    )
    bot.strategy_engine.strategies = {"range_lt": strat}
    bot._save_strategy_sticky("ATOM")
    state = bot._strategy_sticky[("range_lt", "ATOM")]
    assert state["wait_reason"] == "Waiting for 1h rejection close"
