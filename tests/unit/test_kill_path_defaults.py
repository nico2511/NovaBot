"""Lock audit kill-path defaults: confirmed entry, Balanced cascades, Spark/Ember off."""
from __future__ import annotations

import json
from pathlib import Path

from app.core.risk_profiles import STRATEGY_DEFAULT_PROFILES
from strategies.cascade_rider import (
    CASCADE_ENTRY_USE_LIVE,
    DEFAULT_EMBER_MAX_EXTENSION_ATR,
    DEFAULT_MAX_EXTENSION_ATR,
    DEFAULT_SPARK_MAX_EXTENSION_ATR,
)

ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATHS = (
    ROOT / "app" / "core" / "defaults" / "strategies.default.json",
    ROOT / "data" / "config" / "strategies.json",
)
WEEKEND_PAUSED = {
    "trend_lt",
    "range_lt",
    "rocket",
    "waterfall",
    "spark",
    "ember",
}
CASCADE_KEYS = ("rocket", "waterfall", "spark", "ember")


def test_cascade_entry_is_confirmed_bar_only():
    assert CASCADE_ENTRY_USE_LIVE is False
    assert DEFAULT_MAX_EXTENSION_ATR == 1.5
    assert DEFAULT_SPARK_MAX_EXTENSION_ATR == 1.5
    assert DEFAULT_EMBER_MAX_EXTENSION_ATR == 1.5


def test_cascade_strategy_default_profiles_are_balanced():
    for key in CASCADE_KEYS:
        assert STRATEGY_DEFAULT_PROFILES[key] == "Balanced Growth"


def test_strategy_json_kill_path_defaults():
    for path in CONFIG_PATHS:
        cfg = json.loads(path.read_text())
        pause = cfg["weekend_pause"]
        assert pause["enabled"] is True
        assert set(pause["strategies"]) == WEEKEND_PAUSED
        assert "supertrend" not in pause["strategies"]
        for name in CASCADE_KEYS:
            row = cfg[name]
            assert row["risk_profile"] == "Balanced Growth"
            assert float(row["params"]["min_rr"]) == 1.5
            assert float(row["params"]["max_extension_atr"]) == 1.5
        assert cfg["spark"]["enabled"] is False
        assert cfg["ember"]["enabled"] is False
        assert cfg["rocket"]["enabled"] is True
        assert cfg["waterfall"]["enabled"] is True
