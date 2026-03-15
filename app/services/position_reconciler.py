
import logging
import time
from app.services.hyperliquid_service import HyperliquidService
from app.services.safe_order_manager import SafeOrderManager

class PositionReconciler:
    """
    Background Service: Monitors positions and ensures they are managed.
    Detects 'orphans' (positions on exchange but not in bot state) and fixes missing SL/TP.
    """
    
    def __init__(self, hl_service: HyperliquidService, safety_manager: SafeOrderManager):
        self.hl = hl_service
        self.safety = safety_manager
        self.logger = logging.getLogger("PositionReconciler")
        self.interval = 30 # seconds
        self.last_run = 0
        self.last_reconcile_per_symbol = {}  # Track cooldown per symbol (60s)
        self.bot_context = None  # Will be set by BotContext after initialization

    def run_tick(self):
        """Called periodically by the main loop"""
        now = time.time()
        if now - self.last_run >= self.interval:
            self.reconcile()
            self.last_run = now

    def reconcile(self):
        """Single reconciliation pass - Improved state sync"""
        try:
            positions = self.hl.get_positions()
            active_positions = [p for p in positions if float(p.get("size", 0)) > 0]

            if not active_positions:
                return

            # 1. Adopt orphan positions (main fix for user's reboot issue)
            self._adopt_orphan_positions(active_positions)

            # 2. Ensure protection on all positions
            for pos in active_positions:
                symbol = pos.get("symbol")
                now = time.time()
                
                if self._is_on_cooldown(symbol, now):
                    continue

                try:
                    fixed = self.safety.ensure_sl_tp(pos)
                    if fixed:
                        self.logger.info(f"✅ Reconciler fixed protection for {symbol}")
                        self.last_reconcile_per_symbol[symbol] = now
                except Exception as e:
                    self.logger.error(f"❌ Failed to safety-check {symbol}: {e}")
        except Exception as e:
            self.logger.error(f"⚠️ Reconciliation Error: {e}")

    def _adopt_orphan_positions(self, exchange_positions):
        """Adopt positions that exist on exchange but not in bot state"""
        if not self.bot_context:
            return

        exchange_symbols = {p.get("symbol") for p in exchange_positions}
        local_symbols = set(self.bot_context.active_trades.keys())

        for symbol in exchange_symbols - local_symbols:
            self.logger.warning(f"👻 Orphan position detected on exchange: {symbol}. Adopting...")
            # Create minimal trade entry
            self.bot_context.active_trades[symbol] = {
                "symbol": symbol,
                "strategy": "Adopted-Orphan",
                "entry": 0,
                "side": "BUY",
                "status": "ADOPTED"
            }
            self.logger.info(f"✅ Adopted orphan position: {symbol}")

    def _is_on_cooldown(self, symbol: str, now: float) -> bool:
        last_time = self.last_reconcile_per_symbol.get(symbol, 0)
        if now - last_time < 45:  # Reduced cooldown for faster response
            return True
        return False
