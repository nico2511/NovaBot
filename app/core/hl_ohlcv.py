"""
Load and download Hyperliquid OHLCV for causal replay.

The public ``candleSnapshot`` endpoint returns at most the most recent 5000
candles per coin and interval (a retention cap, not only a page size). This
module still pages backward so a deeper mirror keeps working. Nothing here is
imported by the live bot.

CLI::

    python -m app.core.hl_ohlcv --symbols BTC ETH --intervals 1h,15m,1m,4h --out data/ohlcv
"""
from __future__ import annotations

import argparse
import json
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Mapping, Optional, Sequence

import pandas as pd

INFO_URL = "https://api.hyperliquid.xyz/info"

INTERVAL_MS: Dict[str, int] = {
    "1m": 60_000,
    "3m": 180_000,
    "5m": 300_000,
    "15m": 900_000,
    "1h": 3_600_000,
    "4h": 14_400_000,
    "1d": 86_400_000,
}

OHLCV_COLUMNS = ("open", "high", "low", "close", "volume")


def interval_td(interval: str) -> pd.Timedelta:
    if interval not in INTERVAL_MS:
        raise KeyError(f"unsupported interval {interval!r}")
    return pd.Timedelta(milliseconds=INTERVAL_MS[interval])


def candles_to_frame(raw: Sequence[Mapping[str, Any]]) -> pd.DataFrame:
    """Normalize a candleSnapshot payload to a UTC OHLCV frame indexed by open time."""
    if not raw:
        return _empty_ohlcv()
    rows = []
    for candle in raw:
        if not isinstance(candle, Mapping):
            continue
        try:
            open_ms = int(candle["t"])
            rows.append(
                {
                    "time": open_ms,
                    "open": float(candle["o"]),
                    "high": float(candle["h"]),
                    "low": float(candle["l"]),
                    "close": float(candle["c"]),
                    "volume": float(candle.get("v") or 0.0),
                }
            )
        except (KeyError, TypeError, ValueError):
            continue
    if not rows:
        return _empty_ohlcv()
    df = pd.DataFrame(rows)
    df["time"] = pd.to_datetime(df["time"], unit="ms", utc=True)
    df = df.drop_duplicates(subset=["time"], keep="last")
    df = df.sort_values("time").set_index("time")
    for col in OHLCV_COLUMNS:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df = df.dropna(subset=["open", "high", "low", "close"])
    return df[list(OHLCV_COLUMNS)]


def funding_to_frame(raw: Sequence[Mapping[str, Any]]) -> pd.DataFrame:
    """Normalize fundingHistory rows. Index is settlement time (UTC)."""
    rows = []
    for item in raw or []:
        if not isinstance(item, Mapping):
            continue
        try:
            rows.append(
                {
                    "time": int(item["time"]),
                    "funding_rate": float(item["fundingRate"]),
                }
            )
        except (KeyError, TypeError, ValueError):
            continue
    if not rows:
        return pd.DataFrame(columns=["funding_rate"])
    df = pd.DataFrame(rows)
    df["time"] = pd.to_datetime(df["time"], unit="ms", utc=True)
    df = df.drop_duplicates(subset=["time"], keep="last").sort_values("time").set_index("time")
    return df[["funding_rate"]]


def _empty_ohlcv() -> pd.DataFrame:
    return pd.DataFrame(columns=list(OHLCV_COLUMNS))


def _post_info(payload: Mapping[str, Any], *, timeout: float = 60.0) -> Any:
    body = json.dumps(payload).encode()
    req = urllib.request.Request(
        INFO_URL,
        data=body,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode())


def _post_with_retry(payload: Mapping[str, Any], *, retries: int = 4, pause: float = 0.4) -> Any:
    last_err: Optional[Exception] = None
    for attempt in range(retries):
        try:
            return _post_info(payload)
        except urllib.error.HTTPError as exc:
            last_err = exc
            if exc.code != 429 or attempt == retries - 1:
                raise
            time.sleep(pause * (2**attempt))
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            last_err = exc
            if attempt == retries - 1:
                raise
            time.sleep(pause * (2**attempt))
    if last_err:
        raise last_err
    return []


def fetch_candles(
    coin: str,
    interval: str,
    *,
    start_ms: Optional[int] = None,
    end_ms: Optional[int] = None,
    page_pause: float = 0.15,
    transport: Optional[Callable[[Mapping[str, Any]], Any]] = None,
    max_pages: int = 40,
) -> pd.DataFrame:
    """
    Download OHLCV, paging backward.

    On the official API a page older than the most recent 5000 candles comes
    back empty. ``max_pages`` stops a runaway loop if a mirror keeps answering.
    """
    if interval not in INTERVAL_MS:
        raise KeyError(f"unsupported interval {interval!r}")
    post = transport or _post_with_retry
    end = int(end_ms if end_ms is not None else time.time() * 1000)
    floor = int(start_ms or 0)
    step = INTERVAL_MS[interval]
    collected: Dict[int, Mapping[str, Any]] = {}
    pages = 0
    while end > floor and pages < max_pages:
        page_start = max(floor, end - 5000 * step)
        payload = {
            "type": "candleSnapshot",
            "req": {
                "coin": coin,
                "interval": interval,
                "startTime": page_start,
                "endTime": end,
            },
        }
        batch = post(payload) or []
        pages += 1
        if not isinstance(batch, list) or not batch:
            break
        added = 0
        oldest = None
        for candle in batch:
            if not isinstance(candle, Mapping) or "t" not in candle:
                continue
            try:
                ts = int(candle["t"])
            except (TypeError, ValueError):
                continue
            if ts < floor or ts > end:
                continue
            oldest = ts if oldest is None else min(oldest, ts)
            if ts not in collected:
                collected[ts] = candle
                added += 1
        if oldest is None or added == 0 or oldest <= floor:
            break
        next_end = oldest - 1
        if next_end >= end:
            break
        end = next_end
        if page_pause:
            time.sleep(page_pause)
    return candles_to_frame(list(collected.values()))


def fetch_funding(
    coin: str,
    *,
    start_ms: int,
    end_ms: Optional[int] = None,
    page_pause: float = 0.15,
    transport: Optional[Callable[[Mapping[str, Any]], Any]] = None,
    max_pages: int = 80,
) -> pd.DataFrame:
    """Page fundingHistory forward from ``start_ms``. The API returns ~500 rows per call."""
    post = transport or _post_with_retry
    end = int(end_ms if end_ms is not None else time.time() * 1000)
    cursor = int(start_ms)
    rows: List[Mapping[str, Any]] = []
    seen = set()
    for _ in range(max_pages):
        if cursor >= end:
            break
        payload = {
            "type": "fundingHistory",
            "coin": coin,
            "startTime": cursor,
            "endTime": end,
        }
        batch = post(payload) or []
        if not isinstance(batch, list) or not batch:
            break
        newest = cursor
        added = 0
        for item in batch:
            if not isinstance(item, Mapping):
                continue
            try:
                ts = int(item["time"])
            except (KeyError, TypeError, ValueError):
                continue
            if ts in seen or ts > end:
                continue
            seen.add(ts)
            rows.append(item)
            added += 1
            newest = max(newest, ts)
        if added == 0 or newest <= cursor:
            break
        cursor = newest + 1
        if page_pause:
            time.sleep(page_pause)
        if len(batch) < 500:
            break
    frame = funding_to_frame(rows)
    if frame.empty:
        return frame
    return frame[frame.index >= pd.to_datetime(start_ms, unit="ms", utc=True)]


def save_ohlcv(df: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    out = df.copy()
    out.index.name = "time"
    out.to_csv(path, date_format="%Y-%m-%dT%H:%M:%SZ")


def load_ohlcv(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    if "time" not in df.columns:
        raise ValueError(f"{path} has no time column")
    df["time"] = pd.to_datetime(df["time"], utc=True)
    df = df.set_index("time").sort_index()
    for col in OHLCV_COLUMNS:
        if col not in df.columns:
            raise ValueError(f"{path} missing {col}")
        df[col] = pd.to_numeric(df[col], errors="coerce")
    return df.dropna(subset=["open", "high", "low", "close"])[list(OHLCV_COLUMNS)]


def save_funding(df: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    out = df.copy()
    out.index.name = "time"
    out.to_csv(path, date_format="%Y-%m-%dT%H:%M:%SZ")


def load_funding(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame(columns=["funding_rate"])
    df = pd.read_csv(path)
    if df.empty or "time" not in df.columns:
        return pd.DataFrame(columns=["funding_rate"])
    df["time"] = pd.to_datetime(df["time"], utc=True)
    df = df.set_index("time").sort_index()
    df["funding_rate"] = pd.to_numeric(df["funding_rate"], errors="coerce")
    return df.dropna(subset=["funding_rate"])[["funding_rate"]]


def slice_asof(df: Optional[pd.DataFrame], t: Any, n: Optional[int] = None) -> pd.DataFrame:
    """
    Bars whose open time is <= ``t``.

    The last row is the bar that has just opened at ``t`` when ``t`` is on the
    index (the forming bar). Strategies must read the confirmed bar at iloc[-2].
    """
    if df is None or getattr(df, "empty", True):
        return _empty_ohlcv() if df is None else df.iloc[0:0]
    ts = pd.Timestamp(t)
    idx = df.index
    idx_tz = getattr(idx, "tz", None)
    if idx_tz is not None:
        ts = ts.tz_localize("UTC") if ts.tzinfo is None else ts.tz_convert(idx_tz)
    elif ts.tzinfo is not None:
        ts = ts.tz_convert("UTC").tz_localize(None)
    out = df.loc[:ts]
    if n is not None and n > 0 and len(out) > n:
        out = out.iloc[-int(n) :]
    return out


def trim_recent(df: pd.DataFrame, *, days: Optional[float]) -> pd.DataFrame:
    if df is None or df.empty or not days or days <= 0:
        return df
    end = df.index[-1]
    start = end - pd.Timedelta(days=float(days))
    return df.loc[df.index >= start]


def cache_path(out_dir: Path, coin: str, interval: str) -> Path:
    return out_dir / f"{coin}_{interval}.csv"


def funding_path(out_dir: Path, coin: str) -> Path:
    return out_dir / f"{coin}_funding.csv"


def ensure_symbol_cache(
    coin: str,
    intervals: Iterable[str],
    out_dir: Path,
    *,
    fetch: bool = True,
    days: Optional[float] = None,
    page_pause: float = 0.15,
) -> Dict[str, pd.DataFrame]:
    """Load cached frames, downloading any interval that is missing."""
    frames: Dict[str, pd.DataFrame] = {}
    out_dir.mkdir(parents=True, exist_ok=True)
    for interval in intervals:
        path = cache_path(out_dir, coin, interval)
        if path.exists():
            frame = load_ohlcv(path)
        elif fetch:
            print(f"[hl] fetch {coin} {interval}")
            frame = fetch_candles(coin, interval, page_pause=page_pause)
            if frame.empty:
                print(f"[hl] no candles for {coin} {interval}")
            else:
                save_ohlcv(frame, path)
                print(
                    f"[hl] {coin} {interval} {len(frame)} bars "
                    f"{frame.index[0].isoformat()} → {frame.index[-1].isoformat()}"
                )
        else:
            frame = _empty_ohlcv()
        frames[interval] = trim_recent(frame, days=days)
    fund_file = funding_path(out_dir, coin)
    if fund_file.exists():
        frames["funding"] = load_funding(fund_file)
    elif fetch:
        start = None
        for interval in intervals:
            frame = frames.get(interval)
            if frame is not None and not frame.empty:
                start_i = int(frame.index[0].timestamp() * 1000)
                start = start_i if start is None else min(start, start_i)
        if start is not None:
            print(f"[hl] fetch {coin} funding")
            fund = fetch_funding(coin, start_ms=start, page_pause=page_pause)
            save_funding(fund, fund_file)
            frames["funding"] = trim_recent_funding(fund, days=days)
        else:
            frames["funding"] = pd.DataFrame(columns=["funding_rate"])
    else:
        frames["funding"] = load_funding(fund_file) if fund_file.exists() else pd.DataFrame(columns=["funding_rate"])
    if days and not frames["funding"].empty:
        frames["funding"] = trim_recent_funding(frames["funding"], days=days)
    return frames


def trim_recent_funding(df: pd.DataFrame, *, days: Optional[float]) -> pd.DataFrame:
    if df is None or df.empty or not days or days <= 0:
        return df
    end = df.index[-1]
    return df.loc[df.index >= end - pd.Timedelta(days=float(days))]


def describe_span(df: Optional[pd.DataFrame]) -> str:
    if df is None or getattr(df, "empty", True):
        return "none"
    return f"{len(df)} bars {df.index[0].isoformat()} → {df.index[-1].isoformat()}"


def main(argv: Optional[Sequence[str]] = None) -> None:
    parser = argparse.ArgumentParser(description="Download Hyperliquid OHLCV into CSV cache")
    parser.add_argument("--symbols", nargs="+", default=["BTC", "ETH"])
    parser.add_argument("--intervals", default="1h,15m,1m,4h")
    parser.add_argument("--out", default="data/ohlcv")
    parser.add_argument("--days", type=float, default=0.0, help="Keep only the last N days (0 = all the API returned)")
    args = parser.parse_args(argv)
    intervals = [part.strip() for part in str(args.intervals).split(",") if part.strip()]
    out = Path(args.out)
    days = args.days if args.days and args.days > 0 else None
    for coin in args.symbols:
        ensure_symbol_cache(coin.upper(), intervals, out, fetch=True, days=days)


if __name__ == "__main__":
    main()
