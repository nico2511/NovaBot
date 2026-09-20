"""Live-trading guards: Isolated liq band and fill-slippage abort."""
from __future__ import annotations

import pytest

from app.core.live_guards import (
    clamp_sl_inside_liquidation,
    entry_slippage_for_symbol,
    fill_slippage_breached,
    theoretical_isolated_liq,
)


def test_majors_use_tighter_slippage():
    assert entry_slippage_for_symbol("BTC") == 0.008
    assert entry_slippage_for_symbol("kPEPE") == 0.015


def test_fill_within_cap_is_ok():
    breached, slip = fill_slippage_breached(100.0, 100.5, 0.008)
    assert breached is False
    assert slip == 0.005


def test_fill_beyond_2x_configured_slip_aborts():
    # 0.8% cfg → abort > 1.6%, but floor is 1.5% so 1.7% aborts
    breached, slip = fill_slippage_breached(100.0, 101.7, 0.008)
    assert breached is True
    assert slip == pytest.approx(0.017)


def test_missing_prices_do_not_abort():
    assert fill_slippage_breached(0, 100, 0.01)[0] is False
    assert fill_slippage_breached(100, 0, 0.01)[0] is False


def test_theoretical_liq_10x_long():
    assert theoretical_isolated_liq(100.0, "BUY", 10) == 90.0


def test_clamp_keeps_tight_sl():
    sl, note = clamp_sl_inside_liquidation(
        side="BUY", entry=100.0, sl=98.0, leverage=10
    )
    assert sl == 98.0
    assert note is None


def test_clamp_pulls_sl_inside_10x_liq():
    # 12% SL on 10x Isolated is past ~10% liq
    sl, note = clamp_sl_inside_liquidation(
        side="BUY", entry=100.0, sl=88.0, leverage=10
    )
    assert note is not None
    # min_sl = 90 + 0.15*10 = 91.5
    assert sl == 91.5


def test_clamp_short_mirrors_long():
    sl, note = clamp_sl_inside_liquidation(
        side="SELL", entry=100.0, sl=112.0, leverage=10
    )
    assert note is not None
    assert sl == pytest.approx(108.5)


def test_wrong_side_sl_rejected():
    sl, note = clamp_sl_inside_liquidation(
        side="BUY", entry=100.0, sl=105.0, leverage=5
    )
    assert sl is None
    assert "wrong side" in (note or "")


def test_missing_sl_rejected():
    sl, note = clamp_sl_inside_liquidation(
        side="BUY", entry=100.0, sl=0, leverage=5
    )
    assert sl is None
    assert "missing SL" in (note or "")


def test_uses_exchange_liq_when_provided():
    sl, note = clamp_sl_inside_liquidation(
        side="BUY",
        entry=100.0,
        sl=50.0,
        leverage=50,
        liquidation_price=80.0,
    )
    # min_sl = 80 + 0.15*20 = 83
    assert sl == 83.0
    assert note is not None
