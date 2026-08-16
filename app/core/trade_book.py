"""
Multi-position trade book.

Internal key = trade_id. Symbol index is secondary (HL nets one position per coin).
Policy allow_same_symbol_concurrent=False (default) keeps at most one open trade per symbol.
"""
from __future__ import annotations

import time
import uuid
from typing import Dict, Iterable, List, Optional, Set, Tuple


class TradeBook:
    """Thread-unsafe container — callers must hold BotContext.trade_lock."""

    def __init__(self) -> None:
        self._by_id: Dict[str, dict] = {}
        self._by_symbol: Dict[str, Set[str]] = {}

    def __len__(self) -> int:
        return len(self._by_id)

    def __bool__(self) -> bool:
        return bool(self._by_id)

    def clear(self) -> None:
        self._by_id.clear()
        self._by_symbol.clear()

    @staticmethod
    def new_trade_id(symbol: str) -> str:
        return f"{symbol}-{int(time.time())}-{uuid.uuid4().hex[:8]}"

    def all_trades(self) -> List[dict]:
        return list(self._by_id.values())

    def trade_ids(self) -> List[str]:
        return list(self._by_id.keys())

    def get(self, trade_id: str) -> Optional[dict]:
        return self._by_id.get(trade_id)

    def get_for_symbol(self, symbol: str) -> List[dict]:
        ids = self._by_symbol.get(symbol) or set()
        return [self._by_id[i] for i in ids if i in self._by_id]

    def primary_for_symbol(self, symbol: str) -> Optional[dict]:
        """First open trade for symbol (HL 1-pos policy → at most one)."""
        trades = self.get_for_symbol(symbol)
        return trades[0] if trades else None

    def symbols(self) -> List[str]:
        return list(self._by_symbol.keys())

    def has_symbol(self, symbol: str) -> bool:
        return bool(self._by_symbol.get(symbol))

    def can_open(
        self,
        symbol: str,
        *,
        max_positions: int = 1,
        allow_same_symbol_concurrent: bool = False,
    ) -> Tuple[bool, str]:
        max_positions = max(1, int(max_positions or 1))
        if len(self._by_id) >= max_positions:
            return False, f"max_positions reached ({len(self._by_id)}/{max_positions})"
        if not allow_same_symbol_concurrent and self.has_symbol(symbol):
            return False, f"symbol {symbol} already has an open trade"
        return True, "ok"

    def add(self, trade: dict, *, trade_id: Optional[str] = None) -> str:
        """Insert or replace by trade_id. Returns trade_id."""
        if not isinstance(trade, dict):
            raise TypeError("trade must be a dict")
        symbol = str(trade.get("symbol") or "")
        if not symbol:
            raise ValueError("trade.symbol required")
        tid = trade_id or trade.get("trade_id") or self.new_trade_id(symbol)
        trade = dict(trade)
        trade["trade_id"] = tid
        trade["symbol"] = symbol

        old = self._by_id.get(tid)
        if old is not None:
            self._unlink_symbol(old.get("symbol"), tid)

        self._by_id[tid] = trade
        self._by_symbol.setdefault(symbol, set()).add(tid)
        return tid

    def pop(
        self,
        *,
        trade_id: Optional[str] = None,
        symbol: Optional[str] = None,
    ) -> Optional[dict]:
        if trade_id:
            trade = self._by_id.pop(trade_id, None)
            if trade:
                self._unlink_symbol(trade.get("symbol"), trade_id)
            return trade
        if symbol:
            trade = self.primary_for_symbol(symbol)
            if not trade:
                return None
            return self.pop(trade_id=trade.get("trade_id"))
        return None

    def _unlink_symbol(self, symbol: Optional[str], trade_id: str) -> None:
        if not symbol:
            return
        ids = self._by_symbol.get(symbol)
        if not ids:
            return
        ids.discard(trade_id)
        if not ids:
            self._by_symbol.pop(symbol, None)

    def replace_all(self, trades: Iterable[dict]) -> None:
        self.clear()
        for t in trades:
            if isinstance(t, dict) and t.get("symbol"):
                self.add(t)

    def to_persist_dict(self) -> Dict[str, dict]:
        """Persist as trade_id → trade."""
        return {tid: dict(t) for tid, t in self._by_id.items()}

    def to_symbol_dict(self) -> Dict[str, dict]:
        """Legacy view: symbol → primary trade (shared refs)."""
        out: Dict[str, dict] = {}
        for sym, ids in self._by_symbol.items():
            for tid in ids:
                t = self._by_id.get(tid)
                if t is not None:
                    out[sym] = t
                    break
        return out

    def as_symbol_mapping(self) -> "_SymbolTradeMapping":
        return _SymbolTradeMapping(self)

    @classmethod
    def from_persist(cls, raw) -> "TradeBook":
        """
        Load from state.

        Accepts:
        - New format: {trade_id: trade_dict}
        - Legacy format: {symbol: trade_dict}
        """
        book = cls()
        if not isinstance(raw, dict) or not raw:
            return book
        for key, trade in raw.items():
            if not isinstance(trade, dict):
                continue
            t = dict(trade)
            if not t.get("symbol"):
                if "side" in t or "entry" in t or "entry_price" in t:
                    t["symbol"] = key
                else:
                    continue
            tid = t.get("trade_id")
            if not tid:
                # Legacy symbol-keyed map
                if key == t.get("symbol"):
                    tid = cls.new_trade_id(t["symbol"])
                else:
                    # Already keyed by trade_id but field missing
                    tid = str(key)
                t["trade_id"] = tid
            book.add(t, trade_id=t["trade_id"])
        return book


class _SymbolTradeMapping:
    """Dict-like facade: symbol → primary trade (shared dict refs)."""

    def __init__(self, book: TradeBook) -> None:
        self._book = book

    def get(self, symbol, default=None):
        t = self._book.primary_for_symbol(symbol)
        return t if t is not None else default

    def __getitem__(self, symbol):
        t = self._book.primary_for_symbol(symbol)
        if t is None:
            raise KeyError(symbol)
        return t

    def __setitem__(self, symbol, trade):
        if trade is None:
            self.pop(symbol, None)
            return
        t = dict(trade)
        t["symbol"] = symbol
        existing = self._book.primary_for_symbol(symbol)
        if existing and existing.get("trade_id") and existing.get("trade_id") == t.get("trade_id"):
            self._book.add(t, trade_id=t["trade_id"])
            return
        if existing:
            self._book.pop(trade_id=existing.get("trade_id"))
        self._book.add(t)

    def pop(self, symbol, default=None):
        t = self._book.pop(symbol=symbol)
        return t if t is not None else default

    def values(self):
        return list(self._book.to_symbol_dict().values())

    def keys(self):
        return list(self._book.to_symbol_dict().keys())

    def items(self):
        return list(self._book.to_symbol_dict().items())

    def __len__(self):
        return len(self._book)

    def __bool__(self):
        return bool(self._book)

    def __contains__(self, symbol):
        return self._book.has_symbol(symbol)

    def __iter__(self):
        return iter(self.keys())

    def clear(self):
        self._book.clear()

    def copy(self):
        return dict(self.items())
