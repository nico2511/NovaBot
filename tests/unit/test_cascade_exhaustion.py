"""Tests for cascade range exhaustion and wick-trap guards."""
from __future__ import annotations

import numpy as np
import pandas as pd

from strategies.cascade_exhaustion import (
    at_prior_floor,
    check_range_exhaustion_veto,
    clear_breakout_above,
    unbroken_structure_reason,
    wick_trap_reason_long,
    wick_trap_reason_short,
)
from strategies.rocket import StrategyRocket
from strategies.waterfall import StrategyWaterfall
from tests.unit.test_rocket import _bull_1m_confirm, _bull_cascade_15m, _HAPPY_PARAMS
from tests.unit.test_waterfall import _bear_1m_confirm, _bear_cascade_15m, _HAPPY_PARAMS as _WF_HAPPY


def test_range_exhaustion_veto_btc_like_long():
    ctx = {
        "regime": "RANGE",
        "adx_val": 18.12,
        "bb_position": "ABOVE_UPPER",
        "rsi_val": 76.0,
        "volume_ratio": 244.6,
    }
    reason = check_range_exhaustion_veto("BUY", ctx)
    assert reason is not None
    assert "blow-off" in reason.lower() or "range" in reason.lower()


def test_range_exhaustion_allows_trending_extension():
    ctx = {
        "regime": "TREND",
        "adx_val": 18.0,
        "bb_position": "ABOVE_UPPER",
        "rsi_val": 76.0,
    }
    assert check_range_exhaustion_veto("BUY", ctx) is None


def test_range_exhaustion_allows_range_without_extension():
    ctx = {
        "regime": "RANGE",
        "adx_val": 18.0,
        "bb_position": "INSIDE_BANDS",
        "rsi_val": 58.0,
    }
    assert check_range_exhaustion_veto("BUY", ctx) is None


def test_range_exhaustion_veto_waterfall_climax_short():
    ctx = {
        "regime": "RANGE",
        "adx_val": 17.0,
        "bb_position": "BELOW_LOWER",
        "rsi_val": 24.0,
    }
    reason = check_range_exhaustion_veto("SELL", ctx)
    assert reason is not None


def test_wick_trap_long_rejects_spike_wick():
    df = _bull_cascade_15m()
    i = df.index[-1]
    close = float(df.loc[i, "close"])
    df.loc[i, "open"] = close - 0.08
    df.loc[i, "high"] = close + 0.55
    reason = wick_trap_reason_long(df, bar_index=-1)
    assert reason is not None
    assert "wick" in reason.lower()


def test_wick_trap_long_allows_clean_body():
    df = _bull_cascade_15m()
    assert wick_trap_reason_long(df, bar_index=-1) is None


def test_wick_trap_short_rejects_spike_wick():
    df = _bear_cascade_15m()
    i = df.index[-1]
    close = float(df.loc[i, "close"])
    df.loc[i, "open"] = close + 0.08
    df.loc[i, "low"] = close - 0.55
    reason = wick_trap_reason_short(df, bar_index=-1)
    assert reason is not None


def test_clear_breakout_requires_close_not_wick_only():
    assert clear_breakout_above(81234.0, 81000.0, 0.20) is True
    assert clear_breakout_above(81100.0, 81000.0, 0.20) is False


def test_at_prior_floor_noise_pierce_still_at_support():
    # ADA 2026-09-05: 0.20935 vs 0.21000 = 0.31% pierce
    assert at_prior_floor(0.20935, 0.21000, 0.35, 0.60) is True
    assert at_prior_floor(0.20935, 0.21000, 0.35, 0.20) is False


def test_unbroken_structure_blocks_ada_like_support_sell():
    reason = unbroken_structure_reason(
        "SHORT",
        entry=0.20935,
        cascade_close=0.20981,
        prior_level=0.21000,
        proximity_pct=0.35,
        clear_pct=0.60,
        tf_label="15m",
    )
    assert reason is not None
    assert "support" in reason.lower()
    assert "absorption" in reason.lower()


def test_unbroken_structure_allows_clear_15m_breakdown():
    reason = unbroken_structure_reason(
        "SHORT",
        entry=0.20800,
        cascade_close=0.20800,
        prior_level=0.21000,
        proximity_pct=0.35,
        clear_pct=0.60,
        tf_label="15m",
    )
    assert reason is None


def test_rocket_hard_veto_blocks_btc_like_range_blowoff():
    s = StrategyRocket({"params": {}})
    ctx = {
        "regime": "RANGE",
        "adx_val": 18.12,
        "bb_position": "ABOVE_UPPER",
        "rsi_val": 76.0,
        "volume_ratio": 244.6,
        "vol_slope": 176.0,
    }
    reason = s.check_hard_veto("BUY", ctx)
    assert reason is not None
    assert "blow-off" in reason.lower() or "range" in reason.lower()


def test_rocket_generate_signal_rejects_wick_trap():
    s = StrategyRocket({"params": dict(_HAPPY_PARAMS)})
    df_15m = _bull_cascade_15m()
    i = df_15m.index[-1]
    close = float(df_15m.loc[i, "close"])
    df_15m.loc[i, "open"] = close - 0.08
    df_15m.loc[i, "high"] = close + 0.55
    df_1m = _bull_1m_confirm(anchor=close)
    sig = s.generate_signal(df_15m, extra_data={"1m": df_1m})
    assert sig is None
    assert "wick" in (s.last_rejection_reason or "").lower()


def test_waterfall_hard_veto_blocks_range_climax():
    s = StrategyWaterfall({"params": {}})
    ctx = {
        "regime": "RANGE",
        "adx_val": 17.0,
        "bb_position": "BELOW_LOWER",
        "rsi_val": 24.0,
        "volume_ratio": 220.0,
        "vol_slope": 150.0,
    }
    reason = s.check_hard_veto("SELL", ctx)
    assert reason is not None
