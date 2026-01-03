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

    def calculate_position_size(self, price: float, sl_price: float, equity: float, method: str = "fixed", size_value: float = 20.0, leverage: int = 5, size_type: str = "margin") -> float:
        """
        Calculate position size (in coins) based on risk management rules.
        Args:
            size_type: "margin" (Fixed $ cost) | "notional" (Total position size $) | "risk_pct" (% of equity)
            size_value: value associated with method
        """
        try:
            if price <= 0: return 0.0
            
            size_coins = 0.0
            MIN_POSITION_SIZE_USD = 12.0 # Hyperliquid minimum
            
            # 1. Risk % Based (Equity %)
            if method == "risk_pct" and sl_price > 0 and price != sl_price:
                # size_value is treated as % (e.g. 1% = 0.01)
                risk_per_trade_pct = size_value / 100.0 if size_value > 1 else size_value
                risk_amount = equity * risk_per_trade_pct
                price_diff = abs(price - sl_price)
                size_coins = risk_amount / price_diff
                
            # 2. Fixed Notional ($ Value)
            elif size_type == "notional":
                 # size_value is Total Position Value (e.g. $1000)
                 size_coins = size_value / price
                 
            # 3. Fixed Margin (Cost $) - DEFAULT
            else:
                # size_value is Margin Cost (e.g. $20)
                # Position Value = Margin * Leverage
                position_value = size_value * leverage
                size_coins = position_value / price

            # --- SAFETY CLAMPING ---
            position_notional = size_coins * price
            
            # Check Minimum Size
            if position_notional < MIN_POSITION_SIZE_USD:
                print(f"⚠️ Position size ${position_notional:.2f} < Min ${MIN_POSITION_SIZE_USD}. Clamping to Min.")
                size_coins = MIN_POSITION_SIZE_USD / price
                position_notional = MIN_POSITION_SIZE_USD
                
            # Check Maximum Leverage Cap (Safety Net)
            max_allowed_notional = equity * 20 # Hard cap 20x equity even if leverage is higher
            if position_notional > max_allowed_notional:
                 print(f"⚠️ Position size ${position_notional:.2f} exceeds Max Cap. Clamping.")
                 size_coins = max_allowed_notional / price

            return size_coins
                
        except Exception as e:
            print(f"Error calculating position size: {e}")
            # Fallback safe size ($12 min)
            return 12.0 / price if price > 0 else 0.0


