#!/usr/bin/env python3
"""Compare local repo config vs live NovaBot API."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _api_client import REPO_ROOT, api_base_url, get_json, load_local_json

USER_WATCH_PATHS = (
    "risk_defaults.daily_stop_loss",
    "risk_defaults.default_leverage",
    "risk_defaults.max_positions",
    "risk_defaults.risk_profile",
    "scanner.interval",
    "scanner.min_score",
    "scanner.auto_switch",
)

STRATEGY_WATCH = {
    "rocket": ("params.min_volume_ratio_pct", "params.scan_interval_minutes", "version", "risk_profile"),
    "waterfall": ("params.min_volume_ratio_pct", "params.scan_interval_minutes", "version", "risk_profile"),
    "supertrend": ("params.min_volume_ratio_pct", "params.scan_interval_minutes", "version", "risk_profile"),
}

SYNC_CMD = (
    "python .cursor/skills/fetch-novabot-logs/scripts/sync_config.py --apply"
)


def _get_path(obj: Any, dotted: str) -> Any:
    cur = obj
    for part in dotted.split("."):
        if not isinstance(cur, dict) or part not in cur:
            return None
        cur = cur[part]
    return cur


def _flatten_user_settings(settings: dict[str, Any]) -> dict[str, Any]:
    return {path: _get_path(settings, path) for path in USER_WATCH_PATHS}


def _flatten_strategies(cfg: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for strat, paths in STRATEGY_WATCH.items():
        block = cfg.get(strat, {})
        for path in paths:
            out[f"{strat}.{path}"] = _get_path(block, path)
    return out


def _live_user_settings() -> dict[str, Any]:
    global_flat, err = get_json("/api/settings/all")
    if err:
        raise RuntimeError(err)
    return _flatten_user_settings(global_flat or {})


def _live_strategies() -> dict[str, Any]:
    live, err = get_json("/api/config/strategies-config")
    if err:
        raise RuntimeError(err)
    return _flatten_strategies(live or {})


def diff_maps(local: dict[str, Any], live: dict[str, Any]) -> list[tuple[str, Any, Any]]:
    keys = sorted(set(local) | set(live))
    diffs: list[tuple[str, Any, Any]] = []
    for key in keys:
        lv, rv = local.get(key), live.get(key)
        if lv != rv:
            diffs.append((key, lv, rv))
    return diffs


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Diff local config vs live NovaBot API.")
    parser.add_argument("--api-url", default=None, help="Override API base URL")
    args = parser.parse_args(argv)

    if args.api_url:
        import os

        os.environ["NOVABOT_API_URL"] = args.api_url

    print(f"API: {api_base_url()}")
    print(f"Local repo: {REPO_ROOT}\n")

    local_user = load_local_json("data/config/user_settings.json")
    local_strats = load_local_json("data/config/strategies.json")

    local_user_flat = _flatten_user_settings(local_user)
    local_strat_flat = _flatten_strategies(local_strats)

    try:
        live_user_flat = _live_user_settings()
        live_strat_flat = _live_strategies()
    except RuntimeError as exc:
        print(f"ERROR: {exc}")
        return 1

    user_diffs = diff_maps(local_user_flat, live_user_flat)
    strat_diffs = diff_maps(local_strat_flat, live_strat_flat)

    if not user_diffs and not strat_diffs:
        print("OK — live config matches local watch list.")
        return 0

    if user_diffs:
        print("user_settings.json")
        print(f"{'path':<45} {'local':>12} {'live':>12}")
        print("-" * 72)
        for path, local_val, live_val in user_diffs:
            print(f"{path:<45} {str(local_val):>12} {str(live_val):>12}")

    if strat_diffs:
        print()
        print("strategies.json")
        print(f"{'path':<45} {'local':>12} {'live':>12}")
        print("-" * 72)
        for path, local_val, live_val in strat_diffs:
            print(f"{path:<45} {str(local_val):>12} {str(live_val):>12}")

    print(f"\n{len(user_diffs) + len(strat_diffs)} difference(s). Run: {SYNC_CMD}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
