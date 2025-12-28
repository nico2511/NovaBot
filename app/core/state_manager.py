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
            "is_running": context.is_running,
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
        
        # Save Sidebar Settings
        if hasattr(context, 'sidebar_settings'):
            state["sidebar_settings"] = context.sidebar_settings

        # Save Scanner Settings
        if hasattr(context, 'scanner_settings'):
            state["scanner_settings"] = context.scanner_settings

        # Atomic write to prevent corruption
        temp_file = f"{STATE_FILE}.tmp"
        try:
            with open(temp_file, "w") as f:
                json.dump(state, f, indent=4, default=str)
                f.flush()
                # os.fsync(f.fileno()) 
            os.replace(temp_file, STATE_FILE)
            print(f"✅ State saved atomically to {STATE_FILE}")
        except Exception as e:
            print(f"❌ Failed to save state: {e}")
            if os.path.exists(temp_file):
                try: os.remove(temp_file)
                except: pass

    @staticmethod
    def load_state(context):
        """Restores bot state from JSON."""
        if not os.path.exists(STATE_FILE):
            print(f"⚠️ State file {STATE_FILE} not found. Starting fresh.")
            # Initialize crucial settings to avoid overwrite race
            context.sidebar_settings = {}
            return

        try:
            with open(STATE_FILE, "r") as f:
                state = json.load(f)
            
            # Restore Context
            context.active_trade = state.get("active_trade")
            context.trading_enabled = state.get("trading_enabled", False)
            context.is_running = state.get("is_running", False)
            context.active_symbol = state.get("active_symbol", "BTC")
            
            # Restore Risk Manager
            if "risk_state" in state:
                rs = state["risk_state"]
                context.risk_manager.state.daily_pnl = rs.get("daily_pnl", 0.0)
                context.risk_manager.state.open_positions = rs.get("open_positions", 0)
                context.risk_manager.state.is_stop_mode = rs.get("is_stop_mode", False)
                context.risk_manager.state.stop_reason = rs.get("stop_reason", "")
            
            # SANITY CHECK: Sync Risk Manager with Active Trade
            if context.active_trade is None:
                if context.risk_manager.state.open_positions > 0:
                    print(f"⚠️ Detected phantom positions in RiskManager ({context.risk_manager.state.open_positions}). Reseting to 0.")
                    context.risk_manager.state.open_positions = 0
            else:
                # If we have an active trade, ensure at least 1 position is counted
                if context.risk_manager.state.open_positions == 0:
                     context.risk_manager.state.open_positions = 1
            
            # Restore Sidebar Settings
            if "sidebar_settings" in state:
                context.sidebar_settings = state["sidebar_settings"]
                print(f"✅ Loaded sidebar settings: {context.sidebar_settings}")
            else:
                print("⚠️ No sidebar_settings found in state file. Initializing empty.")
                context.sidebar_settings = {}
            
            # Restore Scanner Settings
            if "scanner_settings" in state:
                context.scanner_settings = state["scanner_settings"]
                print(f"✅ Loaded scanner settings: {context.scanner_settings}")
            else:
                context.scanner_settings = {
                    "enabled": False,
                    "interval": 15, 
                    "min_score": 75,
                    "auto_switch": False
                }
                
            print("✅ State restored from persistence file.")
        except Exception as e:
            print(f"❌ Failed to load state: {e}")
            # Ensure sidebar settings exists even if load fails
            if not hasattr(context, 'sidebar_settings'):
                context.sidebar_settings = {}
