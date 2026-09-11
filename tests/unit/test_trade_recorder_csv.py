"""Tests for TradeRecorder CSV schema migration and malformed rows."""
import csv
from pathlib import Path

from app.core.trade_recorder import TradeRecorder, normalize_entry_indicators


def test_read_csv_with_extra_fields_from_unquoted_commas(tmp_path):
    csv_path = tmp_path / "trade_history.csv"
    recorder = TradeRecorder(data_dir=str(tmp_path))

    old_header = recorder.headers[:21]  # through trace_id, before v2 extension cols
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
    old_header = recorder.headers[:21]

    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(old_header)
        writer.writerow(["2026-08-19T10:00:00", "ETH", "BUY"] + [""] * (len(old_header) - 3))

    recorder._maybe_migrate_csv_header()

    with open(csv_path, encoding="utf-8", newline="") as f:
        header = next(csv.reader(f))
    assert header == recorder.headers


def test_normalize_entry_indicators_maps_ai_context_keys():
    snap = normalize_entry_indicators(
        {
            "regime": "TREND",
            "rsi_val": 67.4,
            "adx_val": 41.2,
            "adx_slope": -0.35,
            "volume_ratio": 154.2,
            "bb_position": "ABOVE_UPPER",
            "vol_slope": 120.0,
            "macd_hist": 0.0012,
            "market_bias": "BULLISH",
            "strategy_timeframe": "15m",
            "ai_confidence": 68,
            "ai_reasoning": "ok",
        }
    )
    assert snap["rsi"] == 67.4
    assert snap["adx"] == 41.2
    assert snap["adx_slope"] == -0.35
    assert snap["bb_position"] == "ABOVE_UPPER"
    assert snap["strategy_timeframe"] == "15m"


def test_add_trade_persists_rsi_val_from_ai_context(tmp_path):
    recorder = TradeRecorder(data_dir=str(tmp_path))
    recorder.add_trade(
        {
            "symbol": "HYPE",
            "side": "BUY",
            "entry_price": 80.0,
            "exit_price": 81.0,
            "size": 1.0,
            "pnl": 1.0,
            "strategy": "rocket",
            "exit_reason": "TP",
            "entry_indicators": {
                "regime": "TREND",
                "rsi_val": 68.5,
                "adx_val": 38.0,
                "volume_ratio": 210.0,
                "bb_position": "INSIDE_BANDS",
                "adx_slope": 0.4,
                "vol_slope": 55.0,
                "macd_hist": 0.02,
                "market_bias": "BULLISH",
                "strategy_timeframe": "15m",
                "ai_confidence": 70,
                "ai_reasoning": "test",
            },
        }
    )
    row = recorder.get_history(limit=1)[0]
    assert float(row["entry_rsi"]) == 68.5
    assert float(row["entry_adx"]) == 38.0
    assert row["entry_bb_position"] == "INSIDE_BANDS"
    assert float(row["entry_adx_slope"]) == 0.4
    assert row["entry_strategy_tf"] == "15m"


def test_get_stats_with_string_pnl_values(tmp_path):
    csv_path = tmp_path / "trade_history.csv"
    recorder = TradeRecorder(data_dir=str(tmp_path))

    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f, quoting=csv.QUOTE_MINIMAL)
        writer.writerow(recorder.headers)
        writer.writerow(
            [
                "2026-08-19T10:00:00", "ADA", "BUY", "0.17", "0.18", "100", "1.5",
                "supertrend", "TP", "5", "TREND", "30", "55", "0.17", "0.16", "80",
                "70", "ok", "2026-08-19T09:00:00", "trade-1", "trace-1",
                "", "", "", "", "", "",
            ]
        )
        writer.writerow(
            [
                "2026-08-19T11:00:00", "ETH", "BUY", "1900", "1890", "1", "-0.5",
                "supertrend", "SL", "5", "TREND", "30", "55", "1900", "1890", "80",
                "70", "loss", "2026-08-19T10:00:00", "trade-2", "trace-2",
                "", "", "", "", "", "",
            ]
        )

    stats = recorder.get_stats()
    assert stats["total_trades"] == 2
    assert stats["total_pnl"] == 1.0
    assert stats["win_rate"] == 50.0
