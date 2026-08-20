"""
Shared risk-profile library — presets selectable per strategy or as account default.

Account settings provide portfolio ceilings (daily stop, max positions) and a
fallback profile when a strategy does not declare one.
"""
from __future__ import annotations

from typing import Any, Dict, Optional

from app.core.prompts import RISK_PARAMS_MAP

AVAILABLE_RISK_PROFILES = (
    "Capital Preservation First",
    "Balanced Growth",
    "High Volatility Hunter",
)

DEFAULT_RISK_PROFILE = "Capital Preservation First"

# Extended params (leverage / sizing) kept alongside prompts.RISK_PARAMS_MAP.
_PROFILE_EXTENSIONS: Dict[str, Dict[str, float]] = {
    "Capital Preservation First": {"risk_pct": 1.5, "max_leverage": 3},
    "Balanced Growth": {"risk_pct": 3.5, "max_leverage": 5},
    "High Volatility Hunter": {"risk_pct": 7.0, "max_leverage": 10},
}

# Recommended defaults when a strategy omits risk_profile in config.
STRATEGY_DEFAULT_PROFILES: Dict[str, str] = {
    "rocket": "High Volatility Hunter",
    "waterfall": "High Volatility Hunter",
    "supertrend": "Balanced Growth",
    "trend_lt": "Balanced Growth",
    "range_lt": "Capital Preservation First",
}


def normalize_profile_name(name: Optional[str]) -> str:
    """Return a known profile name or the account default."""
    if not name:
        return DEFAULT_RISK_PROFILE
    cleaned = str(name).strip()
    if cleaned in AVAILABLE_RISK_PROFILES:
        return cleaned
    return DEFAULT_RISK_PROFILE


def get_profile_params(profile_name: Optional[str]) -> Dict[str, Any]:
    """Merge prompt constraints with leverage/sizing extensions."""
    name = normalize_profile_name(profile_name)
    base = dict(RISK_PARAMS_MAP.get(name, RISK_PARAMS_MAP[DEFAULT_RISK_PROFILE]))
    ext = _PROFILE_EXTENSIONS.get(name, _PROFILE_EXTENSIONS[DEFAULT_RISK_PROFILE])
    return {**base, **ext, "name": name}


def resolve_strategy_risk_profile(
    strategy_config: Optional[Dict[str, Any]],
    account_default: Optional[str],
    *,
    strategy_key: Optional[str] = None,
) -> str:
    """
    Resolve effective risk profile for a strategy instance.

    Priority: strategy config ``risk_profile`` → known default for strategy key
    → account default → global default.
    """
    cfg = strategy_config or {}
    explicit = cfg.get("risk_profile")
    if explicit and str(explicit).strip():
        return normalize_profile_name(str(explicit).strip())

    if strategy_key and strategy_key in STRATEGY_DEFAULT_PROFILES:
        return STRATEGY_DEFAULT_PROFILES[strategy_key]

    return normalize_profile_name(account_default)


def get_risk_pct(profile_name: Optional[str]) -> float:
    return float(get_profile_params(profile_name).get("risk_pct", 1.5))


def get_max_leverage(profile_name: Optional[str]) -> int:
    return int(get_profile_params(profile_name).get("max_leverage", 3))


def clamp_leverage(profile_leverage: int, account_cap: Optional[int] = None) -> int:
    """Apply optional account-level leverage ceiling."""
    lev = max(1, int(profile_leverage))
    if account_cap is not None and int(account_cap) > 0:
        return min(lev, int(account_cap))
    return lev


def required_ai_confidence(
    risk_level: Optional[str],
    risk_profile: Optional[str],
    *,
    threshold_high: int = 75,
    threshold_medium: int = 55,
    threshold_low: int = 40,
) -> int:
    """
    Post-AI confidence floor before executing an approved signal.

    Balanced / Capital Preservation: keep the classic HIGH/MEDIUM/LOW bars.
    High Volatility Hunter (rocket / waterfall): the model often tags cascade
    setups as HIGH; do not demand the global HIGH bar (75) — use the profile
    min_conf with at most a MEDIUM bump so 65–72% approvals can trade.
    """
    level = str(risk_level or "MEDIUM").strip().upper()
    profile = normalize_profile_name(risk_profile)
    profile_min = int(get_profile_params(profile).get("min_conf", threshold_medium))

    if level == "HIGH":
        level_req = int(threshold_high)
    elif level == "LOW":
        level_req = int(threshold_low)
    else:
        level_req = int(threshold_medium)

    if profile == "High Volatility Hunter":
        if level == "HIGH":
            return max(profile_min, int(threshold_medium))
        if level == "LOW":
            return min(profile_min, int(threshold_low))
        return max(profile_min, int(threshold_medium))

    return level_req
