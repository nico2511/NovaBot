import json
import os
from datetime import datetime


# Fix: Use absolute path to ensure both backend and main bot access the same file
# app/core/state_manager.py -> app/core -> app -> ROOT
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
STATE_FILE = os.path.join(ROOT_DIR, "bot_state.json")

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
        
        # Save Scanner Settings (centralized config)
        # Save Scanner Settings (centralized config)
        # DISABLED: Now managed via user_settings.json
        # if hasattr(context, 'scanner_settings'):
        #    state["scanner_settings"] = context.scanner_settings
        
        # Save Global Settings (for future frontend config)
        # DISABLED: We now rely on user_settings.json as the Source of Truth.
        # Storing them here caused conflicts/overwrites on reload.
        # if hasattr(context, 'global_settings'):
        #     state["global_settings"] = context.global_settings

        # Atomic write with Backup
        temp_file = f"{STATE_FILE}.tmp"
        backup_file = f"{STATE_FILE}.bak"
        
        try:
            # Create backup if exists
            if os.path.exists(STATE_FILE):
                import shutil
                shutil.copy2(STATE_FILE, backup_file)

            with open(temp_file, "w") as f:
                json.dump(state, f, indent=4, default=str)
                f.flush()
                os.fsync(f.fileno()) 
            
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
            return {}

        try:
            with open(STATE_FILE, "r") as f:
                state = json.load(f)
            
            state_modified = False # Track if we need to auto-save defaults
            
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
            
            # (sidebar_settings removed - use scanner_settings)
            
            # Restore Scanner Settings
            # Restore Scanner Settings
            # DISABLED: Now managed via user_settings.json
            if False: # if "scanner_settings" in state:
                context.scanner_settings = state["scanner_settings"]
                print(f"✅ Loaded scanner settings: {context.scanner_settings}")
            else:
                 # Initialized in BotContext.__init__ via config
                 pass
                # context.scanner_settings = {
                #     "enabled": False,
                #     "interval": 15, 
                #     "min_score": 50,
                #     "auto_switch": False
                # }
                # state_modified = True  # Mark state as modified

            # Restore Global Settings (Deprioritized - Config/User Settings are Source of Truth)
            # We ONLY load from state if context.global_settings is somehow empty (unlikely with new init)
            # But to be safe and respect user_settings.json, we generally SKIP overwriting from state 
            # unless we implement a specific field-level timestamp check (overkill).
            
            # For now: We assume bot.py __init__ loaded the fresh user_settings.json via config.py.
            # We DO NOT overwrite it with stale state data.
            print("ℹ️ Configuration Strategy: Keeping defaults/user_settings (ignoring potentially stale state global_settings)")

            if False: # DISABLED - See note above.
            # if "global_settings" in state:
                gs = state["global_settings"]
                
                # MIGRATION V1 -> V2 (Integer Threshold -> Tri-Level Object)
                if "ai_conf_threshold" in gs and "ai_thresholds" not in gs:
                    old_val = gs.pop("ai_conf_threshold", 55)
                    print(f"🔄 Migrating legacy AI threshold ({old_val}) to tri-level structure...")
                    gs["ai_thresholds"] = {
                        "high": 101,
                        "medium": old_val, # Use legacy value as medium
                        "low": 101
                    }
                    state_modified = True # Mark state as modified
                    
                # Perform Merge (File overrides Defaults)
                merged_settings = context.global_settings.copy()
                merged_settings.update(gs)
                context.global_settings = merged_settings
                
                print(f"✅ Loaded global settings (merged): {context.global_settings}")
            else:
                # Default global settings
                # context.global_settings = { ... } # Already set in bot.py __init__ via config
                pass
                    "max_positions": 1,
                    "daily_stop_loss": 50.0,
                    "trading_timeframe": "15m",
                    "bot_persona": "Conservative Scalper",
                    "risk_profile": "Capital Preservation First",
                    "ai_thresholds": {
                        "high": 101,
                        "medium": 55,
                        "low": 35
                    },
                    "available_personas": ["Conservative Scalper", "Aggressive Day Trader", "Sniper"],
                    "available_risk_profiles": ["Capital Preservation First", "Balanced Growth", "High Volatility Hunter"]
                }
                state_modified = True # Mark state as modified
                
            # If state was modified (defaults applied or migration occurred), persist it immediately
            if state_modified:
                print("💾 State modified during load (defaults applied). Saving updates...")
                StateManager.save_state(context)

            print("✅ State restored from persistence file.")
            return state
        except Exception as e:
            print(f"❌ Failed to load state: {e}")
            return {}
