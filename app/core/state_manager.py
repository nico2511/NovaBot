import json
import os
from datetime import datetime

STATE_FILE = "bot_state.json"

class StateManager:
    @staticmethod
    def save_state(context):
        """Saves critical bot state to JSON."""
        state = {
            "active_trade": context.active_trade,
            "trading_enabled": context.trading_enabled,
            "active_symbol": context.active_symbol,
            "last_updated": str(datetime.now())
        }
        
        # Save Risk Manager State as well
        risk_status = context.risk_manager.get_status()
        state["risk_state"] = {
            "daily_pnl": risk_status["daily_pnl"],
            "open_positions": risk_status["open_positions"],
            "is_stop_mode": risk_status["is_stop_mode"],
            "stop_reason": risk_status["stop_reason"]
        }

        try:
            with open(STATE_FILE, "w") as f:
                json.dump(state, f, indent=4, default=str)
        except Exception as e:
            print(f"❌ Failed to save state: {e}")

    @staticmethod
    def load_state(context):
        """Restores bot state from JSON."""
        if not os.path.exists(STATE_FILE):
            return

        try:
            with open(STATE_FILE, "r") as f:
                state = json.load(f)
            
            # Restore Context
            context.active_trade = state.get("active_trade")
            context.trading_enabled = state.get("trading_enabled", False)
            context.active_symbol = state.get("active_symbol", "BTC")
            
            # Restore Risk Manager
            if "risk_state" in state:
                rs = state["risk_state"]
                context.risk_manager.state.daily_pnl = rs.get("daily_pnl", 0.0)
                context.risk_manager.state.open_positions = rs.get("open_positions", 0)
                context.risk_manager.state.is_stop_mode = rs.get("is_stop_mode", False)
                context.risk_manager.state.stop_reason = rs.get("stop_reason", "")
                
            print("✅ State restored from persistence file.")
        except Exception as e:
            print(f"❌ Failed to load state: {e}")
