
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

    def run_tick(self):
        """Called periodically by the main loop"""
        now = time.time()
        if now - self.last_run >= self.interval:
            self.reconcile()
            self.last_run = now

    def reconcile(self):
        """Single reconciliation pass"""
        # 1. Get Real Truth from Exchange
        try:
            positions = self.hl.get_positions()
            
            # Filter for active positions (size > 0)
            active_positions = [p for p in positions if float(p.get("size", 0)) > 0]
            
            if not active_positions:
                return

            # 2. Check each position for safety
            for pos in active_positions:
                symbol = pos.get("symbol")
                # Ensure SL/TP exist
                try:
                    fixed = self.safety.ensure_sl_tp(pos)
                    if fixed:
                        self.logger.info(f"✅ Reconciler fixed protection for {symbol}")
                except Exception as e:
                    self.logger.error(f"❌ Failed to safety-check {symbol}: {e}")
        except Exception as e:
             self.logger.error(f"⚠️ Reconciliation Error: {e}")
