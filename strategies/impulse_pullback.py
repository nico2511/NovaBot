"""
Impulse pullback — mirrored long/short entry that does not wait for a 15m cascade.

Arm when a confirmed 1m bar breaks the prior swing (long: swing high, short:
swing low). Fill only the first pullback that retests that level and holds.
Invalidate when the break is already extended (~0.35 ATR), when price sits in
the last quintile of a real 5m/15m move, or when 5m/15m RSI is exhausted.

Rocket and waterfall stay the cascade baseline. This plan is off unless
``impulse_pullback`` is enabled in strategies.json.
"""
from __future__ import annotations

from typing import Any, Dict, Optional, Tuple

import numpy as np
import pandas as pd

from strategies.base import BaseStrategy
from strategies.cascade_rider import active_scan_interval_minutes, thesis_confirmed_rows

ACTION_IDLE = "idle"
ACTION_ARM = "arm"
ACTION_WAIT = "wait"
ACTION_FILL = "fill"
ACTION_INVALID = "invalid"

_EMPTY = {
    "action": ACTION_IDLE,
    "side": None,
    "reason": "",
    "break_level": None,
    "pullback_extreme": None,
    "atr": None,
    "fill_price": None,
}


def _finite(value: Any) -> Optional[float]:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    if out != out:
        return None
    return out


def wilder_atr(high: np.ndarray, low: np.ndarray, close: np.ndarray, length: int = 14) -> np.ndarray:
    """Wilder ATR. NaN until ``length`` bars exist."""
    n = len(close)
    out = np.full(n, np.nan, dtype=float)
    if n == 0:
        return out
    prev = np.empty(n, dtype=float)
    prev[0] = close[0]
    if n > 1:
        prev[1:] = close[:-1]
    tr = np.maximum(high - low, np.maximum(np.abs(high - prev), np.abs(low - prev)))
    if n < length:
        return out
    out[length - 1] = float(np.mean(tr[:length]))
    for i in range(length, n):
        out[i] = (out[i - 1] * (length - 1) + tr[i]) / length
    return out


def wilder_rsi(close: np.ndarray, length: int = 14) -> np.ndarray:
    n = len(close)
    out = np.full(n, np.nan, dtype=float)
    if n <= length:
        return out
    delta = np.diff(close)
    gain = np.where(delta > 0, delta, 0.0)
    loss = np.where(delta < 0, -delta, 0.0)
    avg_gain = float(np.mean(gain[:length]))
    avg_loss = float(np.mean(loss[:length]))
    def _rsi(ag: float, al: float) -> float:
        if al <= 1e-12:
            return 100.0 if ag > 0 else 50.0
        rs = ag / al
        return 100.0 - (100.0 / (1.0 + rs))
    out[length] = _rsi(avg_gain, avg_loss)
    for i in range(length, len(delta)):
        avg_gain = (avg_gain * (length - 1) + gain[i]) / length
        avg_loss = (avg_loss * (length - 1) + loss[i]) / length
        out[i + 1] = _rsi(avg_gain, avg_loss)
    return out


def resample_closed_ohlcv(df_1m: pd.DataFrame, minutes: int) -> pd.DataFrame:
    """Higher-TF bars built only from 1m bars that have already closed."""
    if df_1m is None or getattr(df_1m, "empty", True) or len(df_1m) < int(minutes) + 2:
        return pd.DataFrame(columns=["open", "high", "low", "close", "volume"])
    asof = df_1m.index[-1]
    closed = df_1m.iloc[:-1]
    rule = f"{int(minutes)}min"
    grouped = closed.resample(rule, label="left", closed="left").agg(
        open=("open", "first"),
        high=("high", "max"),
        low=("low", "min"),
        close=("close", "last"),
        volume=("volume", "sum"),
    )
    grouped = grouped.dropna(subset=["close"])
    if grouped.empty:
        return grouped
    complete = grouped.index + pd.Timedelta(minutes=int(minutes)) <= asof
    return grouped.loc[complete]


def _confirmed_frame(df: Optional[pd.DataFrame]) -> Optional[pd.DataFrame]:
    """Drop the forming row on an exchange timeframe (slice_asof keeps it)."""
    if df is None or getattr(df, "empty", True) or len(df) < 3:
        return None
    return df.iloc[:-1]


def move_position(
    high: np.ndarray,
    low: np.ndarray,
    price: float,
    side: str,
    lookback: int,
    *,
    min_range_atr: float,
    atr: float,
) -> Optional[float]:
    """
    Where ``price`` sits inside the recent higher-TF range, in the trade direction.

    1.0 is the extreme (long: the high, short: the low). None when the range is
    too small to call a move.
    """
    n = len(high)
    if n < 2 or not np.isfinite(price):
        return None
    span_n = max(2, int(lookback))
    sl = max(0, n - span_n)
    hi = float(np.nanmax(high[sl:]))
    lo = float(np.nanmin(low[sl:]))
    width = hi - lo
    if not np.isfinite(width) or width <= 0:
        return None
    if np.isfinite(atr) and atr > 0 and width < float(min_range_atr) * float(atr):
        return None
    if side == "LONG":
        return (float(price) - lo) / width
    return (hi - float(price)) / width


def _swing_levels(high: np.ndarray, low: np.ndarray, lookback: int) -> Tuple[np.ndarray, np.ndarray]:
    """Prior-window swing high/low. Index i excludes bar i."""
    n = len(high)
    swing_high = np.full(n, np.nan)
    swing_low = np.full(n, np.nan)
    if lookback < 2 or n <= lookback:
        return swing_high, swing_low
    # Rolling max of the previous `lookback` bars.
    h = pd.Series(high)
    l = pd.Series(low)
    swing_high[:] = h.shift(1).rolling(lookback).max().to_numpy()
    swing_low[:] = l.shift(1).rolling(lookback).min().to_numpy()
    return swing_high, swing_low


def evaluate_impulse_window(
    df_1m: pd.DataFrame,
    *,
    params: Dict[str, Any],
    armed_side: Optional[str] = None,
    df_5m: Optional[pd.DataFrame] = None,
    df_15m: Optional[pd.DataFrame] = None,
) -> Dict[str, Any]:
    """
    Causal read of the last *closed* 1m bar.

    ``df_1m`` includes the forming bar at iloc[-1]. ``armed_side`` is LONG/SHORT
    when a previous call already armed, else None (only the last bar can arm).
    """
    if df_1m is None or getattr(df_1m, "empty", True) or len(df_1m) < 4:
        return {**_EMPTY, "reason": "not enough 1m bars"}

    closed = df_1m.iloc[:-1]
    high = closed["high"].to_numpy(dtype=float)
    low = closed["low"].to_numpy(dtype=float)
    close = closed["close"].to_numpy(dtype=float)
    open_ = closed["open"].to_numpy(dtype=float)
    n = len(close)
    lookback = max(2, int(params.get("swing_lookback") or 20))
    max_bars = max(2, int(params.get("pullback_max_bars") or 15))
    min_break = float(params.get("min_break_atr") or 0.02)
    max_chase = float(params.get("max_chase_atr") or 0.35)
    touch = float(params.get("pullback_touch_atr") or 0.20)
    quintile = float(params.get("quintile_cut") or 0.80)
    min_range = float(params.get("exhaustion_min_range_atr") or 1.5)
    look_5 = int(params.get("move_lookback_5m") or 12)
    look_15 = int(params.get("move_lookback_15m") or 8)
    rsi_long = float(params.get("veto_rsi_long") or 78.0)
    rsi_short = float(params.get("veto_rsi_short") or 22.0)
    allow_longs = bool(params.get("allow_longs", True))
    allow_shorts = bool(params.get("allow_shorts", True))

    need = lookback + 16
    if n < need:
        return {**_EMPTY, "reason": "not enough 1m history for a swing break"}

    atr = wilder_atr(high, low, close, 14)
    swing_high, swing_low = _swing_levels(high, low, lookback)
    price = float(close[-1])
    exhaust_cache: Dict[str, Any] = {}

    def _exhaust() -> Tuple[Optional[str], str]:
        if "value" not in exhaust_cache:
            exhaust_cache["value"] = _exhaustion(
                price,
                df_5m=df_5m,
                df_15m=df_15m,
                df_1m=df_1m,
                quintile=quintile,
                min_range_atr=min_range,
                look_5=look_5,
                look_15=look_15,
                rsi_long=rsi_long,
                rsi_short=rsi_short,
            )
        return exhaust_cache["value"]

    def _side_blocked(side: str) -> Optional[str]:
        flag, reason = _exhaust()
        if flag in (side, "BOTH"):
            return reason or f"{side.lower()} exhaustion"
        return None

    def _break_side(i: int) -> Optional[str]:
        atr_i = atr[i]
        if not np.isfinite(atr_i) or atr_i <= 0:
            return None
        if allow_longs and np.isfinite(swing_high[i]) and close[i] > open_[i]:
            dist = (close[i] - swing_high[i]) / atr_i
            if min_break <= dist <= max_chase:
                return "LONG"
        if allow_shorts and np.isfinite(swing_low[i]) and close[i] < open_[i]:
            dist = (swing_low[i] - close[i]) / atr_i
            if min_break <= dist <= max_chase:
                return "SHORT"
        return None

    def _chase_side(i: int) -> Optional[str]:
        """Directional close already more than max_chase ATR through the swing."""
        atr_i = atr[i]
        if not np.isfinite(atr_i) or atr_i <= 0:
            return None
        if allow_longs and np.isfinite(swing_high[i]) and close[i] > open_[i]:
            dist = (close[i] - swing_high[i]) / atr_i
            if dist > max_chase:
                return "LONG"
        if allow_shorts and np.isfinite(swing_low[i]) and close[i] < open_[i]:
            dist = (swing_low[i] - close[i]) / atr_i
            if dist > max_chase:
                return "SHORT"
        return None

    def _pack(action: str, side: Optional[str], reason: str, level: Optional[float], extreme: Optional[float], atr_v: Optional[float], fill: Optional[float]) -> Dict[str, Any]:
        return {
            "action": action,
            "side": side,
            "reason": reason,
            "break_level": level,
            "pullback_extreme": extreme,
            "atr": atr_v,
            "fill_price": fill,
        }

    locked = str(armed_side or "").upper() or None
    if locked not in ("LONG", "SHORT"):
        locked = None

    if locked is None:
        side = _break_side(n - 1)
        if side is None:
            chase_side = _chase_side(n - 1)
            if chase_side is not None:
                return _pack(
                    ACTION_INVALID,
                    chase_side,
                    "chase from break exceeds max ATR",
                    None,
                    None,
                    float(atr[n - 1]) if np.isfinite(atr[n - 1]) else None,
                    None,
                )
            return _pack(ACTION_IDLE, None, "no 1m impulse break", None, None, None, None)
        blocked = _side_blocked(side)
        if blocked:
            return _pack(ACTION_INVALID, side, blocked, None, None, None, None)
        level = float(swing_high[n - 1] if side == "LONG" else swing_low[n - 1])
        return _pack(
            ACTION_ARM,
            side,
            f"armed {side.lower()} break {level:.6g}",
            level,
            None,
            float(atr[n - 1]),
            None,
        )

    # Armed: replay the recent window so the break level is recovered from OHLCV
    # (sticky state only stores the direction).
    start = max(lookback, n - 1 - max_bars)
    arm_i: Optional[int] = None
    level: Optional[float] = None
    for i in range(start, n):
        if arm_i is None:
            if _break_side(i) == locked:
                arm_i = i
                level = float(swing_high[i] if locked == "LONG" else swing_low[i])
            continue
        assert level is not None
        atr_i = atr[i]
        if not np.isfinite(atr_i) or atr_i <= 0:
            continue
        if i == arm_i:
            continue
        if locked == "LONG":
            close_ext = (close[i] - level) / atr_i
            tagged = low[i] <= level + touch * atr_i and close[i] >= level and close_ext <= max_chase
            failed = close[i] < level
        else:
            close_ext = (level - close[i]) / atr_i
            tagged = high[i] >= level - touch * atr_i and close[i] <= level and close_ext <= max_chase
            failed = close[i] > level
        chased = close_ext > max_chase
        if tagged:
            if i == n - 1:
                blocked = _side_blocked(locked)
                if blocked:
                    return _pack(ACTION_INVALID, locked, blocked, level, None, float(atr_i), None)
                extreme = float(low[i] if locked == "LONG" else high[i])
                return _pack(
                    ACTION_FILL,
                    locked,
                    f"first pullback hold {close[i]:.6g}",
                    level,
                    extreme,
                    float(atr_i),
                    float(close[i]),
                )
            arm_i = None
            level = None
            continue
        if chased or failed or (i - arm_i) > max_bars:
            if i == n - 1:
                why = "chase from break" if chased else ("break failed" if failed else "pullback window expired")
                return _pack(ACTION_INVALID, locked, why, level, None, float(atr_i), None)
            arm_i = None
            level = None
            continue
    if arm_i is None or level is None:
        return _pack(ACTION_INVALID, locked, "impulse arm expired", None, None, None, None)
    blocked = _side_blocked(locked)
    if blocked:
        return _pack(ACTION_INVALID, locked, blocked, level, None, float(atr[n - 1]), None)
    return _pack(ACTION_WAIT, locked, "armed — waiting for the first pullback", level, None, float(atr[arm_i]), None)


def _exhaustion(
    price: float,
    *,
    df_5m: Optional[pd.DataFrame],
    df_15m: Optional[pd.DataFrame],
    df_1m: pd.DataFrame,
    quintile: float,
    min_range_atr: float,
    look_5: int,
    look_15: int,
    rsi_long: float,
    rsi_short: float,
) -> Tuple[Optional[str], str]:
    """
    Return ('LONG'|'SHORT'|None, reason).

    LONG means a long is exhausted. SHORT means a short is exhausted.
    A bar can be both when each side's RSI is extreme (unusual).
    """
    frame_5 = _confirmed_frame(df_5m)
    if frame_5 is None:
        frame_5 = resample_closed_ohlcv(df_1m, 5)
        if frame_5 is None or getattr(frame_5, "empty", True):
            frame_5 = None
    frame_15 = _confirmed_frame(df_15m)
    if frame_15 is None:
        built = resample_closed_ohlcv(df_1m, 15)
        frame_15 = built if built is not None and not getattr(built, "empty", True) else None

    long_hit = False
    short_hit = False
    reason = ""

    def _apply(frame: Optional[pd.DataFrame], lookback: int, label: str) -> None:
        nonlocal long_hit, short_hit, reason
        if frame is None or len(frame) < 8:
            return
        high = frame["high"].to_numpy(dtype=float)
        low = frame["low"].to_numpy(dtype=float)
        close = frame["close"].to_numpy(dtype=float)
        atr = wilder_atr(high, low, close, 14)
        atr_now = float(atr[-1]) if np.isfinite(atr[-1]) else float("nan")
        pos_long = move_position(
            high, low, price, "LONG", lookback, min_range_atr=min_range_atr, atr=atr_now
        )
        pos_short = move_position(
            high, low, price, "SHORT", lookback, min_range_atr=min_range_atr, atr=atr_now
        )
        if pos_long is not None and pos_long >= quintile:
            long_hit = True
            reason = f"{label} move last quintile ({pos_long:.2f} >= {quintile:.2f})"
        if pos_short is not None and pos_short >= quintile:
            short_hit = True
            reason = f"{label} move last quintile ({pos_short:.2f} >= {quintile:.2f})"
        rsi = wilder_rsi(close, 14)
        rsi_now = float(rsi[-1]) if np.isfinite(rsi[-1]) else None
        if rsi_now is not None and rsi_now >= rsi_long:
            long_hit = True
            reason = f"{label} RSI {rsi_now:.1f} >= {rsi_long:.0f}"
        if rsi_now is not None and rsi_now <= rsi_short:
            short_hit = True
            reason = f"{label} RSI {rsi_now:.1f} <= {rsi_short:.0f}"

    _apply(frame_5, look_5, "5m")
    _apply(frame_15, look_15, "15m")
    if long_hit and short_hit:
        return "BOTH", reason
    if long_hit:
        return "LONG", reason
    if short_hit:
        return "SHORT", reason
    return None, ""


class StrategyImpulsePullback(BaseStrategy):
    """
    Mirrored impulse-pullback plan.

    Scan ranks a 5m impulse context. The 1m arm and the pullback fill live in
    generate_signal, after a symbol is focused.
    """

    AI_PERSONA = """
    CODENAME: "IMPULSE PULLBACK"

    ROLE:
    You validate a pullback entry after a 1m structure break. Long and short are
    mirrors. This is not a 15m cascade rider and not a chase of an extended bar.

    PRIME DIRECTIVE:
    Approve only when the strategy filled the first retest of a fresh break and
    the stop sits beyond that pullback extreme. Reject late fills.

    RULES OF ENGAGEMENT:
    1. BUY and SELL are both valid — match the signal side.
    2. APPROVE when the pullback held the broken level and R:R meets the profile minimum.
    3. REJECT if price is already in the last quintile of the recent 5m or 15m move.
    4. REJECT if the fill is more than ~0.35 ATR past the break (chase).
    5. REJECT extreme RSI (blow-off long / capitulation short).
    6. REJECT if volume has collapsed and there is no participation left.
    7. Do NOT require a closed 15m cascade (double candle + EMA stack) before entry.
    8. When the retest already failed or the arm expired, REJECT — do not rubber-stamp.
    """

    AI_VALIDATION_CRITERIA = """=== VALIDATION CRITERIA (IMPULSE PULLBACK) ===
The strategy already armed on a 1m swing break and filled the first pullback.

APPROVE when ALL of:
1. Signal is BUY or SELL matching the break direction
2. Entry is a retest of the broken swing, not an extension chase
3. Stop is beyond the pullback extreme (below the pullback low on BUY, above the pullback high on SELL)
4. R:R meets the capital risk-profile minimum
5. Price is not in the last quintile of the recent 5m/15m move and RSI is not exhausted

REJECT when ANY of:
- Fill is already > ~0.35 ATR past the break
- 5m or 15m location is the last quintile of a real move, or RSI is extreme
- Pullback did not hold the broken level
- volume_ratio is below the strategy floor when volume is known
- Computed R:R below profile minimum (BAD_RR)

Do NOT reject solely because:
- The 15m cascade (EMA9/EMA20 + double candle) is not confirmed yet
- The entry waited for a pullback (that wait is the plan)
"""

    def __init__(self, config=None):
        super().__init__(config)
        self.looking_for_entry = False
        self.entry_direction = None
        self._last_entry_time = None
        self._last_signal_bar = None

    def get_ai_validation_criteria(self) -> Optional[str]:
        return self.AI_VALIDATION_CRITERIA

    def get_min_volume_ratio_pct(self) -> Optional[float]:
        return self._float_param("min_volume_ratio_pct", 50.0)

    def get_rr_epsilon(self) -> float:
        return 0.05

    def _float_param(self, key: str, default: float) -> float:
        raw = self.get_param(key, default)
        if raw is None:
            return float(default)
        try:
            return float(raw)
        except (TypeError, ValueError):
            return float(default)

    def _params_snapshot(self) -> Dict[str, Any]:
        return {
            "min_rr": self._float_param("min_rr", 1.5),
            "sl_atr_mult": self._float_param("sl_atr_mult", 0.5),
            "min_sl_pct": self._float_param("min_sl_pct", 0.4),
            "swing_lookback": int(self.get_param("swing_lookback", 20) or 20),
            "pullback_max_bars": int(self.get_param("pullback_max_bars", 15) or 15),
            "min_break_atr": self._float_param("min_break_atr", 0.02),
            "max_chase_atr": self._float_param("max_chase_atr", 0.35),
            "pullback_touch_atr": self._float_param("pullback_touch_atr", 0.20),
            "quintile_cut": self._float_param("quintile_cut", 0.80),
            "exhaustion_min_range_atr": self._float_param("exhaustion_min_range_atr", 1.5),
            "move_lookback_5m": int(self.get_param("move_lookback_5m", 12) or 12),
            "move_lookback_15m": int(self.get_param("move_lookback_15m", 8) or 8),
            "veto_rsi_long": self._float_param("veto_rsi_long", 78.0),
            "veto_rsi_short": self._float_param("veto_rsi_short", 22.0),
            "thesis_rsi_long": self._float_param("thesis_rsi_long", 85.0),
            "thesis_rsi_short": self._float_param("thesis_rsi_short", 15.0),
            "min_volume_ratio_pct": self._float_param("min_volume_ratio_pct", 50.0),
            "cooldown_minutes": int(self.get_param("cooldown_minutes", 10) or 10),
            "allow_longs": bool(self.get_param("allow_longs", True)),
            "allow_shorts": bool(self.get_param("allow_shorts", True)),
            "scan_interval_active_minutes": self._float_param("scan_interval_active_minutes", 1.0),
        }

    def get_scan_timeframe(self) -> str:
        try:
            tf = str((self.config or {}).get("timeframe") or "5m").strip().lower()
            return tf or "5m"
        except Exception:
            return "5m"

    def get_scan_interval_minutes(self, *, scan_context: Optional[Dict[str, Any]] = None) -> float:
        p = self._params_snapshot()
        try:
            raw = self.get_param("scan_interval_minutes", None)
            base = max(1.0, float(raw)) if raw is not None else 5.0
        except (TypeError, ValueError):
            base = 5.0
        ctx = scan_context or {}
        return active_scan_interval_minutes(
            base,
            sticky_armed=bool(ctx.get("sticky_armed")),
            scan_interval_active_minutes=float(p["scan_interval_active_minutes"]),
        )

    def check_hard_veto(self, signal: str, market_context: dict) -> Optional[str]:
        """Last gate on the machine's context. Thresholds are this plan's, not Rocket's."""
        p = self._params_snapshot()
        side = str(signal or "").upper()
        ctx = market_context or {}
        if side == "BUY" and not p["allow_longs"]:
            return "Impulse pullback longs disabled"
        if side == "SELL" and not p["allow_shorts"]:
            return "Impulse pullback shorts disabled"
        if side not in ("BUY", "SELL"):
            return "Impulse pullback signal must be BUY or SELL"

        rsi = _finite(ctx.get("rsi", ctx.get("rsi_val")))
        if rsi is not None:
            if side == "BUY" and rsi >= float(p["veto_rsi_long"]):
                return f"RSI {rsi:.1f} >= {p['veto_rsi_long']:.0f} — long impulse exhausted"
            if side == "SELL" and rsi <= float(p["veto_rsi_short"]):
                return f"RSI {rsi:.1f} <= {p['veto_rsi_short']:.0f} — short impulse exhausted"

        vol = _finite(ctx.get("volume_ratio"))
        if vol is not None and vol < float(p["min_volume_ratio_pct"]):
            return (
                f"Volume {vol:.0f}% < {p['min_volume_ratio_pct']:.0f}% "
                "(no participation on the pullback)"
            )
        return None

    def score_scan_candidate(self, df, *, symbol: str, meta=None):
        """Rank a 5m impulse. The 1m pullback fill is not decided here."""
        p = self._params_snapshot()
        if df is None or getattr(df, "empty", True) or len(df) < 40:
            return None
        # Score the context TF the same way the 1m trigger arms: last closed bar
        # breaks structure and is not already exhausted on this frame.
        # Context TF only. 5m/15m quintile and RSI gates run on the 1m entry,
        # where those frames exist. Chase-from-break still applies here.
        snap = evaluate_impulse_window(df, params=p, armed_side=None)
        if snap.get("action") != ACTION_ARM or not snap.get("side"):
            return None
        side = str(snap["side"])
        try:
            closed = df.iloc[:-1]
            rsi_series = wilder_rsi(closed["close"].to_numpy(dtype=float), 14)
            rsi_now = float(rsi_series[-1]) if np.isfinite(rsi_series[-1]) else None
        except Exception:
            rsi_now = None
        if rsi_now is not None:
            if side == "LONG" and rsi_now >= float(p["veto_rsi_long"]):
                return None
            if side == "SHORT" and rsi_now <= float(p["veto_rsi_short"]):
                return None
        score = 68.0
        reasons = [f"5m {side.lower()} impulse break {snap.get('break_level')}"]
        armed = self._scan_armed_from_meta(meta)
        if armed:
            score += 15.0
            reasons.append("Sticky armed near-entry")
        if rsi_now is not None:
            reasons.append(f"RSI {rsi_now:.1f}")
        return {
            "score": float(min(100.0, round(score, 1))),
            "bias": side,
            "symbol": symbol,
            "rsi": None if rsi_now is None else round(rsi_now, 1),
            "reasons": reasons,
            "armed": armed,
            "timeframe": self.get_scan_timeframe(),
            "break_level": snap.get("break_level"),
        }

    def post_ai_adjust(
        self,
        signal: Dict[str, Any],
        ai_result: Dict[str, Any],
        market_context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        # Keep the mechanical min_rr target so a replay isolates entry, not a trim.
        del signal, market_context
        return ai_result

    def _frame_1m(self, df, extra: Dict[str, Any]) -> Optional[pd.DataFrame]:
        raw = extra.get("1m")
        if isinstance(raw, pd.DataFrame) and not raw.empty:
            return raw
        if isinstance(df, pd.DataFrame) and not df.empty and len(df.index) >= 3:
            try:
                delta = df.index.to_series().diff().dropna().median()
            except Exception:
                delta = None
            if delta is not None and delta <= pd.Timedelta(minutes=2):
                return df
        return None

    def _clear_arm(self) -> None:
        self.looking_for_entry = False
        self.entry_direction = None

    def _bracket(
        self,
        side: str,
        entry: float,
        extreme: float,
        atr: float,
        p: Dict[str, Any],
    ) -> Tuple[Optional[float], Optional[float]]:
        if entry <= 0 or extreme <= 0:
            return None, None
        buf = float(atr) * float(p["sl_atr_mult"]) if atr and atr > 0 else 0.0
        min_dist = entry * float(p["min_sl_pct"]) / 100.0
        if side == "LONG":
            sl = min(float(extreme), entry) - buf
            if entry - sl < min_dist:
                sl = entry - min_dist
            if sl >= entry:
                sl = entry - min_dist
            risk = entry - sl
            if risk <= 0:
                return None, None
            tp = entry + risk * float(p["min_rr"])
            if tp <= entry:
                return None, None
            return float(sl), float(tp)
        sl = max(float(extreme), entry) + buf
        if sl - entry < min_dist:
            sl = entry + min_dist
        if sl <= entry:
            sl = entry + min_dist
        risk = sl - entry
        if risk <= 0:
            return None, None
        tp = entry - risk * float(p["min_rr"])
        if tp >= entry or tp <= 0:
            return None, None
        return float(sl), float(tp)

    def generate_signal(self, df, extra_data=None):
        p = self._params_snapshot()
        extra = extra_data or {}
        df_1m = self._frame_1m(df, extra)
        if df_1m is None or len(df_1m) < 40:
            return self._reject("Not enough 1m data for an impulse break")

        df_5m = extra.get("5m") if isinstance(extra.get("5m"), pd.DataFrame) else None
        df_15m = extra.get("15m") if isinstance(extra.get("15m"), pd.DataFrame) else None
        if df_15m is None and isinstance(df, pd.DataFrame) and df is not df_1m:
            df_15m = df

        armed = str(self.entry_direction or "").upper() if self.looking_for_entry else None
        if armed not in ("LONG", "SHORT"):
            armed = None
        snap = evaluate_impulse_window(
            df_1m,
            params=p,
            armed_side=armed,
            df_5m=df_5m,
            df_15m=df_15m,
        )
        action = snap.get("action")
        if action == ACTION_ARM:
            self.looking_for_entry = True
            self.entry_direction = snap.get("side")
            return self._reject(str(snap.get("reason") or "armed — wait for pullback"))
        if action == ACTION_WAIT:
            self.looking_for_entry = True
            self.entry_direction = snap.get("side")
            return self._reject(str(snap.get("reason") or "waiting for first pullback"))
        if action == ACTION_INVALID:
            self._clear_arm()
            return self._reject(str(snap.get("reason") or "impulse invalidated"))
        if action != ACTION_FILL:
            if not self.looking_for_entry:
                self._clear_arm()
            return self._reject(str(snap.get("reason") or "no impulse pullback"))

        side = str(snap.get("side") or "")
        entry = _finite(snap.get("fill_price"))
        level = _finite(snap.get("break_level"))
        extreme = _finite(snap.get("pullback_extreme"))
        atr = _finite(snap.get("atr")) or 0.0
        if entry is None or extreme is None or side not in ("LONG", "SHORT"):
            self._clear_arm()
            return self._reject("Pullback fill missing price or extreme")

        now_ts = df_1m.index[-2] if len(df_1m) >= 2 else None
        if now_ts is not None and self._same_bar_already_signaled(now_ts):
            return self._reject("Same 1m bar already signaled")
        if not self._cooldown_ok(now_ts, int(p["cooldown_minutes"])):
            return self._reject(f"Fill cooldown {p['cooldown_minutes']}m not elapsed")

        sl, tp = self._bracket(side, float(entry), float(extreme), float(atr), p)
        if sl is None or tp is None:
            self._clear_arm()
            return self._reject("Failed to build SL/TP beyond the pullback extreme")

        signal_side = "BUY" if side == "LONG" else "SELL"
        geo_df = df_15m if isinstance(df_15m, pd.DataFrame) and not df_15m.empty else df_1m
        geo_reason = self.geometry_reject_reason(
            {"signal": signal_side, "price": float(entry), "sl": float(sl), "tp": float(tp)},
            geo_df,
        )
        if geo_reason:
            self._clear_arm()
            return self._reject(geo_reason)

        self._mark_signal_bar(now_ts)
        self._clear_arm()
        risk = abs(float(entry) - float(sl))
        rr = abs(float(tp) - float(entry)) / risk if risk else 0.0
        ema9 = 0.0
        if isinstance(df_15m, pd.DataFrame) and len(df_15m) >= 12 and "close" in df_15m.columns:
            try:
                ema9 = float(df_15m["close"].ewm(span=9, adjust=False).mean().iloc[-2])
            except Exception:
                ema9 = 0.0
        comment = (
            f"Impulse pullback {side}: 1m break {level:.6g}, "
            f"first retest {entry:.6g}, SL beyond pullback extreme, R:R {rr:.2f}"
        )
        out = {
            "signal": signal_side,
            "price": float(entry),
            "sl": float(sl),
            "tp": float(tp),
            "break_level": float(level) if level is not None else None,
            "comment": comment,
        }
        if side == "LONG":
            out["cascade_low"] = float(extreme)
            out["cascade_ema9"] = float(ema9)
        else:
            out["cascade_high"] = float(extreme)
            out["cascade_ema9"] = float(ema9)
        return out

    def supports_trade_thesis(self) -> bool:
        return True

    def get_thesis_timeframe(self) -> str:
        return "15m"

    def evaluate_trade_thesis(self, trade, current_price, *, df, extra_data=None):
        from app.core.trade_thesis import evaluate_impulse_pullback_thesis

        del extra_data
        if df is None or getattr(df, "empty", True) or len(df) < 5:
            return None
        last, _prev = thesis_confirmed_rows(df)
        if last is None:
            return None
        try:
            close = float(last["close"])
        except (TypeError, ValueError, KeyError):
            return None
        rsi = 50.0
        try:
            closed = df.iloc[:-1] if len(df) >= 2 else df
            series = wilder_rsi(closed["close"].to_numpy(dtype=float), 14)
            if np.isfinite(series[-1]):
                rsi = float(series[-1])
        except Exception:
            rsi = 50.0
        meta = trade.get("metadata") or {}
        side = str(trade.get("side") or "").upper()
        if side == "BUY":
            level = meta.get("cascade_low")
        else:
            level = meta.get("cascade_high")
        entry = float(trade.get("entry") or trade.get("entry_price") or 0)
        p = self._params_snapshot()
        return evaluate_impulse_pullback_thesis(
            side=side,
            entry=entry,
            current_price=float(current_price),
            close_tf=close,
            structure_level=float(level) if level is not None else None,
            rsi=rsi,
            rsi_exhaustion_long=float(p["thesis_rsi_long"]),
            rsi_exhaustion_short=float(p["thesis_rsi_short"]),
            timeframe_label="15m",
        )
