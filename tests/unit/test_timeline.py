"""Timeline aggregator unit tests (generic fixtures)."""
from __future__ import annotations

import json
from pathlib import Path

from app.core.timeline import build_timeline


def test_timeline_filters_by_symbol_and_trace(tmp_path: Path):
    sa = tmp_path / "signal_analysis.json"
    sa.write_text(
        json.dumps(
            [
                {
                    "timestamp": "2026-08-16T10:00:00",
                    "symbol": "ETH",
                    "direction": "BUY",
                    "strategy": "supertrend",
                    "approved": True,
                    "reasoning": "clean pullback",
                    "confidence": 80,
                    "trace_id": "abc123",
                    "trade_id": "ETH-1",
                },
                {
                    "timestamp": "2026-08-16T11:00:00",
                    "symbol": "SOL",
                    "direction": "SELL",
                    "strategy": "trend_lt",
                    "approved": False,
                    "reasoning": "weak volume",
                    "confidence": 40,
                    "trace_id": "zzz999",
                },
            ]
        ),
        encoding="utf-8",
    )
    th = tmp_path / "trades.csv"
    th.write_text(
        "timestamp,symbol,side,entry_price,exit_price,size,pnl,strategy,exit_reason,leverage,entry_time,trade_id,trace_id\n"
        "2026-08-16T12:00:00,ETH,BUY,100,101,1,1.0,supertrend,TP,5,2026-08-16T10:05:00,ETH-1,abc123\n",
        encoding="utf-8",
    )
    al = tmp_path / "bot_activity.log"
    al.write_text(
        "12:00:01 ✅ ENTRY CONFIRMED: ETH Size: 1 Entry: 100 | id=ETH-1 (trace=abc123)\n"
        "12:05:01 🛡️ Smart BE trailing on ETH id=ETH-1\n",
        encoding="utf-8",
    )

    out = build_timeline(
        symbol="ETH",
        signal_analysis_path=str(sa),
        trade_history_path=str(th),
        activity_log_path=str(al),
        limit=50,
    )
    assert out["count"] >= 1
    assert all(
        e.get("symbol") in (None, "ETH") or str(e["symbol"]).upper() == "ETH"
        for e in out["events"]
    )
    types = {e["type"] for e in out["events"]}
    assert "ai_decision" in types
    entries = [e for e in out["events"] if e["type"] == "entry"]
    assert entries
    assert any("10:05" in str(e.get("timestamp") or "") for e in entries)

    by_trace = build_timeline(
        trace_id="abc123",
        signal_analysis_path=str(sa),
        trade_history_path=str(th),
        activity_log_path=str(al),
    )
    assert by_trace["count"] >= 1
    assert all(
        e.get("trace_id") in (None, "abc123") or e["trace_id"] == "abc123"
        for e in by_trace["events"]
        if e.get("trace_id")
    )


def test_timeline_empty_sources(tmp_path: Path):
    out = build_timeline(
        signal_analysis_path=str(tmp_path / "missing.json"),
        trade_history_path=str(tmp_path / "missing.csv"),
        activity_log_path=str(tmp_path / "missing.log"),
    )
    assert out["count"] == 0
    assert out["events"] == []
