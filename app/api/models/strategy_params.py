"""
Per-strategy Pydantic schemas used to validate POST /api/engine/config/strategy-params.

Rationale:
- The endpoint accepts a flat dict of params to merge into strategies.json.
- Without validation, typos ("min_rrr") or wrong types ("1.5" as str) would be
  silently persisted and only crash at signal generation time.
- These schemas enforce types + plausible ranges and act as living documentation
  of which params each strategy actually consumes.

All fields are Optional: the endpoint performs a PARTIAL update (merge), so a
caller can send only the keys they want to change.

To add a new param to a strategy:
  1. Wire it in the strategy class (via self.get_param(...)).
  2. Add it to the matching schema below with a sensible range.
  3. Add it to data/config/strategies.json and app/core/defaults/strategies.default.json.
"""
from typing import Dict, Optional, Type
from pydantic import BaseModel, Field, ConfigDict


class _StrictParams(BaseModel):
    """Base class: forbid unknown keys to catch typos early."""
    model_config = ConfigDict(extra="forbid")


class ScalpEmaRsiParams(_StrictParams):
    ema_fast: Optional[int] = Field(None, ge=2, le=200)
    ema_slow: Optional[int] = Field(None, ge=3, le=400)
    adx_threshold: Optional[float] = Field(None, ge=0, le=100)
    min_trend_slope: Optional[float] = Field(None, ge=0, le=5)
    rsi_overbought: Optional[float] = Field(None, ge=50, le=100)
    rsi_oversold: Optional[float] = Field(None, ge=0, le=50)
    volume_multiplier: Optional[float] = Field(None, ge=0, le=20)
    sl_atr_mult: Optional[float] = Field(None, gt=0, le=10)
    min_rr: Optional[float] = Field(None, gt=0, le=10)
    allow_longs: Optional[bool] = None
    allow_shorts: Optional[bool] = None


class ElasticReversionParams(_StrictParams):
    ema_period: Optional[int] = Field(None, ge=5, le=200)
    rsi_period: Optional[int] = Field(None, ge=2, le=100)
    extension_pct: Optional[float] = Field(None, gt=0, le=0.5)
    rsi_overbought: Optional[float] = Field(None, ge=50, le=100)
    rsi_oversold: Optional[float] = Field(None, ge=0, le=50)
    sl_lookback: Optional[int] = Field(None, ge=1, le=200)
    sl_buffer_pct: Optional[float] = Field(None, ge=0, le=0.2)
    min_rr: Optional[float] = Field(None, gt=0, le=10)
    adx_max: Optional[float] = Field(None, ge=0, le=100)
    bonus_rsi_short: Optional[float] = Field(None, ge=50, le=100)
    bonus_rsi_long: Optional[float] = Field(None, ge=0, le=50)
    allow_longs: Optional[bool] = None
    allow_shorts: Optional[bool] = None


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
    allow_longs: Optional[bool] = None
    allow_shorts: Optional[bool] = None


class MemeHunterParams(_StrictParams):
    ema_fast: Optional[int] = Field(None, ge=2, le=200)
    ema_slow: Optional[int] = Field(None, ge=3, le=400)
    ema_trend: Optional[int] = Field(None, ge=10, le=500)
    rsi_buy_max: Optional[float] = Field(None, ge=50, le=100)
    rsi_sell_min: Optional[float] = Field(None, ge=0, le=50)
    atr_multiplier: Optional[float] = Field(None, gt=0, le=20)
    min_rr: Optional[float] = Field(None, gt=0, le=10)
    min_slope: Optional[float] = Field(None, ge=0, le=5)
    test_mode: Optional[bool] = None
    allow_longs: Optional[bool] = None
    allow_shorts: Optional[bool] = None


class MemeBreakoutRetestParams(_StrictParams):
    ema_trend: Optional[int] = Field(None, ge=10, le=500)
    rsi_period: Optional[int] = Field(None, ge=2, le=100)
    atr_period: Optional[int] = Field(None, ge=2, le=100)
    breakout_lookback: Optional[int] = Field(None, ge=3, le=500)
    max_breakout_age: Optional[int] = Field(None, ge=1, le=200)
    breakout_buffer: Optional[float] = Field(None, ge=0, le=0.5)
    retest_tolerance: Optional[float] = Field(None, ge=0, le=0.5)
    volume_multiplier: Optional[float] = Field(None, ge=0, le=20)
    sl_atr_mult: Optional[float] = Field(None, gt=0, le=10)
    min_rr: Optional[float] = Field(None, gt=0, le=10)
    rsi_buy_min: Optional[float] = Field(None, ge=0, le=100)
    rsi_buy_max: Optional[float] = Field(None, ge=0, le=100)
    rsi_sell_min: Optional[float] = Field(None, ge=0, le=100)
    rsi_sell_max: Optional[float] = Field(None, ge=0, le=100)
    allow_longs: Optional[bool] = None
    allow_shorts: Optional[bool] = None


class MemeRangeFundingOiParams(_StrictParams):
    range_lookback: Optional[int] = Field(None, ge=5, le=500)
    rsi_period: Optional[int] = Field(None, ge=2, le=100)
    atr_period: Optional[int] = Field(None, ge=2, le=100)
    adx_max: Optional[float] = Field(None, ge=0, le=100)
    upper_zone: Optional[float] = Field(None, ge=0, le=1)
    lower_zone: Optional[float] = Field(None, ge=0, le=1)
    breakout_buffer: Optional[float] = Field(None, ge=0, le=0.2)
    volume_ma_len: Optional[int] = Field(None, ge=5, le=500)
    min_volume_ratio: Optional[float] = Field(None, ge=0, le=10)
    min_funding_short: Optional[float] = Field(None, ge=-1, le=1)
    max_funding_long: Optional[float] = Field(None, ge=-1, le=1)
    min_oi_vs_ma: Optional[float] = Field(None, ge=0, le=100)
    min_oi_change_pct: Optional[float] = Field(None, ge=-100, le=1000)
    rsi_sell_min: Optional[float] = Field(None, ge=0, le=100)
    rsi_buy_max: Optional[float] = Field(None, ge=0, le=100)
    sl_atr_mult: Optional[float] = Field(None, gt=0, le=10)
    min_rr: Optional[float] = Field(None, gt=0, le=10)
    allow_longs: Optional[bool] = None
    allow_shorts: Optional[bool] = None
    execution_type: Optional[str] = Field(None, pattern="^(auto|manual)$")
    requires_confirmation: Optional[bool] = None


STRATEGY_PARAM_SCHEMAS: Dict[str, Type[_StrictParams]] = {
    "scalp_ema_rsi":          ScalpEmaRsiParams,
    "elastic_reversion":      ElasticReversionParams,
    "supertrend":             SupertrendParams,
    "meme_hunter":            MemeHunterParams,
    "meme_breakout_retest":   MemeBreakoutRetestParams,
    "meme_range_funding_oi":  MemeRangeFundingOiParams,
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
