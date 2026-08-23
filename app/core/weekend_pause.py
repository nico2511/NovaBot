"""Weekend pause for momentum cascade strategies (rocket / waterfall)."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional
from zoneinfo import ZoneInfo

DEFAULT_TIMEZONE = "Europe/Paris"
DEFAULT_STRATEGIES = ("rocket", "waterfall")
# Python weekday: Monday=0 … Sunday=6
DEFAULT_START_WEEKDAY = 5  # Saturday
DEFAULT_START_HOUR = 6
DEFAULT_END_WEEKDAY = 0  # Monday
DEFAULT_END_HOUR = 6

_last_log_bucket: Optional[str] = None


def _pause_config(config: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    return (config or {}).get("weekend_pause") or {}


def _week_minutes(dt: datetime) -> int:
    return dt.weekday() * 24 * 60 + dt.hour * 60 + dt.minute


def is_weekend_pause_active(
    config: Optional[Dict[str, Any]] = None,
    *,
    now: Optional[datetime] = None,
) -> bool:
    """
    True inside the configured pause window (default: Sunday 00:00–12:00 Paris).

    Supports same-day windows (e.g. Sun 0h→12h) and wrap-around (e.g. Sat 6h→Mon 6h).
    """
    cfg = _pause_config(config)
    if not cfg.get("enabled", True):
        return False

    tz_name = str(cfg.get("timezone") or DEFAULT_TIMEZONE)
    tz = ZoneInfo(tz_name)
    cur = now or datetime.now(tz)
    if cur.tzinfo is None:
        cur = cur.replace(tzinfo=tz)
    else:
        cur = cur.astimezone(tz)

    start_wd = int(cfg.get("start_weekday", DEFAULT_START_WEEKDAY))
    start_h = int(cfg.get("start_hour", DEFAULT_START_HOUR))
    end_wd = int(cfg.get("end_weekday", DEFAULT_END_WEEKDAY))
    end_h = int(cfg.get("end_hour", DEFAULT_END_HOUR))

    start_min = start_wd * 24 * 60 + start_h * 60
    end_min = end_wd * 24 * 60 + end_h * 60
    cur_min = _week_minutes(cur)

    if start_min < end_min:
        return start_min <= cur_min < end_min
    return cur_min >= start_min or cur_min < end_min


def get_weekend_paused_strategies(
    config: Optional[Dict[str, Any]] = None,
    *,
    now: Optional[datetime] = None,
) -> List[str]:
    """Strategy names idle during the active weekend pause window."""
    if not is_weekend_pause_active(config, now=now):
        return []
    cfg = _pause_config(config)
    raw = cfg.get("strategies") or list(DEFAULT_STRATEGIES)
    return [str(name) for name in raw if name]


def is_strategy_weekend_paused(
    strategy_name: Optional[str],
    config: Optional[Dict[str, Any]] = None,
    *,
    now: Optional[datetime] = None,
) -> bool:
    if not strategy_name:
        return False
    return str(strategy_name) in get_weekend_paused_strategies(config, now=now)


def weekend_pause_status(
    config: Optional[Dict[str, Any]] = None,
    *,
    now: Optional[datetime] = None,
) -> Dict[str, Any]:
    """Snapshot for API / logs."""
    cfg = _pause_config(config)
    active = is_weekend_pause_active(config, now=now)
    tz_name = str(cfg.get("timezone") or DEFAULT_TIMEZONE)
    tz = ZoneInfo(tz_name)
    cur = now or datetime.now(tz)
    if cur.tzinfo is None:
        cur = cur.replace(tzinfo=tz)
    else:
        cur = cur.astimezone(tz)
    return {
        "enabled": bool(cfg.get("enabled", True)),
        "active": active,
        "timezone": tz_name,
        "window": {
            "start_weekday": int(cfg.get("start_weekday", DEFAULT_START_WEEKDAY)),
            "start_hour": int(cfg.get("start_hour", DEFAULT_START_HOUR)),
            "end_weekday": int(cfg.get("end_weekday", DEFAULT_END_WEEKDAY)),
            "end_hour": int(cfg.get("end_hour", DEFAULT_END_HOUR)),
        },
        "strategies": list(cfg.get("strategies") or DEFAULT_STRATEGIES),
        "paused_strategies": get_weekend_paused_strategies(config, now=cur),
        "local_time": cur.isoformat(),
    }


def log_weekend_pause_once(logger, config: Optional[Dict[str, Any]], paused: List[str]) -> None:
    """At most one log line per hour while pause is active."""
    global _last_log_bucket
    if not paused:
        return
    cfg = _pause_config(config)
    tz = ZoneInfo(str(cfg.get("timezone") or DEFAULT_TIMEZONE))
    bucket = datetime.now(tz).strftime("%Y-%m-%d-%H")
    if _last_log_bucket == bucket:
        return
    _last_log_bucket = bucket
    logger(
        f"[BOT] ⏸️ Weekend pause ({cfg.get('timezone', DEFAULT_TIMEZONE)}): "
        f"{', '.join(paused)} idle"
    )
