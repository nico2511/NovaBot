"""Regression: defaults_revision merge must not skip enabled/active sync."""
from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from app.services.storage import StorageService, strategy_config_keys

ROOT = Path(__file__).resolve().parents[2]
ONLY_ENABLED = "a3_ema_trend_4h"


def _default_cfg() -> dict:
    return json.loads(
        (ROOT / "app" / "core" / "defaults" / "strategies.default.json").read_text()
    )


def _storage_with_defaults(tmp_path: Path) -> StorageService:
    defaults_dir = tmp_path / "app" / "core" / "defaults"
    defaults_dir.mkdir(parents=True)
    shutil.copy(
        ROOT / "app" / "core" / "defaults" / "strategies.default.json",
        defaults_dir / "strategies.default.json",
    )
    return StorageService(str(tmp_path))


def test_sync_applies_flags_when_runtime_meta_lacks_defaults_revision(tmp_path):
    """
    Prod failure mode: persistent volume had every strategy enabled but no
    meta.defaults_revision. _merge_missing copied the new revision first, so
    sync thought it was already up to date and never ran apply_enabled_active.
    """
    default_cfg = _default_cfg()
    ss = _storage_with_defaults(tmp_path)

    stale = json.loads(json.dumps(default_cfg))
    for name in strategy_config_keys(stale):
        stale[name]["enabled"] = True
        stale[name]["active"] = True
    stale["meta"] = {"activation_policy": "legacy volume without revision token"}

    (ss.config_dir / "strategies.json").write_text(json.dumps(stale, indent=2))

    result = ss.sync_strategies_from_defaults()
    assert result["status"] in ("updated", "noop")
    assert result.get("applied_defaults_revision")

    synced = json.loads((ss.config_dir / "strategies.json").read_text())
    for name in strategy_config_keys(synced):
        if name == ONLY_ENABLED:
            assert synced[name]["enabled"] is True
            assert synced[name]["active"] is True
        else:
            assert synced[name]["enabled"] is False, name
            assert synced[name]["active"] is False, name
    assert synced["meta"]["defaults_revision"] == default_cfg["meta"]["defaults_revision"]


def test_sync_restart_same_revision_does_not_reenable_disabled_strategies(tmp_path):
    """Second boot with matching revision must not turn legacy strategies back on."""
    default_cfg = _default_cfg()
    ss = _storage_with_defaults(tmp_path)

    good = json.loads(json.dumps(default_cfg))
    (ss.config_dir / "strategies.json").write_text(json.dumps(good, indent=2))

    first = ss.sync_strategies_from_defaults()
    assert first["status"] in ("updated", "noop")

    second = ss.sync_strategies_from_defaults()
    assert second["status"] == "noop"

    after = json.loads((ss.config_dir / "strategies.json").read_text())
    for name in strategy_config_keys(after):
        if name == ONLY_ENABLED:
            assert after[name]["enabled"] is True
        else:
            assert after[name]["enabled"] is False


def test_full_startup_sequence_persistent_volume_then_sync(tmp_path):
    """Simulate main.py: init storage → sync → engine reads strategies.json."""
    from strategies.engine import StrategyEngine

    default_cfg = _default_cfg()
    ss = _storage_with_defaults(tmp_path)

    volume = {
        "meta": {"defaults_revision": "2026-10-25-strategies-off"},
    }
    for name in strategy_config_keys(default_cfg):
        volume[name] = json.loads(json.dumps(default_cfg[name]))
        volume[name]["enabled"] = True
        volume[name]["active"] = True

    (ss.config_dir / "strategies.json").write_text(json.dumps(volume, indent=2))
    ss.sync_strategies_from_defaults()

    synced = json.loads((ss.config_dir / "strategies.json").read_text())
    engine = StrategyEngine(config=synced)
    for name in strategy_config_keys(engine.config):
        block = engine.config[name]
        if name == ONLY_ENABLED:
            assert block.get("enabled") is True
        else:
            assert block.get("enabled") is False
