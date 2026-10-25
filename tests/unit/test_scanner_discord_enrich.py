"""Scanner Discord alert enrichment (price, vol24h, ADX)."""

from __future__ import annotations

import pandas as pd

from app.core.scanner_job import ScannerJob


def _sample_ohlcv(n: int = 60) -> pd.DataFrame:
    import numpy as np

    idx = pd.date_range("2024-01-01", periods=n, freq="15min", tz="UTC")
    close = 100.0 + np.linspace(0, 5, n)
    return pd.DataFrame(
        {
            "open": close - 0.5,
            "high": close + 1.0,
            "low": close - 1.0,
            "close": close,
            "volume": np.full(n, 1000.0),
        },
        index=idx,
    )


def test_enrich_scan_opp_fills_price_volume_and_adx():
    opp = {"score": 85, "reasons": ["test"]}
    universe_row = {"mark_price": 83.78, "volume_24h": 1_500_000_000.0}
    df = _sample_ohlcv()

    enriched = ScannerJob._enrich_scan_opp(
        opp,
        symbol="HYPE",
        strategy_name="ember",
        universe_row=universe_row,
        df=df,
    )

    assert enriched["symbol"] == "HYPE"
    assert enriched["strategy"] == "ember"
    assert enriched["current_price"] == 83.78
    assert enriched["volume_24h"] == 1_500_000_000.0
    assert enriched["adx"] > 0
    assert enriched["score"] == 85


def test_enrich_scan_opp_preserves_existing_adx():
    opp = {"score": 70, "adx": 42.5, "current_price": 50.0}
    enriched = ScannerJob._enrich_scan_opp(
        opp,
        symbol="BTC",
        strategy_name="spark",
        universe_row={"mark_price": 99.0, "volume_24h": 0},
        df=_sample_ohlcv(),
    )
    assert enriched["adx"] == 42.5
    assert enriched["current_price"] == 50.0


def test_enrich_scan_opp_sets_timeframe_from_lane():
    opp = {"score": 80, "bias": "LONG"}
    enriched = ScannerJob._enrich_scan_opp(
        opp,
        symbol="ETH",
        strategy_name="a3_ema_trend_4h",
        universe_row={"mark_price": 3000.0, "volume_24h": 1e9},
        df=_sample_ohlcv(),
        scan_timeframe="4h",
    )
    assert enriched["timeframe"] == "4h"


def test_discord_block_a3_style_hides_rsi_and_uses_proximity_label():
    opp = {
        "symbol": "BTC",
        "bias": "LONG",
        "strategy": "a3_ema_trend_4h",
        "timeframe": "4h",
        "score": 72,
        "score_label": "Proximité croisement",
        "adx": 28.3,
        "current_price": 95000.0,
        "volume_24h": 2_000_000_000.0,
        "reasons": ["EMA20 vs EMA100 spread 1.00×ATR"],
    }
    block = ScannerJob._format_scan_opp_discord_block(1, opp)
    assert "[a3_ema_trend_4h / 4h]" in block
    assert "Proximité croisement: **72**" in block
    assert "ADX 28.3" in block
    assert "RSI" not in block
    assert "/ ?" not in block


def test_discord_block_default_score_label_and_optional_indicators():
    opp = {
        "symbol": "HYPE",
        "bias": "SHORT",
        "strategy": "ember",
        "score": 85,
        "rsi": 61.0,
        "current_price": 83.78,
        "volume_24h": 1_500_000_000.0,
        "reasons": ["test"],
    }
    block = ScannerJob._format_scan_opp_discord_block(1, opp)
    assert "[ember]" in block
    assert " / " not in block.split("\n")[0]
    assert "Score: **85**" in block
    assert "RSI 61" in block
    assert "ADX" not in block


def test_scan_metric_for_display_rejects_missing_and_zero():
    assert ScannerJob._scan_metric_for_display({}, "rsi") is None
    assert ScannerJob._scan_metric_for_display({"rsi": 0}, "rsi") is None
    assert ScannerJob._scan_metric_for_display({"rsi": 55.2}, "rsi") == 55.2
