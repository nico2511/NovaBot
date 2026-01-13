"""
Risk Manager with tier-based limits.
"""

import threading
import datetime
from dataclasses import dataclass
from app.gamification.enums import TierEnum


@dataclass
class RiskState:
    daily_pnl: float = 0.0
    open_positions: int = 0
    is_stop_mode: bool = False
    stop_reason: str = ""


class RiskManager:
    """
    Risk Manager with tier-based position and leverage limits.
    """
    
    # Tier-based limits
    TIER_LIMITS = {
        TierEnum.NEBULA: {
            "max_positions": 1,
            "max_leverage": 1,
            "max_position_size_usd": 100
        },
        TierEnum.PROTOSTAR: {
            "max_positions": 2,
            "max_leverage": 2,
            "max_position_size_usd": 1000
        },
        TierEnum.SUPERNOVA: {
            "max_positions": 3,
            "max_leverage": 5,
            "max_position_size_usd": 10000
        }
    }
    
    def __init__(self, tier: TierEnum = TierEnum.NEBULA, daily_stop_loss: float = 50.0):
        self._lock = threading.Lock()
        self.tier = tier
        self.daily_stop_loss = daily_stop_loss
        self.state = RiskState()
        self.last_reset_date = datetime.date.today()
        
    def update_tier(self, tier: TierEnum):
        """Update tier and limits"""
        with self._lock:
            self.tier = tier
            
    def get_max_positions(self) -> int:
        """Get max positions for current tier"""
        return self.TIER_LIMITS[self.tier]["max_positions"]
        
    def get_max_leverage(self) -> int:
        """Get max leverage for current tier"""
        return self.TIER_LIMITS[self.tier]["max_leverage"]
        
    def get_max_position_size(self) -> float:
        """Get max position size for current tier"""
        return self.TIER_LIMITS[self.tier]["max_position_size_usd"]
    
    def _check_reset(self):
        """Reset daily stats if new day"""
        today = datetime.date.today()
        if today > self.last_reset_date:
            with self._lock:
                self.state.daily_pnl = 0.0
                self.state.is_stop_mode = False
                self.state.stop_reason = ""
                self.last_reset_date = today
    
    def check_can_trade(self) -> tuple[bool, str]:
        """Check if trading is allowed"""
        self._check_reset()
        with self._lock:
            if self.state.is_stop_mode:
                return False, f"STOP MODE: {self.state.stop_reason}"
            
            max_pos = self.get_max_positions()
            if self.state.open_positions >= max_pos:
                return False, f"Max positions ({self.state.open_positions}/{max_pos}) - Tier: {self.tier.value}"
            
            if self.state.daily_pnl <= -self.daily_stop_loss:
                self.state.is_stop_mode = True
                self.state.stop_reason = "Daily Stop Loss Exceeded"
                return False, self.state.stop_reason
            
            return True, "OK"
    
    def record_trade_open(self):
        """Record trade opening"""
        with self._lock:
            self.state.open_positions += 1
    
    def record_trade_close(self, pnl: float):
        """Record trade closing"""
        with self._lock:
            self.state.open_positions = max(0, self.state.open_positions - 1)
            self.state.daily_pnl += pnl
            
            if self.state.daily_pnl <= -self.daily_stop_loss:
                self.state.is_stop_mode = True
                self.state.stop_reason = f"Daily Stop Loss: {self.state.daily_pnl:.2f}"
    
    def calculate_position_size(
        self,
        price: float,
        equity: float,
        leverage: int = None
    ) -> float:
        """
        Calculate position size with tier limits.
        
        Args:
            price: Current price
            equity: Account equity
            leverage: Desired leverage (capped by tier)
            
        Returns:
            Position size in coins
        """
        try:
            if price <= 0:
                return 0.0
            
            # Apply tier leverage cap
            max_lev = self.get_max_leverage()
            actual_leverage = min(leverage or max_lev, max_lev)
            
            # Apply tier position size cap
            max_size_usd = self.get_max_position_size()
            
            # Calculate size (simple: 20% of max size per position)
            target_size_usd = min(max_size_usd * 0.2, equity * actual_leverage * 0.1)
            
            # Ensure minimum Hyperliquid size
            MIN_SIZE_USD = 12.0
            target_size_usd = max(target_size_usd, MIN_SIZE_USD)
            
            # Convert to coins
            size_coins = target_size_usd / price
            
            return size_coins
            
        except Exception as e:
            print(f"Error calculating position size: {e}")
            return 12.0 / price if price > 0 else 0.0
    
    def get_status(self) -> dict:
        """Get risk manager status"""
        self._check_reset()
        with self._lock:
            return {
                "tier": self.tier.value,
                "daily_pnl": self.state.daily_pnl,
                "open_positions": self.state.open_positions,
                "is_stop_mode": self.state.is_stop_mode,
                "stop_reason": self.state.stop_reason,
                "max_positions": self.get_max_positions(),
                "max_leverage": self.get_max_leverage(),
                "max_position_size": self.get_max_position_size(),
                "daily_stop_loss": self.daily_stop_loss
            }
