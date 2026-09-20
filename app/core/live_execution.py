"""Live entry / exit / SL enforcement — the money path.

Extracted from BotContext so the Hyperliquid order sequence can be unit-tested
with a mocked ``bulk_orders`` without booting the trading loop, AI, Discord
scanner, or adoption. Behavior is a mechanical move: BotContext inherits
``LiveExecutionMixin`` and keeps the same method names.

``trading_loop``, thesis, Discord, scanner, and adoption stay in ``bot.py``.
"""
from __future__ import annotations

import time

import pandas as pd

from app.core.live_guards import (
    clamp_sl_inside_liquidation,
    entry_slippage_for_symbol,
    fill_slippage_breached,
)
from app.core.state_manager import StateManager
from app.services.discord_service import discord_service
from app.services.hyperliquid_service import hyperliquid_service


class LiveExecutionMixin:
    """Atomic entry/exit and local SL backstop. Host must be a BotContext-like."""

    def execute_entry_atomically(self, symbol: str, side: str, size: float, price: float = None, sl: float = None, tp: float = None, strategy: str = "Unknown", metadata: dict = None, entry_indicators: dict = None, equity: float = None):
        """ATOMIC ENTRY FLOW (Unified v2) - Now captures entry indicators for analysis"""
        ctx = dict(
            symbol=symbol,
            side=side,
            strategy=strategy,
            size=size,
            price=price,
            sl=sl,
            tp=tp,
            equity=equity,
        )
        try:
            # 1. LIVE EXECUTION CHECK
            if not self.trading_enabled:
                reason = "Trading Disabled"
                self.add_log(f"⚠️ Signal ignored ({reason}): {side} {symbol}")
                self._log_execution_error(f"⛔ ENTRY BLOCKED: {side} {symbol}", reason=reason, **ctx)
                return { "status": "ignored", "reason": reason }

            mode = str(getattr(self, "execution_mode", "Live") or "Live").strip()
            if not self._is_live_execution():
                reason = f"Execution mode is {mode} (not Live)"
                self.add_log(f"🧪 DRY-RUN: would {side} {symbol} size={size} — live order blocked")
                self._log_execution_error(f"⛔ ENTRY BLOCKED: {side} {symbol}", reason=reason, **ctx)
                return {"status": "ignored", "reason": reason}

            self._sync_daily_risk_pnl(min_interval_sec=0)
            can_trade, risk_reason = self.risk_manager.check_can_trade()
            if not can_trade:
                self.add_log(f"⛔ ENTRY BLOCKED by risk: {risk_reason}")
                self._log_execution_error(
                    f"⛔ ENTRY BLOCKED: {side} {symbol}",
                    reason=risk_reason,
                    **ctx,
                )
                return {"status": "ignored", "reason": risk_reason}

            current_price = price if price else hyperliquid_service.get_current_price(symbol)
            ctx["price"] = current_price

            # Pre-check rounding (same rules as Hyperliquid execute_order)
            canonical = hyperliquid_service.get_canonical_symbol(symbol)
            sz_decimals, _ = hyperliquid_service._get_precision(canonical)
            if sz_decimals == 0:
                rounded_size = int(size)
            else:
                rounded_size = round(size, sz_decimals)
            if rounded_size <= 0:
                reason = f"Quantity rounds to zero (raw={size}, sz_decimals={sz_decimals})"
                self.add_log(f"❌ Entry Failed: {reason}")
                self._log_execution_error(
                    f"❌ ENTRY FAILED: {side} {symbol}",
                    reason=reason,
                    equity=equity,
                    **{k: v for k, v in ctx.items() if k != "equity"},
                )
                return False

            lev = self._resolve_trade_leverage(None if strategy == "Unknown" else strategy)
            if not self.safe_order_manager.pre_validate_order(
                symbol,
                rounded_size,
                side,
                price=current_price,
                leverage=lev,
            ):
                reason = "pre_validate_order failed (withdrawable/margin)"
                self.add_log(f"⛔ ENTRY BLOCKED: {reason}")
                self._log_execution_error(
                    f"⛔ ENTRY BLOCKED: {side} {symbol}",
                    reason=reason,
                    equity=equity,
                    **{k: v for k, v in ctx.items() if k != "equity"},
                )
                return False

            # REAL EXECUTION
            real_positions = hyperliquid_service.get_positions()
            if getattr(hyperliquid_service, "_positions_fetch_failed", False) is True:
                reason = "Positions API unavailable — refusing new entry"
                self.add_log(f"⛔ {reason}")
                self._log_execution_error(
                    f"⛔ ENTRY BLOCKED: {side} {symbol}",
                    reason=reason,
                    equity=equity,
                    **{k: v for k, v in ctx.items() if k != "equity"},
                )
                return False
            if getattr(hyperliquid_service, "_positions_stale", False) is True:
                reason = "Positions snapshot is stale — refusing new entry"
                self.add_log(f"⛔ {reason}")
                self._log_execution_error(
                    f"⛔ ENTRY BLOCKED: {side} {symbol}",
                    reason=reason,
                    equity=equity,
                    **{k: v for k, v in ctx.items() if k != "equity"},
                )
                return False
            active_count = len([p for p in real_positions if float(p["size"]) > 0])

            if active_count >= self.max_positions:
                reason = f"Max positions reached ({active_count}/{self.max_positions})"
                self.add_log(f"⛔ QUOTA EXCEEDED ({active_count}/{self.max_positions}). Entry aborted.")
                self._log_execution_error(
                    f"⛔ ENTRY BLOCKED: {side} {symbol}",
                    reason=reason,
                    equity=equity,
                    **{k: v for k, v in ctx.items() if k != "equity"},
                )
                return False

            ok_book, book_reason = self.can_open_trade(symbol)
            if not ok_book:
                reason = book_reason
                self.add_log(f"⛔ ENTRY BLOCKED (book): {reason}")
                self._log_execution_error(
                    f"⛔ ENTRY BLOCKED: {side} {symbol}",
                    reason=reason,
                    equity=equity,
                    **{k: v for k, v in ctx.items() if k != "equity"},
                )
                return False

            if sl is None or float(sl or 0) <= 0:
                reason = "Live entry requires an exchange SL"
                self.add_log(f"⛔ ENTRY BLOCKED: {reason}")
                self._log_execution_error(
                    f"⛔ ENTRY BLOCKED: {side} {symbol}",
                    reason=reason,
                    equity=equity,
                    **{k: v for k, v in ctx.items() if k != "equity"},
                )
                return False

            try:
                lev = self._resolve_trade_leverage(None if strategy == "Unknown" else strategy)
                new_sl, sl_note = clamp_sl_inside_liquidation(
                    side=side,
                    entry=float(current_price or 0),
                    sl=float(sl),
                    leverage=int(lev or 1),
                )
                if new_sl is None:
                    reason = sl_note or "SL failed liquidation guard"
                    self.add_log(f"⛔ ENTRY BLOCKED: {reason}")
                    self._log_execution_error(
                        f"⛔ ENTRY BLOCKED: {side} {symbol}",
                        reason=reason,
                        equity=equity,
                        **{k: v for k, v in ctx.items() if k != "equity"},
                    )
                    return False
                if sl_note:
                    self.add_log(f"🛡️ LIQUIDATION GUARD: {sl_note}")
                    sl = new_sl
                    ctx["sl"] = sl
            except Exception as liq_err:
                reason = f"Liquidation guard error: {liq_err}"
                self.add_log(f"⛔ ENTRY BLOCKED: {reason}")
                self._log_execution_error(
                    f"⛔ ENTRY BLOCKED: {side} {symbol}",
                    reason=reason,
                    equity=equity,
                    **{k: v for k, v in ctx.items() if k != "equity"},
                )
                return False

            self.add_log(f"🔒 ATOMIC ENTRY START: {side} {symbol} ({size}) via {strategy}")
            self.add_log(f"🧹 Cleaning pre-trade orphans on {symbol}...")
            hyperliquid_service.cancel_all_orders(symbol)

            is_buy = (side == "BUY")
            result = hyperliquid_service.execute_order(
                symbol=symbol, is_buy=is_buy, quantity=size, price=price, sl_price=sl, tp_price=tp
            )

            if result.get("status") != "success":
                reason = result.get("message", "Unknown exchange error")
                self.add_log(f"❌ Entry Failed: {reason}")
                self._log_execution_error(
                    f"❌ ENTRY FAILED: {side} {symbol}",
                    reason=reason,
                    equity=equity,
                    rounded_size=rounded_size,
                    sz_decimals=sz_decimals,
                    **{k: v for k, v in ctx.items() if k not in ("equity",)},
                )
                return False

            self.add_log("⏳ Verifying Fill...")
            filled = False
            oid = "unknown"

            try:
                raw_res = result.get("result", {})
                statuses = raw_res.get("response", {}).get("data", {}).get("statuses", [])
                if statuses and isinstance(statuses[0], dict):
                     oid = statuses[0].get("oid") or statuses[0].get("filled", {}).get("oid") or oid
            except: pass

            for i in range(5):
                time.sleep(1)
                positions = hyperliquid_service.get_positions()
                pos = next((p for p in positions if p["symbol"] == symbol and float(p['size']) > 0), None)
                if pos:
                    filled = True
                    entry_px = float(pos['entry_price'])
                    self.add_log(f"✅ ENTRY CONFIRMED: {symbol} Size: {pos['size']} Entry: {entry_px}")
                    filled_sz = float(pos["size"])

                    avg_px = float(result.get("avg_px") or entry_px or 0)
                    slip_cfg = entry_slippage_for_symbol(symbol)
                    breached, slip_frac = fill_slippage_breached(current_price, avg_px, slip_cfg)
                    if breached:
                        reason = (
                            f"Fill slippage {slip_frac:.2%} exceeds cap "
                            f"(signal={current_price}, avg={avg_px})"
                        )
                        self.add_log(f"⛔ SLIPPAGE ABORT: {reason} — closing {symbol}")
                        try:
                            hyperliquid_service.close_position(symbol)
                        except Exception as close_err:
                            self.add_log(f"❌ Slippage abort close failed: {close_err}")
                        self._log_execution_error(
                            f"⛔ SLIPPAGE ABORT: {side} {symbol}",
                            reason=reason,
                            equity=equity,
                            **{k: v for k, v in ctx.items() if k != "equity"},
                        )
                        return False

                    sl_state = hyperliquid_service.confirm_or_place_sl(
                        symbol,
                        is_buy,
                        filled_sz,
                        float(sl),
                        tp_price=float(tp) if tp else None,
                        entry=entry_px,
                    )
                    if sl_state is False:
                        reason = "SL missing on exchange after fill — closing to avoid naked position"
                        self.add_log(f"⛔ {reason}")
                        try:
                            hyperliquid_service.close_position(symbol)
                        except Exception as close_err:
                            self.add_log(f"❌ Missing-SL close failed: {close_err}")
                        self._log_execution_error(
                            f"⛔ MISSING SL: {side} {symbol}",
                            reason=reason,
                            equity=equity,
                            **{k: v for k, v in ctx.items() if k != "equity"},
                        )
                        return False
                    if sl_state is None:
                        self.add_log(
                            f"⚠️ SL unconfirmed for {symbol} (orders API down) — "
                            "leaving position; reconciler will retry"
                        )

                    with self.trade_lock:
                        # CRITICAL: Always sync active_symbol before setting active_trade
                        # otherwise the setter will use the WRONG key in active_trades
                        if self.active_symbol != symbol:
                            self.active_symbol = symbol

                        trade_id = self._new_trade_id(symbol)
                        self.active_trade = {
                            "trade_id": trade_id,
                            "symbol": symbol,
                            "side": side,
                            "entry": entry_px,
                            "sl": sl,
                            "initial_sl": sl,
                            "tp": tp,
                            "strategy": strategy,
                            "timestamp": pd.Timestamp.now().isoformat(),
                            "size": float(pos['size']),
                            "leverage": float(pos.get("leverage", 1.0)),
                            "oid": oid,
                            "pnl": 0,
                            "max_pnl": 0,
                            "metadata": metadata or {},
                            "entry_indicators": entry_indicators or {}  # Market snapshot at entry
                        }
                        self.risk_manager.record_trade_open()
                        StateManager.save_state(self)
                        # Force Sync to ensure state consistency
                        self._sync_state(silent=False)


                    discord_service.send_alert(
                        f"🚀 ENTERED {side} {symbol}",
                        f"Strategy: {strategy}\nEntry: {entry_px}\nSize: {pos['size']}\nSL: {sl}\nTP: {tp}\nOID: {oid}",
                        color="00FF00" if side == "BUY" else "FF0000"
                    )
                    break

            if not filled:
                reason = "Order sent but position NOT confirmed after 5s"
                self.add_log(f"⚠️ {reason}.")
                self._log_execution_error(
                    f"⚠️ ENTRY UNCONFIRMED: {side} {symbol}",
                    reason=reason,
                    oid=oid,
                    equity=equity,
                    **{k: v for k, v in ctx.items() if k != "equity"},
                )
                return False

            return True

        except Exception as e:
            self.add_log(f"❌ ATOMIC ENTRY ERROR: {e}")
            self._log_execution_error(
                f"❌ ENTRY CRASH: {side} {symbol}",
                reason=str(e),
                equity=equity,
                **{k: v for k, v in ctx.items() if k != "equity"},
            )
            return False

    def execute_exit_atomically(self, symbol: str, reason: str = "SIGNAL"):
        """ATOMIC EXIT FLOW (THE KILL SWITCH)"""
        # Verify position exists before attempting to close
        try:
            positions = hyperliquid_service.get_positions()
            if getattr(hyperliquid_service, "_positions_fetch_failed", False) is True:
                self.add_log(
                    f"⛔ Cannot close {symbol}: positions API unavailable — "
                    f"aborting market close (exchange SL/TP stay in place)"
                )
                return False
            if getattr(hyperliquid_service, "_positions_stale", False) is True:
                self.add_log(
                    f"⛔ Cannot close {symbol}: positions snapshot is stale — "
                    f"aborting market close (exchange SL/TP stay in place)"
                )
                return False
            position_exists = any(p.get("symbol") == symbol and float(p.get("size", 0)) > 0 for p in positions)

            if not position_exists:
                self.add_log(f"⚠️ Cannot close {symbol}: No open position found on exchange.")
                # Only drop memory after a confirmed Close fill — never on a bare empty book
                trade = None
                with self.trade_lock:
                    trade = self.active_trades.get(symbol)
                if trade:
                    self._handle_external_closure(symbol, trade, silent=True)
                return False
        except Exception as e:
            self.add_log(
                f"⛔ Failed to verify position for {symbol}: {e} — "
                f"aborting market close (exchange SL/TP stay in place)"
            )
            return False

        tid = None
        try:
            with self.trade_lock:
                t = self.active_trades.get(symbol)
                tid = t.get("trade_id") if isinstance(t, dict) else None
        except Exception:
            tid = None
        self.add_log(f"🔒 ATOMIC EXIT START: Closing {symbol} ({reason})" + (f" | id={tid}" if tid else ""))

        # Get position data BEFORE closing for accurate PnL calculation
        positions_before = hyperliquid_service.get_positions()
        if getattr(hyperliquid_service, "_positions_fetch_failed", False) is True:
            self.add_log(
                f"⛔ ATOMIC EXIT aborted for {symbol}: positions API unavailable — "
                f"will not market-close (exchange SL/TP remain in place)"
                + (f" | id={tid}" if tid else "")
            )
            return False
        if getattr(hyperliquid_service, "_positions_stale", False) is True:
            self.add_log(
                f"⛔ ATOMIC EXIT aborted for {symbol}: positions snapshot is stale — "
                f"will not market-close (exchange SL/TP remain in place)"
                + (f" | id={tid}" if tid else "")
            )
            return False
        position_data = next((p for p in positions_before if p["symbol"] == symbol), None)

        if not position_data:
            # Flat book from a *successful* fetch — nothing to market-close
            self.add_log(
                f"⚠️ No open position for {symbol} on exchange — skip market close"
                + (f" | id={tid}" if tid else "")
            )
            trade = None
            with self.trade_lock:
                trade = self.active_trades.get(symbol)
            if trade:
                self._handle_external_closure(symbol, trade, silent=True)
            return False

        try:
            result = hyperliquid_service.close_position(symbol)

            if result.get("status") == "success":
                final_positions = hyperliquid_service.get_positions()
                remaining = next((p for p in final_positions if p["symbol"] == symbol), None)

                if not remaining or float(remaining["size"]) == 0:
                     self.add_log(f"✅ POSITION CLOSED: {symbol}")
                     self.add_log(f"🧹 Cleaning post-trade orphans on {symbol}...")
                     hyperliquid_service.cancel_all_orders(symbol)

                     # Calculate PnL from position data (works for all positions)
                     pnl_usdc = 0
                     entry_price = 0
                     exit_price = hyperliquid_service.get_current_price(symbol)
                     size = 0
                     side = "BUY"

                     if position_data:
                         # Use actual position data
                         entry_price = position_data.get("entry_price", 0)
                         size = position_data.get("size", 0)
                         side = position_data.get("side", "BUY")

                         if side == "BUY":
                             pnl_usdc = (exit_price - entry_price) * size
                         else:
                             pnl_usdc = (entry_price - exit_price) * size
                     elif self.active_trade:
                         # Fallback to active_trade if position_data unavailable
                         entry_price = self.active_trade.get("entry", 0)
                         size = self.active_trade.get("size", 0)
                         side = self.active_trade.get("side", "BUY")

                         if side == "BUY":
                             pnl_usdc = (exit_price - entry_price) * size
                         else:
                             pnl_usdc = (entry_price - exit_price) * size

                     # Record trade
                     with self.trade_lock:
                         closed_trade = self.active_trades.get(symbol)
                         self.trade_recorder.add_trade({
                             "trade_id": closed_trade.get("trade_id") if isinstance(closed_trade, dict) else None,
                             "trace_id": (
                                 (closed_trade.get("metadata") or {}).get("trace_id")
                                 if isinstance(closed_trade, dict)
                                 else None
                             ),
                             "symbol": symbol,
                             "strategy": (
                                 closed_trade.get("strategy")
                                 if isinstance(closed_trade, dict) and closed_trade.get("strategy")
                                 else (self.active_trade.get("strategy", "Manual") if self.active_trade else "Manual")
                             ),
                             "side": side,
                             "entry_price": entry_price,
                             "exit_price": exit_price,
                             "size": size,
                             "pnl_usdc": pnl_usdc,
                             "exit_reason": reason,
                             "exit_time": pd.Timestamp.now().isoformat(),
                             "entry_time": (
                                 closed_trade.get("timestamp")
                                 if isinstance(closed_trade, dict)
                                 else None
                             ),
                             "entry_indicators": (
                                 closed_trade.get("entry_indicators", {})
                                 if isinstance(closed_trade, dict)
                                 else (self.active_trade.get("entry_indicators", {}) if self.active_trade else {})
                             ),
                         })

                         discord_service.send_alert(
                             f"🏁 TRADE CLOSED: {symbol}",
                             f"Reason: {reason}\nPnL: ${pnl_usdc:.2f}",
                             color="FFFF00"
                         )
                         self.risk_manager.record_trade_close(pnl_usdc)

                         # Drop local tracking now — intentional close is already recorded.
                         # Prevents _sync_state → _handle_external_closure from double-recording.
                         self.active_trades.pop(symbol, None)

                         # Clear active_trade only if this was the active trade
                         if self.active_trade and self.active_trade.get("symbol") == symbol:
                             self.active_trade = None

                         StateManager.save_state(self)
                         self._sync_state(silent=False)

                     return True
                else:
                    self.add_log(f"⚠️ Close appeared successful but position remains: {remaining['size']}")
                    return False
            else:
                self.add_log(f"❌ Exit Failed: {result.get('message')}")
                return False

        except Exception as e:
            self.add_log(f"❌ ATOMIC EXIT ERROR: {e}")
            return False

    def _verify_and_enforce_sl_tp(self, symbol: str, trade_data: dict, bypass_cooldown: bool = False):
        """Consolidated verification: Fetch Exchange Orders -> Compare -> Enforce if needed."""
        # GUARD: Only enforce if trading is ENABLED (Real Trading)
        if not self.trading_enabled:
             return

        # PREVENT SYSTEMATIC RECALIBRATION: Only enforce on initial adoption or explicit trailing/BE
        if not bypass_cooldown and trade_data.get("initial_sl_tp_set", False):
            return

        # COOLDOWN: Skip verification if we just synced (prevent infinite loop)
        if not bypass_cooldown and self._last_sltp_sync_time:
            elapsed = (pd.Timestamp.now() - self._last_sltp_sync_time).total_seconds()
            if elapsed < self._sltp_sync_cooldown:
                return  # Too soon, wait for cooldown

        try:
            # Must use frontend_open_orders (via get_open_orders) — open_orders omits triggers
            symbol_orders = hyperliquid_service.get_open_orders(symbol)

            desired_sl = float(trade_data.get("sl", 0))
            desired_tp = float(trade_data.get("tp", 0))

            found_sl = False
            found_tp = False
            TOLERANCE = 0.005  # Increased from 0.001 to 0.5% to handle rounding differences

            for o in symbol_orders:
                # FIX: For trigger orders (SL/TP), use triggerPx (actual trigger), not limitPx (aggressive fill price)
                price = float(o.get("triggerPx") or o.get("limitPx", 0))
                if desired_sl > 0 and abs(price - desired_sl) / desired_sl < TOLERANCE:
                    found_sl = True
                if desired_tp > 0 and abs(price - desired_tp) / desired_tp < TOLERANCE:
                     found_tp = True

            needs_sync = False
            if desired_sl > 0 and not found_sl:
                tid = trade_data.get("trade_id") if isinstance(trade_data, dict) else None
                self.add_log(
                    f"⚠️ Audit: SL missing/mismatched on exchange (Target: {desired_sl:.4f}). Enforcing..." +
                    (f" | id={tid}" if tid else "")
                )
                needs_sync = True
            if desired_tp > 0 and not found_tp:
                tid = trade_data.get("trade_id") if isinstance(trade_data, dict) else None
                self.add_log(
                    f"⚠️ Audit: TP missing/mismatched on exchange (Target: {desired_tp:.4f}). Enforcing..." +
                    (f" | id={tid}" if tid else "")
                )
                needs_sync = True

            if needs_sync:
                hyperliquid_service.sync_sl_tp(
                    symbol,
                    trade_data.get("side") == "BUY",
                    float(trade_data.get("size", 0)),
                    desired_sl,
                    desired_tp,
                    entry_price=float(trade_data.get("entry") or trade_data.get("entry_price") or 0),
                )
                tid = trade_data.get("trade_id") if isinstance(trade_data, dict) else None
                self.add_log("✅ Audit: SL/TP enforced via Sync." + (f" | id={tid}" if tid else ""))
                self._last_sltp_sync_time = pd.Timestamp.now()  # Mark sync time for cooldown

        except Exception as e:
            self.add_log(f"⚠️ Error in _verify_and_enforce_sl_tp: {e}")

    def _check_local_exits(self, trade: dict, symbol: str, current_price: float):
        """Backup local SL/TP check — exchange trigger orders remain primary.

        Only market-closes when we have a valid live price AND the position is
        still open on a successful positions fetch. API errors must never force
        a close while exchange SL/TP are working.
        """
        # Never exit on a missing/stale quote — price=0 on a SHORT always hits TP.
        if current_price is None or float(current_price) <= 0:
            return

        side = trade.get("side")
        sl_val = float(trade.get("sl") or 0)
        tp_val = float(trade.get("tp") or 0)
        tid = trade.get("trade_id") if isinstance(trade, dict) else None

        exit_triggered = False
        reason = ""

        if side == "BUY":
            if sl_val > 0 and current_price <= sl_val:
                exit_triggered = True; reason = "STOP_LOSS"
            elif tp_val > 0 and current_price >= tp_val:
                exit_triggered = True; reason = "TAKE_PROFIT"
        else:
             if sl_val > 0 and current_price >= sl_val:
                exit_triggered = True; reason = "STOP_LOSS"
             elif tp_val > 0 and current_price <= tp_val:
                exit_triggered = True; reason = "TAKE_PROFIT"

        if exit_triggered:
            # Prefer letting exchange SL/TP fill; only backstop if position still open
            positions = hyperliquid_service.get_positions()
            if getattr(hyperliquid_service, "_positions_fetch_failed", False) is True:
                self.add_log(
                    f"⚠️ Local {reason} for {symbol} ignored — positions API down; "
                    f"exchange SL/TP remain in charge" + (f" | id={tid}" if tid else "")
                )
                return
            if getattr(hyperliquid_service, "_positions_stale", False) is True:
                self.add_log(
                    f"⚠️ Local {reason} for {symbol} ignored — positions snapshot stale; "
                    f"exchange SL/TP remain in charge" + (f" | id={tid}" if tid else "")
                )
                return
            still_open = any(
                p.get("symbol") == symbol and float(p.get("size", 0) or 0) != 0
                for p in (positions or [])
            )
            if not still_open:
                self.add_log(
                    f"ℹ️ Local {reason} for {symbol} but exchange already flat — syncing memory"
                    + (f" | id={tid}" if tid else "")
                )
                self._handle_external_closure(symbol, trade, silent=True)
                return
            self.add_log(f"🎯 Local Trigger: {reason} @ {current_price}" + (f" | id={tid}" if tid else ""))
            self.execute_exit_atomically(symbol, reason)
