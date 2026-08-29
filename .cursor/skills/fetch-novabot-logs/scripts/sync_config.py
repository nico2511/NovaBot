#!/usr/bin/env python3
"""Push local data/config/*.json to a running NovaBot instance via API."""
from __future__ import annotations

import argparse
import copy
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _api_client import api_base_url, get_json, load_local_json, post_json, put_json

DIFF_CMD = "python .cursor/skills/fetch-novabot-logs/scripts/config_diff.py"


def _push_user_settings(dry_run: bool) -> list[str]:
    local = load_local_json("data/config/user_settings.json")
    live_all, err = get_json("/api/settings/all")
    if err:
        raise RuntimeError(f"Failed to read live settings: {err}")

    merged = copy.deepcopy(local)
    live_notif = (live_all or {}).get("notifications") or {}
    if live_notif:
        merged["notifications"] = live_notif

    sections = ("risk_defaults", "operations", "ai_config", "scanner", "notifications")
    messages: list[str] = []
    for section in sections:
        payload = merged.get(section)
        if not isinstance(payload, dict):
            continue
        if dry_run:
            messages.append(f"DRY-RUN POST /api/settings/update section={section}")
            continue
        resp, err = post_json("/api/settings/update", {"section": section, "data": payload})
        if err:
            raise RuntimeError(f"{section}: {err}")
        messages.append(f"OK  {section} -> {resp.get('status', 'done')}")
    return messages


def _push_strategies(dry_run: bool) -> list[str]:
    local = load_local_json("data/config/strategies.json")
    if dry_run:
        return [f"DRY-RUN PUT /api/config/strategies-config ({len(local)} keys)"]

    resp, err = put_json("/api/config/strategies-config", local)
    if not err:
        refreshed = resp.get("refreshed_runtime") or []
        return [f"OK  strategies.json ({len(local)} keys, runtime refreshed: {', '.join(refreshed) or 'none'})"]

    if "405" not in err and "404" not in err:
        raise RuntimeError(f"strategies: {err}")

    messages = [f"WARN PUT unavailable ({err.strip()}) — falling back to per-strategy params API"]
    for strat_id, cfg in local.items():
        if strat_id == "market_regime" or not isinstance(cfg, dict):
            continue
        params = cfg.get("params")
        if not isinstance(params, dict) or not params:
            continue
        resp2, err2 = post_json(
            "/api/config/strategy-params",
            {"strategy_id": strat_id, "params": params},
        )
        if err2:
            if "Unknown strategy" in err2 or "not found" in err2.lower():
                messages.append(f"SKIP {strat_id} (not loaded in runtime engine)")
                continue
            if "422" in err2 or "validation" in err2.lower():
                messages.append(f"SKIP {strat_id} (param schema mismatch — redeploy needed)")
                continue
            raise RuntimeError(f"{strat_id}: {err2}")
        applied = resp2.get("applied") or {}
        messages.append(f"OK  {strat_id} params ({len(applied)} keys)")
    messages.append(
        "NOTE: metadata (version, risk_profile) needs redeploy + PUT endpoint for full sync"
    )
    return messages


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Sync local config to live NovaBot via API.")
    parser.add_argument("--api-url", default=None, help="Override API base URL")
    parser.add_argument("--apply", action="store_true", help="Actually push changes (default is dry-run)")
    parser.add_argument("--user-only", action="store_true", help="Sync user_settings.json only")
    parser.add_argument("--strategies-only", action="store_true", help="Sync strategies.json only")
    args = parser.parse_args(argv)

    if args.api_url:
        import os

        os.environ["NOVABOT_API_URL"] = args.api_url

    dry_run = not args.apply
    print(f"API: {api_base_url()}")
    print("Mode:", "DRY-RUN" if dry_run else "APPLY")
    print()

    try:
        if not args.strategies_only:
            for line in _push_user_settings(dry_run):
                print(line)
        if not args.user_only:
            for line in _push_strategies(dry_run):
                print(line)
    except RuntimeError as exc:
        print(f"ERROR: {exc}")
        return 1

    if dry_run:
        print("\nRe-run with --apply to push.")
    else:
        print(f"\nDone. Verify with: {DIFF_CMD}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
