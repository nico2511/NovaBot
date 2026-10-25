"""All shipped strategies off by default; no entry signals; revision sync on deploy."""
from __future__ import annotations

import json
import shutil
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from app.services.storage import (
    StorageService,
    apply_enabled_active_from_defaults,
    strategy_config_keys,
)
from strategies.engine import StrategyEngine

ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATHS = (
    ROOT / "app" / "core" / "defaults" / "strategies.default.json",
    ROOT / "data" / "config" / "strategies.json",
)
EXPECTED_REVISION = "2026-10-25-strategies-off"


def _load_cfg(path: Path) -> dict:
    return json.loads(path.read_text())


def test_all_strategy_blocks_disabled_in_default_configs():
    for path in CONFIG_PATHS:
        cfg = _load_cfg(path)
        names = strategy_config_keys(cfg)
        assert names, f"No strategy blocks in {path}"
        for name in names:
            block = cfg[name]
            assert block.get("enabled") is False, f"{path.name}:{name}.enabled"
            assert block.get("active") is False, f"{path.name}:{name}.active"
        meta = cfg.get("meta") or {}
        assert meta.get("defaults_revision") == EXPECTED_REVISION


def test_strategy_engine_emits_no_signals_with_default_config():
    cfg = _load_cfg(ROOT / "data" / "config" / "strategies.json")
    engine = StrategyEngine(config=cfg)
    n = 260
    idx = pd.date_range("2026-01-01", periods=n, freq="15min", tz="UTC")
    close = np.linspace(100.0, 140.0, n) + np.sin(np.linspace(0, 12, n))
    df = pd.DataFrame(
        {
            "open": close - 0.1,
            "high": close + 1.0,
            "low": close - 1.0,
            "close": close,
            "volume": np.full(n, 5000.0),
        },
        index=idx,
    )
    extra = {
        "symbol": "BTC",
        "1h": df.resample("1h").agg(
            {"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"}
        ).dropna(),
        "1m": df,
        "5m": df,
    }
    out = engine.analyze(df, extra_data=extra)
    assert out.get("strategies") == []
    assert out.get("signals") == []


def test_sync_applies_enabled_active_when_defaults_revision_changes(tmp_path):
    default_cfg = _load_cfg(ROOT / "app" / "core" / "defaults" / "strategies.default.json")
    runtime_cfg = json.loads(json.dumps(default_cfg))
    for name in strategy_config_keys(runtime_cfg):
        runtime_cfg[name]["enabled"] = True
        runtime_cfg[name]["active"] = True
    runtime_cfg["meta"] = {"defaults_revision": "legacy-pre-2026-10"}

    defaults_dir = tmp_path / "app" / "core" / "defaults"
    defaults_dir.mkdir(parents=True)
    shutil.copy(
        ROOT / "app" / "core" / "defaults" / "strategies.default.json",
        defaults_dir / "strategies.default.json",
    )
    ss = StorageService(str(tmp_path))
    (ss.config_dir / "strategies.json").write_text(json.dumps(runtime_cfg, indent=2))

    result = ss.sync_strategies_from_defaults()
    assert result["status"] in ("updated", "noop")
    synced = json.loads((ss.config_dir / "strategies.json").read_text())
    for name in strategy_config_keys(synced):
        assert synced[name]["enabled"] is False
        assert synced[name]["active"] is False
    assert synced["meta"]["defaults_revision"] == EXPECTED_REVISION
    assert float(synced["rocket"]["params"]["min_rr"]) == float(
        default_cfg["rocket"]["params"]["min_rr"]
    )


def test_apply_enabled_active_preserves_params():
    default_cfg = _load_cfg(ROOT / "app" / "core" / "defaults" / "strategies.default.json")
    runtime = {
        "rocket": {
            "enabled": True,
            "active": True,
            "type": "trend",
            "params": {"min_rr": 9.9, "custom_flag": True},
        },
        "meta": {"defaults_revision": "old"},
    }
    out = apply_enabled_active_from_defaults(runtime, default_cfg)
    assert out["rocket"]["enabled"] is False
    assert out["rocket"]["params"]["min_rr"] == 9.9
    assert out["rocket"]["params"]["custom_flag"] is True
