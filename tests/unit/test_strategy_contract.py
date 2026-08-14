"""Strategy contract ownership — SuperTrend as reference plan."""
from __future__ import annotations

from strategies.supertrend import StrategySupertrend


def test_supertrend_exposes_persona_and_criteria():
    s = StrategySupertrend({"params": {}})
    assert s.get_ai_persona()
    assert "SUPERTREND" in s.get_ai_persona().upper() or "TREND" in s.get_ai_persona().upper()
    assert s.get_ai_validation_criteria()
    assert "SUPERTREND" in s.get_ai_validation_criteria().upper()


def test_supertrend_hard_veto_same_thresholds_as_helper():
    s = StrategySupertrend({"params": {}})
    ctx = {
        "current_price": 100.0,
        "rsi": 50.0,
        "adx": 25.0,
        "volume_ratio": 80.0,
    }
    assert s.check_hard_veto("BUY", ctx) is None
    assert s.check_hard_veto("BUY", {**ctx, "rsi": 85.0}) is not None
    assert s.check_hard_veto("BUY", {**ctx, "volume_ratio": 12.0}) is not None


def test_supertrend_post_ai_adjust_trims_buy_tp():
    s = StrategySupertrend({"params": {}})
    signal = {"signal": "BUY", "price": 100.0, "tp": 110.0, "sl": 99.0}
    ai = {"approved": True, "reasoning": "x", "suggested_adjustments": {}}
    out = s.post_ai_adjust(signal, ai, {"swing_high": 105.0, "swing_low": 90.0})
    assert out["suggested_adjustments"]["tp"] < 105.0
    assert out["suggested_adjustments"]["tp"] > 100.0
