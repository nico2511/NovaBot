"""Tests for TradeRecorder CSV schema migration and malformed rows."""
import csv
from pathlib import Path

from app.core.trade_recorder import TradeRecorder


def test_read_csv_with_extra_fields_from_unquoted_commas(tmp_path):
    csv_path = tmp_path / "trade_history.csv"
    recorder = TradeRecorder(data_dir=str(tmp_path))

    old_header = recorder.headers[:18]
    with open(csv_path, "w", encoding="utf-8") as f:
        f.write(",".join(old_header) + "\n")
        # Unquoted commas in ai_reasoning inflate field count (prod bug)
        f.write(
            "2026-08-19T10:00:00,ADA,BUY,0.17,0.18,100,1.0,supertrend,TP,5,"
            "TREND,30,55,0.17,0.16,80,70,reason, with, commas,"
            "2026-08-19T09:00:00,trade-1,trace-1\n"
        )

    df = recorder._read_csv_safe()
    assert len(df) == 1
    assert df.iloc[0]["symbol"] == "ADA"
    assert df.iloc[0]["ai_reasoning"] == "reason, with, commas"
    assert df.iloc[0]["trade_id"] == "trade-1"


def test_migrate_csv_header_to_current_schema(tmp_path):
    csv_path = tmp_path / "trade_history.csv"
    recorder = TradeRecorder(data_dir=str(tmp_path))
    old_header = recorder.headers[:18]

    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(old_header)
        writer.writerow(["2026-08-19T10:00:00", "ETH", "BUY"] + [""] * (len(old_header) - 3))

    recorder._maybe_migrate_csv_header()

    with open(csv_path, encoding="utf-8", newline="") as f:
        header = next(csv.reader(f))
    assert header == recorder.headers
