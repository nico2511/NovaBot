"""
Download a Binance USDT-M perpetual OHLCV cache for cascade replay.

Hyperliquid's public ``candleSnapshot`` keeps only ~5000 one-minute bars.
This module fills ``data/ohlcv_proxy/`` from the public Binance Vision archive
(``data.binance.vision``), which is the long 1m/15m history for the same
scanner whitelist. It is a **proxy**, not Hyperliquid: prices, funding, and
listing dates are Binance USDT-M.

The Binance futures REST API is not used. From this environment it returns
HTTP 451; the vision CDN does not. Bybit's REST API returned HTTP 403 here,
so it was not the source.

Symbol map: each NovaBot coin ``BTC`` is the Binance perp ``BTCUSDT``. Coins
with no monthly 1m file are skipped and listed in the manifest.

CLI::

    python -m app.core.proxy_ohlcv --out data/ohlcv_proxy --manifest reports/proxy_ohlcv_manifest.json

The CSVs match ``hl_ohlcv.load_ohlcv`` / ``load_funding`` so
``python -m app.core.strategy_backtest --source proxy --no-fetch`` can read them.
"""
from __future__ import annotations

import argparse
import io
import json
import time
import urllib.error
import urllib.request
import zipfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

import pandas as pd

from app.core.hl_ohlcv import (
    INTERVAL_MS,
    SCANNER_WHITELIST,
    load_funding,
    load_ohlcv,
    save_funding,
    save_ohlcv,
)

VISION_ROOT = "https://data.binance.vision/data/futures/um"
# Six closed months plus the daily files through the HL dump date (2026-09-26).
DEFAULT_MONTHS = ("2026-03", "2026-04", "2026-05", "2026-06", "2026-07", "2026-08")
DEFAULT_DAILY_START = "2026-09-01"
DEFAULT_DAILY_END = "2026-09-26"
USER_AGENT = "NovaBot-proxy-ohlcv/1.0"


def proxy_symbol(coin: str) -> str:
    """NovaBot coin → Binance USDT-M perpetual symbol."""
    return f"{str(coin).upper()}USDT"


def month_kline_url(symbol: str, interval: str, month: str) -> str:
    name = f"{symbol}-{interval}-{month}.zip"
    return f"{VISION_ROOT}/monthly/klines/{symbol}/{interval}/{name}"


def daily_kline_url(symbol: str, interval: str, day: str) -> str:
    name = f"{symbol}-{interval}-{day}.zip"
    return f"{VISION_ROOT}/daily/klines/{symbol}/{interval}/{name}"


def month_funding_url(symbol: str, month: str) -> str:
    name = f"{symbol}-fundingRate-{month}.zip"
    return f"{VISION_ROOT}/monthly/fundingRate/{symbol}/{name}"


def daily_funding_url(symbol: str, day: str) -> str:
    name = f"{symbol}-fundingRate-{day}.zip"
    return f"{VISION_ROOT}/daily/fundingRate/{symbol}/{name}"


def _download(url: str, *, timeout: float = 60.0, retries: int = 4) -> Optional[bytes]:
    last: Optional[Exception] = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.read()
        except urllib.error.HTTPError as exc:
            if exc.code == 404:
                return None
            last = exc
            if exc.code not in (429, 500, 502, 503, 504) or attempt == retries - 1:
                raise
        except (urllib.error.URLError, TimeoutError) as exc:
            last = exc
            if attempt == retries - 1:
                raise
        time.sleep(0.4 * (2**attempt))
    if last:
        raise last
    return None


def _zip_csv_text(blob: bytes) -> str:
    with zipfile.ZipFile(io.BytesIO(blob)) as archive:
        names = [name for name in archive.namelist() if name.endswith(".csv") and not name.endswith("/")]
        if not names:
            raise ValueError("zip has no csv")
        return archive.read(names[0]).decode("utf-8")


def klines_csv_to_frame(text: str) -> pd.DataFrame:
    """Binance vision kline CSV → UTC OHLCV indexed by open time."""
    if not text.strip():
        return pd.DataFrame(columns=["open", "high", "low", "close", "volume"])
    first = text.splitlines()[0]
    header = None
    if first.lower().startswith("open_time"):
        header = 0
    df = pd.read_csv(
        io.StringIO(text),
        header=header,
        usecols=[0, 1, 2, 3, 4, 5],
        names=["time", "open", "high", "low", "close", "volume"] if header is None else None,
    )
    if header is not None:
        df = df.rename(
            columns={
                "open_time": "time",
                "open": "open",
                "high": "high",
                "low": "low",
                "close": "close",
                "volume": "volume",
            }
        )
        df = df[["time", "open", "high", "low", "close", "volume"]]
    df["time"] = pd.to_numeric(df["time"], errors="coerce")
    # Vision files are milliseconds. Guard a seconds-epoch column.
    if df["time"].dropna().median() < 10_000_000_000:
        df["time"] = df["time"] * 1000.0
    df["time"] = pd.to_datetime(df["time"], unit="ms", utc=True)
    for col in ("open", "high", "low", "close", "volume"):
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df = df.dropna(subset=["time", "open", "high", "low", "close"])
    df = df.drop_duplicates(subset=["time"], keep="last").sort_values("time").set_index("time")
    return df[["open", "high", "low", "close", "volume"]]


def funding_csv_to_frame(text: str) -> pd.DataFrame:
    """Binance vision funding CSV → settlement time index and ``funding_rate``.

    Each row is one settlement (usually 8 hours), not a Hyperliquid hourly rate.
    ``funding_drag_r`` sums the rates whose settlement falls inside the hold.
    """
    if not text.strip():
        return pd.DataFrame(columns=["funding_rate"])
    df = pd.read_csv(io.StringIO(text))
    cols = {c.lower(): c for c in df.columns}
    time_col = cols.get("calc_time") or cols.get("time")
    rate_col = cols.get("last_funding_rate") or cols.get("funding_rate")
    if time_col is None or rate_col is None:
        return pd.DataFrame(columns=["funding_rate"])
    out = pd.DataFrame(
        {
            "time": pd.to_numeric(df[time_col], errors="coerce"),
            "funding_rate": pd.to_numeric(df[rate_col], errors="coerce"),
        }
    )
    if "funding_interval_hours" in cols:
        out["interval_hours"] = pd.to_numeric(df[cols["funding_interval_hours"]], errors="coerce")
    out = out.dropna(subset=["time", "funding_rate"])
    out["time"] = pd.to_datetime(out["time"], unit="ms", utc=True)
    out = out.drop_duplicates(subset=["time"], keep="last").sort_values("time").set_index("time")
    return out[["funding_rate"]]


def _day_strings(start: str, end: str) -> List[str]:
    days = pd.date_range(start, end, freq="D")
    return [day.strftime("%Y-%m-%d") for day in days]


def _concat(frames: Sequence[pd.DataFrame]) -> pd.DataFrame:
    parts = [frame for frame in frames if frame is not None and not frame.empty]
    if not parts:
        return pd.DataFrame(columns=["open", "high", "low", "close", "volume"])
    df = pd.concat(parts)
    df = df[~df.index.duplicated(keep="last")].sort_index()
    return df


def gap_count(df: pd.DataFrame, interval: str) -> int:
    if df is None or len(df) < 2 or interval not in INTERVAL_MS:
        return 0
    step = INTERVAL_MS[interval]
    delta_ms = df.index.to_series().diff().dt.total_seconds() * 1000.0
    return int((delta_ms > step * 1.5).sum())


def _fetch_klines(urls: Sequence[str]) -> Tuple[pd.DataFrame, List[str]]:
    frames: List[pd.DataFrame] = []
    missing: List[str] = []
    for url in urls:
        blob = _download(url)
        if blob is None:
            missing.append(url)
            continue
        frames.append(klines_csv_to_frame(_zip_csv_text(blob)))
    return _concat(frames), missing


def _fetch_funding(urls: Sequence[str]) -> Tuple[pd.DataFrame, List[str]]:
    frames: List[pd.DataFrame] = []
    missing: List[str] = []
    for url in urls:
        blob = _download(url)
        if blob is None:
            missing.append(url)
            continue
        frames.append(funding_csv_to_frame(_zip_csv_text(blob)))
    parts = [frame for frame in frames if frame is not None and not frame.empty]
    if not parts:
        return pd.DataFrame(columns=["funding_rate"]), missing
    df = pd.concat(parts)
    df = df[~df.index.duplicated(keep="last")].sort_index()
    return df[["funding_rate"]], missing


def download_symbol(
    coin: str,
    out_dir: Path,
    *,
    months: Sequence[str],
    days: Sequence[str],
    intervals: Sequence[str] = ("1m", "15m"),
    refresh: bool = False,
) -> List[Dict[str, object]]:
    """Download one coin. Returns manifest rows, including a skip row when 1m is empty."""
    symbol = proxy_symbol(coin)
    rows: List[Dict[str, object]] = []
    out_dir.mkdir(parents=True, exist_ok=True)
    for interval in intervals:
        path = out_dir / f"{coin}_{interval}.csv"
        missing: List[str] = []
        if path.exists() and not refresh:
            frame = load_ohlcv(path)
            print(f"[proxy] cache {coin} {interval} {len(frame)} bars")
        else:
            urls = [month_kline_url(symbol, interval, month) for month in months]
            urls.extend(daily_kline_url(symbol, interval, day) for day in days)
            print(f"[proxy] fetch {symbol} {interval} ({len(urls)} files)")
            frame, missing = _fetch_klines(urls)
            if frame.empty:
                print(f"[proxy] skip {coin} {interval}: no Binance USDT-M file")
                rows.append(
                    {
                        "coin": coin,
                        "proxy_symbol": symbol,
                        "interval": interval,
                        "bars": 0,
                        "start": None,
                        "end": None,
                        "gaps": 0,
                        "file": None,
                        "missing_files": len(missing),
                        "source": "binance-usdtm-vision",
                    }
                )
                continue
            save_ohlcv(frame, path)
            if missing:
                print(f"[proxy] {coin} {interval} missing {len(missing)} files")
        rows.append(
            {
                "coin": coin,
                "proxy_symbol": symbol,
                "interval": interval,
                "bars": int(len(frame)),
                "start": frame.index[0].isoformat() if len(frame) else None,
                "end": frame.index[-1].isoformat() if len(frame) else None,
                "gaps": gap_count(frame, interval),
                "file": path.name,
                "missing_files": len(missing),
                "source": "binance-usdtm-vision",
            }
        )
    fund_path = out_dir / f"{coin}_funding.csv"
    if fund_path.exists() and not refresh:
        fund = load_funding(fund_path)
    else:
        urls = [month_funding_url(symbol, month) for month in months]
        urls.extend(daily_funding_url(symbol, day) for day in days)
        fund, missing = _fetch_funding(urls)
        if fund.empty:
            print(f"[proxy] {coin} funding empty")
        else:
            save_funding(fund, fund_path)
            if missing:
                print(f"[proxy] {coin} funding missing {len(missing)} files")
    rows.append(
        {
            "coin": coin,
            "proxy_symbol": symbol,
            "interval": "funding",
            "bars": int(len(fund)),
            "start": fund.index[0].isoformat() if len(fund) else None,
            "end": fund.index[-1].isoformat() if len(fund) else None,
            "gaps": 0,
            "file": fund_path.name if fund_path.exists() else None,
            "missing_files": 0,
            "source": "binance-usdtm-vision-funding-8h",
        }
    )
    return rows


def write_manifest(rows: Sequence[Dict[str, object]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(list(rows), indent=2))


def main(argv: Optional[Sequence[str]] = None) -> None:
    parser = argparse.ArgumentParser(description="Download Binance USDT-M proxy OHLCV (not Hyperliquid)")
    parser.add_argument("--symbols", nargs="+", default=list(SCANNER_WHITELIST))
    parser.add_argument("--months", default=",".join(DEFAULT_MONTHS))
    parser.add_argument("--daily-start", default=DEFAULT_DAILY_START)
    parser.add_argument("--daily-end", default=DEFAULT_DAILY_END)
    parser.add_argument("--intervals", default="1m,15m")
    parser.add_argument("--out", default="data/ohlcv_proxy")
    parser.add_argument("--manifest", default="reports/proxy_ohlcv_manifest.json")
    parser.add_argument("--refresh", action="store_true")
    parser.add_argument("--workers", type=int, default=4)
    args = parser.parse_args(argv)
    months = [part.strip() for part in str(args.months).split(",") if part.strip()]
    days = _day_strings(args.daily_start, args.daily_end) if args.daily_start and args.daily_end else []
    intervals = [part.strip() for part in str(args.intervals).split(",") if part.strip()]
    out = Path(args.out)
    coins = [coin.upper() for coin in args.symbols]
    rows: List[Dict[str, object]] = []
    workers = max(1, int(args.workers))
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {
            pool.submit(
                download_symbol,
                coin,
                out,
                months=months,
                days=days,
                intervals=intervals,
                refresh=bool(args.refresh),
            ): coin
            for coin in coins
        }
        for future in as_completed(futures):
            coin = futures[future]
            try:
                rows.extend(future.result())
            except Exception as exc:
                print(f"[proxy] FAIL {coin}: {exc}")
                rows.append(
                    {
                        "coin": coin,
                        "proxy_symbol": proxy_symbol(coin),
                        "interval": "error",
                        "bars": 0,
                        "start": None,
                        "end": None,
                        "gaps": 0,
                        "file": None,
                        "missing_files": 0,
                        "source": "binance-usdtm-vision",
                        "error": str(exc),
                    }
                )
    rows.sort(key=lambda row: (str(row.get("coin")), str(row.get("interval"))))
    if args.manifest:
        write_manifest(rows, Path(args.manifest))
        print(f"[proxy] manifest {args.manifest} ({len(rows)} rows)")


if __name__ == "__main__":
    main()
