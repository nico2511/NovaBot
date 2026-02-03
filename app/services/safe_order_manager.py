
import logging
import pandas as pd
from typing import Dict, Optional
from app.services.hyperliquid_service import HyperliquidService
from app.core.config import config

class SafeOrderManager:
    """
    Manages safety orders (SL/TP) with focus on idempotency and reliability.
    Phase 0 Hardening: Ensures every position has protection.
    """
    
    def __init__(self, hl_service: HyperliquidService):
        self.hl = hl_service
        self.logger = logging.getLogger("SafeOrderManager")
        
        # Fallback settings (load from config or defaults)
        self.default_sl_pct = 0.02  # 2% SL by default
        self.default_tp_pct = 0.04  # 4% TP by default (1:2 RR)
        self.max_sl_drift = 0.12    # 12% Max SL (Hard cap)

    def ensure_sl_tp(self, position: Dict) -> bool:
        """
        Verify if position has SL/TP. If not, calculate and place them.
        Returns True if actions were taken, False if already safe.
        """
        symbol = position.get("symbol")
        if not symbol:
            return False

        # 1. Check existing orders
        open_orders = self.hl.get_open_orders(symbol)
        has_sl = any(o.get("order_type", {}).get("trigger", {}).get("tpsl") == "sl" for o in open_orders)
        has_tp = any(o.get("order_type", {}).get("trigger", {}).get("tpsl") == "tp" for o in open_orders)
        
        if has_sl and has_tp:
            return False # Already safe
            
        self.logger.info(f"🛡️ Position {symbol} missing protection (SL={has_sl}, TP={has_tp}). Fixing...")
        
        # 2. Calculate Safe Levels (Fallback Logic)
        entry_price = float(position.get("entry_price", 0))
        side = position.get("side", "BUY")
        is_buy = (side == "BUY")
        
        # TODO: Implement ATR-based calculation if market data available
        # For Phase 0 MVP, use percentage-based fallback
        sl_price, tp_price = self._calculate_fallback_levels(entry_price, is_buy)
        
        # 3. Place Orders
        # existing place_protection_orders handles placement. 
        # We only pass what's missing, but the service helper places both.
        # Ideally we should be granular, but for now we can rely on it placing both if needed.
        # Actually place_protection_orders places whatever is passed.
        
        sl_to_send = sl_price if not has_sl else None
        tp_to_send = tp_price if not has_tp else None
        
        size = float(position.get("size", 0))
        
        if sl_to_send or tp_to_send:
            self.hl._place_protection_orders(
                symbol=symbol,
                is_buy=is_buy, # Direction of the POSITION (helper inverts it for exit)
                quantity=size,
                sl_price=sl_to_send,
                tp_price=tp_to_send
            )
            return True
            
        return False

    def _calculate_fallback_levels(self, entry: float, is_buy: bool) -> tuple[float, float]:
        """Calculate fallback SL/TP levels based on configured percentages."""
        if is_buy:
            sl = entry * (1 - self.default_sl_pct)
            tp = entry * (1 + self.default_tp_pct)
        else:
            sl = entry * (1 + self.default_sl_pct)
            tp = entry * (1 - self.default_tp_pct)
            
        return sl, tp

    def ensure_no_open_order_conflict(self, symbol: str):
        """Phase 1: Implement conflict checks (TODO)"""
        pass
