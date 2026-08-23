"""Tests for exchange close PnL aggregation."""
from app.core.close_pnl import aggregate_exchange_close, estimate_gross_pnl


def test_aggregate_sums_partial_sl_fills():
    trade = {
        "side": "BUY",
        "size": 0.723,
        "timestamp": "2026-08-23T13:40:13.726108+00:00",
    }
    fills = [
        {
            "symbol": "BCH",
            "side": "SELL",
            "entry_price": 272.25,
            "size": 0.305,
            "pnl": -1.69275,
            "fee": 0.05,
            "dir": "Close Long",
            "timestamp": "2026-08-23T14:42:35.720000+00:00",
        },
        {
            "symbol": "BCH",
            "side": "SELL",
            "entry_price": 272.25,
            "size": 0.418,
            "pnl": -2.3199,
            "fee": 0.06,
            "dir": "Close Long",
            "timestamp": "2026-08-23T14:42:35.800000+00:00",
        },
    ]
    out = aggregate_exchange_close(fills, symbol="BCH", trade=trade)
    assert out is not None
    assert out["fill_count"] == 2
    assert abs(out["pnl"] - (-4.01265)) < 1e-4
    assert abs(out["close_size"] - 0.723) < 1e-6
    assert abs(out["exit_price"] - 272.25) < 1e-6


def test_aggregate_ignores_fills_before_entry():
    trade = {
        "side": "BUY",
        "size": 1.0,
        "timestamp": "2026-08-23T13:40:13+00:00",
    }
    fills = [
        {
            "symbol": "BCH",
            "side": "SELL",
            "entry_price": 280.0,
            "size": 1.0,
            "pnl": -0.5,
            "dir": "Close Long",
            "timestamp": "2026-08-23T13:00:00+00:00",
        },
        {
            "symbol": "BCH",
            "side": "SELL",
            "entry_price": 272.0,
            "size": 1.0,
            "pnl": -1.0,
            "dir": "Close Long",
            "timestamp": "2026-08-23T14:42:00+00:00",
        },
    ]
    out = aggregate_exchange_close(fills, symbol="BCH", trade=trade)
    assert out is not None
    assert out["pnl"] == -1.0
    assert out["fill_count"] == 1


def test_estimate_gross_pnl_long():
    assert abs(estimate_gross_pnl(side="BUY", entry_price=277.8, exit_price=272.25, size=0.723) + 4.01265) < 1e-4
