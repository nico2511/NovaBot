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
