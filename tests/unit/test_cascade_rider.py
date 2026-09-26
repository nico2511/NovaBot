"""Unit tests for shared rocket/waterfall cascade rider helpers."""
from __future__ import annotations

import numpy as np
import pandas as pd

from strategies.cascade_rider import (
    CASCADE_ENTRY_USE_LIVE,
    DEFAULT_MAX_EXTENSION_ATR,
    active_scan_interval_minutes,
    cascade_age_bars,
    compare_detection_timeframes,
    extension_vs_ema20,
    extension_within_limit,
    minute_entry_decision,
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


def test_cascade_entry_uses_confirmed_bar():
    assert CASCADE_ENTRY_USE_LIVE is False
    assert DEFAULT_MAX_EXTENSION_ATR == 1.5


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


def test_minute_entry_waits_on_red_and_rejects_chase():
    idx = pd.date_range("2024-06-01", periods=5, freq="1min")
    red = pd.DataFrame(
        {
            "open": [10, 10, 10, 10.2, 10.1],
            "high": [10.1, 10.1, 10.1, 10.3, 10.2],
            "low": [9.9, 9.9, 9.9, 10.0, 10.0],
            "close": [10.05, 10.05, 10.05, 10.05, 10.15],
            "volume": [1, 1, 1, 1, 1],
        },
        index=idx,
    )
    # iloc[-2] close 10.05 < open 10.2 → against a long
    status, entry, reason = minute_entry_decision(
        red, side="LONG", confirmed_close=10.0, atr=0.4, max_chase_atr=0.35, require_1m=True
    )
    assert status == "wait" and entry is None and reason

    chased = red.copy()
    chased.loc[chased.index[-2], "open"] = 10.0
    chased.loc[chased.index[-2], "close"] = 10.0 + 2.0 * 0.4
    status, entry, reason = minute_entry_decision(
        chased, side="LONG", confirmed_close=10.0, atr=0.4, max_chase_atr=0.35, require_1m=True
    )
    assert status == "late" and entry is None
    assert "late" in (reason or "").lower()

    ok = chased.copy()
    ok.loc[ok.index[-2], "close"] = 10.05
    status, entry, _reason = minute_entry_decision(
        ok, side="LONG", confirmed_close=10.0, atr=0.4, max_chase_atr=0.35, require_1m=True
    )
    assert status == "enter" and entry == 10.05


def test_active_scan_interval_accelerates_when_armed():
    assert active_scan_interval_minutes(5.0, sticky_armed=True, scan_interval_active_minutes=2.0) == 2.0
    assert active_scan_interval_minutes(5.0, sticky_armed=False, scan_interval_active_minutes=2.0) == 5.0


def test_compare_detection_timeframes_runs_on_synthetic():
    df = _bull_cascade_15m()
    out = compare_detection_timeframes(df, detect_rocket, resample_rule="5min")
    assert out["bars_15m"] == len(df)
    assert out["bars_resampled"] > 0
    assert out["detections_15m_live"] >= 0
