"""MTF + RSI slope hard veto helpers."""
from app.core.veto_checker import (
    check_mtf_sentiment_veto,
    check_rsi_slope_veto,
)


def test_mtf_veto_blocks_buy_on_1h_bearish():
    mtf = (
        "1h: bias=BEARISH ST=BULLISH (MIXED) ADX=24.9 close_vs_ema50=+0.12% | "
        "4h: bias=BULLISH ST=BULLISH (ALIGNED) ADX=30.1 close_vs_ema50=+1.00%"
    )
    reason = check_mtf_sentiment_veto("BUY", mtf)
    assert reason is not None
    assert "1h" in reason.lower()


def test_mtf_veto_blocks_buy_on_1h_mixed_only_when_bias_aligned():
    mtf = (
        "1h: bias=BULLISH ST=BEARISH (MIXED) ADX=20.0 close_vs_ema50=+0.10% | "
        "4h: bias=BULLISH ST=BULLISH (ALIGNED) ADX=28.0 close_vs_ema50=+0.50%"
    )
    reason = check_mtf_sentiment_veto("BUY", mtf)
    assert reason is not None
    assert "MIXED" in reason


def test_mtf_veto_ignores_unavailable():
    assert check_mtf_sentiment_veto("BUY", "Multi-Timeframe Data Unavailable") is None


def test_rsi_slope_veto_blocks_fading_long():
    reason = check_rsi_slope_veto("BUY", {"rsi_slope": -6.8}, min_slope_long=-4.0)
    assert reason is not None
    assert "RSI slope" in reason


def test_trend_lt_hard_veto_eth_like_context():
    from strategies.trend_lt import StrategyTrendLT

    s = StrategyTrendLT({"params": {}})
    ctx = {
        "current_price": 2514.9,
        "rsi": 47.9,
        "rsi_slope": -6.8,
        "adx": 24.9,
        "volume_ratio": 150.0,
        "macd_hist": 0.98,
        "mtf_sentiment": (
            "1h: bias=BEARISH ST=BULLISH (MIXED) ADX=24.9 close_vs_ema50=+0.12% | "
            "4h: bias=BULLISH ST=BULLISH (ALIGNED) ADX=30.1 close_vs_ema50=+1.00%"
        ),
    }
    reason = s.check_hard_veto("BUY", ctx)
    assert reason is not None
    assert "HARD VETO (LT)" in reason
