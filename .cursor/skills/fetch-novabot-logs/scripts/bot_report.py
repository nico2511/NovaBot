#!/usr/bin/env python3
"""Generate a markdown trading/ops report from NovaBot logs + API snapshots."""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _api_client import REPO_ROOT, api_base_url

FETCH_SCRIPT = Path(__file__).resolve().parent / "fetch_logs.py"


def _load_json(path: Path) -> Any:
    if not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _parse_ts(ts: str) -> datetime:
    return datetime.fromisoformat(ts.replace("Z", "+00:00"))


def _trade_stats(trades: list[dict[str, Any]], hours: int) -> dict[str, Any]:
    if not trades:
        return {"count": 0, "pnl": 0.0, "wr": 0.0, "by_strategy": {}}
    latest = max(_parse_ts(t["timestamp"]) for t in trades)
    cutoff = latest - timedelta(hours=hours)
    subset = [t for t in trades if _parse_ts(t["timestamp"]) >= cutoff]
    if not subset:
        return {"count": 0, "pnl": 0.0, "wr": 0.0, "by_strategy": {}}

    pnl = sum(float(t["pnl"]) for t in subset)
    wins = sum(1 for t in subset if float(t["pnl"]) >= 0)
    by_strat: dict[str, dict[str, float]] = defaultdict(lambda: {"n": 0, "pnl": 0.0, "w": 0})
    for t in subset:
        s = t.get("strategy", "?")
        by_strat[s]["n"] += 1
        by_strat[s]["pnl"] += float(t["pnl"])
        if float(t["pnl"]) >= 0:
            by_strat[s]["w"] += 1

    exits = Counter(t.get("exit_reason", "?") for t in subset)
    return {
        "count": len(subset),
        "pnl": pnl,
        "wr": 100.0 * wins / len(subset),
        "by_strategy": dict(by_strat),
        "exits": dict(exits),
        "latest": latest.isoformat(),
        "recent": sorted(subset, key=lambda x: x["timestamp"])[-10:],
    }


def _log_highlights(logs: list[dict[str, Any]]) -> list[str]:
    patterns = (
        "THESIS", "DEAD", "SKIPPED", "VETO", "SIZING", "ENTRY", "EXECUTED",
        "weekend", "paused", "stop mode", "No signal",
    )
    out: list[str] = []
    for entry in logs:
        msg = entry.get("message", "")
        if any(p.lower() in msg.lower() for p in patterns):
            out.append(f"{entry.get('timestamp', '')} {msg}")
    return out[-15:]


def build_report(scratch_dir: Path, hours: int = 48) -> str:
    status = _load_json(scratch_dir / "live_status.json") or {}
    health = _load_json(scratch_dir / "live_health.json") or _load_json(scratch_dir / "health.json") or {}
    trades_doc = _load_json(scratch_dir / "live_trades.json") or {}
    trades = trades_doc.get("trades", []) if isinstance(trades_doc, dict) else []
    stats_doc = _load_json(scratch_dir / "live_trade_stats.json") or {}
    global_stats = stats_doc.get("stats", {}) if isinstance(stats_doc, dict) else {}

    logs_raw = _load_json(scratch_dir / "live_logs.json")
    logs: list[dict[str, Any]] = []
    if isinstance(logs_raw, dict):
        logs = logs_raw.get("logs", [])
    elif isinstance(logs_raw, list):
        logs = logs_raw

    window = _trade_stats(trades, hours)
    lines: list[str] = []
    lines.append("# NovaBot Report")
    lines.append("")
    lines.append(f"- Generated: {datetime.now(timezone.utc).astimezone().strftime('%Y-%m-%d %H:%M %Z')}")
    lines.append(f"- API: {api_base_url()}")
    lines.append(f"- Scratch: `{scratch_dir}`")
    lines.append("")

    lines.append("## Bot status")
    lines.append(f"- Running: **{status.get('status', status.get('is_running', '?'))}**")
    lines.append(f"- Equity: **${float(status.get('balance', 0) or 0):.2f}**")
    lines.append(f"- Active symbol: **{status.get('active_symbol', '?')}**")
    lines.append(f"- Open positions: **{status.get('active_positions', 0)}**")
    lines.append(f"- Daily PnL: **${float(status.get('daily_pnl', 0) or 0):.2f}**")
    weekend = (status.get("settings") or {}).get("weekend_pause") or {}
    if weekend.get("enabled"):
        paused = weekend.get("paused_strategies") or []
        lines.append(
            f"- Weekend pause: **{'active' if weekend.get('active') else 'inactive'}** "
            f"({', '.join(paused) or 'none'})"
        )
    if health:
        lines.append(f"- Health: **{health.get('status', '?')}** (heartbeat {health.get('last_heartbeat_age_sec', '?')}s)")
    lines.append("")

    lines.append(f"## Trades (last {hours}h)")
    lines.append(f"- Count: **{window['count']}** | PnL: **{window['pnl']:+.2f} USDC** | WR: **{window['wr']:.0f}%**")
    if window.get("exits"):
        lines.append(f"- Exits: {', '.join(f'{k}={v}' for k, v in sorted(window['exits'].items()))}")
    lines.append("")
    if window.get("by_strategy"):
        lines.append("| Strategy | Trades | PnL | WR |")
        lines.append("|----------|--------|-----|-----|")
        for strat, v in sorted(window["by_strategy"].items(), key=lambda x: -x[1]["pnl"]):
            wr = 100.0 * v["w"] / v["n"] if v["n"] else 0
            lines.append(f"| {strat} | {int(v['n'])} | {v['pnl']:+.2f} | {wr:.0f}% |")
        lines.append("")
    if window.get("recent"):
        lines.append("### Recent trades")
        for t in window["recent"]:
            lines.append(
                f"- `{t['timestamp'][:16]}` **{t.get('strategy','?')}** {t['symbol']} {t['side']} "
                f"{float(t['pnl']):+.2f} ({t.get('exit_reason','?')})"
            )
        lines.append("")

    if global_stats:
        lines.append("## All-time (recorder)")
        lines.append(
            f"- {global_stats.get('total_trades', 0)} trades | "
            f"WR {global_stats.get('win_rate', 0):.1f}% | "
            f"PnL {global_stats.get('total_pnl', 0):+.2f} | "
            f"PF {global_stats.get('profit_factor', 0):.2f}"
        )
        lines.append("")

    highlights = _log_highlights(logs)
    if highlights:
        lines.append("## Log highlights (in-memory)")
        for h in highlights:
            lines.append(f"- {h}")
        lines.append("")

    manifest = _load_json(scratch_dir / "manifest.json") or {}
    if manifest.get("errors"):
        lines.append("## Fetch warnings")
        for err in manifest["errors"]:
            lines.append(f"- {err}")
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="NovaBot markdown report from scratch/ API snapshots.")
    parser.add_argument("-o", "--output", type=Path, default=REPO_ROOT / "scratch" / "report.md")
    parser.add_argument("--scratch", type=Path, default=REPO_ROOT / "scratch")
    parser.add_argument("--hours", type=int, default=48)
    parser.add_argument("--fetch", action="store_true", help="Run fetch_logs.py --api-only first")
    parser.add_argument("--stdout", action="store_true", help="Print report to stdout")
    args = parser.parse_args(argv)

    if args.fetch:
        cmd = [sys.executable, str(FETCH_SCRIPT), "--api-only", "-o", str(args.scratch)]
        print(f"Fetching API snapshots -> {args.scratch}")
        rc = subprocess.call(cmd, cwd=REPO_ROOT)
        if rc != 0:
            return rc

    report = build_report(args.scratch, hours=args.hours)
    if args.stdout:
        print(report, end="")
    else:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(report, encoding="utf-8")
        print(f"Report written: {args.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
