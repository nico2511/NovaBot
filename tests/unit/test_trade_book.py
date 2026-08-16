"""TradeBook multi-position bookkeeping."""
from __future__ import annotations

from app.core.trade_book import TradeBook


def _trade(symbol: str, side: str = "BUY", trade_id: str | None = None) -> dict:
    t = {"symbol": symbol, "side": side, "entry": 1.0, "sl": 0.9, "tp": 1.2}
    if trade_id:
        t["trade_id"] = trade_id
    return t


def test_two_symbols_open():
    book = TradeBook()
    book.add(_trade("ETH"))
    book.add(_trade("SOL"))
    assert len(book) == 2
    assert set(book.symbols()) == {"ETH", "SOL"}
    assert book.primary_for_symbol("ETH")["symbol"] == "ETH"
    assert book.primary_for_symbol("SOL")["symbol"] == "SOL"


def test_refuse_same_symbol_when_policy_blocks():
    book = TradeBook()
    book.add(_trade("ETH"))
    ok, reason = book.can_open("ETH", max_positions=3, allow_same_symbol_concurrent=False)
    assert ok is False
    assert "already" in reason.lower() or "ETH" in reason


def test_allow_same_symbol_when_policy_permits():
    book = TradeBook()
    book.add(_trade("ETH"))
    ok, _ = book.can_open("ETH", max_positions=3, allow_same_symbol_concurrent=True)
    assert ok is True


def test_refuse_when_max_positions_reached():
    book = TradeBook()
    book.add(_trade("ETH"))
    ok, reason = book.can_open("SOL", max_positions=1, allow_same_symbol_concurrent=False)
    assert ok is False
    assert "max_positions" in reason


def test_symbol_mapping_legacy_api():
    book = TradeBook()
    book.add(_trade("BTC", trade_id="BTC-1"))
    m = book.as_symbol_mapping()
    assert "BTC" in m
    assert m.get("BTC")["trade_id"] == "BTC-1"
    m["ETH"] = _trade("ETH", trade_id="ETH-1")
    assert len(book) == 2
    popped = m.pop("BTC")
    assert popped["trade_id"] == "BTC-1"
    assert len(book) == 1


def test_persist_roundtrip_trade_id_keys():
    book = TradeBook()
    book.add(_trade("LINK", trade_id="LINK-abc"))
    raw = book.to_persist_dict()
    assert "LINK-abc" in raw
    restored = TradeBook.from_persist(raw)
    assert len(restored) == 1
    assert restored.get("LINK-abc")["symbol"] == "LINK"


def test_migrate_legacy_symbol_keyed_persist():
    legacy = {"AVAX": {"symbol": "AVAX", "side": "SELL", "entry": 10.0}}
    book = TradeBook.from_persist(legacy)
    assert len(book) == 1
    t = book.primary_for_symbol("AVAX")
    assert t is not None
    assert t.get("trade_id")
