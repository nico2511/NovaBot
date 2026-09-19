#!/usr/bin/env python3
"""Pull prod config + fetch scratch after .env is set (post-format / new PC)."""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
PY = sys.executable

sys.path.insert(0, str(SCRIPTS))
from _api_client import REPO_ROOT  # noqa: E402


def _run(label: str, args: list[str]) -> int:
    print(f"\n=== {label} ===")
    cmd = [PY, *args]
    print(" ", " ".join(str(c) for c in cmd))
    return subprocess.call(cmd, cwd=REPO_ROOT)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="pull_config --apply, fetch_logs, then config_diff."
    )
    parser.add_argument("--api-url", default=None, help="Set NOVABOT_API_URL for this run")
    parser.add_argument(
        "--archive",
        action="store_true",
        help="Pass --archive to fetch_logs.py",
    )
    parser.add_argument(
        "--skip-fetch",
        action="store_true",
        help="Only pull config + diff (no scratch/)",
    )
    args = parser.parse_args(argv)

    pull_args = [str(SCRIPTS / "pull_config.py"), "--apply"]
    if args.api_url:
        pull_args.extend(["--api-url", args.api_url])

    rc = _run("Pull config from API", pull_args)
    if rc != 0:
        return rc

    if not args.skip_fetch:
        fetch_args = [str(SCRIPTS / "fetch_logs.py")]
        if args.archive:
            fetch_args.append("--archive")
        if args.api_url:
            fetch_args.extend(["--api-url", args.api_url])
        rc = _run("Fetch logs → scratch/", fetch_args)
        if rc != 0:
            print("WARN: fetch_logs failed (API down or API_KEY?) — config pull may still be OK")

    diff_args = [str(SCRIPTS / "config_diff.py")]
    if args.api_url:
        diff_args.extend(["--api-url", args.api_url])
    rc = _run("Config diff", diff_args)
    return rc


if __name__ == "__main__":
    sys.exit(main())
