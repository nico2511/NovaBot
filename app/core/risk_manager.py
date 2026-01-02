import threading
import datetime
from dataclasses import dataclass

@dataclass
class RiskState:
    daily_pnl: float = 0.0
    open_positions: int = 0
    is_stop_mode: bool = False
    stop_reason: str = ""

class RiskManager:
    def __init__(self, max_positions: int = 1, daily_stop_loss: float = 50.0):
        self._lock = threading.Lock()
        self.max_positions = max_positions
        self.daily_stop_loss = daily_stop_loss  # Positive number
        self.state = RiskState()
        self.last_reset_date = datetime.date.today()

    def _check_reset(self):
        today = datetime.date.today()
        if today > self.last_reset_date:
            with self._lock:
                self.state.daily_pnl = 0.0
                self.state.is_stop_mode = False
                self.state.stop_reason = ""
                self.last_reset_date = today

    def check_can_trade(self) -> (bool, str):
        self._check_reset()
        with self._lock:
            if self.state.is_stop_mode:
                return False, f"STOP MODE ACTIVE: {self.state.stop_reason}"
            
            if self.state.open_positions >= self.max_positions:
                return False, f"Max positions reached ({self.state.open_positions}/{self.max_positions})"
            
            # Additional check: if we are already fast approaching the limit
            if self.state.daily_pnl <= -self.daily_stop_loss:
                self.state.is_stop_mode = True
                self.state.stop_reason = "Daily Stop Loss Exceeded (Pre-check)"
                return False, self.state.stop_reason

            return True, "OK"

    def record_trade_open(self):
        with self._lock:
            self.state.open_positions += 1

    def record_trade_close(self, pnl: float):
        with self._lock:
            self.state.open_positions = max(0, self.state.open_positions - 1)
            self.state.daily_pnl += pnl
            
            if self.state.daily_pnl <= -self.daily_stop_loss:
                self.state.is_stop_mode = True
                self.state.stop_reason = f"Daily Stop Loss Hit: {self.state.daily_pnl:.2f} <= -{self.daily_stop_loss}"

    def update_settings(self, max_positions: int = None, daily_stop_loss: float = None):
        with self._lock:
            if max_positions is not None:
                self.max_positions = max_positions
            if daily_stop_loss is not None:
                self.daily_stop_loss = daily_stop_loss

    def get_status(self) -> dict:
        self._check_reset()
        with self._lock:
            return {
                "daily_pnl": self.state.daily_pnl,
                "open_positions": self.state.open_positions,
                "is_stop_mode": self.state.is_stop_mode,
                "stop_reason": self.state.stop_reason,
                "max_positions": self.max_positions,
                "daily_stop_loss": self.daily_stop_loss
            }

    def sync_with_hyperliquid(self, hyperliquid_service):
        """Synchronize position count with actual Hyperliquid positions - HYPERLIQUID IS SOURCE OF TRUTH"""
        try:
            real_positions = hyperliquid_service.get_positions()
            real_count = len(real_positions)
            
            with self._lock:
                # IMPORTANT: Hyperliquid est la source de vérité
                # On force TOUJOURS la synchronisation
                if self.state.open_positions != real_count:
                    print(f"⚠️ SYNC: Position mismatch detected!")
                    print(f"   Bot thinks: {self.state.open_positions}")
                    print(f"   Hyperliquid has: {real_count} (SOURCE OF TRUTH)")
                    
                    # Force sync - PAS DE POSITIONS FANTÔMES
                    old_count = self.state.open_positions
                    self.state.open_positions = real_count
                    
                    print(f"✅ SYNC: Forced sync {old_count} → {real_count}")
                    
                    return {
                        "synced": True,
                        "old_count": old_count,
                        "new_count": real_count,
                        "positions": real_positions
                    }
            
            return {"synced": False, "count": real_count}
            
        except Exception as e:
            print(f"Error syncing with Hyperliquid: {e}")
            return {"synced": False, "error": str(e)}

    def calculate_position_size(self, price: float, sl_price: float, equity: float, method: str = "fixed", risk_per_trade_pct: float = 0.01) -> float:
        """
        Calculate position size (in coins) based on risk management rules.
        """
        try:
            if price <= 0: return 0.0
            
            # 1. Risk-Based Sizing (Standard)
            # Risk Amount = Equity * Risk%
            # Size = Risk Amount / |Entry - SL|
            if method == "risk_pct" and sl_price > 0 and price != sl_price:
                risk_amount = equity * risk_per_trade_pct
                price_diff = abs(price - sl_price)
                size_coins = risk_amount / price_diff
                
                # Cap max leverage (e.g. 5x)
                max_position_value = equity * 5
                if (size_coins * price) > max_position_value:
                    size_coins = max_position_value / price
                    
                return size_coins
                
            # 2. Fixed Sizing (Default/Fallback)
            # Default to $20 margin x 5 leverage = $100 position size
            else:
                from app.core.constants import DEFAULT_SIZE_USDC, DEFAULT_LEVERAGE
                # DEFAULT_SIZE_USDC is usually 20.0 (Margin)
                position_size_usd = DEFAULT_SIZE_USDC * DEFAULT_LEVERAGE
                return position_size_usd / price
                
        except Exception as e:
            print(f"Error calculating position size: {e}")
            # Fallback safe size
            return (20.0 * 5) / price if price > 0 else 0.0


