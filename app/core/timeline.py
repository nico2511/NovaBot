"""
Read-only timeline aggregator for debugging trade lifecycles.

Events: signal_detected | ai_decision | entry | thesis | trailing | exit | error
Filterable by symbol / trade_id / trace_id.
"""
from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

_EVENT_TYPES = frozenset(
    {"signal_detected", "ai_decision", "entry", "thesis", "trailing", "exit", "error"}
)

_LOG_PATTERNS = [
    (re.compile(r"THESIS_|thesis", re.I), "thesis"),
    (re.compile(r"Smart BE|trailing|TRAIL", re.I), "trailing"),
    (re.compile(r"ATOMIC ENTRY|ENTRY CONFIRMED", re.I), "entry"),
    (re.compile(r"ATOMIC EXIT|EXIT CONFIRMED|closed", re.I), "exit"),
    (re.compile(r"signal detected|SIGNAL DETECTED|Pre-AI", re.I), "signal_detected"),
    (re.compile(r"❌|ERROR|Failed|BLOCKED", re.I), "error"),
]

# Explicit "SYMBOL:" / "on SYMBOL" / "CONFIRMED: SYMBOL" beats loose uppercase tokens
_SYMBOL_HINTS = [
    re.compile(r"ENTRY CONFIRMED:\s*([A-Z]{2,10})\b"),
    re.compile(r"ATOMIC (?:ENTRY|EXIT)[^:]*:\s*(?:Closing\s+)?([A-Z]{2,10})\b"),
    re.compile(r"\b(?:on|for)\s+([A-Z]{2,10})\b"),
    re.compile(r"\b([A-Z]{2,10})-(?:BUY|SELL|\d)", re.I),  # trade_id prefix
]

_NOISE_TOKENS = frozenset(
    {
        "BUY",
        "SELL",
        "LONG",
        "SHORT",
        "ENTRY",
        "EXIT",
        "AI",
        "SL",
        "TP",
        "BE",
        "OK",
        "PNL",
        "ADX",
        "RSI",
        "EMA",
        "ST",
        "LT",
        "HL",
        "UTC",
        "USD",
        "USDC",
        "THE",
        "AND",
        "FOR",
        "VIA",
        "WITH",
        "FROM",
        "NEXT",
        "LIVE",
        "SIZE",
        "TRACE",
        "TRADE",
        "MODE",
        "RISK",
        "CONF",
        "VOL",
    }
)

_BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

_ISO_RE = re.compile(
    r"\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:?\d{2})?"
)
_HMS_RE = re.compile(r"^(\d{2}:\d{2}:\d{2})\b")


def _parse_ts(value: Any) -> Optional[str]:
    """Normalize timestamps to ISO-8601 strings for stable sorting."""
    if value is None:
        return None
    if isinstance(value, float) and value != value:  # NaN
        return None
    if isinstance(value, (int, float)):
        try:
            return datetime.fromtimestamp(float(value), tz=timezone.utc).isoformat()
        except Exception:
            return str(value)
    s = str(value).strip()
    if not s or s.lower() in ("nan", "none", "nat"):
        return None
    # Already ISO-ish
    try:
        ts = pd_to_datetime(s)
        if ts is not None:
            return ts
    except Exception:
        pass
    return s or None


def pd_to_datetime(s: str) -> Optional[str]:
    try:
        import pandas as pd

        t = pd.to_datetime(s, utc=True, errors="coerce")
        if t is None or pd.isna(t):
            return None
        return t.isoformat()
    except Exception:
        return None


def _sort_key(ts: Optional[str]) -> str:
    """Sortable key: full ISO first; bare HH:MM:SS sorts last within day-less group."""
    if not ts:
        return ""
    if _ISO_RE.search(ts) or "T" in ts or len(ts) >= 10:
        return ts
    # Time-only → prefix so they don't interleave wrongly with ISO dates
    return f"0000-00-00T{ts}"


def _match_filters(
    event: Dict[str, Any],
    *,
    symbol: Optional[str],
    trade_id: Optional[str],
    trace_id: Optional[str],
) -> bool:
    if symbol and str(event.get("symbol") or "").upper() != symbol.upper():
        return False
    if trade_id and str(event.get("trade_id") or "") != str(trade_id):
        return False
    if trace_id and str(event.get("trace_id") or "") != str(trace_id):
        return False
    return True


def _load_json_list(path: str) -> List[Any]:
    if not path or not os.path.exists(path):
        return []
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, list):
            return data
        if isinstance(data, dict) and isinstance(data.get("history"), list):
            return data["history"]
        return []
    except Exception:
        return []


def _events_from_signal_analysis(path: str) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for row in _load_json_list(path):
        if not isinstance(row, dict):
            continue
        approved = row.get("approved")
        reasoning = row.get("reasoning") or ""
        # Skip synthetic "Entry filled" patches if any leftover duplicates
        if reasoning == "Entry filled on exchange":
            continue
        out.append(
            {
                "type": "ai_decision",
                "timestamp": _parse_ts(row.get("timestamp")),
                "symbol": row.get("symbol"),
                "trade_id": row.get("trade_id"),
                "trace_id": row.get("trace_id"),
                "strategy": row.get("strategy"),
                "direction": row.get("direction") or row.get("signal"),
                "approved": approved,
                "summary": (
                    f"AI {'APPROVED' if approved else 'REJECTED'}: "
                    f"{reasoning[:180]}"
                ),
                "payload": {
                    "confidence": row.get("confidence"),
                    "risk_level": row.get("risk_level"),
                    "rejection_reason_category": row.get("rejection_reason_category"),
                },
            }
        )
        if row.get("trace_id"):
            out.append(
                {
                    "type": "signal_detected",
                    "timestamp": _parse_ts(row.get("timestamp")),
                    "symbol": row.get("symbol"),
                    "trade_id": row.get("trade_id"),
                    "trace_id": row.get("trace_id"),
                    "strategy": row.get("strategy"),
                    "direction": row.get("direction"),
                    "summary": f"Signal {row.get('direction')} via {row.get('strategy')}",
                    "payload": {"market_price": row.get("market_price")},
                }
            )
    return out


def _row_get(row, *keys):
    for k in keys:
        if k in row.index if hasattr(row, "index") else k in row:
            v = row.get(k) if hasattr(row, "get") else row[k]
            if v is not None and str(v).strip() and str(v).lower() != "nan":
                return v
    return None


def _events_from_trade_history(csv_path: str) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    if not csv_path or not os.path.exists(csv_path):
        return out
    try:
        import pandas as pd

        df = pd.read_csv(csv_path)
    except Exception:
        return out
    for _, row in df.iterrows():
        try:
            symbol = _row_get(row, "symbol")
            exit_ts = _parse_ts(_row_get(row, "timestamp", "exit_time", "exit_timestamp"))
            entry_ts = _parse_ts(_row_get(row, "entry_time", "entry_timestamp"))
            trade_id = _row_get(row, "trade_id")
            trace_id = _row_get(row, "trace_id")
            side = _row_get(row, "side")
            strategy = _row_get(row, "strategy")

            out.append(
                {
                    "type": "exit",
                    "timestamp": exit_ts,
                    "symbol": symbol,
                    "trade_id": trade_id,
                    "trace_id": trace_id,
                    "strategy": strategy,
                    "direction": side,
                    "summary": (
                        f"Exit {side} {symbol} pnl={_row_get(row, 'pnl')} "
                        f"reason={_row_get(row, 'exit_reason')}"
                    ),
                    "payload": {
                        "entry_price": _row_get(row, "entry_price"),
                        "exit_price": _row_get(row, "exit_price"),
                        "pnl": _row_get(row, "pnl"),
                        "exit_reason": _row_get(row, "exit_reason"),
                    },
                }
            )
            # Entry: prefer real entry_time; otherwise omit fake same-as-exit stamp
            if entry_ts:
                out.append(
                    {
                        "type": "entry",
                        "timestamp": entry_ts,
                        "symbol": symbol,
                        "trade_id": trade_id,
                        "trace_id": trace_id,
                        "strategy": strategy,
                        "direction": side,
                        "summary": f"Entry {side} {symbol} @ {_row_get(row, 'entry_price')}",
                        "payload": {
                            "entry_price": _row_get(row, "entry_price"),
                            "size": _row_get(row, "size"),
                        },
                    }
                )
            elif _row_get(row, "entry_price") is not None:
                # Legacy CSV without entry_time — mark as approximate (sort near exit)
                out.append(
                    {
                        "type": "entry",
                        "timestamp": exit_ts,
                        "symbol": symbol,
                        "trade_id": trade_id,
                        "trace_id": trace_id,
                        "strategy": strategy,
                        "direction": side,
                        "summary": (
                            f"Entry {side} {symbol} @ {_row_get(row, 'entry_price')} "
                            f"(ts≈exit; legacy CSV)"
                        ),
                        "payload": {
                            "entry_price": _row_get(row, "entry_price"),
                            "size": _row_get(row, "size"),
                            "timestamp_approx": True,
                        },
                    }
                )
        except Exception:
            continue
    return out


def _extract_symbol(line: str) -> Optional[str]:
    for pat in _SYMBOL_HINTS:
        m = pat.search(line)
        if m:
            sym = m.group(1).upper()
            if sym not in _NOISE_TOKENS:
                return sym
    # Fallback: first non-noise uppercase token after stripping time prefix
    body = _HMS_RE.sub("", line).strip()
    for tok in re.findall(r"\b([A-Z]{2,10})\b", body):
        if tok not in _NOISE_TOKENS:
            return tok
    return None


def _extract_log_timestamp(line: str, file_mtime: Optional[float]) -> Optional[str]:
    iso = _ISO_RE.search(line)
    if iso:
        return _parse_ts(iso.group(0))
    m = _HMS_RE.match(line)
    if m and file_mtime:
        try:
            day = datetime.fromtimestamp(file_mtime, tz=timezone.utc).strftime("%Y-%m-%d")
            return _parse_ts(f"{day}T{m.group(1)}Z")
        except Exception:
            return m.group(1)
    if m:
        return m.group(1)
    return None


def _events_from_activity_log(path: str, limit_lines: int = 4000) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    if not path or not os.path.exists(path):
        return out
    try:
        file_mtime = os.path.getmtime(path)
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()[-limit_lines:]
    except Exception:
        return out

    tid_re = re.compile(r"(?:trade_id|id)=([A-Za-z0-9._\-]+)")
    trace_re = re.compile(r"trace=([A-Za-z0-9]+)")

    for line in lines:
        line = line.strip()
        if not line:
            continue
        etype = None
        for pat, name in _LOG_PATTERNS:
            if pat.search(line):
                etype = name
                break
        if not etype:
            continue
        ts = _extract_log_timestamp(line, file_mtime)
        tid_m = tid_re.search(line)
        trace_m = trace_re.search(line)
        symbol = _extract_symbol(line)
        summary = _HMS_RE.sub("", line).strip() if _HMS_RE.match(line) else line
        out.append(
            {
                "type": etype,
                "timestamp": ts,
                "symbol": symbol,
                "trade_id": tid_m.group(1) if tid_m else None,
                "trace_id": trace_m.group(1) if trace_m else None,
                "summary": summary,
                "payload": {"source": "activity_log"},
            }
        )
    return out


def build_timeline(
    *,
    symbol: Optional[str] = None,
    trade_id: Optional[str] = None,
    trace_id: Optional[str] = None,
    limit: int = 200,
    signal_analysis_path: Optional[str] = None,
    trade_history_path: Optional[str] = None,
    activity_log_path: Optional[str] = None,
) -> Dict[str, Any]:
    """Aggregate timeline events from local historization files."""
    limit = max(1, min(int(limit or 200), 1000))
    sa_path = signal_analysis_path or os.path.join(
        _BASE_DIR, "data", "analysis", "signal_analysis.json"
    )
    th_path = trade_history_path or os.path.join(_BASE_DIR, "data", "trade_history.csv")
    if not os.path.exists(th_path):
        alt = os.path.join(_BASE_DIR, "data", "state", "trade_history.csv")
        if os.path.exists(alt):
            th_path = alt
    al_path = activity_log_path or os.path.join(_BASE_DIR, "logs", "bot_activity.log")

    events: List[Dict[str, Any]] = []
    events.extend(_events_from_signal_analysis(sa_path))
    events.extend(_events_from_trade_history(th_path))
    events.extend(_events_from_activity_log(al_path))

    filtered = [
        e
        for e in events
        if e.get("type") in _EVENT_TYPES
        and _match_filters(e, symbol=symbol, trade_id=trade_id, trace_id=trace_id)
    ]

    filtered.sort(key=lambda e: _sort_key(e.get("timestamp")))
    if len(filtered) > limit:
        filtered = filtered[-limit:]

    return {
        "count": len(filtered),
        "limit": limit,
        "filters": {
            "symbol": symbol,
            "trade_id": trade_id,
            "trace_id": trace_id,
        },
        "events": filtered,
    }
