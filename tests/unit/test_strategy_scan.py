"""Strategy-owned scan scoring + ScannerJob merge / interval / armed switch."""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import numpy as np
import pandas as pd

import app.core.scanner_job as scanner_job_mod
from app.core.scanner_job import ScannerJob
from strategies.supertrend import StrategySupertrend
from strategies.trend_lt import StrategyTrendLT


def _ohlcv(n=260, freq="15min", direction="up", start=100.0):
    idx = pd.date_range("2026-01-01", periods=n, freq=freq, tz="UTC")
    base = np.linspace(start, start + 40, n) if direction == "up" else np.linspace(start + 40, start, n)
    noise = np.sin(np.linspace(0, 20, n)) * 0.3
    close = base + noise
    volume = np.full(n, 1000.0)
    volume[-10:] = 2000.0
    return pd.DataFrame(
        {
            "open": close - 0.1,
            "high": close + 0.8,
            "low": close - 0.8,
            "close": close,
            "volume": volume,
        },
        index=idx,
    )


def test_st_score_scan_aligned_uptrend():
    s = StrategySupertrend(
        {
            "params": {
                "period": 10,
                "multiplier": 3.0,
                "ema_filter_period": 50,
                "adx_threshold": 10,
                "min_volume_ratio_pct": 50,
                "max_extension_atr": 50,
            }
        }
    )
    s.name = "supertrend"
    out = s.score_scan_candidate(_ohlcv(direction="up"), symbol="ETH", meta={"volume_24h": 5e6})
    assert out is not None
    assert out["bias"] == "LONG"
    assert out["score"] >= 50
    assert out["timeframe"] == "15m"


def test_st_score_scan_rejects_chop():
    s = StrategySupertrend(
        {"params": {"ema_filter_period": 50, "adx_threshold": 80, "min_volume_ratio_pct": 50}}
    )
    idx = pd.date_range("2026-01-01", periods=120, freq="15min", tz="UTC")
    close = 100 + np.random.default_rng(0).normal(0, 0.2, 120)
    df = pd.DataFrame(
        {
            "open": close,
            "high": close + 0.3,
            "low": close - 0.3,
            "close": close,
            "volume": np.full(120, 1000.0),
        },
        index=idx,
    )
    assert s.score_scan_candidate(df, symbol="CHOP") is None


def test_lt_scan_hooks_and_score_path():
    s = StrategyTrendLT(
        {
            "params": {
                "ema_filter_period": 50,
                "adx_threshold": 10,
                "min_adx_slope": -5.0,
                "min_volume_ratio_pct": 10,
                "max_extension_atr": 50,
                "scan_interval_minutes": 60,
            }
        }
    )
    s.name = "trend_lt"
    assert s.get_scan_timeframe() == "1h"
    assert s.get_scan_interval_minutes() == 60.0
    out = s.score_scan_candidate(
        _ohlcv(n=260, freq="1h", direction="up"), symbol="SUI", meta={"volume_24h": 3e6}
    )
    assert out is not None
    assert out["bias"] == "LONG"
    assert out["timeframe"] == "1h"


def test_lt_veto_is_not_blind_st_copy():
    s = StrategyTrendLT({"params": {"veto_rsi_overbought": 85, "min_volume_ratio_pct": 50}})
    # RSI 82 would veto ST helper (80) but not LT default 85
    assert s.check_hard_veto("BUY", {"current_price": 1.0, "rsi": 82, "adx": 30, "volume_ratio": 80, "macd_hist": 0.01}) is None
    assert s.check_hard_veto("BUY", {"current_price": 1.0, "rsi": 90, "adx": 30, "volume_ratio": 80, "macd_hist": 0.01}) is not None
    assert s.check_hard_veto("BUY", {"current_price": 1.0, "rsi": 50, "adx": 30, "volume_ratio": 10, "macd_hist": 0.01}) is not None


def test_merge_strategy_boards_union_max_score():
    boards = {
        "supertrend": [{"symbol": "ETH", "score": 70, "bias": "LONG"}],
        "trend_lt": [
            {"symbol": "ETH", "score": 88, "bias": "SHORT"},
            {"symbol": "SUI", "score": 75, "bias": "SHORT"},
        ],
    }
    merged = ScannerJob.merge_strategy_boards(boards)
    by_sym = {r["symbol"]: r for r in merged}
    assert set(by_sym) == {"ETH", "SUI"}
    assert by_sym["ETH"]["score"] == 88
    assert set(by_sym["ETH"]["strategies"]) == {"supertrend", "trend_lt"}
    assert by_sym["ETH"]["bias"] == "SHORT"
    assert by_sym["SUI"]["strategies"] == ["trend_lt"]


def test_apply_lane_percentile_scores_preserves_raw():
    boards = {
        "rocket": [
            {"symbol": "A", "score": 70},
            {"symbol": "B", "score": 90},
        ]
    }
    normed = ScannerJob.apply_lane_percentile_scores(boards)
    assert normed["rocket"][0]["raw_score"] == 70
    assert normed["rocket"][1]["raw_score"] == 90
    assert normed["rocket"][1]["score"] >= normed["rocket"][0]["score"]


def test_sticky_armed_bonus_in_scan_score():
    s = StrategySupertrend(
        {
            "params": {
                "period": 10,
                "multiplier": 3.0,
                "ema_filter_period": 50,
                "adx_threshold": 10,
                "min_volume_ratio_pct": 50,
                "max_extension_atr": 50,
            }
        }
    )
    s.name = "supertrend"
    df = _ohlcv(direction="up")
    base = s.score_scan_candidate(df, symbol="ETH", meta={"volume_24h": 5e6})
    armed = s.score_scan_candidate(
        df, symbol="ETH", meta={"volume_24h": 5e6, "sticky_armed": True}
    )
    assert base is not None and armed is not None
    assert armed["score"] > base["score"]
    assert armed["armed"] is True


def test_lane_interval_skip(monkeypatch):
    import time

    job = ScannerJob.__new__(ScannerJob)
    job.bot = SimpleNamespace(add_log=MagicMock())
    time_now = time.time()
    job._lane_last_run = {"supertrend": time_now}
    job.universe = SimpleNamespace(INTER_SYMBOL_SLEEP=0)
    strat = SimpleNamespace(
        get_scan_interval_minutes=lambda: 60.0,
        get_scan_timeframe=lambda: "15m",
        score_scan_candidate=MagicMock(return_value={"symbol": "X", "score": 90}),
    )
    assert job._lane_due("supertrend", strat, time_now + 10, force=False) is False
    assert job._lane_due("supertrend", strat, time_now + 10, force=True) is True
    assert job._lane_due("trend_lt", strat, time_now + 10, force=False) is True


def _job_for_switch(active="ETH", sticky=None, trades=None):
    bot = SimpleNamespace(
        active_symbol=active,
        active_trades=trades or {},
        max_positions=2,
        trade_book=None,
        _strategy_sticky=sticky or {},
        strategy_engine=SimpleNamespace(strategies={}),
        add_log=MagicMock(),
        switch_active_symbol=MagicMock(),
    )
    job = ScannerJob.__new__(ScannerJob)
    job.bot = bot
    return job


def test_armed_hysteresis_any_strategy(monkeypatch):
    monkeypatch.setattr(
        scanner_job_mod,
        "StateManager",
        SimpleNamespace(save_state=MagicMock()),
    )
    monkeypatch.setattr(
        scanner_job_mod,
        "discord_service",
        SimpleNamespace(send_log=MagicMock()),
    )
    sticky = {("trend_lt", "ETH"): {"looking_for_entry": True}}
    job = _job_for_switch(active="ETH", sticky=sticky)
    best = {"symbol": "SUI", "score": 80, "bias": "SHORT", "adx": 25}
    opps = [best, {"symbol": "ETH", "score": 70}]
    # gap 10 < armed hysteresis 35 → keep
    assert job._maybe_auto_switch(best, opps) is None
    job.bot.switch_active_symbol.assert_not_called()


def test_lane_counts_above_min_score():
    boards = {
        "supertrend": [{"symbol": "XRP", "score": 92}, {"symbol": "ADA", "score": 40}],
        "trend_lt": [],
    }
    counts = ScannerJob.lane_counts_above(boards, 65)
    assert counts == {"supertrend": 1, "trend_lt": 0}


def test_strategies_for_analysis_runs_all_when_lane_qualifies():
    """One lane hit → every enabled strategy may analyze the symbol."""
    from app.core.bot import BotContext

    bot = BotContext.__new__(BotContext)
    bot.scanner_settings = {"min_score": 65}
    bot._strategy_sticky = {}
    bot.scanner_job = SimpleNamespace(
        last_results_by_strategy={
            "rocket": [{"symbol": "HYPE", "score": 85}],
            "supertrend": [],
            "trend_lt": [],
        }
    )
    assert bot._strategies_for_analysis("HYPE") is None
    assert bot._strategies_for_analysis("BTC") == set()


def test_strategies_for_analysis_runs_all_when_sticky_armed():
    from app.core.bot import BotContext

    bot = BotContext.__new__(BotContext)
    bot.scanner_settings = {"min_score": 65}
    bot._strategy_sticky = {
        ("trend_lt", "ETH"): {"looking_for_entry": True},
    }
    bot.scanner_job = SimpleNamespace(
        last_results_by_strategy={
            "supertrend": [{"symbol": "SOL", "score": 80}],
            "trend_lt": [],
        }
    )
    assert bot._strategies_for_analysis("ETH") is None
    assert bot._strategies_for_analysis("SOL") is None


def test_strategies_for_analysis_all_when_no_scan_snapshot():
    from app.core.bot import BotContext

    bot = BotContext.__new__(BotContext)
    bot.scanner_settings = {"min_score": 65}
    bot._strategy_sticky = {}
    bot.scanner_job = None
    assert bot._strategies_for_analysis("ETH") is None


def test_analysis_symbols_match_scanner_top_k():
    from app.core.bot import BotContext

    bot = BotContext.__new__(BotContext)
    bot.scanner_settings = {"min_score": 65, "analyze_top_k": 3}
    bot._strategy_sticky = {
        ("range_lt", "SUI"): {"looking_for_entry": True},
    }
    bot.active_symbol = "SUI"
    bot.scanner_job = SimpleNamespace(
        last_results=[
            {"symbol": "SOL", "score": 86},
            {"symbol": "NEAR", "score": 85},
            {"symbol": "XRP", "score": 84},
            {"symbol": "UNI", "score": 82},
        ]
    )
    assert bot._get_analysis_symbols() == ["SOL", "NEAR", "XRP", "SUI"]


def test_analysis_symbols_armed_deduped_when_on_scan():
    from app.core.bot import BotContext

    bot = BotContext.__new__(BotContext)
    bot.scanner_settings = {"min_score": 65, "analyze_top_k": 3}
    bot._strategy_sticky = {
        ("range_lt", "NEAR"): {"looking_for_entry": True},
    }
    bot.scanner_job = SimpleNamespace(
        last_results=[
            {"symbol": "SOL", "score": 86},
            {"symbol": "NEAR", "score": 85},
            {"symbol": "XRP", "score": 84},
        ]
    )
    assert bot._get_analysis_symbols() == ["SOL", "NEAR", "XRP"]


def test_analysis_symbols_fallback_active_when_no_scan():
    from app.core.bot import BotContext

    bot = BotContext.__new__(BotContext)
    bot.scanner_settings = {"min_score": 65, "analyze_top_k": 3}
    bot._strategy_sticky = {}
    bot.active_symbol = "ETH"
    bot.scanner_job = SimpleNamespace(last_results=[])
    assert bot._get_analysis_symbols() == ["ETH"]
