
import logging
import time
from app.services.hyperliquid_service import HyperliquidService
from app.services.safe_order_manager import SafeOrderManager

logger = logging.getLogger("PositionReconciler")


class PositionReconciler:
    """
    Background Service: Monitors positions and ensures they are managed.

    Responsibilities (run every 30s):
      1. CLEANUP GHOSTS   — active_trades entries whose position was closed on exchange
      2. ADOPT ORPHANS    — positions open on exchange but unknown to the bot (manual trades)
      3. ENFORCE SL/TP    — ensure protection orders are in place for all known positions

    Fix (2026-04-13): orphan adoption now reads the real side, entry_price and size
    from Hyperliquid instead of hardcoding side="BUY" and entry=0, which caused
    incorrect PnL calculations and order chaos when the user opened manual positions.
    """

    def __init__(self, hl_service: HyperliquidService, safety_manager: SafeOrderManager):
        self.hl = hl_service
        self.safety = safety_manager
        self.interval = 30  # seconds between full reconciliation passes
        self.last_run = 0
        self.last_reconcile_per_symbol = {}  # cooldown tracker per symbol (45s)
        self.bot_context = None  # Set by BotContext after construction

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def run_tick(self):
        """Called periodically from the main trading loop."""
        now = time.time()
        if now - self.last_run >= self.interval:
            self.reconcile()
            self.last_run = now

    def reconcile(self):
        """Single reconciliation pass — the source of truth is always the exchange."""
        try:
            exchange_positions = self.hl.get_positions()
            # Only positions with a non-zero size are truly open
            active_positions = [
                p for p in exchange_positions
                if abs(float(p.get("size", 0) or 0)) > 0
            ]

            # Step 1 — Remove ghost trades (bot tracks a position that no longer exists)
            self._cleanup_ghost_trades(active_positions)

            # Step 2 — Adopt orphan positions (manual trades opened directly on exchange)
            self._adopt_orphan_positions(active_positions)

            # Step 3 — Ensure SL/TP on all tracked positions
            for pos in active_positions:
                symbol = pos.get("symbol")
                now = time.time()
                if self._is_on_cooldown(symbol, now):
                    continue
                try:
                    fixed = self.safety.ensure_sl_tp(pos)
                    if fixed:
                        logger.info(f"✅ Reconciler fixed protection for {symbol}")
                        self.last_reconcile_per_symbol[symbol] = now
                except Exception as e:
                    logger.error(f"❌ Failed to safety-check {symbol}: {e}")

        except Exception as e:
            logger.error(f"⚠️ Reconciliation Error: {e}")

    # ------------------------------------------------------------------
    # Step 1 — Ghost trade cleanup
    # ------------------------------------------------------------------

    def _cleanup_ghost_trades(self, exchange_positions: list):
        """
        Remove entries in active_trades that have no matching open position
        on the exchange.  This handles manual closes or TP/SL hits that the
        bot's main loop hasn't processed yet.
        """
        if not self.bot_context:
            return

        exchange_symbols = {p.get("symbol") for p in exchange_positions}
        tracked_symbols = list(self.bot_context.active_trades.keys())

        for symbol in tracked_symbols:
            if symbol not in exchange_symbols:
                logger.warning(
                    f"👻 Ghost trade detected: bot tracks {symbol} but exchange shows no position. "
                    f"Cleaning up..."
                )
                try:
                    from app.services.discord_service import discord_service
                    discord_service.send_log(
                        f"🧹 Ghost trade cleaned: **{symbol}**\n"
                        f"Position was closed externally (manual close or TP/SL hit)."
                    )
                except Exception:
                    pass  # Discord failure must never block reconciliation

                with self.bot_context.trade_lock:
                    self.bot_context.active_trades.pop(symbol, None)
                logger.info(f"✅ Ghost trade removed: {symbol}")

    # ------------------------------------------------------------------
    # Step 2 — Orphan adoption
    # ------------------------------------------------------------------

    def _adopt_orphan_positions(self, exchange_positions: list):
        """
        Adopt positions that exist on the exchange but are unknown to the bot.
        This happens when the user opens a trade directly on Hyperliquid while
        the bot is running.

        Critical fix: read the real side, entry_price and size from the exchange
        data instead of assuming BUY / entry=0, which caused bad PnL math and
        confused SL/TP placement for short positions.
        """
        if not self.bot_context:
            return

        local_symbols = set(self.bot_context.active_trades.keys())

        for pos in exchange_positions:
            symbol = pos.get("symbol")
            if symbol in local_symbols:
                continue  # Already tracked — nothing to do

            # ---- Read real position data from exchange ----
            try:
                raw_size = float(pos.get("size", 0) or 0)
                entry_price = float(pos.get("entry_price", 0) or 0)

                # Hyperliquid: size > 0 → LONG, size < 0 → SHORT
                # The service usually returns abs(size); rely on "side" if present,
                # otherwise infer from the raw signed size field ("szi" if available).
                raw_side = pos.get("side", "").upper()
                if raw_side in ("BUY", "LONG"):
                    side = "BUY"
                elif raw_side in ("SELL", "SHORT"):
                    side = "SELL"
                else:
                    # Fallback: check signed size via szi key (raw SDK field)
                    szi = pos.get("szi", None)
                    if szi is not None:
                        side = "BUY" if float(szi) > 0 else "SELL"
                    else:
                        # Last resort: assume LONG (safer for SL/TP placement)
                        side = "BUY"
                        logger.warning(
                            f"⚠️ Could not determine side for orphan {symbol} — defaulting to BUY. "
                            f"Check position manually."
                        )

                size = abs(raw_size)

            except Exception as parse_err:
                logger.error(f"❌ Failed to parse orphan position data for {symbol}: {parse_err}")
                # Skip adoption rather than adopting with bad data
                continue

            # ---- Register in bot state via unified method ----
            try:
                self.bot_context._adopt_existing_position(pos)
                logger.info(f"✅ Reconciler triggered adoption for {symbol}")
            except Exception as e:
                logger.error(f"❌ Reconciler failed to adopt {symbol}: {e}")

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _is_on_cooldown(self, symbol: str, now: float) -> bool:
        last_time = self.last_reconcile_per_symbol.get(symbol, 0)
        return (now - last_time) < 45
