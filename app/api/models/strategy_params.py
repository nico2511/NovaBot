"""
Per-strategy Pydantic schemas used to validate POST /api/engine/config/strategy-params.

All fields are Optional: the endpoint performs a PARTIAL update (merge), so a
caller can send only the keys they want to change.

NovaBot currently runs SuperTrend, Trend LT, and Range LT.
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
    trigger_flip_lookback: Optional[int] = Field(None, ge=1, le=240)
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
    require_recent_flip: Optional[bool] = None
    pullback_lookback_1m: Optional[int] = Field(None, ge=5, le=240)
    pullback_touch_atr: Optional[float] = Field(None, gt=0, le=10)
    allow_longs: Optional[bool] = None
    allow_shorts: Optional[bool] = None
    scan_interval_minutes: Optional[float] = Field(None, ge=1, le=1440)


class RangeLtParams(_StrictParams):
    lookback: Optional[int] = Field(None, ge=12, le=200)
    min_touches: Optional[int] = Field(None, ge=1, le=20)
    adx_max: Optional[float] = Field(None, ge=0, le=50)
    max_adx_slope: Optional[float] = Field(None, ge=-20, le=20)
    ema_period: Optional[int] = Field(None, ge=10, le=200)
    ema_slope_flat_max: Optional[float] = Field(None, ge=0, le=0.05)
    min_range_pct: Optional[float] = Field(None, gt=0, le=30)
    max_range_pct: Optional[float] = Field(None, gt=0, le=50)
    touch_atr: Optional[float] = Field(None, gt=0, le=5)
    touch_width_frac: Optional[float] = Field(None, gt=0, le=1)
    edge_frac: Optional[float] = Field(None, gt=0, le=0.5)
    min_rr: Optional[float] = Field(None, gt=0, le=10)
    sl_atr_mult: Optional[float] = Field(None, gt=0, le=10)
    sl_range_frac: Optional[float] = Field(None, gt=0, le=1)
    min_sl_pct: Optional[float] = Field(None, gt=0, le=20)
    cooldown_minutes: Optional[int] = Field(None, ge=0, le=1440)
    min_volume_ratio_pct: Optional[float] = Field(None, ge=0, le=500)
    htf_slope_max: Optional[float] = Field(None, ge=0, le=0.05)
    veto_rsi_long_max: Optional[float] = Field(None, ge=40, le=100)
    veto_rsi_short_min: Optional[float] = Field(None, ge=0, le=60)
    veto_adx_trend: Optional[float] = Field(None, ge=10, le=80)
    log_veto_report: Optional[bool] = None
    allow_longs: Optional[bool] = None
    allow_shorts: Optional[bool] = None
    scan_interval_minutes: Optional[float] = Field(None, ge=1, le=1440)


class WaterfallParams(_StrictParams):
    min_rr: Optional[float] = Field(None, gt=0, le=10)
    sl_atr_mult: Optional[float] = Field(None, gt=0, le=10)
    min_sl_pct: Optional[float] = Field(None, gt=0, le=20)
    sl_swing_lookback: Optional[int] = Field(None, ge=3, le=50)
    min_volume_ratio_pct: Optional[float] = Field(None, ge=0, le=500)
    volume_spike_pct: Optional[float] = Field(None, ge=0, le=500)
    cooldown_minutes: Optional[int] = Field(None, ge=0, le=1440)
    require_1m_confirm: Optional[bool] = None
    veto_rsi_oversold: Optional[float] = Field(None, ge=0, le=40)
    veto_vol_slope_min: Optional[float] = Field(None, ge=-100, le=0)
    floor_proximity_pct: Optional[float] = Field(None, ge=0, le=5)
    breakdown_clear_pct: Optional[float] = Field(None, ge=0, le=5)
    struct_lookback: Optional[int] = Field(None, ge=8, le=500)
    struct_exclude_bars: Optional[int] = Field(None, ge=1, le=20)
    allow_longs: Optional[bool] = None
    allow_shorts: Optional[bool] = None
    scan_interval_minutes: Optional[float] = Field(None, ge=1, le=1440)
    scan_interval_active_minutes: Optional[float] = Field(None, ge=1, le=60)
    scan_score_use_confirmed_bar: Optional[bool] = None
    max_extension_atr: Optional[float] = Field(None, gt=0, le=20)
    extension_ema_period: Optional[int] = Field(None, ge=5, le=50)
    cascade_fresh_bars_max: Optional[int] = Field(None, ge=1, le=20)
    cascade_fresh_bonus: Optional[float] = Field(None, ge=0, le=30)


class RocketParams(_StrictParams):
    min_rr: Optional[float] = Field(None, gt=0, le=10)
    sl_atr_mult: Optional[float] = Field(None, gt=0, le=10)
    min_sl_pct: Optional[float] = Field(None, gt=0, le=20)
    sl_swing_lookback: Optional[int] = Field(None, ge=3, le=50)
    min_volume_ratio_pct: Optional[float] = Field(None, ge=0, le=500)
    volume_spike_pct: Optional[float] = Field(None, ge=0, le=500)
    cooldown_minutes: Optional[int] = Field(None, ge=0, le=1440)
    require_1m_confirm: Optional[bool] = None
    veto_rsi_overbought: Optional[float] = Field(None, ge=60, le=100)
    veto_vol_slope_min: Optional[float] = Field(None, ge=-100, le=0)
    ceiling_proximity_pct: Optional[float] = Field(None, ge=0, le=5)
    breakout_clear_pct: Optional[float] = Field(None, ge=0, le=5)
    struct_lookback: Optional[int] = Field(None, ge=8, le=500)
    struct_exclude_bars: Optional[int] = Field(None, ge=1, le=20)
    allow_longs: Optional[bool] = None
    allow_shorts: Optional[bool] = None
    scan_interval_minutes: Optional[float] = Field(None, ge=1, le=1440)
    scan_interval_active_minutes: Optional[float] = Field(None, ge=1, le=60)
    scan_score_use_confirmed_bar: Optional[bool] = None
    max_extension_atr: Optional[float] = Field(None, gt=0, le=20)
    extension_ema_period: Optional[int] = Field(None, ge=5, le=50)
    cascade_fresh_bars_max: Optional[int] = Field(None, ge=1, le=20)
    cascade_fresh_bonus: Optional[float] = Field(None, ge=0, le=30)


class SparkParams(_StrictParams):
    min_rr: Optional[float] = Field(None, gt=0, le=10)
    sl_atr_mult: Optional[float] = Field(None, gt=0, le=10)
    min_sl_pct: Optional[float] = Field(None, gt=0, le=20)
    sl_swing_lookback: Optional[int] = Field(None, ge=3, le=50)
    min_volume_ratio_pct: Optional[float] = Field(None, ge=0, le=500)
    volume_spike_pct: Optional[float] = Field(None, ge=0, le=500)
    cooldown_minutes: Optional[int] = Field(None, ge=0, le=1440)
    require_1m_confirm: Optional[bool] = None
    veto_rsi_overbought: Optional[float] = Field(None, ge=60, le=100)
    veto_vol_slope_min: Optional[float] = Field(None, ge=-100, le=0)
    ceiling_proximity_pct: Optional[float] = Field(None, ge=0, le=5)
    breakout_clear_pct: Optional[float] = Field(None, ge=0, le=5)
    struct_lookback: Optional[int] = Field(None, ge=8, le=500)
    struct_exclude_bars: Optional[int] = Field(None, ge=1, le=20)
    allow_longs: Optional[bool] = None
    allow_shorts: Optional[bool] = None
    scan_interval_minutes: Optional[float] = Field(None, ge=1, le=1440)
    scan_interval_active_minutes: Optional[float] = Field(None, ge=1, le=60)
    scan_score_use_confirmed_bar: Optional[bool] = None
    max_extension_atr: Optional[float] = Field(None, gt=0, le=20)
    extension_ema_period: Optional[int] = Field(None, ge=5, le=50)
    cascade_fresh_bars_max: Optional[int] = Field(None, ge=1, le=20)
    cascade_fresh_bonus: Optional[float] = Field(None, ge=0, le=30)


class EmberParams(_StrictParams):
    min_rr: Optional[float] = Field(None, gt=0, le=10)
    sl_atr_mult: Optional[float] = Field(None, gt=0, le=10)
    min_sl_pct: Optional[float] = Field(None, gt=0, le=20)
    sl_swing_lookback: Optional[int] = Field(None, ge=3, le=50)
    min_volume_ratio_pct: Optional[float] = Field(None, ge=0, le=500)
    volume_spike_pct: Optional[float] = Field(None, ge=0, le=500)
    cooldown_minutes: Optional[int] = Field(None, ge=0, le=1440)
    require_1m_confirm: Optional[bool] = None
    veto_rsi_oversold: Optional[float] = Field(None, ge=0, le=40)
    veto_vol_slope_min: Optional[float] = Field(None, ge=-100, le=0)
    floor_proximity_pct: Optional[float] = Field(None, ge=0, le=5)
    breakdown_clear_pct: Optional[float] = Field(None, ge=0, le=5)
    struct_lookback: Optional[int] = Field(None, ge=8, le=500)
    struct_exclude_bars: Optional[int] = Field(None, ge=1, le=20)
    allow_longs: Optional[bool] = None
    allow_shorts: Optional[bool] = None
    scan_interval_minutes: Optional[float] = Field(None, ge=1, le=1440)
    scan_interval_active_minutes: Optional[float] = Field(None, ge=1, le=60)
    scan_score_use_confirmed_bar: Optional[bool] = None
    max_extension_atr: Optional[float] = Field(None, gt=0, le=20)
    extension_ema_period: Optional[int] = Field(None, ge=5, le=50)
    cascade_fresh_bars_max: Optional[int] = Field(None, ge=1, le=20)
    cascade_fresh_bonus: Optional[float] = Field(None, ge=0, le=30)


STRATEGY_PARAM_SCHEMAS: Dict[str, Type[_StrictParams]] = {
    "supertrend": SupertrendParams,
    "range_lt": RangeLtParams,
    "waterfall": WaterfallParams,
    "rocket": RocketParams,
    "spark": SparkParams,
    "ember": EmberParams,
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
