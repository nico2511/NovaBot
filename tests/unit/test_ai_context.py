"""Tests for AI context normalization."""
from app.utils.ai_context import (
    DISCORD_EMBED_DESC_LIMIT,
    format_funding_rate_pct,
    format_signal_discord_description,
    normalize_strategy_context,
)


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


def test_format_signal_discord_description_includes_full_context():
    ctx = {
        "strategy_timeframe": "15m",
        "current_price": 102.71,
        "regime": "RANGE",
        "market_bias": "BULLISH",
        "rsi_val": 52.9,
        "rsi_slope": 0.8,
        "rsi_trend": "↗️ RISING",
        "adx_val": 24.54,
        "adx_slope": -1.1,
        "volume_ratio": 174.8,
        "vol_slope": 209.15,
        "vol_trend": "🔥 SPIKE",
        "ema_20": 102.5191,
        "ema_50": 102.3597,
        "ema_20_slope": 0.00012,
        "ema_50_slope": 0.00008,
        "ema_50_slope_label": "FLAT",
        "macd_line": 0.1132,
        "macd_signal": 0.1412,
        "macd_hist": -0.028,
        "bb_upper": 103.2587,
        "bb_middle": 102.6685,
        "bb_lower": 102.0783,
        "bb_position": "AT_MIDDLE",
        "bb_width": 1.75,
        "swing_high": 103.5,
        "swing_low": 101.8,
        "fib_zone": "MID_ZONE (50-61.8%)",
        "fib_618": 102.9,
        "price_change_pct": 0.12,
        "price_trend": "🟢",
        "open_interest": 1234567,
        "funding_rate": 0.00001,
        "mtf_sentiment": "1h: BULLISH | 4h: BULLISH",
    }
    primary, overflow = format_signal_discord_description(
        symbol="SOL",
        strategy="rocket",
        side="BUY",
        price=102.81,
        sl=102.39876,
        tp=103.22124,
        sig_ts="2026-09-05 15:30:00+00:00",
        market_context=ctx,
        ai_trace_id="6c28c84082",
    )
    assert overflow is None
    assert len(primary) <= DISCORD_EMBED_DESC_LIMIT
    assert "EMA20: 102.5191" in primary
    assert "MACD" in primary
    assert "hist -0.0280" in primary
    assert "mtf_sentiment" not in primary
    assert "1h: BULLISH" in primary
    assert "6c28c84082" in primary
