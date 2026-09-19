#!/usr/bin/env python3
"""Pull live NovaBot config from API into data/config/ (recovery after format / new machine)."""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _api_client import REPO_ROOT, api_base_url, get_json, load_local_json

STRATEGIES_PATH = REPO_ROOT / "data/config/strategies.json"
USER_SETTINGS_PATH = REPO_ROOT / "data/config/user_settings.json"
USER_EXAMPLE_PATH = REPO_ROOT / "data/config/user_settings.example.json"


def _deep_merge(base: dict[str, Any], overlay: dict[str, Any]) -> dict[str, Any]:
    out = dict(base)
    for key, val in overlay.items():
        if isinstance(val, dict) and isinstance(out.get(key), dict):
            out[key] = _deep_merge(out[key], val)
        else:
            out[key] = val
    return out


def _user_settings_template() -> dict[str, Any]:
    if USER_EXAMPLE_PATH.is_file():
        return json.loads(USER_EXAMPLE_PATH.read_text(encoding="utf-8"))
    return {
        "operations": {},
        "risk_defaults": {},
        "ai_config": {},
        "notifications": {},
        "scanner": {},
    }


def _build_user_settings(live: dict[str, Any], *, redact_webhooks: bool) -> dict[str, Any]:
    merged = _deep_merge(_user_settings_template(), live or {})
    if redact_webhooks:
        notif = merged.get("notifications")
        if isinstance(notif, dict):
            merged["notifications"] = {
                "discord_webhook_alerts": "",
                "discord_webhook_logs": "",
            }
    return merged


def pull_strategies() -> tuple[dict[str, Any] | None, str | None]:
    return get_json("/api/config/strategies-config")


def pull_user_settings() -> tuple[dict[str, Any] | None, str | None]:
    return get_json("/api/settings/all")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Pull strategies + user_settings from live NovaBot into data/config/."
    )
    parser.add_argument("--api-url", default=None, help="Override NOVABOT_API_URL / API_URL")
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Write files (default: dry-run, print summary only)",
    )
    parser.add_argument("--strategies-only", action="store_true")
    parser.add_argument("--user-only", action="store_true")
    parser.add_argument(
        "--redact-webhooks",
        action="store_true",
        help="Do not store Discord webhook URLs in user_settings.json",
    )
    args = parser.parse_args(argv)

    if args.api_url:
        os.environ["NOVABOT_API_URL"] = args.api_url.rstrip("/")

    print(f"API: {api_base_url()}")
    print("Mode:", "APPLY" if args.apply else "DRY-RUN")
    print()

    errors = 0

    if not args.user_only:
        live_strat, err = pull_strategies()
        if err:
            print(f"ERROR strategies: {err}")
            errors += 1
        elif live_strat is None:
            print("ERROR strategies: empty response")
            errors += 1
        else:
            keys = [k for k in live_strat if k != "market_regime"]
            print(f"strategies.json: {len(keys)} strategy blocks (+ market_regime)")
            if args.apply:
                STRATEGIES_PATH.parent.mkdir(parents=True, exist_ok=True)
                STRATEGIES_PATH.write_text(
                    json.dumps(live_strat, indent=2, ensure_ascii=False) + "\n",
                    encoding="utf-8",
                )
                print(f"  -> wrote {STRATEGIES_PATH.relative_to(REPO_ROOT)}")

    if not args.strategies_only:
        live_user, err = pull_user_settings()
        if err:
            print(f"ERROR user_settings: {err}")
            errors += 1
        elif not live_user:
            print("WARN user_settings: empty response")
        else:
            payload = _build_user_settings(live_user, redact_webhooks=args.redact_webhooks)
            sections = [k for k in payload if isinstance(payload.get(k), dict)]
            print(f"user_settings.json: sections {', '.join(sections)}")
            if args.redact_webhooks:
                print("  (Discord webhooks redacted — omit --redact-webhooks to keep URLs)")
            if args.apply:
                USER_SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
                USER_SETTINGS_PATH.write_text(
                    json.dumps(payload, indent=4, ensure_ascii=False) + "\n",
                    encoding="utf-8",
                )
                print(f"  -> wrote {USER_SETTINGS_PATH.relative_to(REPO_ROOT)}")

    if errors:
        print(
            "\nIf HTTP 401/403: set API_KEY in .env (same value as Coolify) "
            "and NOVABOT_API_URL=https://your-bot-host"
        )
        return 1

    if not args.apply:
        print("\nRe-run with --apply to write files.")
        print("Then: python .cursor/skills/fetch-novabot-logs/scripts/config_diff.py")
    else:
        print("\nDone. Local config should match live (modulo redacted webhooks).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
