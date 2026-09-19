"""End-to-end live entry/exit/SL with a mocked Hyperliquid bulk_orders.

Goes through LiveExecutionMixin → HyperliquidService.execute_order →
exchange.bulk_orders. No trading loop, no AI, no real network.
"""
from __future__ import annotations

import threading
from unittest.mock import MagicMock, patch

import pytest

from app.core.bot import BotContext
from app.core.live_execution import LiveExecutionMixin
from app.core.trade_book import TradeBook
from app.services.hyperliquid_service import HyperliquidService


BTC_PX = 100_000.0
BTC_SZ = 0.01
BTC_SL = 97_000.0
BTC_TP = 105_000.0


def _filled_bulk(*, avg_px: float = 100_200.0, sl_error: str | None = None) -> dict:
    statuses = [
        {"filled": {"oid": 42, "totalSz": str(BTC_SZ), "avgPx": str(avg_px)}},
    ]
    if sl_error:
        statuses.append({"error": sl_error})
    else:
        statuses.append("waitingForTrigger")
        statuses.append("waitingForTrigger")
    return {"status": "ok", "response": {"data": {"statuses": statuses}}}


def _open_pos(*, entry: float = 100_200.0, size: float = BTC_SZ) -> dict:
    return {
        "symbol": "BTC",
        "size": size,
        "entry_price": entry,
        "leverage": 5,
        "side": "BUY",
    }


class _FakeBot(LiveExecutionMixin):
    """BotContext-shaped host without loop / AI / Discord scanner."""

    def __init__(self):
        self.trading_enabled = True
        self.execution_mode = "Live"
        self.trade_lock = threading.RLock()
        self.trade_book = TradeBook()
        self.active_symbol = "BTC"
        self.max_positions = 3
        self.logs: list[str] = []
        self.risk_manager = MagicMock()
        self.risk_manager.check_can_trade.return_value = (True, "")
        self.safe_order_manager = MagicMock()
        self.safe_order_manager.pre_validate_order.return_value = True
        self.trade_recorder = MagicMock()
        self._last_sltp_sync_time = None
        self._sltp_sync_cooldown = 60
        self.external_closures: list[tuple] = []

    def _is_live_execution(self) -> bool:
        return str(getattr(self, "execution_mode", "Live") or "Live").strip().lower() == "live"

    def add_log(self, msg, metadata=None):
        self.logs.append(str(msg))

    def _log_execution_error(self, title: str, **fields):
        self.logs.append(f"{title} | {fields.get('reason')}")

    def _sync_daily_risk_pnl(self, min_interval_sec: int = 0) -> None:
        return None

    def _resolve_trade_leverage(self, strategy_name=None) -> int:
        return 5

    def can_open_trade(self, symbol: str) -> tuple:
        return self.trade_book.can_open(
            symbol,
            max_positions=int(self.max_positions or 1),
            allow_same_symbol_concurrent=False,
        )

    def _new_trade_id(self, symbol: str) -> str:
        return f"{symbol}-test-id"

    @property
    def active_trades(self):
        return self.trade_book.as_symbol_mapping()

    @property
    def active_trade(self):
        return self.active_trades.get(self.active_symbol)

    @active_trade.setter
    def active_trade(self, value):
        if value is None:
            self.active_trades.pop(self.active_symbol, None)
        else:
            self.active_trades[self.active_symbol] = value

    def _sync_state(self, silent=True):
        return None

    def _handle_external_closure(self, symbol, trade, silent=True, position_confirmed_flat=False):
        self.external_closures.append((symbol, trade, silent))
        self.active_trades.pop(symbol, None)
        return True


def _hl_with_bulk(bulk_result, *, positions=None):
    """Real execute_order, mocked exchange.bulk_orders (no network)."""
    svc = object.__new__(HyperliquidService)
    svc.exchange = MagicMock()
    svc.exchange.bulk_orders.return_value = bulk_result
    svc.log_callback = lambda *a, **k: None
    svc.info = None
    svc._positions_fetch_failed = False
    svc._positions_stale = False
    svc._open_orders_fetch_failed = False
    svc.get_canonical_symbol = lambda symbol: str(symbol).replace("-USD", "").replace("-USDC", "")
    svc._get_precision = lambda symbol: (5, 1)
    svc.get_current_price = MagicMock(return_value=BTC_PX)
    svc._new_cloid = MagicMock(return_value="0x" + "ab" * 16)
    svc.cancel_all_orders = MagicMock()
    svc.close_position = MagicMock(return_value={"status": "success"})
    svc.confirm_or_place_sl = MagicMock(return_value=True)
    svc.sync_sl_tp = MagicMock()
    svc.get_open_orders = MagicMock(return_value=[])
    pos = positions if positions is not None else [_open_pos()]
    svc.get_positions = MagicMock(return_value=pos)
    return svc


@pytest.fixture
def no_sleep():
    with patch("time.sleep"), patch("app.core.live_execution.time.sleep"):
        yield


def _enter(bot, hl, **kwargs):
    defaults = dict(
        symbol="BTC",
        side="BUY",
        size=BTC_SZ,
        price=BTC_PX,
        sl=BTC_SL,
        tp=BTC_TP,
        strategy="supertrend",
    )
    defaults.update(kwargs)
    with patch("app.core.live_execution.hyperliquid_service", hl), patch(
        "app.core.live_execution.StateManager.save_state"
    ), patch("app.core.live_execution.discord_service"):
        return bot.execute_entry_atomically(**defaults)


def test_botcontext_exposes_live_mixin():
    assert issubclass(BotContext, LiveExecutionMixin)
    assert BotContext.execute_entry_atomically is LiveExecutionMixin.execute_entry_atomically


def test_live_entry_calls_bulk_orders_once_with_ioc_sl_tp(no_sleep):
    hl = _hl_with_bulk(_filled_bulk())
    bot = _FakeBot()
    ok = _enter(bot, hl)

    assert ok is True
    hl.exchange.bulk_orders.assert_called_once()
    orders, kwargs = hl.exchange.bulk_orders.call_args.args[0], hl.exchange.bulk_orders.call_args.kwargs
    if not kwargs:
        # grouping may be positional
        grouping = hl.exchange.bulk_orders.call_args.args[1] if len(hl.exchange.bulk_orders.call_args.args) > 1 else None
    else:
        grouping = kwargs.get("grouping")
    assert grouping == "normalTpsl"
    assert len(orders) == 3

    entry, sl, tp = orders
    assert entry["coin"] == "BTC"
    assert entry["is_buy"] is True
    assert entry["reduce_only"] is False
    assert entry["order_type"] == {"limit": {"tif": "Ioc"}}
    assert entry["cloid"] == "0x" + "ab" * 16
    # 0.8% IOC cap on BTC
    assert entry["limit_px"] == pytest.approx(BTC_PX * 1.008, rel=1e-5)

    assert sl["reduce_only"] is True
    assert sl["is_buy"] is False
    assert sl["order_type"]["trigger"]["tpsl"] == "sl"
    assert sl["order_type"]["trigger"]["isMarket"] is True
    assert sl["order_type"]["trigger"]["triggerPx"] == pytest.approx(BTC_SL, rel=1e-5)

    assert tp["reduce_only"] is True
    assert tp["order_type"]["trigger"]["tpsl"] == "tp"

    hl.confirm_or_place_sl.assert_called_once()
    booked = bot.active_trades.get("BTC")
    assert booked is not None
    assert booked["side"] == "BUY"
    assert booked["size"] == BTC_SZ
    assert booked["sl"] == BTC_SL
    hl.close_position.assert_not_called()
    bot.risk_manager.record_trade_open.assert_called_once()


def test_fill_plus_sl_reject_does_not_retry_bulk_orders(no_sleep):
    hl = _hl_with_bulk(_filled_bulk(sl_error="Insufficient margin for trigger"))
    bot = _FakeBot()
    ok = _enter(bot, hl)

    assert ok is True
    assert hl.exchange.bulk_orders.call_count == 1
    booked = bot.active_trades.get("BTC")
    assert booked is not None
    hl.confirm_or_place_sl.assert_called_once()


def test_dry_run_never_calls_bulk_orders(no_sleep):
    hl = _hl_with_bulk(_filled_bulk())
    bot = _FakeBot()
    bot.execution_mode = "Dry Run"
    result = _enter(bot, hl)
    assert result["status"] == "ignored"
    hl.exchange.bulk_orders.assert_not_called()
    assert "BTC" not in bot.active_trades


def test_missing_sl_never_calls_bulk_orders(no_sleep):
    hl = _hl_with_bulk(_filled_bulk())
    bot = _FakeBot()
    result = _enter(bot, hl, sl=0)
    assert result is False
    hl.exchange.bulk_orders.assert_not_called()


def test_stale_positions_never_calls_bulk_orders(no_sleep):
    hl = _hl_with_bulk(_filled_bulk(), positions=[])
    hl._positions_stale = True
    bot = _FakeBot()
    result = _enter(bot, hl)
    assert result is False
    hl.exchange.bulk_orders.assert_not_called()


def test_wrong_side_sl_never_calls_bulk_orders(no_sleep):
    hl = _hl_with_bulk(_filled_bulk())
    bot = _FakeBot()
    result = _enter(bot, hl, sl=105_000.0)  # SL above entry on a BUY
    assert result is False
    hl.exchange.bulk_orders.assert_not_called()


def test_fill_slippage_abort_closes_and_does_not_book(no_sleep):
    # 2.5% fill vs 0.8% cfg (abort > max(1.6%, 1.5%))
    hl = _hl_with_bulk(_filled_bulk(avg_px=102_500.0), positions=[_open_pos(entry=102_500.0)])
    bot = _FakeBot()
    result = _enter(bot, hl)
    assert result is False
    hl.exchange.bulk_orders.assert_called_once()
    hl.close_position.assert_called_once_with("BTC")
    assert "BTC" not in bot.active_trades


def test_missing_sl_after_fill_panic_closes(no_sleep):
    hl = _hl_with_bulk(_filled_bulk())
    hl.confirm_or_place_sl.return_value = False
    bot = _FakeBot()
    result = _enter(bot, hl)
    assert result is False
    hl.close_position.assert_called_once_with("BTC")
    assert "BTC" not in bot.active_trades


def test_orders_api_down_after_fill_keeps_position(no_sleep):
    hl = _hl_with_bulk(_filled_bulk())
    hl.confirm_or_place_sl.return_value = None
    bot = _FakeBot()
    result = _enter(bot, hl)
    assert result is True
    hl.close_position.assert_not_called()
    assert bot.active_trades.get("BTC") is not None


def test_exit_refuses_stale_snapshot():
    hl = _hl_with_bulk(_filled_bulk(), positions=[_open_pos()])
    hl._positions_stale = True
    bot = _FakeBot()
    with patch("app.core.live_execution.hyperliquid_service", hl):
        assert bot.execute_exit_atomically("BTC") is False
    hl.close_position.assert_not_called()


def test_exit_market_closes_then_drops_book(no_sleep):
    open_pos = _open_pos()
    hl = _hl_with_bulk(_filled_bulk())
    hl.get_positions.side_effect = [
        [open_pos],  # verify exists
        [open_pos],  # snapshot before close
        [{"symbol": "BTC", "size": 0, "entry_price": BTC_PX, "side": "BUY"}],
    ]
    hl.close_position.return_value = {"status": "success"}
    bot = _FakeBot()
    bot.active_symbol = "BTC"
    bot.active_trade = {
        "trade_id": "BTC-test-id",
        "symbol": "BTC",
        "side": "BUY",
        "entry": 100_200.0,
        "sl": BTC_SL,
        "tp": BTC_TP,
        "size": BTC_SZ,
        "strategy": "supertrend",
        "metadata": {},
    }
    with patch("app.core.live_execution.hyperliquid_service", hl), patch(
        "app.core.live_execution.StateManager.save_state"
    ), patch("app.core.live_execution.discord_service"):
        assert bot.execute_exit_atomically("BTC", "SIGNAL") is True
    hl.close_position.assert_called_once_with("BTC")
    assert "BTC" not in bot.active_trades
    bot.trade_recorder.add_trade.assert_called_once()


def test_local_exit_zero_price_does_not_close():
    hl = _hl_with_bulk(_filled_bulk(), positions=[_open_pos()])
    bot = _FakeBot()
    bot.execute_exit_atomically = MagicMock()
    trade = {"symbol": "BTC", "side": "SELL", "sl": 110_000.0, "tp": 90_000.0}
    with patch("app.core.live_execution.hyperliquid_service", hl):
        bot._check_local_exits(trade, "BTC", 0)
    bot.execute_exit_atomically.assert_not_called()
    hl.close_position.assert_not_called()


def test_local_sl_hit_calls_exit_when_still_open():
    hl = _hl_with_bulk(_filled_bulk(), positions=[_open_pos()])
    bot = _FakeBot()
    bot.execute_exit_atomically = MagicMock(return_value=True)
    trade = {"symbol": "BTC", "side": "BUY", "sl": BTC_SL, "tp": BTC_TP, "trade_id": "t1"}
    with patch("app.core.live_execution.hyperliquid_service", hl):
        bot._check_local_exits(trade, "BTC", 96_000.0)
    bot.execute_exit_atomically.assert_called_once_with("BTC", "STOP_LOSS")


def test_local_sl_hit_ignored_when_positions_api_down():
    hl = _hl_with_bulk(_filled_bulk(), positions=[_open_pos()])
    hl._positions_fetch_failed = True
    bot = _FakeBot()
    bot.execute_exit_atomically = MagicMock()
    trade = {"symbol": "BTC", "side": "BUY", "sl": BTC_SL, "tp": BTC_TP}
    with patch("app.core.live_execution.hyperliquid_service", hl):
        bot._check_local_exits(trade, "BTC", 96_000.0)
    bot.execute_exit_atomically.assert_not_called()


def test_verify_enforces_missing_sl():
    hl = _hl_with_bulk(_filled_bulk())
    hl.get_open_orders.return_value = []
    bot = _FakeBot()
    trade = {"symbol": "BTC", "side": "BUY", "sl": BTC_SL, "tp": BTC_TP, "size": BTC_SZ, "entry": BTC_PX}
    with patch("app.core.live_execution.hyperliquid_service", hl):
        bot._verify_and_enforce_sl_tp("BTC", trade, bypass_cooldown=True)
    hl.sync_sl_tp.assert_called_once()
    args, kwargs = hl.sync_sl_tp.call_args
    assert args[0] == "BTC"
    assert args[1] is True
    assert args[3] == BTC_SL


def test_verify_skips_when_trading_disabled():
    hl = _hl_with_bulk(_filled_bulk())
    bot = _FakeBot()
    bot.trading_enabled = False
    with patch("app.core.live_execution.hyperliquid_service", hl):
        bot._verify_and_enforce_sl_tp("BTC", {"sl": BTC_SL, "tp": BTC_TP}, bypass_cooldown=True)
    hl.get_open_orders.assert_not_called()
    hl.sync_sl_tp.assert_not_called()
