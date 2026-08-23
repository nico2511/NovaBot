"""Aggregate Hyperliquid close fills into one PnL snapshot for sync closes."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

import pandas as pd


def _fill_time_ms(fill: Dict[str, Any]) -> int:
    raw = fill.get("timestamp", fill.get("time", 0))
    if raw is None:
        return 0
    try:
        return int(raw)
    except (TypeError, ValueError):
        try:
            dt = pd.to_datetime(raw, utc=True, errors="coerce")
            if pd.isna(dt):
                return 0
            return int(dt.value // 1_000_000)
        except Exception:
            return 0


def _trade_entry_ms(trade: Dict[str, Any]) -> int:
    for key in ("timestamp", "entry_time"):
        raw = trade.get(key)
        if not raw:
            continue
        try:
            dt = pd.to_datetime(raw, utc=True, errors="coerce")
            if pd.isna(dt):
                continue
            return int(dt.value // 1_000_000)
        except Exception:
            continue
    return 0


def _is_close_fill(fill: Dict[str, Any]) -> bool:
    pnl = float(fill.get("pnl") or 0)
    dir_s = str(fill.get("dir") or "")
    return pnl != 0 or "Close" in dir_s


def _closing_side_for_position(position_side: str) -> str:
    return "SELL" if str(position_side or "").upper() == "BUY" else "BUY"


def aggregate_exchange_close(
    fills: List[Dict[str, Any]],
    *,
    symbol: str,
    trade: Dict[str, Any],
    burst_window_ms: int = 120_000,
) -> Optional[Dict[str, Any]]:
    """
    Sum all exchange close fills belonging to the open trade.

    Filters by symbol, entry time, and closing side. When Hyperliquid splits
    a stop into several fills, summing ``closedPnl`` matches the account.
    """
    if not fills:
        return None

    entry_ms = _trade_entry_ms(trade)
    pos_side = str(trade.get("side") or "BUY").upper()
    close_side = _closing_side_for_position(pos_side)
    expected_size = float(trade.get("size") or 0)

    candidates: List[tuple[int, Dict[str, Any]]] = []
    for fill in fills:
        if fill.get("symbol") != symbol:
            continue
        ts = _fill_time_ms(fill)
        if entry_ms and ts and ts < entry_ms:
            continue
        if str(fill.get("side") or "").upper() != close_side:
            continue
        if not _is_close_fill(fill):
            continue
        candidates.append((ts, fill))

    if not candidates:
        return None

    candidates.sort(key=lambda x: x[0])

    # Final close burst (SL/TP can shard into multiple fills within ~2 min)
    latest_ts = candidates[-1][0]
    window_start = latest_ts - burst_window_ms if latest_ts else 0
    burst = [(ts, f) for ts, f in candidates if ts >= window_start] or [candidates[-1]]

    # If burst size still short vs tracked size, include earlier close legs since entry
    total_sz = sum(float(f.get("size") or 0) for _, f in burst)
    if expected_size > 0 and total_sz + 1e-9 < expected_size * 0.95:
        cumulative = 0.0
        expanded: List[tuple[int, Dict[str, Any]]] = []
        for ts, f in candidates:
            expanded.append((ts, f))
            cumulative += float(f.get("size") or 0)
            if cumulative >= expected_size * 0.95:
                break
        if cumulative > total_sz:
            burst = expanded
            total_sz = cumulative

    total_pnl = sum(float(f.get("pnl") or 0) for _, f in burst)
    total_fee = sum(float(f.get("fee") or 0) for _, f in burst)
    if total_sz > 0:
        exit_price = sum(
            float(f.get("entry_price") or f.get("exit_price") or 0) * float(f.get("size") or 0)
            for _, f in burst
        ) / total_sz
    else:
        exit_price = float(burst[-1][1].get("entry_price") or burst[-1][1].get("exit_price") or 0)

    return {
        "exit_price": exit_price,
        "pnl": total_pnl,
        "fee": total_fee,
        "close_size": total_sz,
        "fill_count": len(burst),
        "exchange_close_time": burst[-1][1].get("timestamp"),
    }


def estimate_gross_pnl(
    *,
    side: str,
    entry_price: float,
    exit_price: float,
    size: float,
) -> float:
    if entry_price <= 0 or exit_price <= 0 or size <= 0:
        return 0.0
    if str(side or "").upper() == "BUY":
        return (exit_price - entry_price) * size
    return (entry_price - exit_price) * size
