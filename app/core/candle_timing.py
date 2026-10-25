"""OHLCV bar alignment helpers (forming vs closed bars)."""
from __future__ import annotations

from typing import Optional, Tuple

import pandas as pd


def _normalize_interval(interval: str) -> str:
    t = str(interval or "15m").strip().lower()
    aliases = {
        "240m": "4h",
        "60m": "1h",
        "1hour": "1h",
        "60": "1h",
        "15": "15m",
        "5": "5m",
    }
    return aliases.get(t, t)


def current_bar_open(interval: str, now: Optional[pd.Timestamp] = None) -> pd.Timestamp:
    """UTC open time of the candle that is currently forming for ``interval``."""
    ts = now if now is not None else pd.Timestamp.now(tz="UTC")
    if ts.tzinfo is None:
        ts = ts.tz_localize("UTC")
    else:
        ts = ts.tz_convert("UTC")
    iv = _normalize_interval(interval)
    if iv.endswith("m"):
        mins = int(iv[:-1])
        return ts.floor(f"{mins}min")
    if iv.endswith("h"):
        hrs = int(iv[:-1])
        return ts.floor(f"{hrs}h")
    if iv.endswith("d"):
        days = int(iv[:-1])
        return ts.floor(f"{days}d")
    return ts.floor("15min")


def last_candle_is_forming(
    df: pd.DataFrame,
    interval: str,
    *,
    now: Optional[pd.Timestamp] = None,
) -> Tuple[bool, str]:
    """
    True when the last OHLCV row is the currently forming bar (not a stale close).

    Strategies that read iloc[-2] as the last **closed** bar require this invariant.
    """
    if df is None or getattr(df, "empty", True):
        return False, "empty OHLCV"
    try:
        last_ts = pd.Timestamp(df.index[-1])
        if last_ts.tzinfo is None:
            last_ts = last_ts.tz_localize("UTC")
        else:
            last_ts = last_ts.tz_convert("UTC")
    except Exception:
        return False, "invalid candle index"
    expected = current_bar_open(interval, now=now)
    if last_ts != expected:
        return (
            False,
            f"last candle {last_ts.isoformat()} != forming open {expected.isoformat()}",
        )
    return True, ""
