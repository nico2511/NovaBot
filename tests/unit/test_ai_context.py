"""Tests for AI context normalization."""
from app.utils.ai_context import format_funding_rate_pct, normalize_strategy_context


def test_normalize_aliases_and_drops_noise():
    raw = {
        "strategy_timeframe": "1h",
        "current_price": 1.75,
        "regime": "TREND",
        "market_bias": "BULLISH",
        "rsi": 63.1,
        "adx": 47.5,
        "adx_slope": -0.4,
        "volume_ratio": 101.2,
        "price_change_15m": 0.5,
        "recent_closes": [1, 2, 3],
        "atr": 0.02,
        "mtf_sentiment": "1h: bias=BULLISH",
    }
    out = normalize_strategy_context(raw)
    assert out["strategy_timeframe"] == "1h"
    assert out["rsi_val"] == 63.1
    assert out["adx_val"] == 47.5
    assert out["price_change_pct"] == 0.5
    assert "recent_closes" not in out
    assert "atr" not in out


def test_format_funding_rate_pct():
    assert "Longs pay Shorts" in format_funding_rate_pct(0.0000125)
    assert "0.0013" in format_funding_rate_pct(0.0000125)
