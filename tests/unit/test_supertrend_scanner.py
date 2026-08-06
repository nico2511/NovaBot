"""Unit tests for SuperTrend-first scanner scoring (no network)."""
import pandas as pd
import numpy as np

from app.services.supertrend_scanner import SupertrendScanner


def _trending_df(n=260, direction="up"):
    idx = pd.date_range("2026-01-01", periods=n, freq="15min", tz="UTC")
    # Smooth trend so EMA/ST/ADX can form
    base = np.linspace(100, 140, n) if direction == "up" else np.linspace(140, 100, n)
    noise = np.sin(np.linspace(0, 20, n)) * 0.3
    close = base + noise
    high = close + 0.8
    low = close - 0.8
    open_ = close - 0.1
    volume = np.full(n, 1000.0)
    # Spike recent volume above MA
    volume[-10:] = 2000.0
    return pd.DataFrame(
        {"open": open_, "high": high, "low": low, "close": close, "volume": volume},
        index=idx,
    )


def test_score_dataframe_finds_aligned_uptrend():
    scanner = SupertrendScanner(
        st_params={
            "period": 10,
            "multiplier": 3.0,
            "ema_filter_period": 50,  # shorter for synthetic series
            "adx_threshold": 10,
            "min_volume_ratio_pct": 50,
            "rsi_neutral_low": 45,
            "rsi_neutral_high": 55,
            # Synthetic linspace trend is intentionally steep vs ST — allow for unit test
            "max_extension_atr": 50,
        }
    )
    df = _trending_df(direction="up")
    result = scanner.score_dataframe(df, market={"symbol": "TEST", "volume_24h": 5e6})
    assert result is not None
    assert result["bias"] == "LONG"
    assert result["score"] >= 50
    assert result["symbol"] == "TEST"


def test_score_dataframe_rejects_extended_from_st():
    scanner = SupertrendScanner(
        st_params={
            "period": 10,
            "multiplier": 3.0,
            "ema_filter_period": 50,
            "adx_threshold": 10,
            "min_volume_ratio_pct": 50,
            "max_extension_atr": 0.3,  # very strict
        }
    )
    df = _trending_df(direction="up")
    assert scanner.score_dataframe(df, market={"symbol": "FAR"}) is None


def test_score_dataframe_rejects_chop_below_adx():
    scanner = SupertrendScanner(
        st_params={
            "period": 10,
            "multiplier": 3.0,
            "ema_filter_period": 50,
            "adx_threshold": 80,  # impossible on flat noise
            "min_volume_ratio_pct": 50,
        }
    )
    idx = pd.date_range("2026-01-01", periods=120, freq="15min", tz="UTC")
    close = 100 + np.random.default_rng(0).normal(0, 0.2, 120)
    df = pd.DataFrame(
        {
            "open": close,
            "high": close + 0.3,
            "low": close - 0.3,
            "close": close,
            "volume": np.full(120, 1000.0),
        },
        index=idx,
    )
    assert scanner.score_dataframe(df, market={"symbol": "CHOP"}) is None


def test_filter_candidates_volume_and_oi():
    scanner = SupertrendScanner(min_volume_24h=1_000_000, min_open_interest=500_000)
    data = {
        "GOOD": {
            "symbol": "GOOD",
            "volume_24h": 5_000_000,
            "open_interest": 2_000_000,
            "mark_price": 10,
            "prev_day_px": 9,
            "funding": 0.0,
        },
        "THIN": {
            "symbol": "THIN",
            "volume_24h": 10_000,
            "open_interest": 2_000_000,
            "mark_price": 10,
            "prev_day_px": 9,
            "funding": 0.0,
        },
    }
    out = scanner.filter_candidates(data)
    assert len(out) == 1
    assert out[0]["symbol"] == "GOOD"


def test_scan_whitelist_filters_candidates(monkeypatch):
    scanner = SupertrendScanner(min_volume_24h=1_000_000, min_open_interest=500_000)
    market = {
        "BTC": {
            "symbol": "BTC",
            "volume_24h": 50_000_000,
            "open_interest": 10_000_000,
            "mark_price": 60000,
            "prev_day_px": 59000,
            "funding": 0.0,
        },
        "PUMP": {
            "symbol": "PUMP",
            "volume_24h": 40_000_000,
            "open_interest": 8_000_000,
            "mark_price": 0.002,
            "prev_day_px": 0.0019,
            "funding": 0.0,
        },
    }
    monkeypatch.setattr(scanner, "get_market_data", lambda: market)
    monkeypatch.setattr(
        scanner,
        "analyze_token",
        lambda symbol, market=None: {
            "symbol": symbol,
            "score": 80,
            "bias": "LONG",
            "adx": 30,
            "rsi": 55,
            "current_price": 1.0,
            "volume_24h": 10_000_000,
            "reasons": ["test"],
        },
    )
    results = scanner.scan(top_n=10, whitelist=["BTC", "ETH"], force=True)
    assert len(results) == 1
    assert results[0]["symbol"] == "BTC"
