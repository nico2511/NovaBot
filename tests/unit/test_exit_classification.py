"""Tests for exchange-sync exit reason classification."""
from app.core.exit_classification import (
    EXIT_STOP_LOSS,
    EXIT_SYNC_UNCLASSIFIED,
    EXIT_TAKE_PROFIT,
    classify_sync_exit_reason,
)


def test_buy_fill_at_tp_is_take_profit():
    assert (
        classify_sync_exit_reason("BUY", 1.31, sl=1.22, tp=1.31) == EXIT_TAKE_PROFIT
    )


def test_buy_fill_above_tp_is_take_profit():
    assert (
        classify_sync_exit_reason("BUY", 1.312, sl=1.22, tp=1.31) == EXIT_TAKE_PROFIT
    )


def test_buy_fill_at_sl_is_stop_loss():
    assert (
        classify_sync_exit_reason("BUY", 1.22, sl=1.22, tp=1.31) == EXIT_STOP_LOSS
    )


def test_buy_be_stop_classified_as_stop_loss():
    # Thesis BE lock: SL raised near entry; fill there is SL not TP.
    assert (
        classify_sync_exit_reason("BUY", 1.268, sl=1.268, tp=1.31) == EXIT_STOP_LOSS
    )


def test_buy_mid_fill_stays_unclassified():
    assert (
        classify_sync_exit_reason("BUY", 1.27, sl=1.22, tp=1.31)
        == EXIT_SYNC_UNCLASSIFIED
    )


def test_sell_fill_at_tp_is_take_profit():
    assert (
        classify_sync_exit_reason("SELL", 9.0, sl=10.5, tp=9.0) == EXIT_TAKE_PROFIT
    )


def test_sell_fill_at_sl_is_stop_loss():
    assert (
        classify_sync_exit_reason("SELL", 10.5, sl=10.5, tp=9.0) == EXIT_STOP_LOSS
    )


def test_missing_levels_stay_unclassified():
    assert classify_sync_exit_reason("BUY", 1.30, sl=0, tp=0) == EXIT_SYNC_UNCLASSIFIED
