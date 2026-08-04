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
