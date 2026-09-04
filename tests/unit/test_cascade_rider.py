"""Unit tests for shared rocket/waterfall cascade rider helpers."""
from __future__ import annotations

import numpy as np
import pandas as pd

from strategies.cascade_rider import (
    active_scan_interval_minutes,
    cascade_age_bars,
    compare_detection_timeframes,
    extension_vs_ema20,
    extension_within_limit,
)
from strategies.rocket import detect_rocket
from tests.unit.test_rocket import _bull_cascade_15m


def _series_with_extension(ext_atr: float = 3.0) -> pd.DataFrame:
    df = _bull_cascade_15m()
    from strategies.rocket import StrategyRocket

    work = StrategyRocket({"params": {}}).add_indicators(df)
    atr = float(work["ATR_14"].iloc[-1])
    ema9 = float(work["EMA_9"].iloc[-1])
    work.loc[work.index[-1], "close"] = ema9 + ext_atr * atr
    work.loc[work.index[-1], "open"] = ema9 + (ext_atr - 0.2) * atr
    work.loc[work.index[-1], "high"] = work["close"].iloc[-1] + 0.01
    return work


def test_extension_vs_ema20_positive_for_long():
    work = _series_with_extension(2.0)
    ext = extension_vs_ema20(work, "LONG", use_live=True)
    assert ext is not None
    assert ext >= 1.5


def test_extension_within_limit_blocks_late_entry():
    work = _series_with_extension(3.0)
    ok, ext = extension_within_limit(work, "LONG", 1.5, use_live=True)
    assert ok is False
    assert ext is not None and ext > 1.5


def test_cascade_age_counts_green_streak():
    work = _series_with_extension(0.5)
    age = cascade_age_bars(work, "LONG", use_live=True)
    assert age >= 2


def test_active_scan_interval_accelerates_when_armed():
    assert active_scan_interval_minutes(5.0, sticky_armed=True, scan_interval_active_minutes=2.0) == 2.0
    assert active_scan_interval_minutes(5.0, sticky_armed=False, scan_interval_active_minutes=2.0) == 5.0


def test_compare_detection_timeframes_runs_on_synthetic():
    df = _bull_cascade_15m()
    out = compare_detection_timeframes(df, detect_rocket, resample_rule="5min")
    assert out["bars_15m"] == len(df)
    assert out["bars_resampled"] > 0
    assert out["detections_15m_live"] >= 0
