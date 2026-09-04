"""
Background multi-strategy scanner job.

Builds a liquid universe once, then each enabled strategy scores candidates on
its own timeframe. Results are merged for top-K analysis and optional auto-switch.
"""
from __future__ import annotations

import threading
import time
from typing import Any, Dict, List, Optional, Tuple

from app.core.state_manager import StateManager
from app.services.discord_service import discord_service
from app.services.supertrend_scanner import SupertrendScanner
from app.utils.formatters import format_price_for_notification


class ScannerJob:
    """Parallel scanner thread — does not block the trading loop."""

    SWITCH_HYSTERESIS = 10.0
    SWITCH_HYSTERESIS_ARMED = 35.0
    SWITCH_COOLDOWN_SECONDS = 30 * 60
    CANDLE_LIMIT = 260

    def __init__(self, bot_context):
        self.bot = bot_context
        self.is_running = False
        self.thread: Optional[threading.Thread] = None
        self.last_scan_time = 0.0
        self.last_switch_time = 0.0
        self.is_scanning = False
        self.last_results: List[Dict[str, Any]] = []
        self.last_results_by_strategy: Dict[str, List[Dict[str, Any]]] = {}
        self._lane_last_run: Dict[str, float] = {}
        self.results_lock = threading.Lock()
        self.universe = SupertrendScanner()

    def _refresh_universe_config(self):
        settings = getattr(self.bot, "scanner_settings", {}) or {}
        self.universe.update_settings(
            min_volume_24h=settings.get("min_volume_24h", 2_000_000),
            min_open_interest=settings.get("min_open_interest", 1_000_000),
            max_tokens=settings.get("max_tokens", 40),
            funding_filter_enabled=settings.get("funding_filter_enabled", False),
            max_funding_long=settings.get("max_funding_long", 0.001),
            min_funding_short=settings.get("min_funding_short", -0.001),
        )

    def _has_capacity_for_switch(self) -> bool:
        max_pos = int(getattr(self.bot, "max_positions", 1) or 1)
        book = getattr(self.bot, "trade_book", None)
        if book is not None:
            return len(book) < max_pos
        trades = getattr(self.bot, "active_trades", {}) or {}
        return len(trades) < max_pos

    def start(self):
        if self.is_running:
            return
        self.is_running = True
        self.last_scan_time = 0.0
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
                # Global poll cadence (min); each strategy lane has its own interval
                poll_minutes = float(settings.get("interval", 5) or 5)
                min_score = float(settings.get("min_score", 60) or 60)
                auto_switch = bool(settings.get("auto_switch", False))

                if not enabled:
                    time.sleep(10)
                    continue

                if not self._has_capacity_for_switch() and not settings.get(
                    "scan_while_in_trade", False
                ):
                    time.sleep(10)
                    continue

                now = time.time()
                required = max(30.0, poll_minutes * 60.0)
                if (now - self.last_scan_time) < required:
                    time.sleep(5)
                    continue

                self.last_scan_time = now
                self.bot.add_log(
                    f"🕵️ Running strategy scan (poll={poll_minutes:.0f}m, min_score={min_score:.0f})"
                )
                result = self._execute_scan(
                    min_score=min_score, auto_switch=auto_switch, alert=True, force_all=False
                )
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
        self.bot.add_log("🕵️ Manual strategy scan started")
        return self._execute_scan(
            min_score=min_score, auto_switch=do_switch, alert=True, force_all=True
        )

    def _whitelist(self) -> Optional[List[str]]:
        settings = getattr(self.bot, "scanner_settings", {}) or {}
        wl = settings.get("whitelist") or []
        if not isinstance(wl, list) or not wl:
            return None
        return [str(s).strip().upper() for s in wl if str(s).strip()]

    def _active_strategies(self) -> List[Tuple[str, Any]]:
        engine = getattr(self.bot, "strategy_engine", None)
        if not engine:
            return []
        cfg = getattr(engine, "config", None) or {}
        from app.core.weekend_pause import is_strategy_weekend_paused

        out = []
        for name, strat in (getattr(engine, "strategies", None) or {}).items():
            if strat is None:
                continue
            scfg = cfg.get(name) or {}
            if scfg.get("enabled") is False or scfg.get("active") is False:
                continue
            if is_strategy_weekend_paused(name, cfg):
                continue
            # Participate only if score_scan_candidate is overridden meaningfully —
            # call it; base returns None for all. Still iterate enabled strats.
            out.append((name, strat))
        return out

    def _sticky_armed_for(self, strategy_name: str, symbol: str) -> bool:
        """Per-(strategy, symbol) sticky looking_for_entry from bot state."""
        sticky = getattr(self.bot, "_strategy_sticky", None) or {}
        sym = str(symbol or "").upper()
        for key, state in sticky.items():
            if not isinstance(key, tuple) or len(key) != 2:
                continue
            sname, ssym = key
            if str(sname) != strategy_name or str(ssym).upper() != sym:
                continue
            if isinstance(state, dict) and state.get("looking_for_entry"):
                return True
        return False

    @staticmethod
    def apply_lane_percentile_scores(
        boards: Dict[str, List[Dict[str, Any]]],
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        Blend raw lane scores with within-lane percentile for fairer cross-strategy merge.
        Preserves raw_score on each row; score becomes the merge comparison value.
        """
        out: Dict[str, List[Dict[str, Any]]] = {}
        for sname, rows in (boards or {}).items():
            if not rows:
                out[sname] = []
                continue
            scores = [float(r.get("score") or 0) for r in rows]
            n = len(scores)
            new_rows: List[Dict[str, Any]] = []
            for row in rows:
                raw = float(row.get("score") or 0)
                rank = sum(1 for x in scores if x <= raw)
                pct = (100.0 * rank / n) if n else raw
                merged_score = round(min(100.0, 0.65 * raw + 0.35 * pct), 1)
                nr = dict(row)
                nr["raw_score"] = raw
                nr["score"] = merged_score
                new_rows.append(nr)
            out[sname] = new_rows
        return out

    @staticmethod
    def merge_strategy_boards(
        boards: Dict[str, List[Dict[str, Any]]],
    ) -> List[Dict[str, Any]]:
        """
        Union by symbol: score = max across lanes; tag strategies list.
        Sorted by score descending.
        """
        by_sym: Dict[str, Dict[str, Any]] = {}
        for sname, rows in (boards or {}).items():
            for row in rows or []:
                if not isinstance(row, dict):
                    continue
                sym = row.get("symbol")
                if not sym:
                    continue
                score = float(row.get("score") or 0)
                existing = by_sym.get(sym)
                if existing is None:
                    merged = dict(row)
                    merged["strategies"] = [sname]
                    merged["score"] = score
                    by_sym[sym] = merged
                    continue
                tags = list(existing.get("strategies") or [])
                if sname not in tags:
                    tags.append(sname)
                existing["strategies"] = tags
                if score >= float(existing.get("score") or 0):
                    # Keep higher-score lane payload but preserve tags
                    keep_tags = tags
                    by_sym[sym] = dict(row)
                    by_sym[sym]["strategies"] = keep_tags
                    by_sym[sym]["score"] = score
                else:
                    existing["strategies"] = tags
        results = list(by_sym.values())
        results.sort(key=lambda o: float(o.get("score") or 0), reverse=True)
        return results

    @staticmethod
    def lane_counts_above(
        boards: Dict[str, List[Dict[str, Any]]],
        min_score: float,
    ) -> Dict[str, int]:
        """How many candidates per lane scored ≥ min_score."""
        out: Dict[str, int] = {}
        for name, rows in (boards or {}).items():
            n = 0
            for row in rows or []:
                if not isinstance(row, dict):
                    continue
                try:
                    score = float(row.get("score") or 0)
                except (TypeError, ValueError):
                    score = 0.0
                if score >= min_score:
                    n += 1
            out[str(name)] = n
        return out

    def _lane_due(self, name: str, strat, now: float, force: bool) -> bool:
        if force:
            return True
        try:
            interval_m = float(strat.get_scan_interval_minutes())
        except Exception:
            interval_m = 15.0
        interval_s = max(60.0, interval_m * 60.0)
        last = float(self._lane_last_run.get(name) or 0)
        return (now - last) >= interval_s

    def _score_lane(
        self,
        name: str,
        strat,
        universe: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        try:
            tf = str(strat.get_scan_timeframe() or "15m")
        except Exception:
            tf = "15m"
        results: List[Dict[str, Any]] = []
        for i, data in enumerate(universe):
            symbol = data.get("symbol")
            if not symbol:
                continue
            df = self.universe.get_candles(symbol, tf, limit=self.CANDLE_LIMIT)
            if df is None or getattr(df, "empty", True):
                continue
            try:
                meta = dict(data)
                meta["sticky_armed"] = self._sticky_armed_for(name, symbol)
                opp = strat.score_scan_candidate(df, symbol=symbol, meta=meta)
            except Exception as e:
                self.bot.add_log(f"⚠️ Scan score {name}/{symbol}: {e}")
                opp = None
            if opp and opp.get("score") is not None:
                opp = dict(opp)
                opp["strategy"] = name
                opp.setdefault("symbol", symbol)
                results.append(opp)
            if i < len(universe) - 1:
                time.sleep(self.universe.INTER_SYMBOL_SLEEP)
        results.sort(key=lambda o: float(o.get("score") or 0), reverse=True)
        return results

    def _execute_scan(
        self,
        min_score: float,
        auto_switch: bool,
        alert: bool,
        force_all: bool = False,
    ) -> Dict[str, Any]:
        self.is_scanning = True
        try:
            self._refresh_universe_config()
            whitelist = self._whitelist()
            universe = self.universe.build_universe(whitelist=whitelist)
            if not universe:
                with self.results_lock:
                    self.last_results = []
                return {
                    "status": "success",
                    "results": [],
                    "valid_count": 0,
                    "count": 0,
                    "switched_to": None,
                }

            now = time.time()
            boards: Dict[str, List[Dict[str, Any]]] = {}
            # Keep previous lane results when interval not due
            with self.results_lock:
                boards = {
                    k: list(v) for k, v in (self.last_results_by_strategy or {}).items()
                }

            engine = getattr(self.bot, "strategy_engine", None)
            cfg = getattr(engine, "config", None) or {}
            from app.core.weekend_pause import get_weekend_paused_strategies

            for paused_name in get_weekend_paused_strategies(cfg):
                boards.pop(paused_name, None)

            lanes_run = []
            for name, strat in self._active_strategies():
                if not hasattr(strat, "score_scan_candidate"):
                    continue
                if not self._lane_due(name, strat, now, force_all):
                    continue
                self.bot.add_log(
                    f"🕵️ Lane `{name}` TF={strat.get_scan_timeframe()} "
                    f"universe={len(universe)}"
                )
                scored = self._score_lane(name, strat, universe)
                boards[name] = scored
                self._lane_last_run[name] = now
                lanes_run.append(f"{name}:{len(scored)}")

            boards = self.apply_lane_percentile_scores(boards)
            merged = self.merge_strategy_boards(boards)
            with self.results_lock:
                self.last_results_by_strategy = boards
                self.last_results = merged

            valid = [o for o in merged if float(o.get("score", 0)) >= min_score]
            self.bot.add_log(
                f"🕵️ Scan done: lanes [{', '.join(lanes_run) or 'cached'}] → "
                f"{len(merged)} symbols, {len(valid)} ≥ {min_score:.0f}"
            )

            if alert:
                if valid and self._has_capacity_for_switch():
                    self._send_discord_alert(valid, min_score, boards, warning=False)
                elif merged and self._has_capacity_for_switch():
                    self._send_discord_alert(merged[:3], min_score, boards, warning=True)
                elif not merged:
                    discord_service.send_log(
                        "🕵️ **Scanner**: no strategy-aligned tokens this pass"
                    )

            switched = None
            if auto_switch and valid:
                switched = self._maybe_auto_switch(valid[0], merged)

            return {
                "status": "success",
                "results": merged,
                "by_strategy": boards,
                "valid_count": len(valid),
                "count": len(merged),
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

    def _current_setup_armed(self) -> bool:
        """True if any strategy is looking_for_entry on the active symbol."""
        sticky = getattr(self.bot, "_strategy_sticky", None) or {}
        current = getattr(self.bot, "active_symbol", None)
        if current:
            for (_sname, sym), state in sticky.items():
                if sym != current or not isinstance(state, dict):
                    continue
                if state.get("looking_for_entry"):
                    return True
        try:
            engine = getattr(self.bot, "strategy_engine", None)
            for strat in (getattr(engine, "strategies", None) or {}).values():
                if bool(getattr(strat, "looking_for_entry", False)):
                    return True
        except Exception:
            pass
        return False

    def _maybe_auto_switch(
        self, best: Dict[str, Any], opportunities: List[Dict[str, Any]]
    ) -> Optional[str]:
        if not self._has_capacity_for_switch():
            self.bot.add_log(
                f"⚠️ Scanner best={best.get('symbol')} ({best.get('score')}) — "
                f"skip switch (no free slots)"
            )
            return None

        best_symbol = best.get("symbol")
        best_score = float(best.get("score", 0) or 0)
        if not best_symbol:
            return None

        current = self.bot.active_symbol
        if best_symbol == current:
            return None

        settings = getattr(self.bot, "scanner_settings", {}) or {}
        try:
            cooldown_s = float(
                settings.get("switch_cooldown_minutes", 30) or 30
            ) * 60.0
        except (TypeError, ValueError):
            cooldown_s = float(self.SWITCH_COOLDOWN_SECONDS)
        last_switch = float(getattr(self, "last_switch_time", 0) or 0)
        if last_switch > 0 and (time.time() - last_switch) < cooldown_s:
            elapsed = int(time.time() - last_switch)
            self.bot.add_log(
                f"🕵️ Keep {current} — post-switch cooldown "
                f"({elapsed}s / {int(cooldown_s)}s)"
            )
            return None

        current_score = self._score_for_symbol(current, opportunities)
        hysteresis = self.SWITCH_HYSTERESIS
        armed = self._current_setup_armed()
        if armed:
            hysteresis = self.SWITCH_HYSTERESIS_ARMED

        if current_score > 0 and best_score < current_score + hysteresis:
            why = "armed near-entry" if armed else f"hysteresis {hysteresis:.0f}"
            self.bot.add_log(
                f"🕵️ Keep {current} (score {current_score:.0f}, {why}) — best {best_symbol} "
                f"{best_score:.0f} needs +{hysteresis:.0f}"
            )
            return None

        if armed and current_score <= 0 and best_score < 90:
            self.bot.add_log(
                f"🕵️ Keep {current} (setup armed, not on board) — best {best_symbol} "
                f"{best_score:.0f} < sticky floor 90"
            )
            return None

        old = current
        self.bot.switch_active_symbol(best_symbol)
        self.last_switch_time = time.time()
        StateManager.save_state(self.bot)
        lanes = ",".join(best.get("strategies") or [best.get("strategy") or "?"])
        msg = (
            f"🔄 **Auto-Switch**: `{old}` → **`{best_symbol}`** "
            f"(score {best_score:.0f}, bias {best.get('bias')}, "
            f"ADX {best.get('adx')}, lanes={lanes})"
        )
        self.bot.add_log(msg.replace("**", "").replace("`", ""))
        discord_service.send_log(msg)
        return best_symbol

    def get_last_results(self) -> List[Dict[str, Any]]:
        with self.results_lock:
            return list(self.last_results)

    def _send_discord_alert(
        self,
        opps: List[Dict[str, Any]],
        min_score: float,
        boards: Dict[str, List[Dict[str, Any]]],
        warning: bool = False,
    ):
        if not opps:
            return
        counts = self.lane_counts_above(boards, min_score)
        lane_bits = [f"{name}:{n}" for name, n in counts.items()]
        lane_summary = " | ".join(lane_bits) if lane_bits else "n/a"

        if warning:
            title = f"⚠️ SCANNER: marché calme (Top {len(opps)})"
            description = (
                f"Aucune opportunité ≥{min_score:.0f}. Meilleurs scores "
                f"(lanes {lane_summary}):\n\n"
            )
            color = "ffa500"
        else:
            title = f"🔍 SCANNER: {len(opps)} opportunités"
            description = (
                f"Setups multi-stratégie ≥ {min_score:.0f} "
                f"(lanes {lane_summary})\n\n"
            )
            color = "2ecc71"

        for i, opp in enumerate(opps[:5]):
            bias = opp.get("bias", "?")
            trend_icon = "📈" if bias == "LONG" else "📉" if bias == "SHORT" else "➡️"
            price_str = format_price_for_notification(opp.get("current_price", 0))
            tags = ",".join(opp.get("strategies") or [opp.get("strategy") or "?"])
            tf = opp.get("timeframe") or "?"
            description += (
                f"**{i+1}. {opp.get('symbol')}** {trend_icon} `{bias}` "
                f"[{tags} / {tf}]\n"
                f"Score: **{float(opp.get('score', 0)):.0f}** | "
                f"ADX {opp.get('adx', 0)} | RSI {opp.get('rsi', 0)}\n"
                f"Price: {price_str} | Vol24h: ${float(opp.get('volume_24h', 0))/1e6:.1f}M\n"
            )
            for reason in (opp.get("reasons") or [])[:2]:
                description += f"> {reason}\n"
            description += "\n"

        discord_service.send_alert(title, description, color=color)
