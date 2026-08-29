"""
Unit tests for IAService._enforce_hard_constraints.

The hard-constraint layer is the safety net that overrides AI approvals that
violate mechanical rules (currently: minimum Risk:Reward ratio per risk profile).
These tests pin that behavior so a regression cannot silently approve bad R:R.
"""
from __future__ import annotations

import pytest

from app.services.ia import IAService


@pytest.fixture
def ia():
    """Instantiate IAService; OpenRouter key is optional for these pure-logic tests."""
    return IAService()


def test_rejected_ai_result_passes_through_untouched(ia):
    """If AI already rejected, we must not flip anything."""
    signal = {"price": 100.0, "sl": 98.0, "tp": 105.0}
    ai_result = {"approved": False, "reasoning": "low confidence"}

    out = ia._enforce_hard_constraints(signal, ai_result, "Capital Preservation First")
    assert out["approved"] is False
    assert out["reasoning"] == "low confidence"


def test_good_rr_is_preserved(ia):
    """Approved trade with R:R >= min_rr stays approved."""
    # entry=100, sl=98 (risk=2), tp=104 (reward=4) → R:R = 2.0 > 1.5
    signal = {"price": 100.0, "sl": 98.0, "tp": 104.0}
    ai_result = {"approved": True, "confidence": 80, "reasoning": "good setup"}

    out = ia._enforce_hard_constraints(signal, ai_result, "Capital Preservation First")
    assert out["approved"] is True
    assert out.get("rejection_reason_category") is None


def test_bad_rr_is_overridden_to_rejected(ia):
    """Approved trade with R:R < min_rr is flipped to rejected."""
    # entry=100, sl=98 (risk=2), tp=102 (reward=2) → R:R = 1.0 < 1.5
    signal = {"price": 100.0, "sl": 98.0, "tp": 102.0}
    ai_result = {"approved": True, "confidence": 90, "reasoning": "AI thought it was fine"}

    out = ia._enforce_hard_constraints(signal, ai_result, "Capital Preservation First")

    assert out["approved"] is False
    assert out["rejection_reason_category"] == "BAD_RR"
    assert "R:R" in out["reasoning"]
    assert out["risk_score"] == 9


def test_risk_profile_changes_min_rr_threshold(ia):
    """A 1.2 R:R passes 'High Volatility Hunter' (min 1.0) but fails 'Capital Preservation' (min 1.5)."""
    # entry=100, sl=98 (risk=2), tp=102.4 (reward=2.4) → R:R = 1.2
    signal = {"price": 100.0, "sl": 98.0, "tp": 102.4}
    ai_result_a = {"approved": True, "confidence": 70}
    ai_result_b = {"approved": True, "confidence": 70}

    permissive = ia._enforce_hard_constraints(signal, ai_result_a, "High Volatility Hunter")
    strict = ia._enforce_hard_constraints(signal, ai_result_b, "Capital Preservation First")

    assert permissive["approved"] is True
    assert strict["approved"] is False
    assert strict["rejection_reason_category"] == "BAD_RR"


def test_suggested_adjustments_override_signal_levels(ia):
    """If AI proposes its own SL/TP, those are used for the R:R check."""
    # Signal has bad R:R, but AI's suggested SL/TP fix it.
    signal = {"price": 100.0, "sl": 95.0, "tp": 101.0}  # bad R:R = 0.2
    ai_result = {
        "approved": True,
        "confidence": 80,
        "suggested_adjustments": {"sl": 98.0, "tp": 104.0},  # good R:R = 2.0
    }

    out = ia._enforce_hard_constraints(signal, ai_result, "Capital Preservation First")
    assert out["approved"] is True


def test_missing_price_levels_does_not_crash(ia):
    """Robustness: if any level is missing, we return the result as-is."""
    signal = {"price": 0, "sl": 0, "tp": 0}
    ai_result = {"approved": True, "confidence": 80}

    out = ia._enforce_hard_constraints(signal, ai_result, "Capital Preservation First")
    # No crash + approval preserved when we cannot compute R:R
    assert out["approved"] is True


def test_rocket_1r_passes_high_volatility_hunter(ia):
    """Momentum strategies target ~1R; HV Hunter profile must allow it."""
    signal = {"price": 1.7517, "sl": 1.7267, "tp": 1.7767}  # R:R = 1.0
    ai_result = {"approved": True, "confidence": 65, "reasoning": "rocket cascade"}

    out = ia._enforce_hard_constraints(signal, ai_result, "High Volatility Hunter")
    assert out["approved"] is True


def test_rocket_1r_rejected_under_balanced_growth(ia):
    signal = {"price": 1.7517, "sl": 1.7267, "tp": 1.7767}
    ai_result = {"approved": True, "confidence": 65}

    out = ia._enforce_hard_constraints(signal, ai_result, "Balanced Growth")
    assert out["approved"] is False
    assert out["rejection_reason_category"] == "BAD_RR"


def test_unknown_risk_profile_falls_back_to_default(ia):
    """Unknown profiles use 1.5 default min_rr (same as Capital Preservation)."""
    signal = {"price": 100.0, "sl": 98.0, "tp": 102.0}  # R:R = 1.0
    ai_result = {"approved": True, "confidence": 80}

    out = ia._enforce_hard_constraints(signal, ai_result, "NonexistentProfile")
    assert out["approved"] is False  # 1.0 < 1.5 default


def test_weak_volume_is_overridden_to_rejected(ia):
    """Approved trade with volume_ratio < 50% is flipped to WEAK_VOLUME."""
    signal = {"price": 100.0, "sl": 98.0, "tp": 104.0}  # good R:R
    ai_result = {"approved": True, "confidence": 80, "reasoning": "AI ignored thin volume"}
    ctx = {"volume_ratio": 12.9}

    out = ia._enforce_hard_constraints(
        signal, ai_result, "Capital Preservation First", market_context=ctx
    )
    assert out["approved"] is False
    assert out["rejection_reason_category"] == "WEAK_VOLUME"
    assert "Volume" in out["reasoning"]


def test_healthy_volume_preserves_approval(ia):
    signal = {"price": 100.0, "sl": 98.0, "tp": 104.0}
    ai_result = {"approved": True, "confidence": 80, "reasoning": "ok"}
    ctx = {"volume_ratio": 110.0}

    out = ia._enforce_hard_constraints(
        signal, ai_result, "Capital Preservation First", market_context=ctx
    )
    assert out["approved"] is True
    assert out.get("rejection_reason_category") is None


def test_supertrend_trims_tp_above_swing_high(ia):
    """BUY SuperTrend TP beyond swing high is trimmed before R:R check."""
    from strategies.supertrend import StrategySupertrend

    # entry=100, sl=99 (risk=1), mechanical tp=104, swing=102 → trim ~101.949
    # reward after trim ≈ 1.95 → R:R ≈ 1.95 >= 1.5 for Capital Preservation
    signal = {
        "strategy": "supertrend",
        "signal": "BUY",
        "price": 100.0,
        "sl": 99.0,
        "tp": 104.0,
    }
    ai_result = {
        "approved": True,
        "confidence": 70,
        "reasoning": "good trend",
        "suggested_adjustments": {"sl": None, "tp": None},
    }
    ctx = {"swing_high": 102.0, "swing_low": 95.0, "volume_ratio": 120.0}

    out = ia._enforce_hard_constraints(
        signal,
        ai_result,
        "Capital Preservation First",
        market_context=ctx,
        strategy=StrategySupertrend({"params": {}}),
    )
    assert out["approved"] is True
    trimmed = out["suggested_adjustments"]["tp"]
    assert trimmed < 102.0
    assert trimmed > 100.0
    assert "trimmed to structural swing" in out["reasoning"]


def test_supertrend_trim_that_breaks_min_rr_is_rejected(ia):
    """If structural TP trim leaves R:R below profile min, reject BAD_RR."""
    from strategies.supertrend import StrategySupertrend

    # entry=100, sl=98 (risk=2), tp=110, swing=100.5 → trim ~100.45, reward=0.45 → RR=0.225
    signal = {
        "strategy": "supertrend",
        "signal": "BUY",
        "price": 100.0,
        "sl": 98.0,
        "tp": 110.0,
    }
    ai_result = {"approved": True, "confidence": 70, "reasoning": "chase tp"}
    ctx = {"swing_high": 100.5, "swing_low": 90.0, "volume_ratio": 120.0}

    out = ia._enforce_hard_constraints(
        signal,
        ai_result,
        "Capital Preservation First",
        market_context=ctx,
        strategy=StrategySupertrend({"params": {}}),
    )
    assert out["approved"] is False
    assert out["rejection_reason_category"] == "BAD_RR"


def test_rr_epsilon_allows_near_miss_after_trim(ia):
    """Post-trim R:R 1.49 passes Cap Pres 1.5 thanks to strategy rr epsilon."""
    from strategies.supertrend import StrategySupertrend

    # entry=75.995, sl=76.60296, tp≈75.089 → RR≈1.49 (SOL-style)
    entry = 75.995
    sl = 76.60296
    risk = abs(entry - sl)
    tp = entry - 1.49 * risk
    signal = {
        "strategy": "supertrend",
        "signal": "SELL",
        "price": entry,
        "sl": sl,
        "tp": tp,
    }
    ai_result = {
        "approved": True,
        "confidence": 67,
        "reasoning": "ok",
        "suggested_adjustments": {"sl": None, "tp": None},
    }
    ctx = {"volume_ratio": 120.0}

    out = ia._enforce_hard_constraints(
        signal,
        ai_result,
        "Capital Preservation First",
        market_context=ctx,
        strategy=StrategySupertrend({"params": {}}),
    )
    assert out["approved"] is True


def test_pre_ai_geometry_veto_when_trim_breaks_strategy_min_rr():
    """Structural trim that collapses advertised 2.0 R:R must veto before AI."""
    from strategies.supertrend import StrategySupertrend

    s = StrategySupertrend({"params": {"min_rr": 2.0}})
    signal = {
        "strategy": "supertrend",
        "signal": "BUY",
        "price": 100.0,
        "sl": 98.0,
        "tp": 104.0,  # advertised R:R = 2.0
    }
    ctx = {"swing_high": 100.5, "swing_low": 90.0, "volume_ratio": 120.0}

    adjusted, reason = s.pre_ai_geometry_veto(signal, ctx)
    assert reason is not None
    assert "min_rr" in reason
    assert adjusted["tp"] < 101.0  # trimmed toward swing, not the mechanical 104


def test_post_trim_below_min_rr_never_reaches_openrouter(ia):
    """A setup whose post-trim R:R is below strategy min_rr must not call the AI."""
    from unittest.mock import MagicMock

    from strategies.supertrend import StrategySupertrend

    s = StrategySupertrend({"params": {"min_rr": 2.0}})
    signal = {
        "strategy": "supertrend",
        "signal": "BUY",
        "symbol": "SOL",
        "price": 100.0,
        "sl": 98.0,
        "tp": 104.0,
    }
    ctx = {"swing_high": 100.5, "swing_low": 90.0, "volume_ratio": 120.0}

    ia._call_openrouter_api = MagicMock(
        return_value={"raw_output": '{"approved": true, "confidence": 80}'}
    )
    out = ia.validate_signal(signal, ctx, strategy=s)

    ia._call_openrouter_api.assert_not_called()
    assert out["approved"] is False
    assert out["rejection_reason_category"] == "BAD_RR"
    assert "min_rr" in (out.get("reasoning") or "")


def test_valid_post_trim_rr_still_calls_openrouter(ia):
    """When structural TP still meets min_rr, the AI gate is allowed to run."""
    from unittest.mock import MagicMock

    from strategies.supertrend import StrategySupertrend

    s = StrategySupertrend({"params": {"min_rr": 2.0}})
    # risk=1, mechanical tp=102; swing 110 is beyond TP so no trim
    signal = {
        "strategy": "supertrend",
        "signal": "BUY",
        "symbol": "ETH",
        "price": 100.0,
        "sl": 99.0,
        "tp": 102.0,
    }
    ctx = {"swing_high": 110.0, "swing_low": 90.0, "volume_ratio": 120.0}

    ia.client = MagicMock()
    ia._call_openrouter_api = MagicMock(
        return_value={
            "raw_output": (
                '{"approved": true, "confidence": 80, "reasoning": "ok",'
                ' "risk_level": "MEDIUM", "suggested_adjustments": {}}'
            )
        }
    )
    out = ia.validate_signal(signal, ctx, strategy=s)
    ia._call_openrouter_api.assert_called_once()
    assert out.get("rejection_reason_category") != "BAD_RR"
