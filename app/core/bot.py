
"""
Core Bot Logic Module
Contains the central BotContext class that manages the trading loop, state, and services.
"""
import sys
import os
import logging
import threading
import time
import asyncio
import json
import uuid
import pandas as pd
from collections import deque

# Root Directory Logic
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logger = logging.getLogger(__name__)

from app.core.config import config
from app.core.risk_manager import RiskManager
from app.core.constants import *
from app.core.state_manager import StateManager
from app.core.trade_book import TradeBook
from app.core.trailing_logic import compute_trailing_decision
from app.core.trade_thesis import (
    ACTION_CLOSE_IF_PROFIT,
    ACTION_TIGHTEN_SL,
    MIN_SOFT_CLOSE_PNL_PCT,
    THESIS_DEAD,
    THESIS_WEAK,
    break_even_sl,
    evaluate_supertrend_thesis,
    should_apply_be_tighten,
    thesis_indicators_ready,
)
from app.services.hyperliquid_service import hyperliquid_service
from app.services.discord_service import discord_service
from app.core.trade_recorder import TradeRecorder
from strategies.engine import StrategyEngine
from app.services.ia import ia_service
from app.services.indicators import Indicators
from app.utils.data_processing import get_dynamic_context

# Hardening Phase 0
from app.services.safe_order_manager import SafeOrderManager
from app.services.position_reconciler import PositionReconciler
from app.services.storage import storage_service

class BotContext:
    """Main bot context"""
    def __init__(self):
        logger.info("BotContext v1.1.0 booting (Refactored Core)")
        
        # Thread Safety Lock
        # Re-entrant lock: the trading loop sometimes calls helper methods that
        # also take the lock (e.g. state save → read active_trades). A plain Lock
        # would deadlock; an RLock lets the same thread re-acquire safely.
        self.trade_lock = threading.RLock()
        
        self.risk_manager = RiskManager(
            max_positions=config.DEFAULT_MAX_POSITIONS,
            daily_stop_loss=config.DEFAULT_DAILY_STOP_LOSS,
            max_notional_cap_multiplier=config.MAX_NOTIONAL_CAP_MULTIPLIER,
        )
        # GLOBAL QUOTA - Will be set from global_settings after initialization
        self.max_positions = config.DEFAULT_MAX_POSITIONS
        self.strategy_engine = StrategyEngine(self.risk_manager)
        self.is_running = False
        self.trading_enabled = False
        self.thread = None
        self.account_value = 0.0
        
        # Multi-Position Support: trade_id keyed book (+ symbol index)
        # MUST be initialized BEFORE any property access (like self.latest_data)
        self.active_symbol = config.TRADING_SYMBOL  # Must be set before latest_data
        self.trade_book = TradeBook()
        self.latest_data_map = {}  # { "HYPE": DataFrame, "ETH": DataFrame }
        # HL-safe default: one bot trade per symbol (exchange nets per coin)
        self.allow_same_symbol_concurrent = False
        
        self.latest_data = pd.DataFrame()
        self.latest_analysis = {}
        self.signals_log = deque(maxlen=200)
        self.logs = deque(maxlen=1000)
        self.latest_strategy_result = {}
        self.last_candle_time = None
        # In-trade thesis follow-up (per symbol cooldown)
        self._last_thesis_check: dict = {}
        self._thesis_check_interval_sec = 180  # every ~3 minutes while in a trade
        
        self.trading_enabled = config.AUTO_START_TRADING  # Respect "Auto-start Trading on Bot Launch"
        self.is_running = False      # Loop Switch
        self.active_strategy_name = "supertrend"
        self.active_strategies = []

        # Scanner Settings defaults
        # Scanner Settings defaults (Seeded from user_settings API via config)
        self.scanner_settings = {
            "enabled": config.SCANNER_ENABLED,
            "interval": config.SCANNER_INTERVAL,
            "min_score": config.SCANNER_MIN_SCORE,
            "auto_switch": config.SCANNER_AUTO_SWITCH,
            "min_volume_24h": 2_000_000,
            "min_open_interest": 1_000_000,
            "max_tokens": 40,
            "funding_filter_enabled": False,
            "scan_while_in_trade": False,
            "analyze_top_k": 3,
            "whitelist": [
                "BTC", "ETH", "SOL", "ARB", "OP", "SUI", "APT", "AVAX",
                "LINK", "UNI", "AAVE", "ADA", "NEAR", "INJ", "TIA",
                "DOT", "ATOM", "LTC", "BCH", "XRP"
            ],
        }
        # Per (strategy, symbol) sticky armed state for multi-symbol analysis
        self._strategy_sticky: dict = {}
        # Lazy-init after StrategyEngine exists (constructed just above)
        from app.core.scanner_job import ScannerJob
        self.scanner_job = ScannerJob(self)
        # Global Settings Defaults (Seeded from user_settings API via config)
        self.global_settings = {
            "operations": {
                "trading_timeframe": config.TRADING_TIMEFRAME,
                "auto_start_trading": config.AUTO_START_TRADING,
                "log_level": config.LOG_LEVEL
            },
            "risk_defaults": {
                "max_positions": config.DEFAULT_MAX_POSITIONS,
                "daily_stop_loss": config.DEFAULT_DAILY_STOP_LOSS,
                "bot_persona": config.BOT_PERSONA,
                "risk_profile": config.RISK_PROFILE,
                "default_leverage": config.DEFAULT_LEVERAGE,
                "default_margin_type": "ISOLATED",
                # HL nets one position per coin — keep False until scale-in is implemented
                "allow_same_symbol_concurrent": False,
                "available_personas": ["Conservative Scalper", "Aggressive Day Trader", "Sniper"],
                "available_risk_profiles": ["Capital Preservation First", "Balanced Growth", "High Volatility Hunter"]
            },
            "ai_config": {
                "conf_threshold_high": config.AI_CONF_THRESHOLD_HIGH,
                "conf_threshold_medium": config.AI_CONF_THRESHOLD_MEDIUM,
                "conf_threshold_low": config.AI_CONF_THRESHOLD_LOW,
                "model_name": config.AI_MODEL_NAME,
                "call_cooldown": config.AI_CALL_COOLDOWN
            },
            "notifications": {
                "discord_webhook_alerts": config.DISCORD_WEBHOOK_ALERTS,
                "discord_webhook_logs": config.DISCORD_WEBHOOK_LOGS
            }
        }
        
        # AI Commentary Cache
        self.ai_cache = {
            "last_market_analysis": None,
            "last_market_analysis_time": None,
            "last_position_analysis": None,
            "last_position_analysis_time": None,
            "signal_analyses": deque(maxlen=50),
            "market_snapshots": deque(maxlen=10)
        }
        
        # Startup synchronization flags
        self.startup_sync_done = False
        
        # Periodic Reporting Timers
        self._last_copilot_report_time = time.time()
        self._copilot_report_interval = 600  # 10 minutes
        self._initial_position_analyzed = False
        
        # Candle analysis cache
        self.last_analyzed_candle = None
        
        # Thread health monitoring (heartbeat)
        self._loop_heartbeat = 0  # Timestamp of last trading loop tick
        
        # SL/TP Sync Cooldown (prevent infinite loop)
        self._last_sltp_sync_time = None
        self._sltp_sync_cooldown = 60  # Wait 60s after sync before re-verifying
        
        # AI Call Management
        self.last_ai_call = 0 
        self.ai_call_cooldown = config.AI_CALL_COOLDOWN 
        
        # Leverage state
        self._leverage_synced = False 
        
        # Sync Timers
        self._last_state_sync_time = 0
        self._state_sync_interval = 10  # Seconds
        self._last_pnl_sync = 0  # To track daily PnL sync
        
        # Execution Mode
        self.execution_mode = os.getenv("EXECUTION_MODE", "Live") # Default to Live
        
        # Cooldown tracking (anti-overtrading)
        self._last_trade_info = {"symbol": None, "direction": None, "time": None}
        
        # Discord signal detection anti-spam (same signal repeating every loop)
        self._last_signal_discord = {"signature": None, "time": 0}
        
        # Open Interest History (InMemory)
        self.oi_history = deque(maxlen=2000) 
        
        # Data Persistence (Core)
        self.trade_recorder = TradeRecorder()
        self.latest_analysis = {}
        
        # Phase 0 Hardening Services
        self.safe_order_manager = SafeOrderManager(hyperliquid_service)
        self.safe_order_manager.bot_context = self
        # Position Reconciler - Set reference to self for adoption check
        self.position_reconciler = PositionReconciler(hyperliquid_service, self.safe_order_manager)
        self.position_reconciler.bot_context = self
        

        self.signal_analysis_file = os.path.abspath(os.path.join(BASE_DIR, "data", "analysis", "signal_analysis.json"))
        self._ensure_data_dir()
        
        # Load persisted state
        try:
            state = StateManager.load_state(self)
            
            # Load trading params from global_settings (centralized source)
            requested_max = self.global_settings.get("risk_defaults", {}).get("max_positions", 1)
            
            self.max_positions = requested_max
            try:
                self.risk_manager.update_settings(max_positions=int(requested_max or 1))
            except Exception:
                pass
            self.add_log(f"⚙️ Max positions: {self.max_positions}")
            self.allow_same_symbol_concurrent = bool(
                self.global_settings.get("risk_defaults", {}).get(
                    "allow_same_symbol_concurrent",
                    getattr(self, "allow_same_symbol_concurrent", False),
                )
            )

            # Merge scanner knobs from user_settings.json (SoT for scanner)
            try:
                from app.services.storage import storage_service
                disk_scanner = (storage_service.load_settings() or {}).get("scanner") or {}
                if disk_scanner:
                    self.scanner_settings = {**self.scanner_settings, **disk_scanner}
                    self.add_log(
                        f"🕵️ Scanner settings loaded (enabled={self.scanner_settings.get('enabled')}, "
                        f"auto_switch={self.scanner_settings.get('auto_switch')})"
                    )
            except Exception as scan_load_err:
                logger.warning("Could not load scanner settings from disk: %s", scan_load_err)
                    
        except Exception as e:
            logger.error("Error loading state: %s", e)

        # Initialize Services
        self.trade_recorder = TradeRecorder()
        self.latest_analysis = {}

    def _new_trade_id(self, symbol: str) -> str:
        """Create a stable internal identifier for a trade lifecycle."""
        return TradeBook.new_trade_id(symbol or "UNKNOWN")

    @property
    def active_trades(self):
        """Symbol-keyed view over trade_book (legacy call sites / reconciler)."""
        return self.trade_book.as_symbol_mapping()

    @active_trades.setter
    def active_trades(self, value):
        """Accept dict (legacy symbol map or trade_id map) or TradeBook."""
        if isinstance(value, TradeBook):
            self.trade_book = value
            return
        if isinstance(value, dict):
            self.trade_book = TradeBook.from_persist(value)
            return
        self.trade_book = TradeBook()

    def can_open_trade(self, symbol: str) -> tuple:
        """Return (ok, reason) for a new entry on symbol."""
        return self.trade_book.can_open(
            symbol,
            max_positions=int(self.max_positions or 1),
            allow_same_symbol_concurrent=bool(
                getattr(self, "allow_same_symbol_concurrent", False)
            ),
        )

    def _get_analysis_symbols(self) -> list:
        """Sticky armed symbols ∪ scanner top-K (active_symbol always included)."""
        try:
            k = int((self.scanner_settings or {}).get("analyze_top_k", 3) or 3)
        except (TypeError, ValueError):
            k = 3
        k = max(1, min(k, 10))

        ordered: list = []
        sticky = getattr(self, "_strategy_sticky", {}) or {}
        for (_sname, sym), state in sticky.items():
            if state and state.get("looking_for_entry") and sym and sym not in ordered:
                ordered.append(sym)

        job = getattr(self, "scanner_job", None)
        results = list(getattr(job, "last_results", []) or []) if job else []
        for row in results:
            sym = row.get("symbol") if isinstance(row, dict) else None
            if sym and sym not in ordered:
                ordered.append(sym)
            if len(ordered) >= k:
                break

        active = getattr(self, "active_symbol", None)
        if active and active not in ordered:
            ordered.insert(0, active)
        elif active and ordered and ordered[0] != active:
            # Keep UI focus first among analyzed set when present
            ordered = [active] + [s for s in ordered if s != active]

        return ordered[:k] if ordered else ([active] if active else [])

    _STICKY_FIELDS = ("looking_for_entry", "entry_direction", "_last_entry_time")

    def _restore_strategy_sticky(self, symbol: str) -> None:
        engine = getattr(self, "strategy_engine", None)
        if not engine or not getattr(engine, "strategies", None):
            return
        sticky = getattr(self, "_strategy_sticky", None)
        if sticky is None:
            self._strategy_sticky = {}
            sticky = self._strategy_sticky
        for name, strat in engine.strategies.items():
            state = sticky.get((name, symbol))
            if not state:
                if hasattr(strat, "looking_for_entry"):
                    strat.looking_for_entry = False
                if hasattr(strat, "entry_direction"):
                    strat.entry_direction = None
                continue
            for field in self._STICKY_FIELDS:
                if hasattr(strat, field) and field in state:
                    setattr(strat, field, state[field])

    def _save_strategy_sticky(self, symbol: str) -> None:
        engine = getattr(self, "strategy_engine", None)
        if not engine or not getattr(engine, "strategies", None):
            return
        if not hasattr(self, "_strategy_sticky") or self._strategy_sticky is None:
            self._strategy_sticky = {}
        for name, strat in engine.strategies.items():
            self._strategy_sticky[(name, symbol)] = {
                field: getattr(strat, field, None) for field in self._STICKY_FIELDS
            }

    def _analyze_symbol_market(self, symbol: str) -> dict:
        """
        Fetch candles + run strategy engine for one symbol.
        Returns dict with keys: ok, result, technical_context, df_15m, df_1m, error
        Restores/saves sticky around the call.
        """
        self._restore_strategy_sticky(symbol)
        try:
            df_15m = hyperliquid_service.get_candles(symbol, interval="15m", limit=300)
            df_1m = hyperliquid_service.get_candles(symbol, interval="1m", limit=100)
            df_1h = hyperliquid_service.get_candles(symbol, interval="1h", limit=300)

            if df_15m.empty:
                df_15m = hyperliquid_service.get_candles(symbol, interval="15m", limit=300)
            if df_1m.empty:
                df_1m = hyperliquid_service.get_candles(symbol, interval="1m", limit=100)
            if df_1h.empty:
                df_1h = hyperliquid_service.get_candles(symbol, interval="1h", limit=300)

            if df_15m.empty or df_1m.empty:
                return {
                    "ok": False,
                    "error": f"No data for {symbol}: 15m={len(df_15m)} 1m={len(df_1m)}",
                }

            numeric_cols = ["open", "high", "low", "close", "volume"]
            for df_target in [df_15m, df_1m, df_1h]:
                if df_target is None or getattr(df_target, "empty", True):
                    continue
                for col in numeric_cols:
                    if col in df_target.columns:
                        df_target[col] = df_target[col].astype(float)

            self.latest_data_map[symbol] = df_15m

            funding_rate_live = 0.0
            try:
                funding_rate_live = float(hyperliquid_service.get_funding_rate(symbol) or 0.0)
            except Exception:
                funding_rate_live = 0.0

            result = self.strategy_engine.analyze(
                df_15m,
                extra_data={
                    "1m": df_1m,
                    "1h": df_1h,
                    "symbol": symbol,
                    "funding_rate": funding_rate_live,
                },
            )

            technical_context = {
                "regime": result.get("regime"),
                "adx": round(result.get("adx", 0), 2),
                "adx_slope": round(result.get("adx_slope", 0), 2),
                "rsi": round(result.get("rsi", 0), 2),
                "ema_9": round(result.get("ema_9", 0), 4),
                "ema_20": round(result.get("ema_20", 0), 4),
                "ema_50": round(result.get("ema_50", 0), 4),
                "bb_upper": round(result.get("bb_upper", 0), 4),
                "bb_lower": round(result.get("bb_lower", 0), 4),
                "bb_width": round(result.get("bb_width", 0), 2),
                "volume_ratio": round(result.get("volume_ratio", 100), 1),
                "current_price": result.get("current_price"),
            }

            return {
                "ok": True,
                "result": result,
                "technical_context": technical_context,
                "df_15m": df_15m,
                "df_1m": df_1m,
                "df_1h": df_1h,
            }
        except Exception as e:
            return {"ok": False, "error": str(e)}
        finally:
            self._save_strategy_sticky(symbol)

    @staticmethod
    def _signal_priority(sig: dict) -> tuple:
        """LT wins over ST on the same tick; then score."""
        name = str((sig or {}).get("strategy") or "")
        pri = 100 if name == "trend_lt" else 50
        try:
            score = float((sig or {}).get("score") or 0)
        except (TypeError, ValueError):
            score = 0.0
        return (pri, score)

    def add_log(self, message: str, metadata: dict = None):
        """Add log message with optional metadata"""
        timestamp = pd.Timestamp.now().strftime('%H:%M:%S')
        
        # Store structured entry for API/Frontend
        structured_entry = {
            "timestamp": timestamp,
            "message": message,
            "metadata": metadata
        }
        self.logs.append(structured_entry)
        
        # String representation for Console/File
        log_str = f"{timestamp} {message}"
        print(f"[BOT] {message}")
        # Reduce console noise: keep metadata for API/history, print it only on important events.
        metadata_quiet_prefixes = (
            "📊 Regime:",
            "🟡 Live (forming):",
            "⏸️ Next analysis",
            "🔄 Entering strategy analysis",
            "🎯 Stratégies actives >",
        )
        should_print_metadata = bool(metadata) and not message.startswith(metadata_quiet_prefixes)
        if should_print_metadata:
            print(f"   >>> Metadata: {metadata}")
            
        try:
            self._write_activity_log(log_str)
        except Exception as e:
            logger.warning("Log write error: %s", e)

        self._forward_log_to_discord(message, metadata)

    def _forward_log_to_discord(self, message: str, metadata: dict = None) -> None:
        """Mirror bot warnings/errors to Discord alerts (Coolify log limit workaround)."""
        if metadata and metadata.get("discord_sent"):
            return
        if metadata and metadata.get("quiet"):
            return

        quiet_prefixes = (
            "📊 Regime:",
            "🟡 Live (forming):",
            "⏸️ Next analysis",
            "🔄 Entering strategy analysis",
            "🎯 Stratégies actives >",
            "📏 Sizing:",
            "📏 SIZING",
        )
        if message.startswith(quiet_prefixes):
            return

        level = None
        upper = message.upper()
        if any(marker in message for marker in ("❌", "⛔", "🔥")) or any(
            token in upper for token in ("ERROR", "FAILED", "EXCEPTION", "TRACEBACK", "CRASH")
        ):
            level = "ERROR"
        elif message.startswith("⚠️") or "⚠️" in message[:4] or "WARNING" in upper:
            level = "WARNING"

        if not level:
            return

        body = message
        if metadata:
            try:
                import json
                extra = json.dumps(metadata, default=str)[:900]
                body = f"{message}\n\n`{extra}`"
            except Exception:
                pass

        try:
            discord_service.notify(level, "NovaBot", body, source="bot")
        except Exception as e:
            logger.warning("Discord bot log forward failed: %s", e)

    def _log_execution_error(self, title: str, **fields):
        """Structured execution failure → Discord + local log (single alert)."""
        try:
            discord_service.send_execution_error(title, **fields)
        except Exception as e:
            logger.warning("Discord execution alert failed: %s", e)
        summary = title
        reason = fields.get("reason")
        if reason:
            summary = f"{title} — {reason}"
        self.add_log(f"❌ {summary}", metadata={"discord_sent": True})

    # Lightweight rotation for bot_activity.log: when the file exceeds
    # _ACTIVITY_LOG_MAX_BYTES, it is rotated to .1 (keeping a single backup).
    # Using a custom rotation instead of logging.RotatingFileHandler because
    # add_log writes pre-formatted lines (with its own timestamp format).
    _ACTIVITY_LOG_MAX_BYTES = 5 * 1024 * 1024  # 5 MB
    _ACTIVITY_LOG_PATH = os.path.join(BASE_DIR, "logs", "bot_activity.log")
    _AI_PAYLOAD_LOG_PATH = os.path.join(BASE_DIR, "logs", "ai_payload.jsonl")

    def _write_activity_log(self, line: str) -> None:
        path = self._ACTIVITY_LOG_PATH
        try:
            os.makedirs(os.path.dirname(path), exist_ok=True)
        except Exception:
            pass
        try:
            if os.path.exists(path) and os.path.getsize(path) >= self._ACTIVITY_LOG_MAX_BYTES:
                backup = path + ".1"
                try:
                    if os.path.exists(backup):
                        os.remove(backup)
                    os.rename(path, backup)
                except Exception:
                    pass
        except Exception:
            pass
        with open(path, "a", encoding="utf-8") as f:
            f.write(f"{line}\n")

    def _write_ai_payload_log(self, obj: dict) -> None:
        """
        Write AI payload/response to a dedicated JSONL log file.
        This is meant for coherence/debugging: what we sent vs what we got back.
        """
        try:
            os.makedirs(os.path.dirname(self._AI_PAYLOAD_LOG_PATH), exist_ok=True)
        except Exception:
            pass
        try:
            with open(self._AI_PAYLOAD_LOG_PATH, "a", encoding="utf-8") as f:
                f.write(json.dumps(obj, ensure_ascii=False, default=str) + "\n")
        except Exception as e:
            self.add_log(f"⚠️ Failed to write AI payload log: {e}")

    def _ai_payload_debug_enabled(self) -> bool:
        try:
            return bool(
                config.AI_PAYLOAD_DEBUG or
                (self.global_settings.get("operations", {}) or {}).get("ai_payload_debug", False)
            )
        except Exception:
            return bool(config.AI_PAYLOAD_DEBUG)

    def _ai_payload_debug_discord_enabled(self) -> bool:
        try:
            return bool(
                config.AI_PAYLOAD_DEBUG_DISCORD or
                (self.global_settings.get("operations", {}) or {}).get("ai_payload_debug_discord", False)
            )
        except Exception:
            return bool(config.AI_PAYLOAD_DEBUG_DISCORD)

    @staticmethod
    def _safe_json_preview(obj: dict, max_chars: int) -> str:
        try:
            s = json.dumps(obj, ensure_ascii=False, default=str)
        except Exception:
            s = str(obj)
        if max_chars and len(s) > max_chars:
            return s[:max_chars] + "…(truncated)"
        return s

    def _notify_signal_detected_discord(
        self,
        sig: dict,
        technical_context: dict,
        ai_trace_id: str = None,
        ai_payload_preview: dict = None,
    ):
        """Send a Discord notification when a strategy signal is detected (pre-AI)."""
        try:
            symbol = sig.get("symbol", self.active_symbol)
            side = str(sig.get("signal", "UNKNOWN")).upper()
            strategy = sig.get("strategy", "unknown")
            price = float(sig.get("price", 0) or 0)
            sl = sig.get("sl")
            tp = sig.get("tp")
            sig_ts = str(sig.get("timestamp", "n/a"))

            # Avoid Discord spam: dedupe by strategy signal candle, not by live price ticks.
            # Same candle can trigger repeated loops with tiny price changes.
            signature = (
                f"{symbol}|{strategy}|{side}|"
                f"{round(float(sl), 8) if sl else 'na'}|"
                f"{round(float(tp), 8) if tp else 'na'}|"
                f"{sig_ts}"
            )
            now_ts = time.time()
            if (
                self._last_signal_discord.get("signature") == signature and
                (now_ts - float(self._last_signal_discord.get("time", 0) or 0)) < 300
            ):
                return

            self._last_signal_discord = {"signature": signature, "time": now_ts}

            regime = technical_context.get("regime", "UNKNOWN")
            adx = technical_context.get("adx", 0)
            adx_slope = technical_context.get("adx_slope", 0)
            rsi = technical_context.get("rsi", 0)
            ema20 = technical_context.get("ema_20", 0)
            ema50 = technical_context.get("ema_50", 0)
            vol_ratio = technical_context.get("volume_ratio", 0)
            ema_trend = "↗" if ema20 > ema50 else "↘" if ema20 < ema50 else "→"

            debug_payload = {
                "symbol": symbol,
                "strategy": strategy,
                "signal": side,
                "price": round(price, 8),
                "sl": round(float(sl), 8) if sl is not None else None,
                "tp": round(float(tp), 8) if tp is not None else None,
                "regime": regime,
                "adx": adx,
                "adx_slope": adx_slope,
                "rsi": rsi,
                "ema_20": ema20,
                "ema_50": ema50,
                "ema_trend": ema_trend,
                "volume_ratio": vol_ratio,
                "timestamp": sig_ts,
            }
            payload_str = json.dumps(debug_payload, ensure_ascii=False)

            color = "00FF00" if side == "BUY" else "FF0000" if side == "SELL" else "FFD166"
            trace_part = f" (trace={ai_trace_id})" if ai_trace_id else ""
            title = f"📡 SIGNAL DETECTED (Pre-AI): {side} {symbol}{trace_part}"

            ai_payload_str = ""
            if ai_payload_preview:
                try:
                    ai_payload_str = json.dumps(ai_payload_preview, ensure_ascii=False, default=str)
                except Exception:
                    ai_payload_str = str(ai_payload_preview)
            description = (
                f"Strategy: {strategy}\n"
                f"Entry: {price:.8f}\n"
                f"SL/TP: {sl if sl is not None else 'N/A'} / {tp if tp is not None else 'N/A'}\n"
                f"Regime: {regime} | ADX: {adx} ({adx_slope:+.2f}) | RSI: {rsi}\n"
                f"EMA20/50: {ema_trend} | Vol: {vol_ratio}%\n"
                f"Payload: `{payload_str[:1200]}`"
                + (f"\nAI Data Sent (preview): `{ai_payload_str[:1200]}`" if ai_payload_str else "")
            )
            discord_service.send_alert(title, description, color=color)

            self.add_log(
                f"📨 Discord signal notification sent for {side} {symbol} ({strategy})",
                metadata=debug_payload
            )
        except Exception as notify_err:
            self.add_log(f"⚠️ Failed to send Discord signal notification: {notify_err}")

    def switch_active_symbol(self, new_symbol: str):
        """Securely switch active symbol and update WebSocket subscription"""
        if self.active_symbol == new_symbol:
            return

        old_symbol = self.active_symbol
        self.add_log(f"🔄 Switching active symbol from {old_symbol} to {new_symbol}")
        
        # Multi-Position: No need to clear trades when switching symbols
        # Each symbol maintains its own trade state in active_trades dict
        
        self.active_symbol = new_symbol
        
        try:
            if hyperliquid_service.ws_manager:
                hyperliquid_service.ws_manager.add_symbol(new_symbol)
        except Exception as e:
            self.add_log(f"⚠️ Failed to update WebSocket subscription: {e}")
        
        StateManager.save_state(self)

    # ==========================================
    # BACKWARD COMPATIBILITY LAYER
    # ==========================================
    @property
    def active_trade(self):
        """Backward compatibility: Returns trade for active_symbol"""
        return self.active_trades.get(self.active_symbol)
    
    @active_trade.setter
    def active_trade(self, value):
        """Backward compatibility: Sets trade for active_symbol"""
        if value is None:
            self.active_trades.pop(self.active_symbol, None)
        else:
            self.active_trades[self.active_symbol] = value
    
    @property
    def latest_data(self):
        """Backward compatibility: Returns data for active_symbol"""
        return self.latest_data_map.get(self.active_symbol, pd.DataFrame())
    
    @latest_data.setter
    def latest_data(self, value):
        """Backward compatibility: Sets data for active_symbol"""
        self.latest_data_map[self.active_symbol] = value

    @property
    def copilot_sentiment(self) -> str:
        """Returns the latest market sentiment from Copilot analysis"""
        cache = self.ai_cache.get("last_market_analysis")
        if not cache:
            return "N/A (No analysis yet)"
        
        # New structure: cache is a dict of timeframes
        if isinstance(cache, dict) and "1h" in cache:
            parts = []
            for tf in ["5m", "1h", "4h"]:
                s = cache.get(tf, {})
                sentiment = s.get('sentiment', 'N/A')
                score = s.get('score', 0)
                parts.append(f"{tf}: {sentiment} ({score})")
            return " | ".join(parts)
        
        return "N/A (Analysis pending)"

    def _prepare_ai_context(self, position_data: dict = None) -> dict:
        """Prepare comprehensive market context for professional AI analysis"""
        if not hasattr(self, 'latest_data') or self.latest_data.empty:
            return {}
        
        df = self.latest_data
        current_price = float(df['close'].iloc[-1])
        
        # Technical Indicators
        rsi = float(df['RSI_14'].iloc[-1]) if 'RSI_14' in df.columns else 0.0
        atr_col = next((c for c in ('ATR_14', 'ATRr_14') if c in df.columns), None)
        atr = float(df[atr_col].iloc[-1]) if atr_col else 0.0
        
        # EMAs
        ema_20 = float(df['close'].ewm(span=20).mean().iloc[-1])
        ema_50 = float(df['close'].ewm(span=50).mean().iloc[-1])
        ema_200 = float(df['close'].ewm(span=200).mean().iloc[-1]) if len(df) >= 200 else None
        
        # Price levels — confirmed candle (avoid live-bar wick noise for TP structure)
        hi_idx = -2 if len(df) >= 2 else -1
        swing_high = float(df["high"].iloc[: hi_idx + 1].rolling(20).max().iloc[-1])
        swing_low = float(df["low"].iloc[: hi_idx + 1].rolling(20).min().iloc[-1])
        
        # Volume — confirmed candle only (live bar often starts at ~0 and false-vetoes)
        if "volume" in df.columns and len(df) >= 2:
            vol_confirmed = df["volume"].iloc[:-1]
            avg_volume = float(vol_confirmed.rolling(50).mean().iloc[-1])
            current_volume = float(vol_confirmed.iloc[-1])
        elif "volume" in df.columns and len(df) >= 1:
            avg_volume = float(df["volume"].rolling(50).mean().iloc[-1])
            current_volume = float(df["volume"].iloc[-1])
        else:
            avg_volume = 0.0
            current_volume = 0.0
        volume_ratio = (current_volume / avg_volume) * 100 if avg_volume > 0 else 100
        
        # Volatility percentile
        volatility_percentile = None
        if atr and atr_col:
            atr_series = df[atr_col].dropna()
            if len(atr_series) > 0:
                volatility_percentile = int((atr_series < atr).sum() / len(atr_series) * 100)
        
        # Custom ADX Calculation for Regime
        # IMPORTANT: use confirmed candle (-2) to avoid live-candle noise.
        adx_value = 0
        try:
            adx_df = Indicators.adx(df['high'], df['low'], df['close'], 14)
            adx_idx = -2 if len(adx_df) >= 2 else -1
            adx_value = float(adx_df['ADX'].iloc[adx_idx])
        except Exception:
            pass
            
        # === ENHANCED CONTEXT: MACD ===
        macd_line = 0
        macd_signal = 0
        macd_hist = 0
        try:
             macd_df = Indicators.macd(df['close'])
             macd_line = float(macd_df['MACD'].iloc[-1])
             macd_signal = float(macd_df['MACDs'].iloc[-1])
             macd_hist = float(macd_df['MACDh'].iloc[-1])
        except Exception: 
            pass

        # Regime (15m): avoid binary ADX-only classification.
        # Use ADX hysteresis + compression (BB width) + EMA slope as tiebreakers.
        # Goal: identify clean ranges earlier, while still recognizing real trends.
        adx_trend_on = 27.0
        adx_range_on = 22.0
        bb_width_range_max = 3.0  # % width; lower = tighter range
        ema_slope_flat_max = 0.00015  # ~0.015% per candle
        regime = "UNKNOWN"
        
        # Market Bias maintained via EMA alignment
        market_bias = "BULLISH" if ema_20 > ema_50 else "BEARISH"
        
        # Add ADX and MACD to dynamic context
        dynamic_ctx = get_dynamic_context(df)
        dynamic_ctx['adx'] = round(float(adx_value or 0), 2)
        dynamic_ctx['macd_line'] = round(float(macd_line or 0), 4)
        dynamic_ctx['macd_signal'] = round(float(macd_signal or 0), 4)
        dynamic_ctx['macd_hist'] = round(float(macd_hist or 0), 4)
        
        # === ENHANCED CONTEXT: Bollinger Bands ===
        bb_period = 20
        bb_std = 2.0
        bb_width = None
        try:
            # Use confirmed candle (-2) for regime stability
            bb_idx = -2 if len(df) >= 2 else -1
            bb_middle = df['close'].rolling(bb_period).mean().iloc[bb_idx]
            bb_std_val = df['close'].rolling(bb_period).std().iloc[bb_idx]
            bb_upper = bb_middle + (bb_std * bb_std_val)
            bb_lower = bb_middle - (bb_std * bb_std_val)
            
            # BB Position
            if current_price > bb_upper:
                bb_position = "ABOVE_UPPER"
            elif current_price < bb_lower:
                bb_position = "BELOW_LOWER"
            elif abs(current_price - bb_middle) / bb_middle < 0.005:  # Within 0.5% of middle
                bb_position = "AT_MIDDLE"
            else:
                bb_position = "INSIDE_BANDS"
            
            # BB Width (volatility indicator)
            bb_width = ((bb_upper - bb_lower) / bb_middle) * 100 if bb_middle > 0 else 0
            
            dynamic_ctx['bb_upper'] = round(float(bb_upper or 0), 4)
            dynamic_ctx['bb_middle'] = round(float(bb_middle or 0), 4)
            dynamic_ctx['bb_lower'] = round(float(bb_lower or 0), 4)
            dynamic_ctx['bb_position'] = bb_position
            dynamic_ctx['bb_width'] = round(float(bb_width or 0), 2)
        except Exception:
            pass
        
        # === ENHANCED CONTEXT: EMA Slopes ===
        ema_20_slope = 0.0
        ema_50_slope = 0.0
        try:
            # Calculate EMA slopes (current vs previous candle)
            # Use confirmed candle (-2) vs its previous (-3) where possible
            ema_now_idx = -2 if len(df) >= 2 else -1
            ema_prev_idx = -3 if len(df) >= 3 else -2
            ema_20_now = float(df['close'].ewm(span=20).mean().iloc[ema_now_idx])
            ema_50_now = float(df['close'].ewm(span=50).mean().iloc[ema_now_idx])
            ema_20_prev = float(df['close'].ewm(span=20).mean().iloc[ema_prev_idx])
            ema_50_prev = float(df['close'].ewm(span=50).mean().iloc[ema_prev_idx])
            
            ema_20_slope = ((ema_20_now - ema_20_prev) / ema_20_prev) if ema_20_prev > 0 else 0
            ema_50_slope = ((ema_50_now - ema_50_prev) / ema_50_prev) if ema_50_prev > 0 else 0
            
            dynamic_ctx['ema_20_slope'] = round(ema_20_slope, 6)
            dynamic_ctx['ema_50_slope'] = round(ema_50_slope, 6)
            
            # Slope labels
            if abs(ema_50_slope) < 0.0001:
                dynamic_ctx['ema_50_slope_label'] = "FLAT"
            elif ema_50_slope > 0.0005:
                dynamic_ctx['ema_50_slope_label'] = "RISING"
            elif ema_50_slope < -0.0005:
                dynamic_ctx['ema_50_slope_label'] = "FALLING"
            else:
                dynamic_ctx['ema_50_slope_label'] = "NEUTRAL"
        except Exception:
            pass

        # Final regime decision (after bb_width + ema slopes are available)
        try:
            ema_flat = (abs(float(ema_20_slope or 0)) <= ema_slope_flat_max) and (abs(float(ema_50_slope or 0)) <= ema_slope_flat_max)
            compressed = (bb_width is not None) and (float(bb_width) <= bb_width_range_max)

            if adx_value >= adx_trend_on:
                regime = "TREND"
            elif adx_value <= adx_range_on:
                regime = "RANGE"
            else:
                # Gray zone: decide via structure
                if compressed and ema_flat:
                    regime = "RANGE"
                else:
                    regime = "TREND"

            dynamic_ctx["regime_reason"] = (
                f"adx={adx_value:.1f} "
                f"(range<= {adx_range_on:.0f}, trend>= {adx_trend_on:.0f}), "
                f"bb_width={float(bb_width or 0):.2f}% (<= {bb_width_range_max:.1f}%), "
                f"ema_flat={ema_flat}"
            )
        except Exception:
            # fallback to old behavior
            regime = "TREND" if (adx_value or 0) > 25 else "RANGE"
        
        # === ENHANCED CONTEXT: Fibonacci Levels ===
        try:
            # Calculate Fibonacci retracement levels from swing high/low
            if swing_high and swing_low and swing_high > swing_low:
                swing_range = swing_high - swing_low
                
                # Key Fibonacci levels
                fib_236 = swing_low + (swing_range * 0.236)
                fib_382 = swing_low + (swing_range * 0.382)
                fib_50 = swing_low + (swing_range * 0.50)
                fib_618 = swing_low + (swing_range * 0.618)
                fib_786 = swing_low + (swing_range * 0.786)
                
                # Determine which Fibo zone price is in
                fib_zone = "UNKNOWN"
                if current_price >= fib_786:
                    fib_zone = "ABOVE_78.6%"
                elif current_price >= fib_618:
                    fib_zone = "GOLDEN_ZONE (61.8-78.6%)"
                elif current_price >= fib_50:
                    fib_zone = "MID_ZONE (50-61.8%)"
                elif current_price >= fib_382:
                    fib_zone = "LOWER_ZONE (38.2-50%)"
                elif current_price >= fib_236:
                    fib_zone = "SHALLOW (23.6-38.2%)"
                else:
                    fib_zone = "BELOW_23.6%"
                
                dynamic_ctx['fib_236'] = round(fib_236, 4)
                dynamic_ctx['fib_382'] = round(fib_382, 4)
                dynamic_ctx['fib_50'] = round(fib_50, 4)
                dynamic_ctx['fib_618'] = round(fib_618, 4)
                dynamic_ctx['fib_786'] = round(fib_786, 4)
                dynamic_ctx['fib_zone'] = fib_zone
                dynamic_ctx['swing_range'] = round(swing_range, 4)
        except Exception:
            pass
        
        # Position-specific data
        pnl_percent = 0
        time_in_trade = None
        sl_distance = None
        tp_distance = None
        rr_ratio = None
        
        if position_data:
            entry = position_data.get('entry_price') if isinstance(position_data, dict) else position_data
            if entry is None:
                entry = position_data.get('entry') if isinstance(position_data, dict) else current_price
            
            try:
                entry = float(entry) if entry else current_price
            except (TypeError, ValueError):
                entry = current_price
            
            side = position_data.get('side', 'BUY') if isinstance(position_data, dict) else 'BUY'
            
            if side == 'BUY':
                pnl_percent = ((current_price - entry) / entry) * 100
            else:
                pnl_percent = ((entry - current_price) / entry) * 100
            
            if isinstance(position_data, dict) and 'timestamp' in position_data:
                entry_time = pd.Timestamp(position_data['timestamp'])
                time_in_trade = str(pd.Timestamp.now() - entry_time).split('.')[0]
            
            if isinstance(position_data, dict):
                if 'sl' in position_data and position_data['sl']:
                    try:
                        sl_val = float(position_data['sl'])
                        sl_distance = abs((sl_val - entry) / entry) * 100
                    except (TypeError, ValueError): pass
                if 'tp' in position_data and position_data['tp']:
                    try:
                        tp_val = float(position_data['tp'])
                        tp_distance = abs((tp_val - entry) / entry) * 100
                    except (TypeError, ValueError): pass
            
            if sl_distance and tp_distance and sl_distance > 0:
                rr_ratio = round(tp_distance / sl_distance, 2)
        
        # === ENHANCED CONTEXT: Open Interest & Funding ===
        funding_rate = 0.0
        try:
            funding_rate = hyperliquid_service.get_funding_rate(self.active_symbol)
        except Exception as e:
            logger.debug("Funding rate fetch failed for %s: %s", self.active_symbol, e)
            
        # Extract OI Metrics calculated in trading_loop
        oi_change_pct = float(df['OI_Change_Pct'].iloc[-1]) if 'OI_Change_Pct' in df.columns else 0.0
        oi_divergence = float(df['OI_Divergence'].iloc[-1]) if 'OI_Divergence' in df.columns else 0.0
        oi_vs_ma = float(df['OI_vs_MA'].iloc[-1]) if 'OI_vs_MA' in df.columns else 0.0
        
        return {
            "symbol": self.active_symbol,
            "current_price": current_price,
            "regime": regime,
            "market_bias": market_bias,
            "rsi": rsi,
            "atr": atr,
            "volatility_percentile": volatility_percentile,
            "ema_20": ema_20,
            "ema_50": ema_50,
            "ema_200": ema_200,
            "ema20_distance": round(((current_price - ema_20) / ema_20) * 100, 2),
            "ema50_distance": round(((current_price - ema_50) / ema_50) * 100, 2),
            "swing_high": swing_high,
            "swing_low": swing_low,
            "current_volume": current_volume,
            "avg_volume": avg_volume,
            "volume_ratio": round(volume_ratio, 1),
            "pnl_percent": round(pnl_percent, 2) if position_data else None,
            "time_in_trade": time_in_trade,
            "sl_distance": round(sl_distance, 2) if sl_distance else None,
            "tp_distance": round(tp_distance, 2) if tp_distance else None,
            "rr_ratio": rr_ratio,
            "recent_closes": df['close'].tail(20).tolist() if not df.empty else [],
            "open_interest": hyperliquid_service.get_open_interest(self.active_symbol),
            "funding_rate": funding_rate,
            "oi_change_15m": round(oi_change_pct, 4),
            "oi_divergence": round(oi_divergence, 4),
            "oi_sentiment": "ACCUMULATION" if oi_vs_ma > 1.05 and funding_rate > 0 else "DISTRIBUTION" if oi_vs_ma < 0.95 else "NEUTRAL",
            **dynamic_ctx
        }

    async def _update_market_analysis(self):
        """Disabled"""
        pass

    def _fetch_mtf_sentiment(self, symbol: str) -> str:
        """Build a compact 1h/4h text summary (EMA bias + SuperTrend + ADX)."""
        try:
            from app.services.indicators import Indicators

            lines = []
            for tf in ("1h", "4h"):
                try:
                    df = hyperliquid_service.get_candles(symbol, interval=tf, limit=80)
                except Exception as e:
                    lines.append(f"{tf}: fetch error ({e})")
                    continue
                if df is None or df.empty or len(df) < 30:
                    lines.append(f"{tf}: insufficient data")
                    continue

                idx = -2 if len(df) >= 2 else -1
                close = df["close"]
                ema50 = close.ewm(span=50, adjust=False).mean()
                price = float(close.iloc[idx])
                ema_val = float(ema50.iloc[idx])
                bias = "BULLISH" if price >= ema_val else "BEARISH"
                dist_pct = ((price - ema_val) / ema_val) * 100 if ema_val else 0.0

                st_dir = "N/A"
                try:
                    st = Indicators.supertrend(df["high"], df["low"], df["close"], period=10, multiplier=3.0)
                    direction = int(st["Direction"].iloc[idx])
                    st_dir = "BULLISH" if direction > 0 else "BEARISH"
                except Exception:
                    pass

                adx_val = 0.0
                try:
                    adx_df = Indicators.adx(df["high"], df["low"], df["close"], 14)
                    adx_val = float(adx_df["ADX"].iloc[idx])
                except Exception:
                    pass

                aligned = "ALIGNED" if (
                    (bias == "BULLISH" and st_dir == "BULLISH")
                    or (bias == "BEARISH" and st_dir == "BEARISH")
                ) else "MIXED"
                lines.append(
                    f"{tf}: bias={bias} ST={st_dir} ({aligned}) "
                    f"ADX={adx_val:.1f} close_vs_ema50={dist_pct:+.2f}%"
                )

            if not lines:
                return "Multi-Timeframe Data Unavailable"
            return " | ".join(lines)
        except Exception as e:
            logger.warning("MTF sentiment failed for %s: %s", symbol, e)
            return "Multi-Timeframe Data Unavailable"

    def _ensure_data_dir(self):
        """Ensure data directory exists"""
        data_dir = os.path.dirname(self.signal_analysis_file)
        if not os.path.exists(data_dir):
            os.makedirs(data_dir)

    def _record_signal_analysis(
        self,
        sig: dict,
        ai_data: dict,
        approved: bool,
        indicators: dict = None,
        trace_id: str = None,
        trade_id: str = None,
    ):
        """Record AI signal analysis to a persistent JSON file for audit trail."""
        try:
            # Base entry
            entry = {
                "timestamp": pd.Timestamp.now().isoformat(),
                "symbol": sig.get("symbol") or self.active_symbol,
                "direction": sig.get("signal"),
                "strategy": sig.get("strategy"),
                "approved": approved,
                "confidence": ai_data.get("confidence", 0),
                "reasoning": ai_data.get("reasoning", "No reasoning provided"),
                "risk_level": ai_data.get("risk_level", "UNKNOWN"),
                "risk_score": ai_data.get("risk_score"),
                "decisive_factors": ai_data.get("decisive_factors", []),
                "rejection_reason_category": ai_data.get("rejection_reason_category"),
                "market_price": sig.get("price"),
                "suggested_sl": ai_data.get("suggested_adjustments", {}).get("sl") or sig.get("sl"),
                "suggested_tp": ai_data.get("suggested_adjustments", {}).get("tp") or sig.get("tp"),
                "trace_id": trace_id or sig.get("trace_id") or ai_data.get("trace_id"),
                "trade_id": trade_id or sig.get("trade_id"),
            }
            
            # Enrich with market context for retrospective analysis
            try:
                # 1. Technical Indicators (Use explicit pass if available, else try simple extraction)
                if indicators:
                    entry["indicators"] = indicators
                elif not self.latest_data.empty:
                    last_row = self.latest_data.iloc[-1]
                    entry["indicators"] = {
                        "rsi": round(float(last_row.get("rsi", 0)), 2),
                        "adx": round(float(last_row.get("adx", 0)), 2),
                        "ema20": round(float(last_row.get("ema20", 0)), 6),
                        "ema50": round(float(last_row.get("ema50", 0)), 6),
                        "bb_upper": round(float(last_row.get("bb_upper", 0)), 6),
                        "bb_middle": round(float(last_row.get("bb_middle", 0)), 6),
                        "bb_lower": round(float(last_row.get("bb_lower", 0)), 6),
                        "volume_ratio": round(float(last_row.get("volume_ratio", 0)), 2),
                        "macd": round(float(last_row.get("macd", 0)), 6),
                        "macd_signal": round(float(last_row.get("macd_signal", 0)), 6),
                        "macd_hist": round(float(last_row.get("macd_hist", 0)), 6)
                    }
                
                # 2. Market Regime from latest_analysis
                if self.latest_analysis:
                    entry["regime"] = {
                        "type": self.latest_analysis.get("regime", "UNKNOWN"),
                        "bias": self.latest_analysis.get("bias", "NEUTRAL")
                    }
                
                # 3. Copilot Sentiment (from AI cache)
                if self.ai_cache.get("last_market_analysis"):
                    market_sentiment = self.ai_cache["last_market_analysis"]
                    entry["copilot_sentiment"] = {
                        "5m": {
                            "sentiment": market_sentiment.get("5m", {}).get("sentiment", "UNKNOWN"),
                            "score": market_sentiment.get("5m", {}).get("score", 0),
                            "rsi": market_sentiment.get("5m", {}).get("rsi", 0)
                        },
                        "1h": {
                            "sentiment": market_sentiment.get("1h", {}).get("sentiment", "UNKNOWN"),
                            "score": market_sentiment.get("1h", {}).get("score", 0),
                            "rsi": market_sentiment.get("1h", {}).get("rsi", 0),
                            "trend": market_sentiment.get("1h", {}).get("trend", "UNKNOWN")
                        },
                        "4h": {
                            "sentiment": market_sentiment.get("4h", {}).get("sentiment", "UNKNOWN"),
                            "score": market_sentiment.get("4h", {}).get("score", 0),
                            "rsi": market_sentiment.get("4h", {}).get("rsi", 0)
                        }
                    }
                
                # 4. Funding & OI if available (from latest market data fetch)
                try:
                    # Logic improved: Use the bot's own service (Sync)
                    entry["market_data"] = {
                        "funding_rate": hyperliquid_service.get_funding_rate(self.active_symbol),
                        "open_interest": hyperliquid_service.get_open_interest(self.active_symbol)
                    }
                except: pass
                
            except Exception as ctx_err:
                self.add_log(f"⚠️ Failed to enrich signal context: {ctx_err}")
            
            # Read existing or init new
            history = []
            data_dir = os.path.dirname(self.signal_analysis_file)
            if not os.path.exists(data_dir):
                os.makedirs(data_dir, exist_ok=True)
                
            if os.path.exists(self.signal_analysis_file):
                try:
                    with open(self.signal_analysis_file, "r") as f:
                        history = json.load(f)
                except: history = []
            
            history.append(entry)
            # Keep last 500 signals
            if len(history) > 500:
                history = history[-500:]
            
            with open(self.signal_analysis_file, "w") as f:
                json.dump(history, f, indent=2)
                f.flush()
                os.fsync(f.fileno())
                
            self.add_log(f"💾 Signal Analysis saved to history ({'Approved' if approved else 'Rejected'}) with full market context")
        except Exception as e:
            self.add_log(f"⚠️ Failed to record signal analysis: {e}")


    def execute_entry_atomically(self, symbol: str, side: str, size: float, price: float = None, sl: float = None, tp: float = None, strategy: str = "Unknown", metadata: dict = None, entry_indicators: dict = None, equity: float = None):
        """ATOMIC ENTRY FLOW (Unified v2) - Now captures entry indicators for analysis"""
        ctx = dict(
            symbol=symbol,
            side=side,
            strategy=strategy,
            size=size,
            price=price,
            sl=sl,
            tp=tp,
            equity=equity,
        )
        try:
            # 1. LIVE EXECUTION CHECK
            if not self.trading_enabled:
                reason = "Trading Disabled"
                self.add_log(f"⚠️ Signal ignored ({reason}): {side} {symbol}")
                self._log_execution_error(f"⛔ ENTRY BLOCKED: {side} {symbol}", reason=reason, **ctx)
                return { "status": "ignored", "reason": reason }

            can_trade, risk_reason = self.risk_manager.check_can_trade()
            if not can_trade:
                self.add_log(f"⛔ ENTRY BLOCKED by risk: {risk_reason}")
                self._log_execution_error(
                    f"⛔ ENTRY BLOCKED: {side} {symbol}",
                    reason=risk_reason,
                    **ctx,
                )
                return {"status": "ignored", "reason": risk_reason}
            
            current_price = price if price else hyperliquid_service.get_current_price(symbol)
            ctx["price"] = current_price
            
            # Pre-check rounding (same rules as Hyperliquid execute_order)
            canonical = hyperliquid_service.get_canonical_symbol(symbol)
            sz_decimals, _ = hyperliquid_service._get_precision(canonical)
            if sz_decimals == 0:
                rounded_size = int(size)
            else:
                rounded_size = round(size, sz_decimals)
            if rounded_size <= 0:
                reason = f"Quantity rounds to zero (raw={size}, sz_decimals={sz_decimals})"
                self.add_log(f"❌ Entry Failed: {reason}")
                self._log_execution_error(
                    f"❌ ENTRY FAILED: {side} {symbol}",
                    reason=reason,
                    equity=equity,
                    **{k: v for k, v in ctx.items() if k != "equity"},
                )
                return False
            
            # REAL EXECUTION
            real_positions = hyperliquid_service.get_positions()
            active_count = len([p for p in real_positions if float(p["size"]) > 0])
            
            if active_count >= self.max_positions:
                reason = f"Max positions reached ({active_count}/{self.max_positions})"
                self.add_log(f"⛔ QUOTA EXCEEDED ({active_count}/{self.max_positions}). Entry aborted.")
                self._log_execution_error(
                    f"⛔ ENTRY BLOCKED: {side} {symbol}",
                    reason=reason,
                    equity=equity,
                    **{k: v for k, v in ctx.items() if k != "equity"},
                )
                return False

            ok_book, book_reason = self.can_open_trade(symbol)
            if not ok_book:
                reason = book_reason
                self.add_log(f"⛔ ENTRY BLOCKED (book): {reason}")
                self._log_execution_error(
                    f"⛔ ENTRY BLOCKED: {side} {symbol}",
                    reason=reason,
                    equity=equity,
                    **{k: v for k, v in ctx.items() if k != "equity"},
                )
                return False

            self.add_log(f"🔒 ATOMIC ENTRY START: {side} {symbol} ({size}) via {strategy}")
            self.add_log(f"🧹 Cleaning pre-trade orphans on {symbol}...")
            hyperliquid_service.cancel_all_orders(symbol)

            is_buy = (side == "BUY")
            result = hyperliquid_service.execute_order(
                symbol=symbol, is_buy=is_buy, quantity=size, price=price, sl_price=sl, tp_price=tp
            )
            
            if result.get("status") != "success":
                reason = result.get("message", "Unknown exchange error")
                self.add_log(f"❌ Entry Failed: {reason}")
                self._log_execution_error(
                    f"❌ ENTRY FAILED: {side} {symbol}",
                    reason=reason,
                    equity=equity,
                    rounded_size=rounded_size,
                    sz_decimals=sz_decimals,
                    **{k: v for k, v in ctx.items() if k not in ("equity",)},
                )
                return False

            self.add_log("⏳ Verifying Fill...")
            filled = False
            oid = "unknown"
            
            try:
                raw_res = result.get("result", {})
                statuses = raw_res.get("response", {}).get("data", {}).get("statuses", [])
                if statuses and isinstance(statuses[0], dict):
                     oid = statuses[0].get("oid") or statuses[0].get("filled", {}).get("oid") or oid
            except: pass

            for i in range(5):
                time.sleep(1)
                positions = hyperliquid_service.get_positions()
                pos = next((p for p in positions if p["symbol"] == symbol and float(p['size']) > 0), None)
                if pos:
                    filled = True
                    entry_px = float(pos['entry_price'])
                    self.add_log(f"✅ ENTRY CONFIRMED: {symbol} Size: {pos['size']} Entry: {entry_px}")
                    
                    with self.trade_lock:
                        # CRITICAL: Always sync active_symbol before setting active_trade
                        # otherwise the setter will use the WRONG key in active_trades
                        if self.active_symbol != symbol:
                            self.active_symbol = symbol
                            
                        trade_id = self._new_trade_id(symbol)
                        self.active_trade = {
                            "trade_id": trade_id,
                            "symbol": symbol,
                            "side": side,
                            "entry": entry_px,
                            "sl": sl,
                            "tp": tp,
                            "strategy": strategy,
                            "timestamp": pd.Timestamp.now().isoformat(),
                            "size": float(pos['size']),
                            "leverage": float(pos.get("leverage", 1.0)),
                            "oid": oid,
                            "pnl": 0,
                            "max_pnl": 0,
                            "metadata": metadata or {},
                            "entry_indicators": entry_indicators or {}  # Market snapshot at entry
                        }
                        self.risk_manager.record_trade_open()
                        StateManager.save_state(self)
                        # Force Sync to ensure state consistency
                        self._sync_state(silent=False)

                    
                    discord_service.send_alert(
                        f"🚀 ENTERED {side} {symbol}",
                        f"Strategy: {strategy}\nEntry: {entry_px}\nSize: {pos['size']}\nSL: {sl}\nTP: {tp}\nOID: {oid}",
                        color="00FF00" if side == "BUY" else "FF0000"
                    )
                    break
            
            if not filled:
                reason = "Order sent but position NOT confirmed after 5s"
                self.add_log(f"⚠️ {reason}.")
                self._log_execution_error(
                    f"⚠️ ENTRY UNCONFIRMED: {side} {symbol}",
                    reason=reason,
                    oid=oid,
                    equity=equity,
                    **{k: v for k, v in ctx.items() if k != "equity"},
                )
                return False
                
            return True

        except Exception as e:
            self.add_log(f"❌ ATOMIC ENTRY ERROR: {e}")
            self._log_execution_error(
                f"❌ ENTRY CRASH: {side} {symbol}",
                reason=str(e),
                equity=equity,
                **{k: v for k, v in ctx.items() if k != "equity"},
            )
            return False

    def execute_exit_atomically(self, symbol: str, reason: str = "SIGNAL"):
        """ATOMIC EXIT FLOW (THE KILL SWITCH)"""
        # Verify position exists before attempting to close
        try:
            positions = hyperliquid_service.get_positions()
            if getattr(hyperliquid_service, "_positions_fetch_failed", False) is True:
                self.add_log(
                    f"⛔ Cannot close {symbol}: positions API unavailable — "
                    f"aborting market close (exchange SL/TP stay in place)"
                )
                return False
            position_exists = any(p.get("symbol") == symbol and float(p.get("size", 0)) > 0 for p in positions)
            
            if not position_exists:
                self.add_log(f"⚠️ Cannot close {symbol}: No open position found on exchange.")
                # Only drop memory after a confirmed Close fill — never on a bare empty book
                trade = None
                with self.trade_lock:
                    trade = self.active_trades.get(symbol)
                if trade:
                    self._handle_external_closure(symbol, trade, silent=True)
                return False
        except Exception as e:
            self.add_log(
                f"⛔ Failed to verify position for {symbol}: {e} — "
                f"aborting market close (exchange SL/TP stay in place)"
            )
            return False
            
        tid = None
        try:
            with self.trade_lock:
                t = self.active_trades.get(symbol)
                tid = t.get("trade_id") if isinstance(t, dict) else None
        except Exception:
            tid = None
        self.add_log(f"🔒 ATOMIC EXIT START: Closing {symbol} ({reason})" + (f" | id={tid}" if tid else ""))
        
        # Get position data BEFORE closing for accurate PnL calculation
        positions_before = hyperliquid_service.get_positions()
        if getattr(hyperliquid_service, "_positions_fetch_failed", False) is True:
            self.add_log(
                f"⛔ ATOMIC EXIT aborted for {symbol}: positions API unavailable — "
                f"will not market-close (exchange SL/TP remain in place)"
                + (f" | id={tid}" if tid else "")
            )
            return False
        position_data = next((p for p in positions_before if p["symbol"] == symbol), None)
        
        if not position_data:
            # Flat book from a *successful* fetch — nothing to market-close
            self.add_log(
                f"⚠️ No open position for {symbol} on exchange — skip market close"
                + (f" | id={tid}" if tid else "")
            )
            trade = None
            with self.trade_lock:
                trade = self.active_trades.get(symbol)
            if trade:
                self._handle_external_closure(symbol, trade, silent=True)
            return False
        
        try:
            result = hyperliquid_service.close_position(symbol)
            
            if result.get("status") == "success":
                final_positions = hyperliquid_service.get_positions()
                remaining = next((p for p in final_positions if p["symbol"] == symbol), None)
                
                if not remaining or float(remaining["size"]) == 0:
                     self.add_log(f"✅ POSITION CLOSED: {symbol}")
                     self.add_log(f"🧹 Cleaning post-trade orphans on {symbol}...")
                     hyperliquid_service.cancel_all_orders(symbol)
                     
                     # Calculate PnL from position data (works for all positions)
                     pnl_usdc = 0
                     entry_price = 0
                     exit_price = hyperliquid_service.get_current_price(symbol)
                     size = 0
                     side = "BUY"
                     
                     if position_data:
                         # Use actual position data
                         entry_price = position_data.get("entry_price", 0)
                         size = position_data.get("size", 0)
                         side = position_data.get("side", "BUY")
                         
                         if side == "BUY":
                             pnl_usdc = (exit_price - entry_price) * size
                         else:
                             pnl_usdc = (entry_price - exit_price) * size
                     elif self.active_trade:
                         # Fallback to active_trade if position_data unavailable
                         entry_price = self.active_trade.get("entry", 0)
                         size = self.active_trade.get("size", 0)
                         side = self.active_trade.get("side", "BUY")
                         
                         if side == "BUY":
                             pnl_usdc = (exit_price - entry_price) * size
                         else:
                             pnl_usdc = (entry_price - exit_price) * size
                     
                     # Record trade
                     with self.trade_lock:
                         closed_trade = self.active_trades.get(symbol)
                         self.trade_recorder.add_trade({
                             "trade_id": closed_trade.get("trade_id") if isinstance(closed_trade, dict) else None,
                             "trace_id": (
                                 (closed_trade.get("metadata") or {}).get("trace_id")
                                 if isinstance(closed_trade, dict)
                                 else None
                             ),
                             "symbol": symbol,
                             "strategy": (
                                 closed_trade.get("strategy")
                                 if isinstance(closed_trade, dict) and closed_trade.get("strategy")
                                 else (self.active_trade.get("strategy", "Manual") if self.active_trade else "Manual")
                             ),
                             "side": side,
                             "entry_price": entry_price,
                             "exit_price": exit_price,
                             "size": size,
                             "pnl_usdc": pnl_usdc,
                             "exit_reason": reason,
                             "exit_time": pd.Timestamp.now().isoformat(),
                             "entry_time": (
                                 closed_trade.get("timestamp")
                                 if isinstance(closed_trade, dict)
                                 else None
                             ),
                             "entry_indicators": (
                                 closed_trade.get("entry_indicators", {})
                                 if isinstance(closed_trade, dict)
                                 else (self.active_trade.get("entry_indicators", {}) if self.active_trade else {})
                             ),
                         })
                         
                         discord_service.send_alert(
                             f"🏁 TRADE CLOSED: {symbol}",
                             f"Reason: {reason}\nPnL: ${pnl_usdc:.2f}",
                             color="FFFF00"
                         )
                         self.risk_manager.record_trade_close(pnl_usdc)

                         # Drop local tracking now — intentional close is already recorded.
                         # Prevents _sync_state → _handle_external_closure from double-recording.
                         self.active_trades.pop(symbol, None)
                         
                         # Clear active_trade only if this was the active trade
                         if self.active_trade and self.active_trade.get("symbol") == symbol:
                             self.active_trade = None
                         
                         StateManager.save_state(self)
                         self._sync_state(silent=False)

                     return True
                else:
                    self.add_log(f"⚠️ Close appeared successful but position remains: {remaining['size']}")
                    return False
            else:
                self.add_log(f"❌ Exit Failed: {result.get('message')}")
                return False

        except Exception as e:
            self.add_log(f"❌ ATOMIC EXIT ERROR: {e}")
            return False

    def _check_hard_veto(self, signal: str, market_context: dict, strategy=None):
        """HARD VETO: delegate to the active strategy plan (bot stays a machine)."""
        if strategy is not None and hasattr(strategy, "check_hard_veto"):
            try:
                return strategy.check_hard_veto(signal, market_context)
            except Exception as e:
                self.add_log(f"⚠️ Strategy hard veto error: {e}")
                return None
        # No strategy plan attached — do not apply orphan global métier vetoes
        return None

    def _clear_strategy_entry_cooldown(self, strategy_name: str | None, symbol: str | None = None) -> None:
        """Undo strategy-side entry cooldown after veto/AI reject (no fill happened)."""
        if not strategy_name or not hasattr(self, "strategy_engine"):
            return
        strat = self.strategy_engine.strategies.get(strategy_name)
        if strat is not None and hasattr(strat, "_last_entry_time"):
            strat._last_entry_time = None
        # Sticky map survives across top-K symbol swaps — clear it too
        sym = symbol or getattr(self, "active_symbol", None)
        sticky = getattr(self, "_strategy_sticky", None)
        if sticky is not None and sym:
            key = (strategy_name, sym)
            state = sticky.get(key)
            if isinstance(state, dict):
                state = dict(state)
                state["_last_entry_time"] = None
                sticky[key] = state

    def _attach_trade_id_to_signal_analysis(self, trace_id: str, trade_id: str, symbol: str = None) -> None:
        """Patch the latest matching AI decision with trade_id (no duplicate row)."""
        if not trace_id or not trade_id:
            return
        try:
            path = self.signal_analysis_file
            if not os.path.exists(path):
                return
            with open(path, "r", encoding="utf-8") as f:
                history = json.load(f)
            if not isinstance(history, list) or not history:
                return
            for row in reversed(history):
                if not isinstance(row, dict):
                    continue
                if str(row.get("trace_id") or "") != str(trace_id):
                    continue
                if symbol and str(row.get("symbol") or "").upper() != str(symbol).upper():
                    continue
                row["trade_id"] = trade_id
                break
            with open(path, "w", encoding="utf-8") as f:
                json.dump(history, f, indent=2)
                f.flush()
                os.fsync(f.fileno())
        except Exception as e:
            self.add_log(f"⚠️ Failed to attach trade_id to signal analysis: {e}")

    @staticmethod
    def _normalize_symbol(symbol: str) -> str:
        s = str(symbol or "").upper().replace("-USD", "").replace("-USDC", "").strip()
        # Hyperliquid k-prefix (e.g. kPEPE) → bare ticker for whitelist match
        if s.startswith("K") and len(s) > 2 and s[1:].isalpha():
            return s[1:]
        return s

    def _is_symbol_whitelisted(self, symbol: str) -> bool:
        """Empty whitelist = allow all. Non-empty = only listed coins."""
        settings = getattr(self, "scanner_settings", {}) or {}
        wl = settings.get("whitelist") or []
        if not isinstance(wl, list) or not wl:
            return True
        allowed = {self._normalize_symbol(x) for x in wl if str(x).strip()}
        return self._normalize_symbol(symbol) in allowed

    def _verify_and_enforce_sl_tp(self, symbol: str, trade_data: dict, bypass_cooldown: bool = False):
        """Consolidated verification: Fetch Exchange Orders -> Compare -> Enforce if needed."""
        # GUARD: Only enforce if trading is ENABLED (Real Trading)
        if not self.trading_enabled:
             return

        # PREVENT SYSTEMATIC RECALIBRATION: Only enforce on initial adoption or explicit trailing/BE
        if not bypass_cooldown and trade_data.get("initial_sl_tp_set", False):
            return

        # COOLDOWN: Skip verification if we just synced (prevent infinite loop)
        if not bypass_cooldown and self._last_sltp_sync_time:
            elapsed = (pd.Timestamp.now() - self._last_sltp_sync_time).total_seconds()
            if elapsed < self._sltp_sync_cooldown:
                return  # Too soon, wait for cooldown

        try:
            # Must use frontend_open_orders (via get_open_orders) — open_orders omits triggers
            symbol_orders = hyperliquid_service.get_open_orders(symbol)
            
            desired_sl = float(trade_data.get("sl", 0))
            desired_tp = float(trade_data.get("tp", 0))
            
            found_sl = False
            found_tp = False
            TOLERANCE = 0.005  # Increased from 0.001 to 0.5% to handle rounding differences
            
            for o in symbol_orders:
                # FIX: For trigger orders (SL/TP), use triggerPx (actual trigger), not limitPx (aggressive fill price)
                price = float(o.get("triggerPx") or o.get("limitPx", 0))
                if desired_sl > 0 and abs(price - desired_sl) / desired_sl < TOLERANCE:
                    found_sl = True
                if desired_tp > 0 and abs(price - desired_tp) / desired_tp < TOLERANCE:
                     found_tp = True
            
            needs_sync = False
            if desired_sl > 0 and not found_sl:
                tid = trade_data.get("trade_id") if isinstance(trade_data, dict) else None
                self.add_log(
                    f"⚠️ Audit: SL missing/mismatched on exchange (Target: {desired_sl:.4f}). Enforcing..." +
                    (f" | id={tid}" if tid else "")
                )
                needs_sync = True
            if desired_tp > 0 and not found_tp:
                tid = trade_data.get("trade_id") if isinstance(trade_data, dict) else None
                self.add_log(
                    f"⚠️ Audit: TP missing/mismatched on exchange (Target: {desired_tp:.4f}). Enforcing..." +
                    (f" | id={tid}" if tid else "")
                )
                needs_sync = True
                
            if needs_sync:
                hyperliquid_service.sync_sl_tp(
                    symbol, 
                    trade_data.get("side") == "BUY", 
                    float(trade_data.get("size", 0)), 
                    desired_sl, 
                    desired_tp
                )
                tid = trade_data.get("trade_id") if isinstance(trade_data, dict) else None
                self.add_log("✅ Audit: SL/TP enforced via Sync." + (f" | id={tid}" if tid else ""))
                self._last_sltp_sync_time = pd.Timestamp.now()  # Mark sync time for cooldown
                
        except Exception as e:
            self.add_log(f"⚠️ Error in _verify_and_enforce_sl_tp: {e}")


    def _update_trailing_stops(self, trade: dict, current_price: float) -> bool:
        """Apply a trailing-stop upgrade if `compute_trailing_decision` suggests one.

        This method is intentionally a thin shell: all math lives in
        ``app.core.trailing_logic`` so it can be unit-tested without the bot.
        Side-effects (state save, logging, Discord alert) stay here.
        """
        decision = compute_trailing_decision(trade, current_price)
        if decision is None:
            return False

        tid = trade.get("trade_id") if isinstance(trade, dict) else None
        sl_price = float(trade.get("sl") or 0)
        entry_price = float(trade.get("entry") or 0)
        tp_price = float(trade.get("tp") or 0)
        symbol = trade.get("symbol", self.active_symbol)

        self.add_log(
            f"🛡️ {decision.reason}: Progress {decision.progress_pct:.1f}% / PnL {decision.pnl_pct:.2f}%. "
            f"Moving SL {sl_price:.4f}→{decision.new_sl:.4f}" + (f" | id={tid}" if tid else "")
        )

        with self.trade_lock:
            t_ref = self.active_trades.get(trade.get("symbol"))
            if t_ref:
                t_ref["sl"] = decision.new_sl
                StateManager.save_state(self)

        threshold_hint = {
            "Smart BE": "threshold 75% (or PnL > 2.0% on LONG)",
            "Trailing 80%": "threshold 80%",
            "Aggressive Lock 90%": "threshold 90%",
        }.get(decision.reason, decision.reason)

        discord_service.send_alert(
            f"🛡️ TRAILING — {decision.reason} ({threshold_hint}): {symbol}",
            (
                f"Progress toward TP: {decision.progress_pct:.1f}%\n"
                f"Unrealized PnL: {decision.pnl_pct:+.2f}%\n"
                f"Entry: {entry_price:.2f} | Price: {current_price:.2f} | TP: {tp_price:.2f}\n"
                f"SL: {sl_price:.2f} → {decision.new_sl:.2f}"
            ),
            color="FFA500",  # Orange
        )
        return True

    def _check_local_exits(self, trade: dict, symbol: str, current_price: float):
        """Backup local SL/TP check — exchange trigger orders remain primary.

        Only market-closes when we have a valid live price AND the position is
        still open on a successful positions fetch. API errors must never force
        a close while exchange SL/TP are working.
        """
        # Never exit on a missing/stale quote — price=0 on a SHORT always hits TP.
        if current_price is None or float(current_price) <= 0:
            return

        side = trade.get("side")
        sl_val = float(trade.get("sl") or 0)
        tp_val = float(trade.get("tp") or 0)
        tid = trade.get("trade_id") if isinstance(trade, dict) else None
        
        exit_triggered = False
        reason = ""

        if side == "BUY":
            if sl_val > 0 and current_price <= sl_val:
                exit_triggered = True; reason = "STOP_LOSS"
            elif tp_val > 0 and current_price >= tp_val:
                exit_triggered = True; reason = "TAKE_PROFIT"
        else:
             if sl_val > 0 and current_price >= sl_val:
                exit_triggered = True; reason = "STOP_LOSS"
             elif tp_val > 0 and current_price <= tp_val:
                exit_triggered = True; reason = "TAKE_PROFIT"
                
        if exit_triggered:
            # Prefer letting exchange SL/TP fill; only backstop if position still open
            positions = hyperliquid_service.get_positions()
            if getattr(hyperliquid_service, "_positions_fetch_failed", False) is True:
                self.add_log(
                    f"⚠️ Local {reason} for {symbol} ignored — positions API down; "
                    f"exchange SL/TP remain in charge" + (f" | id={tid}" if tid else "")
                )
                return
            still_open = any(
                p.get("symbol") == symbol and float(p.get("size", 0) or 0) != 0
                for p in (positions or [])
            )
            if not still_open:
                self.add_log(
                    f"ℹ️ Local {reason} for {symbol} but exchange already flat — syncing memory"
                    + (f" | id={tid}" if tid else "")
                )
                self._handle_external_closure(symbol, trade, silent=True)
                return
            self.add_log(f"🎯 Local Trigger: {reason} @ {current_price}" + (f" | id={tid}" if tid else ""))
            self.execute_exit_atomically(symbol, reason)

    def _manage_all_trades(self):
        """Centralized Management for ALL active trades (Concurrent)"""
        trades_to_manage = []
        with self.trade_lock:
            trades_to_manage = list(self.active_trades.values())
        
        if not trades_to_manage:
            return

        for trade in trades_to_manage:
            try:
                symbol = trade.get("symbol")
                if not symbol: continue
                
                # Use current price for specific symbol
                current_price = hyperliquid_service.get_current_price(symbol)
                if current_price is None or float(current_price) <= 0:
                    self.add_log(f"⚠️ No valid price for {symbol}; skipping manage/exit this tick")
                    continue
                
                # --- STRATEGY DELEGATION ---
                handled_by_strategy = False
                strategy_name = trade.get("strategy")
                
                if strategy_name and strategy_name in self.strategy_engine.strategies:
                    strat_instance = self.strategy_engine.strategies[strategy_name]
                    
                    # Manage trade (pass None for df to avoid heavy fetching in loop)
                    custom_updates = strat_instance.manage_trade(trade, current_price, df=None)
                    
                    if custom_updates is not None:
                        handled_by_strategy = True
                        if custom_updates:
                            with self.trade_lock:
                                changed = False
                                t_ref = self.active_trades.get(symbol)
                                if t_ref:
                                    if "sl" in custom_updates:
                                        t_ref["sl"] = custom_updates["sl"]
                                        changed = True
                                        self.add_log(f"🤖 Strategy {strategy_name} updated SL for {symbol} to {custom_updates['sl']}")
                                    if "tp" in custom_updates:
                                        t_ref["tp"] = custom_updates["tp"]
                                        changed = True
                                        self.add_log(f"🤖 Strategy {strategy_name} updated TP for {symbol} to {custom_updates['tp']}")
                                        
                                    if changed:
                                        t_ref["initial_sl_tp_set"] = True
                                        self._verify_and_enforce_sl_tp(symbol, t_ref, bypass_cooldown=True)
                                        StateManager.save_state(self)

                # 2. Default Smart Trailing (Fallback) - Only on actual change
                if not handled_by_strategy:
                    if self._update_trailing_stops(trade, current_price):
                         tid = trade.get("trade_id") if isinstance(trade, dict) else None
                         self.add_log(f"🔄 Trailing Stop Updated for {symbol}. Enforcing..." + (f" | id={tid}" if tid else ""))
                         with self.trade_lock:
                             t_ref = self.active_trades.get(symbol)
                             if t_ref:
                                t_ref["initial_sl_tp_set"] = True
                                self._verify_and_enforce_sl_tp(symbol, t_ref, bypass_cooldown=True)

                # 2b. SuperTrend thesis follow-up (soft exit if dead + green)
                closed_by_thesis = self._maybe_evaluate_trade_thesis(
                    symbol, trade, current_price
                )

                # 3. Local Exit Check (Safety) — skip if thesis already closed
                if not closed_by_thesis:
                    self._check_local_exits(trade, symbol, current_price)
                
            except Exception as manage_err:
                self.add_log(f"⚠️ Management Error on {symbol}: {manage_err}")

    def _maybe_evaluate_trade_thesis(self, symbol: str, trade: dict, current_price: float) -> bool:
        """Periodic in-trade SuperTrend thesis check → HOLD / tighten BE / soft close.

        Returns True if this call closed the position (caller should skip local exits).
        """
        if not self.trading_enabled:
            return False
        strategy_name = str(trade.get("strategy") or "")
        if strategy_name and strategy_name != "supertrend":
            return False

        now = time.time()
        last = float(self._last_thesis_check.get(symbol, 0) or 0)
        if now - last < float(self._thesis_check_interval_sec):
            return False

        try:
            df = hyperliquid_service.get_candles(symbol, interval="15m", limit=250)
            if df is None or getattr(df, "empty", True) or len(df) < 50:
                return False

            strat = self.strategy_engine.strategies.get("supertrend")
            if strat is None:
                return False
            p = strat._params_snapshot() if hasattr(strat, "_params_snapshot") else {}
            ema_need = int(p.get("ema_filter", 200) or 200) + 10
            if len(df) < ema_need:
                return False

            strat.add_indicators(df, p)

            last_15m = df.iloc[-2]
            adx = float(last_15m.get("ADX_14", 0) or 0)
            try:
                adx_slope = adx - float(df["ADX_14"].iloc[-3])
            except Exception:
                adx_slope = 0.0

            close_15m = float(last_15m.get("close", 0) or 0)
            ema_filter = float(last_15m.get("EMA_200", 0) or 0)
            st_direction = int(last_15m.get("ST_Direction", 0) or 0)
            supertrend = float(last_15m.get("Supertrend", 0) or 0)
            if not thesis_indicators_ready(
                close_15m=close_15m,
                ema_filter=ema_filter,
                st_direction=st_direction,
                supertrend=supertrend,
                adx=adx,
            ):
                return False

            # Only advance cooldown after a usable evaluation
            self._last_thesis_check[symbol] = now

            side = str(trade.get("side") or "BUY").upper()
            entry = float(trade.get("entry") or trade.get("entry_price") or 0)
            # Strategy min_adx_slope is an ENTRY soft filter (default -0.35).
            # In-trade: that maps to WEAK; DEAD uses a harder floor (default -1.0).
            raw_entry_slope = p.get("min_adx_slope", -0.35)
            try:
                weak_adx_slope = (
                    float(raw_entry_slope) if raw_entry_slope is not None else -0.35
                )
            except (TypeError, ValueError):
                weak_adx_slope = -0.35
            dead_adx_slope = min(-1.0, weak_adx_slope - 0.65)
            verdict = evaluate_supertrend_thesis(
                side=side,
                entry=entry,
                current_price=float(current_price),
                close_15m=close_15m,
                ema_filter=ema_filter,
                st_direction=st_direction,
                supertrend=supertrend,
                adx=adx,
                adx_slope=adx_slope,
                adx_threshold=float(p.get("adx_threshold", 22) or 22),
                min_adx_slope=dead_adx_slope,
                weak_adx_slope=weak_adx_slope,
            )
            prev = trade.get("thesis_status")
            if prev != verdict.status:
                self.add_log(
                    f"🧠 Thesis {symbol}: {verdict.status} → {verdict.action} "
                    f"(PnL {verdict.pnl_pct:+.2f}%) | {'; '.join(verdict.reasons)}"
                )
                # Discord only on WEAK/DEAD (skip VALID chatter + DEAD soft-close
                # which has its own alert below).
                will_soft_close = (
                    verdict.status == THESIS_DEAD
                    and verdict.action == ACTION_CLOSE_IF_PROFIT
                    and verdict.pnl_pct >= MIN_SOFT_CLOSE_PNL_PCT
                )
                if verdict.status == THESIS_WEAK or (
                    verdict.status == THESIS_DEAD and not will_soft_close
                ):
                    try:
                        discord_service.send_alert(
                            f"🧠 Thesis {verdict.status}: {side} {symbol}",
                            (
                                f"Action: {verdict.action}\n"
                                f"PnL: {verdict.pnl_pct:+.2f}%\n"
                                f"ADX {verdict.adx:.1f} (slope {verdict.adx_slope:+.2f})\n"
                                + "\n".join(f"• {r}" for r in verdict.reasons)
                            ),
                            color=(
                                "f39c12" if verdict.status == THESIS_WEAK else "e74c3c"
                            ),
                        )
                    except Exception:
                        pass

            with self.trade_lock:
                t_ref = self.active_trades.get(symbol)
                if not t_ref:
                    return False
                t_ref["thesis_status"] = verdict.status
                t_ref["thesis_action"] = verdict.action
                t_ref["thesis_pnl_pct"] = verdict.pnl_pct
                cur_sl = float(t_ref.get("sl") or 0)
                entry = float(t_ref.get("entry") or t_ref.get("entry_price") or entry)

            if verdict.action == ACTION_TIGHTEN_SL:
                be = break_even_sl(side, entry)
                if be and should_apply_be_tighten(side, entry, cur_sl, be):
                    self.add_log(
                        f"🛡️ Thesis WEAK: tighten SL {symbol} {cur_sl:.6g}→{be:.6g} (BE lock)"
                    )
                    with self.trade_lock:
                        t_ref = self.active_trades.get(symbol)
                        if t_ref:
                            t_ref["sl"] = float(be)
                            t_ref["initial_sl_tp_set"] = True
                            self._verify_and_enforce_sl_tp(symbol, t_ref, bypass_cooldown=True)
                            StateManager.save_state(self)

            elif verdict.action == ACTION_CLOSE_IF_PROFIT:
                if verdict.pnl_pct >= MIN_SOFT_CLOSE_PNL_PCT:
                    self.add_log(
                        f"🚪 Thesis DEAD + green ({verdict.pnl_pct:+.2f}%) — closing {symbol}"
                    )
                    try:
                        discord_service.send_alert(
                            f"🚪 Soft close (thesis dead): {side} {symbol}",
                            f"PnL {verdict.pnl_pct:+.2f}%\n" + "\n".join(verdict.reasons),
                            color="e74c3c",
                        )
                    except Exception:
                        pass
                    self.execute_exit_atomically(symbol, reason="THESIS_DEAD")
                    return True
                self.add_log(
                    f"🧠 Thesis DEAD but PnL {verdict.pnl_pct:+.2f}% "
                    f"< {MIN_SOFT_CLOSE_PNL_PCT:.2f}% min — leave SL on {symbol}"
                )

        except Exception as e:
            self.add_log(f"⚠️ Thesis check failed for {symbol}: {e}")
        return False

    def _sync_state(self, silent=True):
        """Unified State Synchronization (Stateless Truth) - Multi-Position aware"""
        try:
            positions = hyperliquid_service.get_positions()
            if getattr(hyperliquid_service, "_positions_fetch_failed", False) is True:
                self.add_log("⚠️ SYNC: positions unavailable — skipping adopt/close this tick")
                return

            # Map of symbols currently on exchange
            active_exchange_positions = {p["symbol"]: p for p in positions if float(p.get("size", 0)) != 0}
            
            # 1. Update/Adopt positions from Exchange
            for symbol, pos in active_exchange_positions.items():
                trade = self.active_trades.get(symbol)
                
                if not trade:
                    # New Position Detected (Adoption)
                    if not silent: self.add_log(f"🕵️ SYNC: Deteced ORPHAN {symbol} on exchange. Adopting...")
                    # We switch context to assist adoption if it uses self.active_symbol internally
                    self.switch_active_symbol(symbol)
                    self._adopt_existing_position(pos)
                else:
                    # Update Existing Memory
                    with self.trade_lock:
                        if "trade_id" not in trade or not trade.get("trade_id"):
                            trade["trade_id"] = self._new_trade_id(symbol)
                        trade["pnl"] = float(pos.get("pnl", 0))
                        trade["size"] = float(pos.get("size", 0))
                        trade["leverage"] = float(pos.get("leverage", 1.0))
            
            # 2. Detect External Closures (Trades tracked but not on exchange)
            tracked_symbols = list(self.active_trades.keys())
            for symbol in tracked_symbols:
                if symbol not in active_exchange_positions:
                    trade = self.active_trades.get(symbol)
                    if not trade: continue

                    # Confirm once more before treating as closed (transient API gaps)
                    time.sleep(0.5)
                    confirm = hyperliquid_service.get_positions()
                    if getattr(hyperliquid_service, "_positions_fetch_failed", False) is True:
                        self.add_log(f"⚠️ SYNC: skip closure for {symbol} (confirm fetch failed)")
                        continue
                    if any(
                        p.get("symbol") == symbol and float(p.get("size", 0) or 0) != 0
                        for p in (confirm or [])
                    ):
                        self.add_log(f"⚠️ SYNC: {symbol} still open on confirm — not closing")
                        continue
                    
                    # ALWAYS log closure detections (critical state transition)
                    tid = trade.get("trade_id") if isinstance(trade, dict) else None
                    self.add_log(f"🕵️ SYNC: Position {symbol} vanished from exchange. Handling closure..." + (f" | id={tid}" if tid else ""))
                    self._handle_external_closure(symbol, trade, silent)
        except Exception as e:
            # ALWAYS log sync errors (was silent=True before, hiding ghost trade bugs)
            self.add_log(f"⚠️ Sync Error: {e}")

    def _handle_external_closure(self, symbol: str, trade: dict, silent: bool = True, position_confirmed_flat: bool = False):
        """Record a trade only after Hyperliquid confirms a closing fill.

        Never market-closes on the exchange. Never drops local tracking / records
        estimated PnL on API gaps (504, empty history, WS blips) — exchange SL/TP
        remain the source of truth until a real Close fill appears.
        """
        tid = (trade or {}).get("trade_id") if isinstance(trade, dict) else None
        _ = position_confirmed_flat  # kept for call-site compatibility

        try:
            recent_trades = hyperliquid_service.get_trade_history(limit=50)
        except Exception as hist_err:
            self.add_log(
                f"⚠️ SYNC: history error for {symbol} — keeping trade active (SL/TP stay on exchange): {hist_err}"
                + (f" | id={tid}" if tid else "")
            )
            return False

        if recent_trades is None:
            self.add_log(
                f"⚠️ SYNC: history unavailable for {symbol} — keeping trade active "
                f"(no estimated close; exchange SL/TP remain authoritative)"
                + (f" | id={tid}" if tid else "")
            )
            return False

        def _trade_ts(t):
            ts = t.get("timestamp", t.get("time", 0))
            try:
                return int(ts)
            except (TypeError, ValueError):
                try:
                    dt = pd.to_datetime(ts, utc=True, errors="coerce")
                    if pd.isna(dt):
                        return 0
                    return int(dt.value // 1_000_000)
                except Exception:
                    return 0

        # Hard requirement: a real closing fill (not "latest fill" / estimated mid)
        symbol_trades = [t for t in recent_trades if t.get("symbol") == symbol]
        symbol_trades.sort(key=_trade_ts, reverse=True)
        closing_trade = next(
            (
                t for t in symbol_trades
                if float(t.get("pnl") or 0) != 0
                or "Close" in str(t.get("dir", ""))
            ),
            None,
        )

        if not closing_trade:
            self.add_log(
                f"⚠️ SYNC: {symbol} missing from book but no Close fill yet — "
                f"keeping trade active (waiting for exchange SL/TP fill)"
                + (f" | id={tid}" if tid else "")
            )
            return False

        # Confirmed close fill → safe to release local tracking
        with self.trade_lock:
            current = self.active_trades.get(symbol)
            if not current:
                return False
            trade = current
            self.active_trades.pop(symbol, None)
            tid = trade.get("trade_id") if isinstance(trade, dict) else None

        self.add_log(
            f"🔄 EXTERNAL CLOSURE CONFIRMED: {symbol} — Close fill found"
            + (f" | id={tid}" if tid else "")
        )
        try:
            entry_price = float(trade.get("entry", 0))
            size = float(trade.get("size", 0))
            side = trade.get("side")
            exit_price = float(closing_trade.get("entry_price", 0))
            pnl_usdc = float(closing_trade.get("pnl", 0))
            exchange_close_time = None
            raw_ts = closing_trade.get("timestamp", closing_trade.get("time"))
            try:
                if raw_ts is not None:
                    try:
                        ts_val = int(raw_ts)
                        exchange_close_time = pd.to_datetime(ts_val, unit="ms", utc=True).isoformat()
                    except Exception:
                        dt = pd.to_datetime(raw_ts, utc=True, errors="coerce")
                        if not pd.isna(dt):
                            exchange_close_time = dt.isoformat()
            except Exception:
                exchange_close_time = None

            if pnl_usdc == 0 and entry_price > 0 and exit_price > 0:
                pnl_usdc = (
                    (exit_price - entry_price) * size
                    if side == "BUY"
                    else (entry_price - exit_price) * size
                )

            self.add_log(
                f"📝 SYNC: Confirmed close for {symbol} (Exit: {exit_price}, PnL: ${float(pnl_usdc):.2f}"
                + (f", ExchangeTime: {exchange_close_time}" if exchange_close_time else "")
                + ")"
                + (f" | id={tid}" if tid else "")
            )

            self.trade_recorder.add_trade({
                "trade_id": tid,
                "trace_id": (trade.get("metadata") or {}).get("trace_id"),
                "symbol": symbol,
                "strategy": trade.get("strategy", "Unknown"),
                "side": side,
                "entry_price": entry_price,
                "exit_price": exit_price,
                "size": size,
                "pnl": pnl_usdc,
                "pnl_usdc": pnl_usdc,
                "exit_reason": "External/Sync Close",
                "exit_time": pd.Timestamp.now().isoformat(),
                "entry_time": trade.get("timestamp"),
                "entry_indicators": trade.get("entry_indicators", {}),
            })
            try:
                self.risk_manager.record_trade_close(float(pnl_usdc))
            except Exception as risk_err:
                self.add_log(f"⚠️ Failed to update daily risk after external close: {risk_err}")

            discord_service.send_alert(
                f"🏁 TRADE CLOSED (Exchange): {symbol}",
                f"Reason: Confirmed exchange fill (SL/TP/manual)\n"
                f"PnL: ${pnl_usdc:.2f}\n"
                f"Exchange close time (if available): {exchange_close_time or 'N/A'}\n"
                f"Detected by bot at: {pd.Timestamp.now(tz='UTC').isoformat()}",
                color="00FF00" if pnl_usdc >= 0 else "FF0000",
            )

            try:
                StateManager.save_state(self)
                self.add_log(f"✅ Trade {symbol} cleaned from state after confirmed close")
            except Exception as save_err:
                self.add_log(f"⚠️ Failed to save state after external close {symbol}: {save_err}")
            return True

        except Exception as e:
            # Restore tracking if we popped but failed mid-record
            with self.trade_lock:
                if symbol not in self.active_trades and trade:
                    self.active_trades[symbol] = trade
            self.add_log(f"⚠️ Error in _handle_external_closure for {symbol}: {e} — trade restored")
            return False

    def force_sync(self):
        """Manually trigger synchronization with Exchange."""
        self.add_log("🔄 FORCE SYNC: Initiated by User")
        result = self._sync_state(silent=False)
        return {"status": "success", "message": "Resync initiated"}


    def _enforce_leverage(self):
        """Enforce leverage based on Risk Profile settings"""
        try:
            # Fallback: Use global_settings default_leverage
            default_leverage = self.global_settings.get("risk_defaults", {}).get("default_leverage", 5)
            default_margin_type = self.global_settings.get("risk_defaults", {}).get("default_margin_type", "Cross")
            
            # Read trading params from scanner_settings (centralized source) with fallbacks
            requested_leverage = self.scanner_settings.get("leverage")
            
            # If leverage not explicitly set or set to 1 (likely default), derive from risk profile
            if requested_leverage is None or int(requested_leverage) <= 1:
                risk_profile = self.global_settings.get("risk_defaults", {}).get("risk_profile", "Capital Preservation First")
                if risk_profile == "Capital Preservation First":
                    requested_leverage = 3
                elif risk_profile == "Balanced Growth":
                    requested_leverage = 5
                elif risk_profile == "High Volatility Hunter":
                    requested_leverage = 10
                else:
                    requested_leverage = default_leverage
            else:
                requested_leverage = int(requested_leverage)

            margin_type = self.scanner_settings.get("margin_type", default_margin_type)
            is_cross = (margin_type == "Cross")
            
            target_leverage = requested_leverage
            
            # RISK PROFILE BASED LEVERAGE (Sync with prompts.py)
            risk_profile = self.global_settings.get("risk_defaults", {}).get("risk_profile", "Capital Preservation First")
            
            if risk_profile == "Capital Preservation First":
                target_leverage = 3
            elif risk_profile == "Balanced Growth":
                target_leverage = 5
            elif risk_profile == "High Volatility Hunter":
                target_leverage = 10
            else:
                target_leverage = int(self.scanner_settings.get("leverage", default_leverage))
            
            self.add_log(f"🛡️ RISK PROFILE ({risk_profile}): Using leverage: {target_leverage}x")
            try:
                balance_data = hyperliquid_service.get_account_balance()
                if balance_data.get("status") == "success":
                    self.account_value = float(balance_data.get("total_equity", 0.0))
            except Exception as e:
                logger.debug("Balance fetch during leverage sync failed: %s", e)
            self.add_log(f"⚙️ SYNC: Enforcing Leverage {target_leverage}x ({margin_type}) on Exchange...")
            hyperliquid_service.update_leverage(self.active_symbol, target_leverage, is_cross)
            self._leverage_synced = True
            
        except Exception as e:
            self.add_log(f"⚠️ LEVERAGE SYNC FAILED: {e}")

    def _resolve_trade_leverage(self) -> int:
        """Same leverage rules as _enforce_leverage (risk profile overrides scanner default)."""
        default_leverage = self.global_settings.get("risk_defaults", {}).get("default_leverage", 5)
        requested_leverage = self.scanner_settings.get("leverage")
        risk_profile = self.global_settings.get("risk_defaults", {}).get("risk_profile", "Capital Preservation First")

        if requested_leverage is None or int(requested_leverage) <= 1:
            if risk_profile == "Capital Preservation First":
                return 3
            if risk_profile == "Balanced Growth":
                return 5
            if risk_profile == "High Volatility Hunter":
                return 10
            return int(default_leverage)

        target = int(requested_leverage)
        if risk_profile == "Capital Preservation First":
            return 3
        if risk_profile == "Balanced Growth":
            return 5
        if risk_profile == "High Volatility Hunter":
            return 10
        return target

    def trading_loop(self):
        """Main trading loop"""
        self.add_log("🚀 Trading loop started")
        self.add_log(f"⚙️ Loop initialized. is_running={self.is_running}")
        
        # STARTUP SYNC
        if not self.startup_sync_done:
            self.add_log("🔄 STARTUP SYNC: Checking Hyperliquid positions...")
            # Real-time mids for manage/exit — without this, prices fall back to candles
            try:
                symbols = list({self.active_symbol} | set(self.active_trades.keys()))
                symbols = [s for s in symbols if s]
                if symbols:
                    hyperliquid_service.start_websocket(symbols)
                    self.add_log(f"📡 WebSocket price feed started for: {', '.join(symbols)}")
            except Exception as ws_err:
                self.add_log(f"⚠️ WebSocket price feed failed to start: {ws_err}")

            if self.trading_enabled:
                 self._enforce_leverage()
            
            # Initial Synchro
            self._sync_state(silent=False)
            try:
                self.risk_manager.sync_with_hyperliquid(hyperliquid_service)
            except Exception as risk_sync_err:
                self.add_log(f"⚠️ Risk position sync failed: {risk_sync_err}")
            self.startup_sync_done = True
            self.add_log("✅ STARTUP SYNC: Complete")
            self.add_log("🕵️ Starting Position Reconciler...")
            
        while self.is_running:
            try:
                # 1. Reconciliation & State Sync (The Heartbeat)
                # Run reconciler (fixes SL/TP)
                if hasattr(self, 'position_reconciler'):
                    self.position_reconciler.run_tick()
                
                # Check Exchange State (Adopt/Close)
                # Update heartbeat (thread health monitoring)
                self._loop_heartbeat = time.time()
                
                now = time.time()
                if now - self._last_state_sync_time >= self._state_sync_interval:
                    self._sync_state(silent=True)
                    self._last_state_sync_time = now
            except Exception as tick_err:
                self.add_log(f"⚠️ Loop Tick Error: {tick_err}")

            # Dynamic Leverage & Gamification Enforcement
            if self.trading_enabled and not self._leverage_synced:
                self._enforce_leverage()
            elif not self.trading_enabled:
                self._leverage_synced = False

            action = None
            sl = None
            tp = None
            
            # --- CONTINUOUS ADOPTION (Manual Trades) ---
            # Use _sync_state(silent=False) occasionally to detect and notify adoption
            # instead of a restrictive single-symbol check.
            if not self.active_trade and int(time.time()) % 30 == 0:
                self._sync_state(silent=False)
            
            try:
                acc_data = hyperliquid_service.get_account_balance()
                if acc_data.get("status") == "success":
                   self.account_value = float(acc_data.get("total_equity", 0))
            except: pass
            
            # --- PERIODIC MARKET ANALYSIS (For Copilot when flat) ---
            try:
                # Update Daily PnL Snapshot every hour
                if not hasattr(self, "_last_pnl_sync") or (time.time() - self._last_pnl_sync) > 3600:
                    self.add_log("🔄 Triggering Daily PnL Sync Task...")
                    def sync_pnl():
                        try:
                            # 1. Dynamic PnL Log
                            hyperliquid_service.get_daily_pnl()
                            
                            # 2. Daily Snapshot
                            acc = hyperliquid_service.get_account_balance()
                            equity = float(acc.get("total_equity", 0)) if acc.get("status") == "success" else 0
                            
                            if equity > 0:
                                today_str = pd.Timestamp.now(tz='UTC').strftime("%Y-%m-%d")
                                snapshots = storage_service.load_pnl_snapshot()
                                
                                if today_str not in snapshots:
                                    snapshots[today_str] = {
                                        "start_value": equity,
                                        "timestamp": pd.Timestamp.now(tz='UTC').isoformat()
                                    }
                                    storage_service.save_pnl_snapshot(snapshots)
                                    self.add_log(f"📸 Daily Snapshot Saved: ${equity:.2f}")

                        except Exception as e:
                            self.add_log(f"⚠️ PnL Sync Error: {e}")
                    
                    threading.Thread(target=sync_pnl, daemon=True).start()
                    self._last_pnl_sync = time.time()

                # Run market analysis every 15 minutes or if cache is empty
                last_market_time = self.ai_cache.get("last_market_analysis_time")
                if not last_market_time or (pd.Timestamp.now() - last_market_time).total_seconds() > 900:
                    self.add_log("🧠 Triggering Background Market Analysis Refresh...")
                    def refresh_market():
                        try:
                            # Create a new loop for this one-off background task in the thread
                            loop = asyncio.new_event_loop()
                            asyncio.set_event_loop(loop)
                            loop.run_until_complete(self._update_market_analysis())
                            loop.close()
                        except Exception as e:
                            self.add_log(f"⚠️ refresh_market Error: {e}")
                    
                    threading.Thread(target=refresh_market, daemon=True).start()
                    # Prevent multiple starts before first completion (temporary debounce)
                    self.ai_cache["last_market_analysis_time"] = pd.Timestamp.now() 
            except: pass
            # --------------------------------------------------------
            
            # P1 FIX: Gérer les trades ouverts ET détecter les clôtures AVANT le guard max_positions.
            # Avant ce fix, _manage_all_trades() était dans le même bloc que le guard,
            # ce qui faisait que la détection de clôture (TP/SL hit) était sautée via `continue`.
            try:
                self._manage_all_trades()
            except Exception as manage_err:
                self.add_log(f"⚠️ _manage_all_trades Error: {manage_err}")

            try:
                # Skip NEW ENTRY analysis only if we are at max positions
                # Trade management and close detection always run (see above)
                if len(self.trade_book) >= self.max_positions:
                     # Log désactivé pour éviter le spam dans Coolify
                     time.sleep(10)
                     continue
                if self.trade_book.has_symbol(self.active_symbol):
                     self.add_log(f"📍 Active trade on {self.active_symbol}. Running analysis for new opportunities...")

                analysis_symbols = self._get_analysis_symbols()
                self.add_log(
                    f"🔄 Entering strategy analysis for {len(analysis_symbols)} symbol(s): "
                    f"{', '.join(analysis_symbols)}"
                )

                best = None  # (priority_tuple, symbol, sig, result, technical_context, df_15m)
                result = {"signals": [], "rejections": []}
                technical_context = {}
                df_15m = pd.DataFrame()
                signals = []

                for analysis_symbol in analysis_symbols:
                    if len(self.trade_book) >= self.max_positions:
                        break
                    ok_open, open_reason = self.can_open_trade(analysis_symbol)
                    if not ok_open:
                        self.add_log(
                            f"⏭️ Skip {analysis_symbol}: {open_reason}",
                            metadata={"quiet": True},
                        )
                        continue

                    packed = self._analyze_symbol_market(analysis_symbol)
                    if not packed.get("ok"):
                        self.add_log(f"⚠️ {packed.get('error') or 'analyze failed'}")
                        continue

                    sym_result = packed["result"]
                    sym_tech = packed["technical_context"]
                    sym_df = packed["df_15m"]
                    self.latest_strategy_result = sym_result
                    self.active_strategies = sym_result.get("strategies", [])

                    regime = sym_result.get("regime", "UNKNOWN")
                    adx = sym_result.get("adx", 0)
                    rsi = sym_result.get("rsi", 0)
                    ema_20 = sym_result.get("ema_20", 0)
                    ema_50 = sym_result.get("ema_50", 0)
                    volume_ratio = sym_result.get("volume_ratio", 100)
                    ema_trend = "↗" if ema_20 > ema_50 else "↘" if ema_20 < ema_50 else "→"
                    adx_note = ">25=TREND" if adx < 25 else "TRENDING"
                    current_price = float(sym_result.get("current_price", sym_df["close"].iloc[-2]))
                    analysis_metrics = {
                        "regime": regime,
                        "adx": round(adx, 1),
                        "rsi": round(rsi, 1),
                        "volume_ratio": round(volume_ratio, 0),
                        "current_price": current_price,
                        "symbol": analysis_symbol,
                    }
                    self.add_log(
                        f"📊 {analysis_symbol} Regime: {regime} | Price: {current_price:.4f} | "
                        f"ADX: {adx:.1f} ({adx_note}) | RSI: {rsi:.1f} | EMA20/50: {ema_trend} | "
                        f"Vol: {volume_ratio:.0f}%",
                        metadata=analysis_metrics,
                    )
                    live_price = float(sym_result.get("current_price_live", sym_df["close"].iloc[-1]))
                    live_rsi = float(sym_result.get("rsi_live", rsi))
                    live_ema20 = float(sym_result.get("ema_20_live", ema_20))
                    live_ema50 = float(sym_result.get("ema_50_live", ema_50))
                    live_ema_trend = "↗" if live_ema20 > live_ema50 else "↘" if live_ema20 < live_ema50 else "→"
                    self.add_log(
                        f"🟡 {analysis_symbol} Live: Price {live_price:.4f} | RSI {live_rsi:.1f} | "
                        f"EMA20/50 {live_ema_trend} | Vol(conf) {volume_ratio:.0f}%"
                    )
                    for rej in (sym_result.get("rejections") or []):
                        reason = rej.get("reason") or "no reason"
                        strat_name = rej.get("strategy") or "strategy"
                        self.add_log(f"⛔ No signal ({analysis_symbol}/{strat_name}): {reason}")

                    sym_tech = dict(sym_tech)
                    sym_tech["current_price"] = sym_tech.get("current_price") or current_price

                    for cand in (sym_result.get("signals") or []):
                        if not cand.get("signal") or not cand.get("price"):
                            continue
                        cand = dict(cand)
                        cand["symbol"] = cand.get("symbol") or analysis_symbol
                        pri = self._signal_priority(cand)
                        row = (pri, analysis_symbol, cand, sym_result, sym_tech, sym_df)
                        if best is None or row[0] > best[0]:
                            best = row

                if best:
                    _pri, focus_symbol, sig, result, technical_context, df_15m = best
                    signals = result.get("signals", []) or [sig]
                    current_price = float(
                        technical_context.get("current_price")
                        or (df_15m["close"].iloc[-2] if not df_15m.empty else 0)
                    )
                else:
                    focus_symbol = None
                    sig = None
                    signals = []
                    current_price = 0

                ui_symbol = self.active_symbol
                entry_committed = False
                if sig and sig.get("signal") and sig.get("price"):
                    # Temp focus for helpers that read active_symbol; restore unless we fill
                    if focus_symbol and self.active_symbol != focus_symbol:
                        self.add_log(
                            f"🎯 Evaluating entry candidate {focus_symbol} "
                            f"(UI focus stays {ui_symbol} unless filled)"
                        )
                        self.active_symbol = focus_symbol
                    try:
                        # --- BOOK GATE (max_positions + same-symbol policy) ---
                        sig_symbol = sig.get("symbol", self.active_symbol)
                        ok_open, open_reason = self.can_open_trade(sig_symbol)
                        if not ok_open:
                            self.add_log(
                                f"⛔ SLOT/POLICY: {sig.get('signal')} {sig_symbol} skipped ({open_reason})"
                            )
                            time.sleep(10)
                            continue

                        # Trace id to correlate Pre-AI + AI verdict + (optional) payload logs.
                        ai_trace_id = uuid.uuid4().hex[:10]

                        # --- WHITELIST GATE (before AI to skip memes / explosive alts) ---
                        if not self._is_symbol_whitelisted(sig_symbol):
                            self.add_log(
                                f"⛔ WHITELIST BLOCK: {sig.get('signal')} {sig_symbol} "
                                f"(not in scanner whitelist)"
                            )
                            try:
                                discord_service.send_alert(
                                    f"⛔ WHITELIST BLOCK: {sig.get('signal')} {sig_symbol}",
                                    "Symbol not in majors/L2 whitelist — signal skipped before AI.",
                                    color="FF9900",
                                )
                            except Exception:
                                pass
                            time.sleep(10)
                            continue
                    
                        # --- COOLDOWN CHECK (BEFORE AI to save tokens) ---
                        cooldown_minutes = self.global_settings.get("risk_defaults", {}).get("cooldown_minutes", 0)
                        if cooldown_minutes > 0 and self._last_trade_info.get("time"):
                            last_symbol = self._last_trade_info.get("symbol")
                            last_direction = self._last_trade_info.get("direction")
                            last_time = self._last_trade_info.get("time")
                        
                            if last_symbol == self.active_symbol and last_direction == sig.get("signal"):
                                elapsed_minutes = (pd.Timestamp.now() - pd.Timestamp(last_time)).total_seconds() / 60
                                if elapsed_minutes < max(1, cooldown_minutes):  # min 1 minute
                                    remaining = max(1, cooldown_minutes) - elapsed_minutes
                                    self.add_log(f"⏳ COOLDOWN: {self.active_symbol} {sig.get('signal')} - Skip (wait {remaining:.1f}min)")
                                    time.sleep(10)
                                    continue
                    
                        market_context = self._prepare_ai_context()
                        # Prefer engine confirmed-candle volume over any live-bar leftovers
                        if isinstance(technical_context, dict) and technical_context.get("volume_ratio") is not None:
                            market_context["volume_ratio"] = technical_context["volume_ratio"]
                        # Inject Copilot MTF Sentiment
                        market_context['mtf_sentiment'] = self._fetch_mtf_sentiment(self.active_symbol)

                        strat_name = sig.get('strategy')
                        strat_obj = self.strategy_engine.strategies.get(strat_name) if strat_name else None

                        # --- HARD VETO (strategy-owned) before spending AI tokens ---
                        veto_reason = self._check_hard_veto(
                            sig.get("signal", "BUY"),
                            market_context,
                            strategy=strat_obj,
                        )
                        if veto_reason:
                            self.add_log(f"⛔ {veto_reason}")
                            # Signal armed strategy cooldown — clear so a false veto doesn't burn 15m
                            self._clear_strategy_entry_cooldown(sig.get("strategy"), sig_symbol)
                            try:
                                discord_service.send_alert(
                                    f"⛔ HARD VETO (trace={ai_trace_id}): {sig.get('signal')} {sig_symbol}",
                                    veto_reason,
                                    color="FF0000",
                                )
                            except Exception:
                                pass
                            time.sleep(10)
                            continue
                    
                        # Discord debug notification at strategy-detection stage (before AI gate).
                        # Include a compact preview of the *actual* data that will be sent to IA.
                        ai_payload_preview = {
                            "trace_id": ai_trace_id,
                            "signal_data": {
                                "symbol": sig.get("symbol", self.active_symbol),
                                "signal": sig.get("signal"),
                                "strategy": sig.get("strategy"),
                                "price": sig.get("price"),
                                "sl": sig.get("sl"),
                                "tp": sig.get("tp"),
                                "timestamp": sig.get("timestamp"),
                            },
                            "market_context_keys": sorted(list((market_context or {}).keys())),
                            "market_context_focus": {
                                # Helpful coherence checks (values may be absent depending on context builder)
                                "current_price": market_context.get("current_price") if isinstance(market_context, dict) else None,
                                "regime": market_context.get("regime") if isinstance(market_context, dict) else None,
                                "market_bias": market_context.get("market_bias") if isinstance(market_context, dict) else None,
                                "rsi_val": market_context.get("rsi_val") if isinstance(market_context, dict) else None,
                                "adx_val": market_context.get("adx_val") if isinstance(market_context, dict) else None,
                                "bb_position": market_context.get("bb_position") if isinstance(market_context, dict) else None,
                                "volume_ratio": market_context.get("volume_ratio") if isinstance(market_context, dict) else None,
                            },
                        }
                        self._notify_signal_detected_discord(
                            sig,
                            technical_context,
                            ai_trace_id=ai_trace_id,
                            ai_payload_preview=ai_payload_preview,
                        )
                        strategy_persona = None
                        if strat_obj is not None:
                            if hasattr(strat_obj, "get_ai_persona"):
                                strategy_persona = strat_obj.get_ai_persona()
                            else:
                                strategy_persona = getattr(strat_obj, "AI_PERSONA", None)
                    
                        current_time = time.time()
                        time_since_last_call = current_time - self.last_ai_call
                    
                        # Score threshold removed - risk thresholds are already configured in settings
                        # AI validation handles the filtering based on configured risk thresholds
                    
                        if time_since_last_call < 45:  # 45s cooldown to save credits
                            self.add_log(f"⏳ AI COOLDOWN: Skipping (only {time_since_last_call:.0f}s since last)")
                            continue
                    
                        approved = False
                        self.add_log(f"🤖 Validating signal (trace={ai_trace_id}): {sig.get('signal')} from {sig.get('strategy')}")
                        if self._ai_payload_debug_enabled():
                            payload_obj = {
                                "ts": pd.Timestamp.now().isoformat(),
                                "trace_id": ai_trace_id,
                                "symbol": sig.get("symbol", self.active_symbol),
                                "strategy": sig.get("strategy"),
                                "signal_data": sig,
                                "market_context": market_context,
                            }
                            self._write_ai_payload_log({"type": "ai_request", **payload_obj})
                            # Short preview into regular bot logs (API/history), full stays in ai_payload.jsonl
                            preview = self._safe_json_preview(
                                {
                                    "trace_id": ai_trace_id,
                                    "signal_data": sig,
                                    "market_context_keys": sorted(list((market_context or {}).keys())),
                                },
                                max_chars=900,
                            )
                            self.add_log(f"🧠 AI PAYLOAD (trace={ai_trace_id})", metadata={"preview": preview})
                            if self._ai_payload_debug_discord_enabled():
                                try:
                                    discord_service.send_log(f"AI PAYLOAD trace={ai_trace_id}: {preview}")
                                except Exception as discord_err:
                                    self.add_log(f"⚠️ Discord log failed (AI payload): {discord_err}")
                        val_res = ia_service.validate_signal(
                            sig,
                            market_context,
                            strategy_persona=strategy_persona,
                            strategy=strat_obj,
                        )


                        self.last_ai_call = current_time
                        if self._ai_payload_debug_enabled():
                            try:
                                raw = (val_res or {}).get("raw_output")
                                resp_obj = {
                                    "ts": pd.Timestamp.now().isoformat(),
                                    "trace_id": ai_trace_id,
                                    "symbol": sig.get("symbol", self.active_symbol),
                                    "strategy": sig.get("strategy"),
                                    "raw_output": raw,
                                    "model": (val_res or {}).get("model"),
                                }
                                self._write_ai_payload_log({"type": "ai_response", **resp_obj})
                                if self._ai_payload_debug_discord_enabled():
                                    preview = self._safe_json_preview(
                                        {"trace_id": ai_trace_id, "raw_output": raw},
                                        max_chars=config.AI_PAYLOAD_DEBUG_MAX_CHARS,
                                    )
                                    discord_service.send_log(f"AI RESPONSE trace={ai_trace_id}: {preview}")
                            except Exception as e:
                                self.add_log(f"⚠️ Failed to capture AI response (trace={ai_trace_id}): {e}")
                    
                        if not val_res:
                            approved = False
                            self.add_log("⚠️ AI Validation: empty response. Defaulting to REJECT.")
                        elif val_res.get("rejection_reason_category") == "AI_PARSE_ERROR":
                            approved = False
                            parse_reason = val_res.get("reasoning", "Invalid AI JSON")
                            raw_snippet = str(val_res.get("raw_output") or "")[:500]
                            self.add_log(f"⚠️ AI Validation JSON Error: {parse_reason}. Defaulting to REJECT.")
                            try:
                                discord_service.send_alert(
                                    f"⚠️ AI ERROR (JSON parse): {sig.get('signal')} {sig.get('symbol')}",
                                    f"Strategy: {sig.get('strategy')}\n"
                                    f"Error: {parse_reason}\n"
                                    f"Raw AI snippet: `{raw_snippet}`\n\n"
                                    f"Signal was defaulted to REJECT for safety.",
                                    color="FF9900"
                                )
                            except Exception as discord_err:
                                self.add_log(f"⚠️ Discord notification failed (AI JSON error): {discord_err}")
                        elif val_res.get("raw_output") or "approved" in val_res:
                            ai_data = val_res
                            approved = ai_data.get("approved", False)
                            confidence = ai_data.get("confidence", 0)
                            risk_level_raw = ai_data.get("risk_level")
                            risk_level = str(risk_level_raw).upper() if risk_level_raw else "MEDIUM"
                        
                            if approved:
                                # HYBRID CONFIDENCE THRESHOLD CHECK
                                required_conf = config.AI_CONF_THRESHOLD_MEDIUM  # Default
                                if risk_level == "HIGH":
                                    required_conf = config.AI_CONF_THRESHOLD_HIGH
                                elif risk_level == "LOW":
                                    required_conf = config.AI_CONF_THRESHOLD_LOW
                            
                                if confidence >= required_conf:
                                    reason = ai_data.get('reasoning', 'No reason')
                                    self.add_log(f"✅ AI APPROVED (Conf: {confidence}%): {reason}", metadata=ai_data)
                                    self._record_signal_analysis(
                                        sig, ai_data, True, indicators=technical_context, trace_id=ai_trace_id
                                    )
                                
                                    # Discord Notification for AI Approval
                                    discord_service.send_alert(
                                        f"✅ AI APPROVED (trace={ai_trace_id}): {sig.get('signal')} {sig.get('symbol')}",
                                        f"Strategy: {sig.get('strategy')}\nConfidence: {confidence}%\nRisk: {risk_level}\n\n{reason}",
                                        color="00FF00"
                                    )
                                
                                    if ai_data.get("suggested_adjustments"):
                                        adj = ai_data["suggested_adjustments"]
                                    
                                        # Robust parsing for AI suggestions (handle "$0.50" strings)
                                        if adj.get("sl"): 
                                            try:
                                                val = adj["sl"]
                                                if isinstance(val, str):
                                                    val = float(val.replace('$', '').replace(',', '').strip())
                                                sig["sl"] = float(val)
                                            except Exception as e:
                                                self.add_log(f"⚠️ Failed to parse AI SL adjustment: {adj['sl']} ({e})")
                                            
                                        if adj.get("tp"): 
                                            try:
                                                val = adj["tp"]
                                                if isinstance(val, str):
                                                    val = float(val.replace('$', '').replace(',', '').strip())
                                                sig["tp"] = float(val)
                                            except Exception as e:
                                                self.add_log(f"⚠️ Failed to parse AI TP adjustment: {adj['tp']} ({e})")
                                else:
                                    self.add_log(f"⚠️ AI approved but CONFIDENCE TOO LOW ({confidence}% < {required_conf}% for {risk_level} risk)", metadata=ai_data)
                                    self._record_signal_analysis(
                                        sig, ai_data, False, indicators=technical_context, trace_id=ai_trace_id
                                    )
                                    try:
                                        reason = ai_data.get('reasoning', 'No reason')
                                        discord_service.send_alert(
                                            f"⚠️ AI REFUSED (Low confidence) (trace={ai_trace_id}): {sig.get('signal')} {sig.get('symbol')}",
                                            f"Strategy: {sig.get('strategy')}\n"
                                            f"Confidence: {confidence}% (required: {required_conf}% for {risk_level})\n"
                                            f"Risk: {risk_level}\n\n"
                                            f"{reason}",
                                            color="FFD166"
                                        )
                                    except Exception as discord_err:
                                        self.add_log(f"⚠️ Discord notification failed (AI low confidence): {discord_err}")
                                    approved = False
                            else:
                                reason = ai_data.get('reasoning', 'No reason')
                                self.add_log(f"❌ AI REJECTED: {reason}", metadata=ai_data)
                                self._record_signal_analysis(
                                    sig, ai_data, False, indicators=technical_context, trace_id=ai_trace_id
                                )
                                try:
                                    discord_service.send_alert(
                                        f"❌ AI REJECTED (trace={ai_trace_id}): {sig.get('signal')} {sig.get('symbol')}",
                                        f"Strategy: {sig.get('strategy')}\n"
                                        f"Confidence: {confidence}%\n"
                                        f"Risk: {risk_level}\n\n"
                                        f"{reason}",
                                        color="FF0000"
                                    )
                                except Exception as discord_err:
                                    self.add_log(f"⚠️ Discord notification failed (AI rejected): {discord_err}")
                        else:
                            approved = True
                        
                        if approved:
                            acc = hyperliquid_service.get_account_balance(force_refresh=True)
                            if acc.get("status") == "success":
                                equity = float(acc.get("total_equity", 0) or 0)
                                acct_mode = acc.get("account_abstraction_mode", "unknown")
                                if acct_mode not in ("unknown", "default", "disabled", ""):
                                    self.add_log(
                                        f"💰 Hyperliquid account mode: {acct_mode} | "
                                        f"perp=${float(acc.get('perp_account_value', 0) or 0):.2f} "
                                        f"spot_usdc=${float(acc.get('spot_usdc_total', 0) or 0):.2f}"
                                    )
                            else:
                                equity = 0.0
                                err_msg = acc.get("message", "unknown error")
                                self.add_log(f"⚠️ Balance API unavailable: {err_msg}")
                                self._log_execution_error(
                                    f"⚠️ BALANCE API ERROR: {self.active_symbol}",
                                    reason=err_msg,
                                    symbol=self.active_symbol,
                                    side=sig.get("signal"),
                                    strategy=sig.get("strategy"),
                                )
                            if equity <= 0 and getattr(self, "account_value", 0) > 0:
                                equity = float(self.account_value)
                                self.add_log(
                                    f"⚠️ Using cached account value ${equity:.2f} (live balance was $0)"
                                )
                                self._log_execution_error(
                                    f"⚠️ EQUITY FALLBACK: {self.active_symbol}",
                                    reason="Live balance API returned $0; using cached account_value",
                                    equity=equity,
                                    symbol=self.active_symbol,
                                    side=sig.get("signal"),
                                    strategy=sig.get("strategy"),
                                )
                            elif acc.get("status") == "success" and equity <= 0:
                                self._log_execution_error(
                                    f"⚠️ ZERO EQUITY: {self.active_symbol}",
                                    reason="Hyperliquid accountValue is $0 — check HL_ACCOUNT_ADDRESS and wallet funding",
                                    symbol=self.active_symbol,
                                    side=sig.get("signal"),
                                    strategy=sig.get("strategy"),
                                )
                        
                            sl_price = sig.get("sl")
                            entry_price = sig.get("price")
                        
                            # --- ATR-BASED SL FLOOR (Prevent unrealistically tight SL) ---
                            try:
                                if sl_price and entry_price and not df_15m.empty:
                                    # Prefer strategy ATR (Wilder); fall back to SMA-TR if missing
                                    atr_col = next((c for c in ('ATR_14', 'ATRr_14') if c in df_15m.columns), None)
                                    if atr_col:
                                        current_atr = float(df_15m[atr_col].iloc[-1])
                                    else:
                                        tr = pd.concat([
                                            df_15m['high'] - df_15m['low'],
                                            (df_15m['high'] - df_15m['close'].shift(1)).abs(),
                                            (df_15m['low'] - df_15m['close'].shift(1)).abs()
                                        ], axis=1).max(axis=1)
                                        current_atr = float(tr.rolling(14).mean().iloc[-1])
                                
                                    min_sl_distance = current_atr * 1.0  # Minimum 1x ATR
                                    actual_sl_distance = abs(entry_price - sl_price)
                                
                                    if actual_sl_distance < min_sl_distance:
                                        direction = sig.get("signal", "BUY")
                                        if direction == "BUY":
                                            adjusted_sl = entry_price - min_sl_distance
                                        else:
                                            adjusted_sl = entry_price + min_sl_distance
                                    
                                        self.add_log(f"⚠️ SL FLOOR: AI SL too tight ({actual_sl_distance:.4f} < 1x ATR {current_atr:.4f}). Adjusted: {sl_price:.4f} → {adjusted_sl:.4f}")
                                        sl_price = adjusted_sl
                                        sig["sl"] = adjusted_sl  # Update signal too
                            except Exception as atr_err:
                                self.add_log(f"⚠️ ATR SL floor check failed: {atr_err}")
                        
                            # DYNAMIC POSITION SIZING based on RISK PROFILE
                            # Keep RiskManager.split in sync with runtime max_positions
                            try:
                                self.risk_manager.update_settings(
                                    max_positions=int(self.max_positions or 1)
                                )
                            except Exception:
                                pass
                            if not self.scanner_settings.get("gamification_enabled", True):
                                risk_profile = self.global_settings.get("risk_defaults", {}).get("risk_profile", "Capital Preservation First")
                            
                                # Assign risk % constants based on profile
                                risk_pct = 1.5 # Default (Conservative)
                                if risk_profile == "Balanced Growth": risk_pct = 3.5
                                elif risk_profile == "High Volatility Hunter": risk_pct = 7.0
                                split = max(1, int(self.max_positions or 1))
                                per_trade_pct = risk_pct / split
                            
                                self.add_log(
                                    f"📏 SIZING: {risk_profile} budget {risk_pct:.1f}% equity "
                                    f"→ {per_trade_pct:.2f}%/trade (÷{split} max_positions)"
                                )
                                size = self.risk_manager.calculate_position_size(
                                    price=entry_price,
                                    sl_price=sl_price,
                                    equity=equity,
                                    method="risk_pct",
                                    size_value=risk_pct
                                )
                            else:
                                # Standard sizing (Fixed $20 Margin @ Target Leverage),
                                # split across max_positions inside RiskManager
                                current_leverage = self._resolve_trade_leverage()
                                split = max(1, int(self.max_positions or 1))
                                self.add_log(
                                    f"📏 SIZING: fixed margin ${DEFAULT_SIZE_USDC:.0f} "
                                    f"→ ${DEFAULT_SIZE_USDC / split:.1f}/slot (÷{split} max_positions)"
                                )
                                size = self.risk_manager.calculate_position_size(
                                    price=entry_price, 
                                    sl_price=sl_price, 
                                    equity=equity,
                                    method="fixed",
                                    size_value=DEFAULT_SIZE_USDC,
                                    leverage=current_leverage
                                )

                            current_leverage = self._resolve_trade_leverage()
                            split = max(1, int(self.max_positions or 1))
                            target_notional = (DEFAULT_SIZE_USDC / split) * current_leverage
                            self.add_log(
                                f"📏 Sizing: equity=${equity:.2f}, target notional/slot≈${target_notional:.0f}, "
                                f"size={size:.4f} {self.active_symbol}"
                            )
                            try:
                                discord_service.send_log(
                                    f"📏 SIZING {sig.get('signal')} {self.active_symbol} | "
                                    f"equity=${equity:.2f} | target/slot≈${target_notional:.0f} | "
                                    f"size={size:.4f} | lev={current_leverage}x | "
                                    f"max_pos={split} | strat={sig.get('strategy')}"
                                )
                            except Exception:
                                pass

                            if size <= 0:
                                cap_mult = self.risk_manager.max_notional_cap_multiplier
                                min_eq_target = target_notional / cap_mult
                                reason = (
                                    f"Position size is zero (equity=${equity:.2f}). "
                                    f"Need equity ≥ ~${MIN_POSITION_NOTIONAL_USD / cap_mult:.2f} for min order, "
                                    f"≥ ~${min_eq_target:.2f} for ${target_notional:.0f} target (cap ×{cap_mult:.0f})."
                                )
                                self.add_log(f"⛔ Entry skipped: {reason}")
                                self._clear_strategy_entry_cooldown(sig.get("strategy"), sig_symbol)
                                self._log_execution_error(
                                    f"⛔ ENTRY SKIPPED: {sig.get('signal')} {self.active_symbol}",
                                    reason=reason,
                                    equity=equity,
                                    target_notional=target_notional,
                                    cap_multiplier=cap_mult,
                                    strategy=sig.get("strategy"),
                                    entry=entry_price,
                                    sl=sl_price,
                                    tp=sig.get("tp"),
                                )
                                continue

                            # ---------------------------------------------------
                            # 2. EXECUTION LOGIC (Live)
                            # ---------------------------------------------------
                            if self.trading_enabled:
                                if sig.get("manual_approval"):
                                    self.add_log(
                                        f"📝 MANUAL SIGNAL ONLY: {sig.get('strategy')} approved but auto-execution disabled (manual_approval=True)"
                                    )
                                    try:
                                        discord_service.send_alert(
                                            f"📝 MANUAL ACTION REQUIRED: {sig.get('signal')} {sig.get('symbol')}",
                                            f"Strategy: {sig.get('strategy')}\n"
                                            f"Entry: {float(entry_price or 0):.8f}\n"
                                            f"SL/TP: {sig.get('sl')} / {sig.get('tp')}\n"
                                            f"AI approved this setup, but the strategy is configured in alert-only mode.",
                                            color="FFD166"
                                        )
                                    except Exception as manual_alert_err:
                                        self.add_log(f"⚠️ Manual alert notification failed: {manual_alert_err}")
                                    continue
                            
                                # Sync Positions periodically
                                if int(time.time()) % 60 == 0:
                                     self.force_sync()
                            
                                # Capture full market snapshot for trade analysis
                                # Use pre-calculated technical_context mixed with AI data
                                entry_indicators = technical_context.copy()
                                entry_indicators.update({
                                    "ai_confidence": confidence if 'confidence' in locals() else 0,
                                    "ai_reasoning": (ai_data.get("reasoning", "") if 'ai_data' in locals() else sig.get("reason", "Strategy Signal"))[:200]
                                })
                            
                                meta = dict(sig.get("metadata") or {})
                                meta["trace_id"] = ai_trace_id
                                entry_ok = self.execute_entry_atomically(
                                    self.active_symbol,
                                    sig.get("signal"),
                                    size,
                                    entry_price,
                                    sl_price,
                                    sig.get("tp"),
                                    sig.get("strategy"),
                                    meta,
                                    entry_indicators,
                                    equity=equity,
                                )
                            
                            if entry_ok:
                                entry_committed = True
                                # Update last trade info for cooldown
                                self._last_trade_info = {
                                    "symbol": self.active_symbol,
                                    "direction": sig.get("signal"),
                                    "time": pd.Timestamp.now().isoformat()
                                }
                                trade = self.active_trades.get(self.active_symbol) or {}
                                tid = trade.get("trade_id")
                                if tid:
                                    self.add_log(
                                        f"🧾 Timeline ids: trade_id={tid} trace_id={ai_trace_id}"
                                    )
                                    self._attach_trade_id_to_signal_analysis(
                                        ai_trace_id, tid, symbol=self.active_symbol
                                    )
                            else:
                                self.add_log(f"⚠️ TRADE NOT EXECUTED: trading_enabled=False (Signal approved but bot in observation mode)")
                                self._log_execution_error(
                                    f"⛔ ENTRY BLOCKED: {sig.get('signal')} {self.active_symbol}",
                                    reason="trading_enabled=False (observation mode)",
                                    strategy=sig.get("strategy"),
                                    entry=entry_price,
                                    sl=sl_price,
                                    tp=sig.get("tp"),
                                    equity=equity,
                                )
                        else:
                            # AI/gate rejected — do not burn the 15m strategy entry cooldown
                            self._clear_strategy_entry_cooldown(sig.get("strategy"), sig_symbol)
            
                    finally:
                        if not entry_committed:
                            if ui_symbol and self.active_symbol != ui_symbol:
                                self.active_symbol = ui_symbol
                        elif focus_symbol and focus_symbol != ui_symbol:
                            # Persist focus + ensure WS for the filled symbol
                            try:
                                if hyperliquid_service.ws_manager:
                                    hyperliquid_service.ws_manager.add_symbol(focus_symbol)
                            except Exception:
                                pass
                            try:
                                StateManager.save_state(self)
                            except Exception:
                                pass

                # Optimized Sleep Loop + Anti-Signal Spam
                has_active_trade = len(self.active_trades) > 0
                sleep_duration = 10 if has_active_trade else (15 if signals else 10)
                self.add_log(f"⏸️ Next analysis in {sleep_duration}s... (signals detected: {len(signals)})")
                for _ in range(int(sleep_duration)):
                    if not self.is_running: break
                    time.sleep(1)
                
            except Exception as e:
                import traceback
                tb = traceback.format_exc()
                self.add_log(f"❌ Error in trading loop: {e}")
                self.add_log(f"🔍 Traceback: {tb}")
                self._log_execution_error(
                    "❌ TRADING LOOP ERROR",
                    reason=str(e),
                    symbol=self.active_symbol,
                    traceback=tb[-1500:],
                )
                time.sleep(5)
        
        self.add_log("⏸️ Trading loop stopped")

    def _adopt_existing_position(self, active_pos, sl=0, tp=0):
        """Adopt an existing position from the exchange into the bot's memory."""
        try:
            symbol = active_pos['symbol']
            side = active_pos['side']
            size = float(active_pos['size'])
            entry_price = float(active_pos['entry_price'])
            leverage = float(active_pos.get('leverage', 1.0))
            
            with self.trade_lock:
                trade_id = self._new_trade_id(symbol)
                self.active_trades[symbol] = {
                    "trade_id": trade_id,
                    "symbol": symbol,
                    "side": side,
                    "entry": entry_price,
                    "size": size,
                    "leverage": leverage,
                    "oid": "external_position",
                    "sl": float(sl or 0),
                    "tp": float(tp or 0),
                    "strategy": "Manual (Adopted)",
                    "entry_time": pd.Timestamp.now().isoformat(),

                    "pnl": float(active_pos.get('pnl', 0)),
                    "max_pnl": float(active_pos.get('pnl', 0)),
                    "status": "OPEN",
                    "ai_analysis": None,
                    "metadata": {"stage": "1_raw_adoption"}
                }
                StateManager.save_state(self)
            
            self.add_log(f"🕵️ ADOPTED {symbol}: Size {size} | Entry {entry_price}")
            try:
                if hyperliquid_service.ws_manager:
                    hyperliquid_service.ws_manager.add_symbol(symbol)
            except Exception as ws_add_err:
                self.add_log(f"⚠️ Failed to subscribe WS price for adopted {symbol}: {ws_add_err}")
            
            # --- GLOBAL ADOPTION NOTIFICATION ---
            direction_label = "LONG 🟢" if side == "BUY" else "SHORT 🔴"
            try:
                discord_service.send_alert(
                    f"📥 Manual Position Detected: {symbol}",
                    f"Direction: {direction_label}\n"
                    f"Entry: {entry_price}\n"
                    f"Size: {size}\n"
                    f"The bot will now track and protect this position.",
                    color="FFA500"  # Orange — informational
                )
            except Exception as e:
                self.add_log(f"⚠️ Discord notification failed during adoption: {e}")
            
            try:
                self.add_log(f"🔍 Analyzing market context for {symbol}...")
                df_15m = hyperliquid_service.get_candles(symbol, "15m", 200)
                current_price = df_15m['close'].iloc[-1] if not df_15m.empty else entry_price
                
                self.add_log(f"🔎 Checking existing orders for {symbol}...")
                # frontend_open_orders includes SL/TP triggers (open_orders does not)
                symbol_orders = hyperliquid_service.get_open_orders(symbol)
                
                existing_sl = None
                existing_tp = None
                
                for order in symbol_orders:
                    px = float(order.get("triggerPx", 0))
                    if order.get("reduceOnly", False) and px > 0:
                        if side == "BUY":
                            if px < current_price: existing_sl = px
                            else: existing_tp = px
                        else: # SELL
                            if px > current_price: existing_sl = px
                            else: existing_tp = px
                
                pnl_pct = ((current_price - entry_price) / entry_price) * 100 if side == "BUY" else ((entry_price - current_price) / entry_price) * 100
                
                should_set_sl_tp = False
                sl_price = 0
                tp_price = 0
                strategy_name = "Manual (Adopted)"

                if existing_sl or existing_tp:
                    self.add_log(f"✅ Protection orders detected for {symbol}. Validating...")
                    
                    # Use existing values if present, else use placeholders
                    sl_to_use = existing_sl if existing_sl else 0
                    tp_to_use = existing_tp if existing_tp else 0

                    # Smart BE check for adopted trades (aligned with trailing_logic)
                    if pnl_pct >= 2.0:
                         sl_is_be = (sl_to_use >= entry_price * 1.001) if side == "BUY" else (sl_to_use <= entry_price * 0.999) if sl_to_use > 0 else False
                         if not sl_is_be:
                              sl_price = entry_price * 1.002 if side == "BUY" else entry_price * 0.998
                              tp_price = tp_to_use if tp_to_use > 0 else (entry_price * 1.05 if side == "BUY" else entry_price * 0.95)
                              should_set_sl_tp = True
                              self.add_log(f"🛡️ Smart BE: Moving existing SL to break-even for {symbol}")
                         else:
                              sl_price = sl_to_use
                              tp_price = tp_to_use
                    else:
                        sl_price = sl_to_use
                        tp_price = tp_to_use
                else:
                    self.add_log(f"⚠️ No protection orders for {symbol}. Calculating rational ATR-based stops.")
                    should_set_sl_tp = True
                    
                    # Prefer active strategy plan SL mult (bot = machine)
                    atr_mult = 2.0
                    try:
                        strat_for_adopt = None
                        if self.strategy_engine and getattr(self.strategy_engine, "strategies", None):
                            # Prefer supertrend when registered; else first strategy
                            strat_for_adopt = self.strategy_engine.strategies.get("supertrend")
                            if strat_for_adopt is None and self.strategy_engine.strategies:
                                strat_for_adopt = next(iter(self.strategy_engine.strategies.values()))
                        if strat_for_adopt is not None and hasattr(strat_for_adopt, "get_param"):
                            atr_mult = float(strat_for_adopt.get_param("sl_atr_mult", 2.0) or 2.0)
                    except (TypeError, ValueError):
                        atr_mult = 2.0
                    
                    # 2. Get ATR from data
                    atr_val = 0
                    if not df_15m.empty:
                        try:
                            # Try to find ATR in columns
                            atr_col = next((c for c in df_15m.columns if 'ATR' in c.upper()), None)
                            if atr_col:
                                atr_val = float(df_15m[atr_col].iloc[-1])
                            else:
                                # Quick manual ATR
                                tr = pd.concat([
                                    df_15m['high'] - df_15m['low'],
                                    (df_15m['high'] - df_15m['close'].shift(1)).abs(),
                                    (df_15m['low'] - df_15m['close'].shift(1)).abs()
                                ], axis=1).max(axis=1)
                                atr_val = tr.rolling(14).mean().iloc[-1]
                        except Exception as e:
                            self.add_log(f"⚠️ ATR Calculation failed during adoption: {e}")
                    
                    # 3. Fallback if ATR is 0
                    if not atr_val or pd.isna(atr_val):
                        self.add_log("⚠️ ATR unavailable, falling back to 3% distance")
                        sl_dist = entry_price * 0.03
                    else:
                        sl_dist = atr_val * atr_mult
                        self.add_log(f"📏 Using {atr_mult}x ATR ({atr_val:.4f}) for SL distance: {sl_dist:.4f}")

                    # 4. Calculate proposed SL/TP
                    if side == "BUY":
                        proposed_sl = entry_price - sl_dist
                        proposed_tp = entry_price + (sl_dist * 1.5) # RR 1:1.5
                    else:
                        proposed_sl = entry_price + sl_dist
                        proposed_tp = entry_price - (sl_dist * 1.5)

                    # 5. LIQUIDATION GUARD
                    liq_price = active_pos.get("liquidation_price")
                    if liq_price and liq_price > 0:
                        # Ensure SL is at least 15% distance from liquidation (of the entry-to-liq gap)
                        gap = abs(entry_price - liq_price)
                        buffer = gap * 0.15
                        
                        if side == "BUY":
                            min_sl = liq_price + buffer
                            if proposed_sl <= min_sl:
                                self.add_log(f"🛡️ LIQUIDATION GUARD: Proposed SL ({proposed_sl:.4f}) too close to Liquidation ({liq_price:.4f}). Adjusted to {min_sl:.4f}")
                                proposed_sl = min_sl
                        else:
                            max_sl = liq_price - buffer
                            if proposed_sl >= max_sl:
                                self.add_log(f"🛡️ LIQUIDATION GUARD: Proposed SL ({proposed_sl:.4f}) too close to Liquidation ({liq_price:.4f}). Adjusted to {max_sl:.4f}")
                                proposed_sl = max_sl

                    sl_price = proposed_sl
                    tp_price = proposed_tp

                with self.trade_lock:
                    t_ref = self.active_trades.get(symbol)
                    if t_ref:
                        t_ref["sl"] = sl_price
                        t_ref["tp"] = tp_price
                        t_ref["strategy"] = strategy_name
                        t_ref["status"] = "OPEN (ADOPTED)"
                        t_ref["initial_sl_tp_set"] = True
                        if should_set_sl_tp:
                            self._verify_and_enforce_sl_tp(symbol, t_ref, bypass_cooldown=True)
                        StateManager.save_state(self)
                self.add_log(f"✅ Adoption Complete for {symbol}.")

            except Exception as e:
                self.add_log(f"⚠️ Adoption Analysis Error for {symbol}: {e}")

        except Exception as e:
            self.add_log(f"❌ Critical Adoption Error: {e}")

    def _on_hyperliquid_log(self, message: str, level: str = "INFO") -> None:
        """Route Hyperliquid service logs into bot logs (+ Discord for warnings/errors)."""
        text = (message or "").strip()
        if not text:
            return
        if level in ("ERROR", "CRITICAL") and "❌" not in text:
            text = f"❌ {text}"
        elif level == "WARNING" and "⚠️" not in text:
            text = f"⚠️ {text}"
        self.add_log(text, metadata={"source": "hyperliquid"})

    def start(self):
        """Start the bot"""
        try:
            hyperliquid_service.set_log_callback(self._on_hyperliquid_log)
        except Exception as e:
            logger.warning("Failed to wire Hyperliquid log callback: %s", e)
        self.add_log(f"🔧 start() called. Current is_running={self.is_running}")
        thread_alive = self.thread and self.thread.is_alive()
        
        if not self.is_running or not thread_alive:
            if thread_alive:
                self.add_log("⚠️ Thread exists but is_running=False, fixing state...")
            elif self.is_running:
                self.add_log("⚠️ is_running=True but thread dead, restarting...")
            
            self.is_running = True
            self.add_log("🧵 Creating trading thread...")
            self.thread = threading.Thread(target=self.trading_loop, daemon=True)
            self.add_log("🚀 Starting trading thread...")
            self.thread.start()
            self.add_log(f"✅ Thread started. Thread alive={self.thread.is_alive()}")

            try:
                if getattr(self, "scanner_job", None):
                    self.scanner_job.start()
            except Exception as scan_err:
                self.add_log(f"⚠️ Failed to start ScannerJob: {scan_err}")
            
            StateManager.save_state(self)
        else:
            self.add_log("⚠️ Bot already running with active thread, skipping start")

    def is_loop_responsive(self) -> bool:
        """Check if the trading loop is alive and responsive (not frozen)."""
        if not self.is_running or not self.thread or not self.thread.is_alive():
            return False
        if self._loop_heartbeat == 0:
            return True  # Not yet started, give it a chance
        return (time.time() - self._loop_heartbeat) < 120  # 2 min tolerance

    def stop(self):
        """Stop the bot with complete graceful shutdown"""
        if self.is_running:
            self.is_running = False
            self.add_log("🛑 Initiating graceful shutdown...")
            
            # Final sync: clean up ghost trades before stopping
            try:
                self.add_log("🔄 Final sync with exchange before shutdown...")
                self._sync_state(silent=False)
            except Exception as e:
                self.add_log(f"⚠️ Final sync failed: {e}")
            
            # Do NOT cancel exchange orders on shutdown — SL/TP must stay live
            # across redeploys/restarts. Leaving reduce-only triggers in place.
            if self.active_trades:
                self.add_log(
                    f"🛡️ Leaving exchange SL/TP in place for: "
                    f"{', '.join(self.active_trades.keys())}"
                )
            
            try:
                if getattr(self, "scanner_job", None):
                    self.scanner_job.stop()
            except Exception as scan_err:
                self.add_log(f"⚠️ Failed to stop ScannerJob: {scan_err}")

            try:
                self.add_log("🔌 Stopping WebSocket...")
                hyperliquid_service.stop_websocket()
                self.add_log("✅ WebSocket stopped")
            except Exception as e:
                self.add_log(f"⚠️ Failed to stop WebSocket: {e}")
            
            if self.thread:
                self.add_log("⏳ Waiting for trading thread...")
                self.thread.join(timeout=10)
                if self.thread.is_alive():
                    self.add_log("⚠️ Trading thread did not stop gracefully")
                else:
                    self.add_log("✅ Trading thread stopped")
            
            try:
                StateManager.save_state(self)
                self.add_log("✅ State saved")
            except Exception as e:
                self.add_log(f"⚠️ Failed to save state: {e}")
            
            self.add_log("⏹️ Bot stopped gracefully")

    def close_active_trade(self, reason="Manual Close"):
        """Close the currently active trade"""
        with self.trade_lock:
            if not self.active_trade:
                return False, "No active trade"
            symbol = self.active_trade["symbol"]
            
        try:
            if self.execution_mode == "Dry Run":
                self.add_log(f"[DRY] Would close {symbol} ({reason})")
                with self.trade_lock:
                    self.active_trade = None
                    StateManager.save_state(self)
                return True, "[DRY] Trade closed (simulated)"
            
            self.add_log(f"📉 MANUAL CLOSE REQUESTED for {symbol} ({reason})")
            success = self.execute_exit_atomically(symbol, reason=reason)
            
            if success:
                return True, "Trade closed successfully"
            else:
                return False, "Failed to close trade (Check logs)"
            
        except Exception as e:
            self.add_log(f"❌ Error in close_active_trade: {e}")
            return False, str(e)

    async def recalibrate_position_stops(self):
        """Manual override to recalculate and update TP/SL."""
        with self.trade_lock:
            if not self.active_trade:
                 return "ERROR", "No active trade to recalibrate."
            symbol = self.active_trade["symbol"]
            
        self.add_log(f"♻️ RECALIBRATE: Auditing stops for {symbol}...")

        try:
            positions = hyperliquid_service.get_positions()
            real_pos = next((p for p in positions if p["symbol"] == symbol and float(p["size"]) != 0), None)
            
            if not real_pos:
                self.add_log(f"⚠️ Recalibration aborted: No position found on exchange for {symbol}")
                with self.trade_lock:
                    self.active_trade = None 
                return "ERROR", "No real position found (Local state cleared)."

            entry_price = float(real_pos["entry_price"])
            side = real_pos["side"]
            size = float(real_pos["size"])
            
            df = self.latest_data
            if df is None or df.empty:
                self.add_log("📡 Recalibrate: Cache empty, fetching fresh 15m data...")
                try:
                    df = hyperliquid_service.get_candles(symbol, "15m", 100)
                except Exception as fetch_err:
                    self.add_log(f"⚠️ Fresh fetch failed: {fetch_err}")
            
            atr = 0.0
            try:
                if df is not None and not df.empty:
                    atr_col = next((c for c in ('ATR_14', 'ATRr_14') if c in df.columns), None)
                    if atr_col:
                         atr = float(df[atr_col].iloc[-1])
                    else:
                         high = df['high']; low = df['low']; close = df['close']
                         tr1 = high - low; tr2 = (high - close.shift()).abs(); tr3 = (low - close.shift()).abs()
                         tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
                         atr = float(tr.rolling(14).mean().iloc[-1])
            except Exception:
                pass
            
            # Use REAL-TIME price for validation, not candle close
            current_price = hyperliquid_service.get_current_price(symbol)
            if (not current_price or current_price <= 0) and df is not None and not df.empty:
                 current_price = float(df['close'].iloc[-1])
            
            self.add_log(f"🔍 Recalibrate: Current Price for validation: {current_price}")

            # Recalculate based on Entry but ensuring validity vs Current Price
            atr_val = atr if atr > 0 else entry_price * 0.015
            
            # --- SMART CONTEXT AWARENESS ---
            sl_mult = 2.0; tp_mult = 3.0
            
            try:
                # Prefer strategy plan multipliers when available
                strategy_name = (self.active_trade.get("strategy", "Unknown") or "Unknown")
                strat_obj = None
                if self.strategy_engine and getattr(self.strategy_engine, "strategies", None):
                    strat_obj = self.strategy_engine.strategies.get(strategy_name)
                    if strat_obj is None and strategy_name == "Manual (Adopted)":
                        strat_obj = self.strategy_engine.strategies.get("supertrend")

                if strat_obj is not None and hasattr(strat_obj, "get_param"):
                    try:
                        sl_mult = float(strat_obj.get_param("sl_atr_mult", 2.0) or 2.0)
                    except (TypeError, ValueError):
                        sl_mult = 2.0
                    try:
                        min_rr = float(strat_obj.get_param("min_rr", 2.0) or 2.0)
                    except (TypeError, ValueError):
                        min_rr = 2.0
                    tp_mult = max(sl_mult * min_rr, sl_mult)
                else:
                    # Capital appetite fallback only (no scalp legacy branch)
                    if not hasattr(self, "global_settings"):
                        self.global_settings = {}
                    risk_profile = self.global_settings.get("risk_defaults", {}).get(
                        "risk_profile", "Capital Preservation First"
                    )
                    if risk_profile == "Capital Preservation First":
                        sl_mult = 2.0
                        tp_mult = 3.0
                    elif risk_profile == "High Volatility Hunter":
                        sl_mult = 2.5
                        tp_mult = 4.0
                    else:
                        sl_mult = 2.0
                        tp_mult = 3.0
            except Exception as e:
                self.add_log(f"⚠️ Context Logic Error: {e}")
                sl_mult = 2.0
                tp_mult = 3.0
            
            MIN_DIST_PCT = 0.001 # 0.1% minimal buffer
            
            # --- SAFETY CLAMP (Active Management Sanity Check) ---
            ideal_sl_dist = atr_val * sl_mult
            ideal_tp_dist = atr_val * tp_mult
            
            MAX_SL_DIST_PCT = 0.10 # 10% Max SL
            MAX_TP_DIST_PCT = 0.20 # 20% Max TP (was causing +400% targets)
            
            if ideal_sl_dist > current_price * MAX_SL_DIST_PCT:
                 self.add_log(f"🛡️ Safety Clamp: Limiting SL Calc ({ideal_sl_dist:.4f}) to 10%")
                 ideal_sl_dist = current_price * MAX_SL_DIST_PCT
                 
            if ideal_tp_dist > current_price * MAX_TP_DIST_PCT:
                 self.add_log(f"🛡️ Safety Clamp: Limiting TP Calc ({ideal_tp_dist:.4f}) to 20%")
                 ideal_tp_dist = current_price * MAX_TP_DIST_PCT
            # -----------------------------------------------------
            
            if side == "BUY":
                # LONG: SL below Entry, TP above Entry
                # Use Current Price as base for recalibration logic if intended to trail, 
                # but standard is Entry Based. Let's stick to Entry based for consistency unless trailing.
                
                ideal_sl = entry_price - ideal_sl_dist
                ideal_tp = entry_price + ideal_tp_dist
                
                # Validation: SL must be < Current Price
                if ideal_sl >= current_price * (1 - MIN_DIST_PCT):
                    # self.add_log(f"⚠️ Ideal SL ({ideal_sl:.2f}) above current price ({current_price:.2f}). Adjusting.") # Reduced noise
                    ideal_sl = current_price * (1 - 0.005) # 0.5% below current
                
                # Validation: TP must be > Current Price
                if ideal_tp <= current_price * (1 + MIN_DIST_PCT):
                     ideal_tp = current_price * (1 + 0.005) 

            else:
                # SHORT: SL above Entry, TP below Entry
                ideal_sl = entry_price + ideal_sl_dist
                ideal_tp = entry_price - ideal_tp_dist
                
                # Validation: SL must be > Current Price
                if ideal_sl <= current_price * (1 + MIN_DIST_PCT):
                    # self.add_log(f"⚠️ Ideal SL ({ideal_sl:.2f}) below current price ({current_price:.2f}). Adjusting.")
                    ideal_sl = current_price * (1 + 0.005) 
                    
                # Validation: TP must be < Current Price
                if ideal_tp >= current_price * (1 - MIN_DIST_PCT):
                     ideal_tp = current_price * (1 - 0.005)

            current_sl = float(self.active_trade.get("sl") or 0)
            current_tp = float(self.active_trade.get("tp") or 0)
            
            sl_diff = abs(current_sl - ideal_sl) / current_sl if current_sl else 1.0
            tp_diff = abs(current_tp - ideal_tp) / current_tp if current_tp else 1.0
            
            TP_SL_RECALIBRATION_THRESHOLD_PCT = 0.02 
            is_divergent = (sl_diff > TP_SL_RECALIBRATION_THRESHOLD_PCT) or (tp_diff > TP_SL_RECALIBRATION_THRESHOLD_PCT)
            
            if not is_divergent:
                self.add_log(f"✅ Audit: Orders aligned locally. Verifying exchange...")
                # return "UNCHANGED", "Orders are aligned."  <-- REMOVED to force verification
            else:
                self.add_log(f"⚠️ Audit: Divergence detected (Price: {current_price:.2f}). Updating to SL: {ideal_sl:.2f} | TP: {ideal_tp:.2f}")
            
                with self.trade_lock:
                    self.active_trade["sl"] = ideal_sl
                    self.active_trade["tp"] = ideal_tp
            
            # Force verification immediately to sync with exchange
            self._verify_and_enforce_sl_tp(symbol, self.active_trade, bypass_cooldown=True)
            StateManager.save_state(self)
            
            return "UPDATED", f"Orders recalibrated to SL: {ideal_sl:.2f}, TP: {ideal_tp:.2f}"
            
        except Exception as e:
            self.add_log(f"❌ Recalibrate Error: {e}")
            return "ERROR", str(e)
