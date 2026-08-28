import json
import logging
import os
from datetime import datetime


# Fix: Use absolute path to ensure both backend and main bot access the same file
# app/core/state_manager.py -> app/core -> app -> ROOT
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
# Hardening for Coolify: Keep state in the persistent data volume
STATE_FILE = os.path.join(ROOT_DIR, "data", "bot_state.json")

logger = logging.getLogger(__name__)

class StateManager:
    @staticmethod
    def _parse_sticky_ts(value):
        if not value:
            return None
        try:
            import pandas as pd

            parsed = pd.to_datetime(value, errors="coerce")
            if parsed is not None and not pd.isna(parsed):
                return parsed
        except Exception:
            return None
        return None

    @staticmethod
    def _dump_sticky_ts(value):
        if value is None:
            return None
        try:
            return str(value)
        except Exception:
            return None

    @staticmethod
    def _serialize_sticky(sticky) -> list:
        """Persist per-(strategy, symbol) armed state across restarts."""
        if not isinstance(sticky, dict) or not sticky:
            return []
        out = []
        for key, state in sticky.items():
            try:
                if isinstance(key, tuple) and len(key) >= 2:
                    sname, symbol = key[0], key[1]
                elif isinstance(key, str) and "|" in key:
                    sname, symbol = key.split("|", 1)
                else:
                    continue
                if not isinstance(state, dict):
                    continue
                out.append(
                    {
                        "strategy": sname,
                        "symbol": symbol,
                        "looking_for_entry": bool(state.get("looking_for_entry")),
                        "entry_direction": state.get("entry_direction"),
                        "_last_entry_time": StateManager._dump_sticky_ts(
                            state.get("_last_entry_time")
                        ),
                        "_last_signal_bar": StateManager._dump_sticky_ts(
                            state.get("_last_signal_bar")
                        ),
                    }
                )
            except Exception:
                continue
        return out

    @staticmethod
    def _deserialize_sticky(raw) -> dict:
        sticky = {}
        if not isinstance(raw, list):
            return sticky
        for row in raw:
            if not isinstance(row, dict):
                continue
            sname = row.get("strategy")
            symbol = row.get("symbol")
            if not sname or not symbol:
                continue
            sticky[(sname, symbol)] = {
                "looking_for_entry": bool(row.get("looking_for_entry")),
                "entry_direction": row.get("entry_direction"),
                "_last_entry_time": StateManager._parse_sticky_ts(
                    row.get("_last_entry_time")
                ),
                "_last_signal_bar": StateManager._parse_sticky_ts(
                    row.get("_last_signal_bar")
                ),
            }
        return sticky

    @staticmethod
    def save_state(context):
        """Saves critical bot state to JSON."""
        # Snapshot under trade_lock (persist by trade_id)
        trade_lock = getattr(context, "trade_lock", None)
        book = getattr(context, "trade_book", None)
        if trade_lock is not None:
            with trade_lock:
                if book is not None:
                    active_trades_snapshot = book.to_persist_dict()
                else:
                    active_trades_snapshot = dict(context.active_trades)
        else:
            if book is not None:
                active_trades_snapshot = book.to_persist_dict()
            else:
                active_trades_snapshot = dict(context.active_trades)

        state = {
            "active_trades": active_trades_snapshot,  # trade_id → trade (migrates from symbol keys on load)
            "trading_enabled": context.trading_enabled,
            # NOTE: is_running is intentionally NOT saved — it is a runtime-only flag.
            # Threads never survive a process restart; restoring is_running=True would
            # cause a misleading 'thread dead, restarting' message on every boot.
            "active_symbol": context.active_symbol,
            "allow_same_symbol_concurrent": bool(
                getattr(context, "allow_same_symbol_concurrent", False)
            ),
            "strategy_sticky": StateManager._serialize_sticky(
                getattr(context, "_strategy_sticky", None)
            ),
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
            logger.debug("State saved atomically to %s", STATE_FILE)
        except Exception as e:
            logger.error("Failed to save state: %s", e)
            if os.path.exists(temp_file):
                try:
                    os.remove(temp_file)
                except OSError:
                    pass

    @staticmethod
    def load_state(context):
        """Restores bot state from JSON."""
        if not os.path.exists(STATE_FILE):
            logger.info("State file %s not found. Starting fresh.", STATE_FILE)
            return {}

        try:
            with open(STATE_FILE, "r") as f:
                state = json.load(f)
            
            state_modified = False # Track if we need to auto-save defaults
            
            # MIGRATION: Convert old active_trade (singleton) to active_trades (dict)
            from app.core.trade_book import TradeBook

            if "active_trade" in state and "active_trades" not in state:
                old_trade = state.get("active_trade")
                if old_trade:
                    from app.core.config import bootstrap_active_symbol
                    symbol = old_trade.get("symbol", bootstrap_active_symbol())
                    context.active_trades = {symbol: old_trade}
                    logger.info("Migrated legacy active_trade to active_trades[%s]", symbol)
                    state_modified = True
                else:
                    context.active_trades = {}
            else:
                active_trades = state.get("active_trades", {})
                if not isinstance(active_trades, dict):
                    logger.warning(
                        "Corrupted active_trades in state file (got %s). Resetting to empty dict.",
                        type(active_trades),
                    )
                    active_trades = {}
                context.trade_book = TradeBook.from_persist(active_trades)

            context.allow_same_symbol_concurrent = bool(
                state.get("allow_same_symbol_concurrent", False)
            )
            context._strategy_sticky = StateManager._deserialize_sticky(
                state.get("strategy_sticky")
            )
            
            context.trading_enabled = state.get("trading_enabled", False)
            # is_running is always False at load time — threads do not survive restarts.
            context.is_running = False
            
            from app.core.config import bootstrap_active_symbol
            context.active_symbol = state.get("active_symbol") or bootstrap_active_symbol()
            
            # Restore Risk Manager
            if "risk_state" in state:
                rs = state["risk_state"]
                context.risk_manager.state.daily_pnl = rs.get("daily_pnl", 0.0)
                context.risk_manager.state.open_positions = rs.get("open_positions", 0)
                context.risk_manager.state.is_stop_mode = rs.get("is_stop_mode", False)
                context.risk_manager.state.stop_reason = rs.get("stop_reason", "")
            
            # SANITY CHECK: Sync Risk Manager with Active Trades
            num_active_trades = len(context.active_trades)
            if num_active_trades == 0:
                if context.risk_manager.state.open_positions > 0:
                    logger.warning(
                        "Detected phantom positions in RiskManager (%s). Resetting to 0.",
                        context.risk_manager.state.open_positions,
                    )
                    context.risk_manager.state.open_positions = 0
            elif context.risk_manager.state.open_positions != num_active_trades:
                logger.info(
                    "Syncing RiskManager position count: %s -> %s",
                    context.risk_manager.state.open_positions,
                    num_active_trades,
                )
                context.risk_manager.state.open_positions = num_active_trades
            
            # Scanner + Global settings are NOT restored from bot_state.json.
            # They come from data/config/user_settings.json (or .env defaults) and are
            # seeded in BotContext.__init__ via app.core.config. This avoids persisting
            # stale configuration back into runtime.

            # If state was modified (defaults applied or migration occurred), persist it immediately
            if state_modified:
                logger.info("State modified during load (defaults applied). Saving updates...")
                StateManager.save_state(context)

            logger.info("State restored from persistence file.")
            return state
        except Exception as e:
            logger.error("Failed to load state: %s", e)
            return {}
