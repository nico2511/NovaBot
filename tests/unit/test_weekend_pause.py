"""Tests for weekend cascade pause (rocket / waterfall)."""
from datetime import datetime
from zoneinfo import ZoneInfo

from app.core.weekend_pause import (
    get_weekend_paused_strategies,
    is_strategy_weekend_paused,
    is_weekend_pause_active,
    weekend_pause_status,
)

CFG = {
    "weekend_pause": {
        "enabled": True,
        "timezone": "Europe/Paris",
        "start_weekday": 5,
        "start_hour": 6,
        "end_weekday": 0,
        "end_hour": 6,
        "strategies": ["rocket", "waterfall"],
    }
}

PARIS = ZoneInfo("Europe/Paris")


def _dt(y, m, d, h, mi=0):
    return datetime(y, m, d, h, mi, tzinfo=PARIS)


def test_friday_before_pause_is_active():
    assert not is_weekend_pause_active(CFG, now=_dt(2026, 8, 21, 5, 59))  # Fri


def test_sunday_morning_only_pause():
    cfg = {
        "weekend_pause": {
            "enabled": True,
            "timezone": "Europe/Paris",
            "start_weekday": 6,
            "start_hour": 0,
            "end_weekday": 6,
            "end_hour": 12,
            "strategies": ["rocket", "waterfall"],
        }
    }
    assert is_weekend_pause_active(cfg, now=_dt(2026, 8, 23, 9, 0))
    assert not is_weekend_pause_active(cfg, now=_dt(2026, 8, 23, 13, 0))
    assert not is_weekend_pause_active(cfg, now=_dt(2026, 8, 22, 17, 0))


def test_saturday_6am_starts_pause():
    assert is_weekend_pause_active(CFG, now=_dt(2026, 8, 22, 6, 0))


def test_sunday_is_paused():
    assert is_weekend_pause_active(CFG, now=_dt(2026, 8, 23, 12, 0))


def test_monday_before_6am_still_paused():
    assert is_weekend_pause_active(CFG, now=_dt(2026, 8, 24, 5, 59))


def test_monday_6am_resumes():
    assert not is_weekend_pause_active(CFG, now=_dt(2026, 8, 24, 6, 0))


def test_paused_strategies_only_when_active():
    paused = get_weekend_paused_strategies(CFG, now=_dt(2026, 8, 23, 10, 0))
    assert paused == ["rocket", "waterfall"]
    assert not get_weekend_paused_strategies(CFG, now=_dt(2026, 8, 21, 10, 0))


def test_is_strategy_weekend_paused():
    now = _dt(2026, 8, 23, 10, 0)
    assert is_strategy_weekend_paused("rocket", CFG, now=now)
    assert is_strategy_weekend_paused("waterfall", CFG, now=now)
    assert not is_strategy_weekend_paused("supertrend", CFG, now=now)


def test_disabled_config():
    cfg = {"weekend_pause": {"enabled": False}}
    assert not is_weekend_pause_active(cfg, now=_dt(2026, 8, 23, 10, 0))


def test_status_snapshot():
    st = weekend_pause_status(CFG, now=_dt(2026, 8, 23, 10, 0))
    assert st["active"] is True
    assert "rocket" in st["paused_strategies"]
