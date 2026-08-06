"""
Per-strategy Pydantic schemas used to validate POST /api/engine/config/strategy-params.

All fields are Optional: the endpoint performs a PARTIAL update (merge), so a
caller can send only the keys they want to change.

NovaBot currently runs a single strategy: SuperTrend.
"""
from typing import Dict, Optional, Type
from pydantic import BaseModel, Field, ConfigDict


class _StrictParams(BaseModel):
    """Base class: forbid unknown keys to catch typos early."""
    model_config = ConfigDict(extra="forbid")


class SupertrendParams(_StrictParams):
    period: Optional[int] = Field(None, ge=2, le=100)
    multiplier: Optional[float] = Field(None, gt=0, le=20)
    ema_filter_period: Optional[int] = Field(None, ge=10, le=500)
    adx_threshold: Optional[float] = Field(None, ge=0, le=100)
    min_rr: Optional[float] = Field(None, gt=0, le=10)
    sl_atr_mult: Optional[float] = Field(None, gt=0, le=10)
    trigger_flip_lookback: Optional[int] = Field(None, ge=1, le=100)
    cooldown_minutes: Optional[int] = Field(None, ge=0, le=1440)
    # Anti stop-hunt guard (thin liquidity + neutral RSI)
    min_volume_ratio_pct: Optional[float] = Field(None, ge=0, le=500)
    rsi_neutral_low: Optional[float] = Field(None, ge=0, le=100)
    rsi_neutral_high: Optional[float] = Field(None, ge=0, le=100)
    # Quality filters
    min_adx_slope: Optional[float] = Field(None, ge=-20, le=20)
    max_rsi_long: Optional[float] = Field(None, ge=50, le=100)
    min_rsi_short: Optional[float] = Field(None, ge=0, le=50)
    max_extension_atr: Optional[float] = Field(None, gt=0, le=20)
    min_sl_pct: Optional[float] = Field(None, gt=0, le=20)
    require_pullback: Optional[bool] = None
    pullback_lookback_1m: Optional[int] = Field(None, ge=5, le=240)
    pullback_touch_atr: Optional[float] = Field(None, gt=0, le=10)
    allow_longs: Optional[bool] = None
    allow_shorts: Optional[bool] = None


STRATEGY_PARAM_SCHEMAS: Dict[str, Type[_StrictParams]] = {
    "supertrend": SupertrendParams,
}


def validate_strategy_params(strategy_id: str, params: dict) -> dict:
    """
    Validate an incoming params dict against the matching strategy schema.

    Returns a clean dict containing ONLY the fields the caller explicitly
    provided (no defaults injected), so the endpoint can safely do a
    partial merge into strategies.json.

    Raises:
        KeyError if strategy_id is unknown.
        pydantic.ValidationError if any param is invalid.
    """
    if strategy_id not in STRATEGY_PARAM_SCHEMAS:
        raise KeyError(f"Unknown strategy id: {strategy_id}")
    schema_cls = STRATEGY_PARAM_SCHEMAS[strategy_id]
    model = schema_cls(**(params or {}))
    return model.model_dump(exclude_unset=True, exclude_none=False)
