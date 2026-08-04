"""
Background SuperTrend scanner job.

Periodically ranks the market and optionally auto-switches active_symbol
when the bot is flat (no open trades / under max_positions).
"""
from __future__ import annotations

import threading
import time
from typing import Any, Dict, List, Optional

from app.core.state_manager import StateManager
from app.services.discord_service import discord_service
from app.services.supertrend_scanner import SupertrendScanner
from app.utils.formatters import format_price_for_notification


class ScannerJob:
    """Parallel scanner thread — does not block the trading loop."""

    SWITCH_HYSTERESIS = 10.0  # require this many points above current symbol

    def __init__(self, bot_context):
        self.bot = bot_context
        self.is_running = False
        self.thread: Optional[threading.Thread] = None
        self.last_scan_time = 0.0
        self.is_scanning = False
        self.last_results: List[Dict[str, Any]] = []
        self.results_lock = threading.Lock()
        self.scanner = SupertrendScanner(st_params=self._load_st_params())

    def _load_st_params(self) -> Dict[str, Any]:
        try:
            engine = getattr(self.bot, "strategy_engine", None)
            cfg = getattr(engine, "config", None) or {}
            return dict(cfg.get("supertrend", {}).get("params", {}) or {})
        except Exception:
            return {}

    def _refresh_scanner_config(self):
        settings = getattr(self.bot, "scanner_settings", {}) or {}
        self.scanner.update_settings(
            st_params=self._load_st_params(),
            min_volume_24h=settings.get("min_volume_24h", 2_000_000),
            min_open_interest=settings.get("min_open_interest", 1_000_000),
            max_tokens=settings.get("max_tokens", 40),
            funding_filter_enabled=settings.get("funding_filter_enabled", False),
            max_funding_long=settings.get("max_funding_long", 0.001),
            min_funding_short=settings.get("min_funding_short", -0.001),
        )

    def _has_capacity_for_switch(self) -> bool:
        """Never rotate while any trade is open (safe default for max_positions=1)."""
        trades = getattr(self.bot, "active_trades", {}) or {}
        if trades:
            return False
        max_pos = int(getattr(self.bot, "max_positions", 1) or 1)
        if len(trades) >= max_pos:
            return False
        return True

    def start(self):
        if self.is_running:
            return
        self.is_running = True
        self.last_scan_time = 0.0  # immediate first scan when enabled
        self.thread = threading.Thread(target=self._run_loop, daemon=True, name="ScannerJob")
        self.thread.start()
        self.bot.add_log("🔍 ScannerJob started")

    def stop(self):
        self.is_running = False
        if self.thread and self.thread.is_alive():
            try:
                self.thread.join(timeout=3)
            except Exception:
                pass
        self.bot.add_log("⏹️ ScannerJob stopped")

    def _run_loop(self):
        self.bot.add_log("🔍 Scanner loop entered")
        while self.is_running:
            try:
                settings = getattr(self.bot, "scanner_settings", {}) or {}
                enabled = bool(settings.get("enabled", False))
                interval_minutes = float(settings.get("interval", 15) or 15)
                min_score = float(settings.get("min_score", 60) or 60)
                auto_switch = bool(settings.get("auto_switch", False))

                if not enabled:
                    time.sleep(10)
                    continue

                if not self._has_capacity_for_switch() and not settings.get("scan_while_in_trade", False):
                    # Still allow scoring later for alerts if scan_while_in_trade; default skip heavy work.
                    time.sleep(10)
                    continue

                now = time.time()
                required = max(60.0, interval_minutes * 60.0)
                if (now - self.last_scan_time) < required:
                    time.sleep(5)
                    continue

                self.last_scan_time = now
                self.bot.add_log(f"🕵️ Running SuperTrend scan (interval={interval_minutes:.0f}m, min_score={min_score:.0f})")
                result = self._execute_scan(min_score=min_score, auto_switch=auto_switch, alert=True)
                if result.get("status") == "error":
                    self.bot.add_log(f"❌ Scanner error: {result.get('message')}")

            except Exception as e:
                self.bot.add_log(f"❌ ScannerJob Error: {e}")
                time.sleep(30)

            time.sleep(5)

    def manual_scan(self, auto_switch: Optional[bool] = None) -> Dict[str, Any]:
        if self.is_scanning:
            return {"status": "busy", "message": "Scan already in progress"}
        settings = getattr(self.bot, "scanner_settings", {}) or {}
        min_score = float(settings.get("min_score", 60) or 60)
        do_switch = settings.get("auto_switch", False) if auto_switch is None else bool(auto_switch)
        self.bot.add_log("🕵️ Manual SuperTrend scan started")
        return self._execute_scan(min_score=min_score, auto_switch=do_switch, alert=True)

    def _whitelist(self) -> Optional[List[str]]:
        settings = getattr(self.bot, "scanner_settings", {}) or {}
        wl = settings.get("whitelist") or []
        if not isinstance(wl, list) or not wl:
            return None
        return [str(s).strip().upper() for s in wl if str(s).strip()]

    def _execute_scan(self, min_score: float, auto_switch: bool, alert: bool) -> Dict[str, Any]:
        self.is_scanning = True
        try:
            self._refresh_scanner_config()
            whitelist = self._whitelist()
            opportunities = self.scanner.scan(top_n=10, whitelist=whitelist, force=True)
            with self.results_lock:
                self.last_results = opportunities

            valid = [o for o in opportunities if float(o.get("score", 0)) >= min_score]
            self.bot.add_log(
                f"🕵️ Scan done: {len(opportunities)} ST setups, {len(valid)} ≥ {min_score:.0f}"
            )

            if alert:
                if valid and self._has_capacity_for_switch():
                    self._send_discord_alert(valid, min_score, warning=False)
                elif opportunities and self._has_capacity_for_switch():
                    self._send_discord_alert(opportunities[:3], min_score, warning=True)
                elif not opportunities:
                    discord_service.send_log("🕵️ **Scanner**: no SuperTrend-aligned tokens this pass")

            switched = None
            if auto_switch and valid:
                switched = self._maybe_auto_switch(valid[0], opportunities)

            return {
                "status": "success",
                "results": opportunities,
                "valid_count": len(valid),
                "count": len(opportunities),
                "switched_to": switched,
            }
        except Exception as e:
            return {"status": "error", "message": str(e), "results": []}
        finally:
            self.is_scanning = False

    def _score_for_symbol(self, symbol: str, opportunities: List[Dict[str, Any]]) -> float:
        for opp in opportunities:
            if opp.get("symbol") == symbol:
                return float(opp.get("score", 0) or 0)
        return 0.0

    def _maybe_auto_switch(self, best: Dict[str, Any], opportunities: List[Dict[str, Any]]) -> Optional[str]:
        if not self._has_capacity_for_switch():
            self.bot.add_log(
                f"⚠️ Scanner best={best.get('symbol')} ({best.get('score')}) — skip switch (trade active)"
            )
            return None

        best_symbol = best.get("symbol")
        best_score = float(best.get("score", 0) or 0)
        if not best_symbol:
            return None

        current = self.bot.active_symbol
        if best_symbol == current:
            return None

        current_score = self._score_for_symbol(current, opportunities)
        if current_score > 0 and best_score < current_score + self.SWITCH_HYSTERESIS:
            self.bot.add_log(
                f"🕵️ Keep {current} (score {current_score:.0f}) — best {best_symbol} "
                f"{best_score:.0f} within hysteresis {self.SWITCH_HYSTERESIS:.0f}"
            )
            return None

        old = current
        self.bot.switch_active_symbol(best_symbol)
        StateManager.save_state(self.bot)
        msg = (
            f"🔄 **Auto-Switch**: `{old}` → **`{best_symbol}`** "
            f"(score {best_score:.0f}, bias {best.get('bias')}, ADX {best.get('adx')})"
        )
        self.bot.add_log(msg.replace("**", "").replace("`", ""))
        discord_service.send_log(msg)
        return best_symbol

    def get_last_results(self) -> List[Dict[str, Any]]:
        with self.results_lock:
            return list(self.last_results)

    def _send_discord_alert(self, opps: List[Dict[str, Any]], min_score: float, warning: bool = False):
        if not opps:
            return
        if warning:
            title = f"⚠️ SCANNER ST: marché calme (Top {len(opps)})"
            description = f"Aucune opportunité ≥{min_score:.0f}. Meilleurs scores SuperTrend:\n\n"
            color = "ffa500"
        else:
            title = f"🔍 SCANNER ST: {len(opps)} opportunités"
            description = f"Setups SuperTrend 15m avec score ≥ {min_score:.0f}\n\n"
            color = "2ecc71"

        for i, opp in enumerate(opps[:5]):
            bias = opp.get("bias", "?")
            trend_icon = "📈" if bias == "LONG" else "📉" if bias == "SHORT" else "➡️"
            price_str = format_price_for_notification(opp.get("current_price", 0))
            description += (
                f"**{i+1}. {opp.get('symbol')}** {trend_icon} `{bias}`\n"
                f"Score: **{float(opp.get('score', 0)):.0f}** | ADX {opp.get('adx', 0)} | RSI {opp.get('rsi', 0)}\n"
                f"Price: {price_str} | Vol24h: ${float(opp.get('volume_24h', 0))/1e6:.1f}M\n"
            )
            for reason in (opp.get("reasons") or [])[:2]:
                description += f"> {reason}\n"
            description += "\n"

        discord_service.send_alert(title, description, color=color)
