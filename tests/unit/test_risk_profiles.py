"""Unit tests for per-strategy risk profile resolution."""
from __future__ import annotations

import pytest

from app.core.risk_profiles import (
    AVAILABLE_RISK_PROFILES,
    clamp_leverage,
    get_max_leverage,
    get_profile_params,
    get_risk_pct,
    required_ai_confidence,
    resolve_strategy_risk_profile,
)
from strategies.rocket import StrategyRocket


def test_resolve_explicit_strategy_profile():
    cfg = {"risk_profile": "High Volatility Hunter"}
    assert resolve_strategy_risk_profile(cfg, "Balanced Growth", strategy_key="rocket") == (
        "High Volatility Hunter"
    )


def test_resolve_strategy_key_default_when_missing():
    assert resolve_strategy_risk_profile({}, "Balanced Growth", strategy_key="rocket") == (
        "High Volatility Hunter"
    )
    assert resolve_strategy_risk_profile({}, "Balanced Growth", strategy_key="supertrend") == (
        "Balanced Growth"
    )


def test_resolve_falls_back_to_account_default():
    assert resolve_strategy_risk_profile({}, "Capital Preservation First") == (
        "Capital Preservation First"
    )


def test_profile_params_include_sizing_and_leverage():
    p = get_profile_params("Balanced Growth")
    assert p["min_rr"] == 1.3
    assert p["risk_pct"] == 3.5
    assert p["max_leverage"] == 5


def test_clamp_leverage_respects_account_cap():
    assert clamp_leverage(10, 5) == 5
    assert clamp_leverage(3, 5) == 3


def test_strategy_get_risk_profile_from_config():
    strat = StrategyRocket({"risk_profile": "High Volatility Hunter", "params": {}})
    strat.name = "rocket"
    assert strat.get_risk_profile("Balanced Growth") == "High Volatility Hunter"


def test_all_presets_known():
    for name in AVAILABLE_RISK_PROFILES:
        assert get_risk_pct(name) > 0
        assert get_max_leverage(name) >= 1


def test_hv_hunter_high_risk_does_not_require_global_high_bar():
    """Rocket/waterfall: AI tags HIGH often — 68% must clear the gate."""
    req = required_ai_confidence("HIGH", "High Volatility Hunter")
    assert req == 55
    assert req <= 68


def test_balanced_high_risk_keeps_strict_bar():
    assert required_ai_confidence("HIGH", "Balanced Growth") == 75


def test_hv_hunter_medium_uses_profile_floor():
    assert required_ai_confidence("MEDIUM", "High Volatility Hunter") == 55
