import datetime
import logging
import threading
from dataclasses import dataclass

from app.core.constants import MAX_NOTIONAL_CAP_MULTIPLIER, MIN_POSITION_NOTIONAL_USD

logger = logging.getLogger(__name__)

@dataclass
class RiskState:
    daily_pnl: float = 0.0
    open_positions: int = 0
    is_stop_mode: bool = False
    stop_reason: str = ""

class RiskManager:
    def __init__(
        self,
        max_positions: int = 2,
        daily_stop_loss: float = 50.0,
        max_notional_cap_multiplier: float = MAX_NOTIONAL_CAP_MULTIPLIER,
    ):
        self._lock = threading.Lock()
        self.max_positions = max_positions
        self.daily_stop_loss = daily_stop_loss  # Positive number
        self.max_notional_cap_multiplier = float(max_notional_cap_multiplier)
        self.state = RiskState()
        self.last_reset_date = datetime.date.today()

    def _max_notional(self, equity: float) -> float:
        return equity * self.max_notional_cap_multiplier

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
            if self._maybe_trigger_daily_stop():
                return False, self.state.stop_reason

            return True, "OK"

    def record_trade_open(self):
        with self._lock:
            self.state.open_positions += 1

    def record_trade_close(self, pnl: float):
        with self._lock:
            self.state.open_positions = max(0, self.state.open_positions - 1)
            self.state.daily_pnl += pnl
            self._maybe_trigger_daily_stop()

    def apply_exchange_daily_pnl(self, pnl: float) -> bool:
        """
        Replace daily PnL with the exchange snapshot (realized + unrealized).

        Hyperliquid is the source of truth for portfolio drawdown; this catches
        manual trades, fees, and open-position losses that record_trade_close misses.
        Returns True when stop mode was newly triggered.
        """
        self._check_reset()
        with self._lock:
            self.state.daily_pnl = float(pnl)
            return self._maybe_trigger_daily_stop()

    def _maybe_trigger_daily_stop(self) -> bool:
        """Activate stop mode when daily PnL breaches the configured ceiling."""
        if self.state.daily_pnl <= -self.daily_stop_loss:
            if not self.state.is_stop_mode:
                self.state.is_stop_mode = True
                self.state.stop_reason = (
                    f"Daily Stop Loss Hit: {self.state.daily_pnl:.2f} <= -{self.daily_stop_loss}"
                )
                return True
        return False

    def update_settings(
        self,
        max_positions: int = None,
        daily_stop_loss: float = None,
        max_notional_cap_multiplier: float = None,
    ):
        with self._lock:
            if max_positions is not None:
                self.max_positions = max_positions
            if daily_stop_loss is not None:
                self.daily_stop_loss = daily_stop_loss
            if max_notional_cap_multiplier is not None:
                self.max_notional_cap_multiplier = float(max_notional_cap_multiplier)

    def get_status(self) -> dict:
        self._check_reset()
        with self._lock:
            return {
                "daily_pnl": self.state.daily_pnl,
                "open_positions": self.state.open_positions,
                "is_stop_mode": self.state.is_stop_mode,
                "stop_reason": self.state.stop_reason,
                "max_positions": self.max_positions,
                "daily_stop_loss": self.daily_stop_loss,
                "max_notional_cap_multiplier": self.max_notional_cap_multiplier,
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
                    old_count = self.state.open_positions
                    logger.warning(
                        "Position mismatch: bot=%s, hyperliquid=%s (source of truth). Forcing sync.",
                        old_count,
                        real_count,
                    )
                    self.state.open_positions = real_count
                    return {
                        "synced": True,
                        "old_count": old_count,
                        "new_count": real_count,
                        "positions": real_positions,
                    }

            return {"synced": False, "count": real_count}

        except Exception as e:
            logger.error("Error syncing with Hyperliquid: %s", e)
            return {"synced": False, "error": str(e)}

    def calculate_position_size(self, price: float, sl_price: float, equity: float, method: str = "fixed", size_value: float = 20.0, leverage: int = 5, size_type: str = "margin") -> float:
        """
        Calculate position size (in coins) based on risk management rules.
        Args:
            size_type: "margin" (Fixed $ cost) | "notional" (Total position size $) | "risk_pct" (% of equity)
            size_value: value associated with method

        Each trade is sized on full portfolio equity; the risk profile (risk_pct,
        leverage) and max_notional cap define exposure. max_positions only limits
        how many concurrent entries are allowed — it does not divide the budget.
        """
        try:
            if price <= 0:
                return 0.0

            MIN_POSITION_SIZE_USD = MIN_POSITION_NOTIONAL_USD
            max_allowed_notional = self._max_notional(equity)

            if equity <= 0:
                logger.error(
                    "Cannot size position: account equity is $%.2f (need equity > 0).",
                    equity,
                )
                return 0.0

            size_coins = 0.0
            
            # 1. Risk % Based (Equity %) — full portfolio, profile defines %
            if method == "risk_pct" and sl_price is not None and sl_price > 0 and price != sl_price:
                # size_value is treated as % (e.g. 1% = 0.01)
                risk_per_trade_pct = size_value / 100.0 if size_value > 1 else size_value
                risk_amount = equity * risk_per_trade_pct
                price_diff = abs(price - sl_price)
                if price_diff <= 0:
                    logger.warning("Risk sizing skipped: entry price equals stop-loss.")
                else:
                    size_coins = risk_amount / price_diff
                
            # 2. Fixed Notional ($ Value)
            elif size_type == "notional":
                 size_coins = size_value / price
                 
            # 3. Fixed Margin (Cost $) - DEFAULT
            else:
                position_value = min(size_value * leverage, max_allowed_notional)
                if position_value < size_value * leverage:
                    logger.info(
                        "Sizing scaled to $%.2f notional (target $%.2f, equity $%.2f).",
                        position_value,
                        size_value * leverage,
                        equity,
                    )
                size_coins = position_value / price

            # --- SAFETY CLAMPING (max cap first, then Hyperliquid minimum) ---
            position_notional = size_coins * price

            if position_notional > max_allowed_notional + 1e-6:
                logger.warning(
                    "Position size $%.2f exceeds notional cap $%.2f "
                    "(equity $%.2f × %.0f). Clamping.",
                    position_notional,
                    max_allowed_notional,
                    equity,
                    self.max_notional_cap_multiplier,
                )
                position_notional = max_allowed_notional
                size_coins = max_allowed_notional / price

            if position_notional < MIN_POSITION_SIZE_USD:
                if max_allowed_notional < MIN_POSITION_SIZE_USD:
                    logger.error(
                        "Position blocked: max affordable notional $%.2f (equity $%.2f) "
                        "is below Hyperliquid minimum $%.2f.",
                        max_allowed_notional,
                        equity,
                        MIN_POSITION_SIZE_USD,
                    )
                    return 0.0
                logger.warning(
                    "Position size $%.2f < Min $%.2f. Clamping to Min.",
                    position_notional,
                    MIN_POSITION_SIZE_USD,
                )
                size_coins = MIN_POSITION_SIZE_USD / price

            return size_coins

        except Exception as e:
            logger.error("Error calculating position size: %s", e)
            return 0.0


