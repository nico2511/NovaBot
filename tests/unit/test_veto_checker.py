"""
Unit tests for app.core.veto_checker.check_hard_veto.

These tests pin the hard-veto rules (RSI, ADX, Volume) so any regression
in the thresholds or branching is caught immediately. The checker is
stateless, so each test constructs its own market_context dict.
"""
from __future__ import annotations

from app.core.veto_checker import (
    ADX_RUNAWAY,
    LOW_VOLUME_RATIO_PCT,
    RSI_OVERBOUGHT,
    RSI_OVERSOLD,
    check_hard_veto,
)


def _base_context(**overrides) -> dict:
    ctx = {
        "current_price": 100.0,
        "rsi": 50.0,
        "adx": 20.0,
        "current_volume": 1000.0,
        "avg_volume": 1000.0,
    }
    ctx.update(overrides)
    return ctx


def test_no_veto_in_neutral_market():
    assert check_hard_veto("BUY", _base_context()) is None
    assert check_hard_veto("SELL", _base_context()) is None


def test_buy_vetoed_when_rsi_overbought():
    ctx = _base_context(rsi=RSI_OVERBOUGHT + 5)
    reason = check_hard_veto("BUY", ctx)
    assert reason is not None
    assert "Overbought" in reason


def test_sell_vetoed_when_rsi_oversold():
    ctx = _base_context(rsi=RSI_OVERSOLD - 5)
    reason = check_hard_veto("SELL", ctx)
    assert reason is not None
    assert "Oversold" in reason


def test_rsi_at_threshold_is_not_vetoed():
    """Strictly > / < — so equality passes through."""
    assert check_hard_veto("BUY", _base_context(rsi=RSI_OVERBOUGHT)) is None
    assert check_hard_veto("SELL", _base_context(rsi=RSI_OVERSOLD)) is None


def test_buy_is_not_vetoed_by_oversold_rsi():
    """Oversold RSI vetoes SELL but not BUY (it can even favor BUY)."""
    ctx = _base_context(rsi=RSI_OVERSOLD - 5)
    assert check_hard_veto("BUY", ctx) is None


def test_adx_runaway_vetoes_any_side():
    ctx = _base_context(adx=ADX_RUNAWAY + 1)
    assert check_hard_veto("BUY", ctx) is not None
    assert check_hard_veto("SELL", ctx) is not None


def test_low_volume_vetoes_trade():
    # current = 10% of avg → below LOW_VOLUME_RATIO_PCT (20%)
    ctx = _base_context(current_volume=100.0, avg_volume=1000.0)
    reason = check_hard_veto("BUY", ctx)
    assert reason is not None
    assert "Low Volume" in reason


def test_volume_ratio_at_threshold_passes():
    # exactly at threshold (20%) → not vetoed (strict <)
    ctx = _base_context(
        current_volume=LOW_VOLUME_RATIO_PCT * 10,
        avg_volume=1000.0,
    )
    assert check_hard_veto("BUY", ctx) is None


def test_missing_indicators_do_not_crash():
    assert check_hard_veto("BUY", {"current_price": 42.0}) is None
    assert check_hard_veto("BUY", {}) is None


def test_zero_avg_volume_does_not_divide_by_zero():
    ctx = _base_context(current_volume=1000.0, avg_volume=0)
    assert check_hard_veto("BUY", ctx) is None
