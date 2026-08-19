#!/usr/bin/env python3
"""
Fetch all NovaBot logs: local files + live API snapshots.

Writes JSON snapshots and copies text logs under scratch/ (default).
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

DEFAULT_TIMEOUT_SEC = 5

# Repo root = NovaBot/ (four levels up from this script)
REPO_ROOT = Path(__file__).resolve().parents[4]
DEFAULT_OUTPUT = REPO_ROOT / "scratch"
LOCAL_LOG_DIR = REPO_ROOT / "logs"

LOCAL_LOG_FILES = (
    "novabot.log",
    "novabot.log.1",
    "novabot.log.2",
    "novabot.log.3",
    "bot_activity.log",
    "bot_activity.log.1",
    "ai_payload.jsonl",
)

API_SNAPSHOTS: tuple[tuple[str, str], ...] = (
    ("health.json", "/health"),
    ("live_logs.json", "/api/logs?limit=1000"),
    ("live_status.json", "/api/status"),
    ("live_scanner.json", "/api/scanner/status"),
    ("live_opps.json", "/api/scanner/opportunities"),
    ("live_strats.json", "/api/config/strategies-config"),
    ("live_trades.json", "/api/history/bot/trades"),
    ("live_trade_stats.json", "/api/history/bot/trades/stats"),
    ("live_signal_analysis.json", "/api/signal-analysis"),
    ("live_sentiment.json", "/api/sentiment-history"),
)


def _load_dotenv() -> None:
    env_path = REPO_ROOT / ".env"
    if not env_path.is_file():
        return
    try:
        from dotenv import load_dotenv

        load_dotenv(env_path)
    except ImportError:
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def _fetch_json(
    base_url: str,
    path: str,
    api_key: str | None,
    timeout: float = DEFAULT_TIMEOUT_SEC,
) -> tuple[Any | None, str | None]:
    url = f"{base_url.rstrip('/')}{path}"
    headers = {"Accept": "application/json"}
    if api_key:
        headers["X-API-Key"] = api_key
    req = Request(url, headers=headers, method="GET")
    try:
        with urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8")
            return json.loads(raw), None
    except HTTPError as exc:
        body = ""
        try:
            body = exc.read().decode("utf-8", errors="replace")[:300]
        except Exception:
            pass
        return None, f"HTTP {exc.code}: {body or exc.reason}"
    except URLError as exc:
        return None, f"Connection failed: {exc.reason}"
    except json.JSONDecodeError as exc:
        return None, f"Invalid JSON: {exc}"


def _copy_local_logs(out_dir: Path) -> dict[str, str]:
    local_dir = out_dir / "local"
    local_dir.mkdir(parents=True, exist_ok=True)
    copied: dict[str, str] = {}
    for name in LOCAL_LOG_FILES:
        src = LOCAL_LOG_DIR / name
        if not src.is_file():
            continue
        dst = local_dir / name
        shutil.copy2(src, dst)
        copied[name] = str(dst.relative_to(out_dir))
    return copied


def _write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def _fetch_api_snapshots(
    output_dir: Path,
    api_url: str,
    api_key: str | None,
    timeout: float,
) -> tuple[dict[str, Any], list[str]]:
    snapshots: dict[str, Any] = {}
    errors: list[str] = []

    def _one(item: tuple[str, str]) -> tuple[str, str, Any | None, str | None]:
        filename, path = item
        data, err = _fetch_json(api_url, path, api_key, timeout=timeout)
        return filename, path, data, err

    with ThreadPoolExecutor(max_workers=6) as pool:
        futures = {pool.submit(_one, item): item for item in API_SNAPSHOTS}
        for future in as_completed(futures):
            filename, path, data, err = future.result()
            dest = output_dir / filename
            if err:
                snapshots[filename] = {"ok": False, "error": err}
                errors.append(f"{filename}: {err}")
                _write_json(dest, {"error": err, "endpoint": path})
            else:
                snapshots[filename] = {"ok": True, "endpoint": path}
                _write_json(dest, data)
    return snapshots, errors


def fetch_all(
    output_dir: Path,
    *,
    api_url: str | None,
    api_key: str | None,
    local_only: bool,
    api_only: bool,
    timeout: float = DEFAULT_TIMEOUT_SEC,
) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    manifest: dict[str, Any] = {
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "repo_root": str(REPO_ROOT),
        "output_dir": str(output_dir),
        "local_files": {},
        "api_snapshots": {},
        "errors": [],
    }

    if not api_only:
        manifest["local_files"] = _copy_local_logs(output_dir)
        if not manifest["local_files"]:
            manifest["errors"].append("No local log files found in logs/")

    if not local_only and api_url:
        snapshots, api_errors = _fetch_api_snapshots(output_dir, api_url, api_key, timeout)
        manifest["api_snapshots"] = snapshots
        manifest["errors"].extend(api_errors)
    elif not local_only:
        manifest["errors"].append("API URL not configured — skipped API snapshots")

    _write_json(output_dir / "manifest.json", manifest)
    return manifest


def main(argv: list[str] | None = None) -> int:
    _load_dotenv()

    parser = argparse.ArgumentParser(description="Fetch all NovaBot logs (local + API).")
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help=f"Output directory (default: {DEFAULT_OUTPUT})",
    )
    parser.add_argument(
        "--archive",
        action="store_true",
        help="Write to scratch/archives/YYYY-MM-DD_HH-MM-SS/ instead of overwriting scratch/",
    )
    parser.add_argument(
        "--api-url",
        default=os.getenv("NOVABOT_API_URL") or os.getenv("API_URL") or "http://localhost:3001",
        help="NovaBot API base URL (default: http://localhost:3001)",
    )
    parser.add_argument(
        "--api-key",
        default=os.getenv("API_KEY"),
        help="X-API-Key header (default: API_KEY from .env)",
    )
    parser.add_argument(
        "--local-only",
        action="store_true",
        help="Copy local log files only, skip API",
    )
    parser.add_argument(
        "--api-only",
        action="store_true",
        help="Fetch API snapshots only, skip local files",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=DEFAULT_TIMEOUT_SEC,
        help=f"HTTP timeout per endpoint in seconds (default: {DEFAULT_TIMEOUT_SEC})",
    )
    args = parser.parse_args(argv)

    out = args.output
    if args.archive:
        stamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        out = DEFAULT_OUTPUT / "archives" / stamp

    manifest = fetch_all(
        out,
        api_url=None if args.local_only else args.api_url,
        api_key=args.api_key,
        local_only=args.local_only,
        api_only=args.api_only,
        timeout=args.timeout,
    )

    ok_api = sum(1 for v in manifest["api_snapshots"].values() if v.get("ok"))
    total_api = len(manifest["api_snapshots"])
    local_count = len(manifest["local_files"])

    print(f"Output: {out}")
    print(f"Local files copied: {local_count}")
    if total_api:
        print(f"API snapshots OK: {ok_api}/{total_api}")
    if manifest["errors"]:
        print("Warnings:")
        for err in manifest["errors"]:
            print(f"  - {err}")
        return 1 if ok_api == 0 and local_count == 0 else 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
