
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

        # 1. Check existing orders - SIMPLIFIED DETECTION
        open_orders = self.hl.get_open_orders(symbol)
        
        sl_orders = []
        tp_orders = []
        
        entry_price = float(position.get("entry_price", 0))
        side = position.get("side", "BUY")
        
        for o in open_orders:
            # Use reduceOnly as primary indicator for protection orders
            is_reduce = o.get("reduceOnly", False)
            trigger_px = float(o.get("triggerPx", 0) or o.get("limitPx", 0) or 0)
            
            if not is_reduce or trigger_px == 0:
                continue  # Not a protection order
            
            # Determine if SL or TP based on price vs entry
            if side == "BUY":
                if trigger_px < entry_price:
                    sl_orders.append(o)
                    self.logger.debug(f"   Found SL order @ {trigger_px:.2f} (entry: {entry_price:.2f})")
                else:
                    tp_orders.append(o)
                    self.logger.debug(f"   Found TP order @ {trigger_px:.2f} (entry: {entry_price:.2f})")
            else:  # SELL
                if trigger_px > entry_price:
                    sl_orders.append(o)
                    self.logger.debug(f"   Found SL order @ {trigger_px:.2f} (entry: {entry_price:.2f})")
                else:
                    tp_orders.append(o)
                    self.logger.debug(f"   Found TP order @ {trigger_px:.2f} (entry: {entry_price:.2f})")
        
        # Count validation - PREVENT ADDING MORE DUPLICATES
        count_sl = len(sl_orders)
        count_tp = len(tp_orders)
        
        if count_sl > 1 or count_tp > 1:
            self.logger.warning(f"⚠️ {symbol} has duplicate orders (SL={count_sl}, TP={count_tp}). Skipping placement to avoid more duplicates.")
            return False
        
        has_sl = count_sl >= 1
        has_tp = count_tp >= 1
        
        if has_sl and has_tp:
            self.logger.debug(f"✅ {symbol} already has protection (SL + TP)")
            return False # Already safe
            
        self.logger.info(f"🛡️ Position {symbol} missing protection (SL={has_sl}, TP={has_tp}). Fixing...")
        
        # 2. Calculate Safe Levels (Fallback Logic)
        is_buy = (side == "BUY")
        
        # TODO: Implement ATR-based calculation if market data available
        # For Phase 0 MVP, use percentage-based fallback
        sl_price, tp_price = self._calculate_fallback_levels(entry_price, is_buy)
        
        # 3. Place Orders - Only what's missing
        sl_to_send = sl_price if not has_sl else None
        tp_to_send = tp_price if not has_tp else None
        
        size = float(position.get("size", 0))
        
        if sl_to_send or tp_to_send:
            sl_text = f"{sl_to_send:.2f}" if sl_to_send else "skip"
            tp_text = f"{tp_to_send:.2f}" if tp_to_send else "skip"
            self.logger.info(f"   Placing: SL={sl_text}, TP={tp_text}")
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

    def pre_validate_order(self, symbol: str, size: float, side: str) -> bool:
        """Pre-validation before placing any order (STORY-003)"""
        from app.utils.rate_limiter import rate_limiter
        
        if not rate_limiter.can_call("order_validation"):
            self.logger.warning(f"Rate limited: skipping pre-validation for {symbol}")
            return False
        rate_limiter.record_call("order_validation")
        
        try:
            # Get current user state for margin check
            user_state = self.hl.info.user_state(config.HL_ACCOUNT_ADDRESS) if hasattr(self.hl, 'info') else None
            if not user_state:
                return True  # Cannot validate, allow with warning
                
            # Basic margin check (simplified)
            available_margin = float(user_state.get("marginSummary", {}).get("accountValue", 0))
            if available_margin < 50:  # Minimum safety threshold
                self.logger.error(f"❌ Insufficient margin for {symbol} ({available_margin:.2f})")
                return False
                
            self.logger.debug(f"✅ Pre-validation passed for {symbol} ({side} {size})")
            return True
        except Exception as e:
            self.logger.warning(f"⚠️ Pre-validation failed for {symbol}: {e}")
            return True  # Fail open for safety (better to try than block completely)
