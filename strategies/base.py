"""
Strategy contract — the strategy IS the trading plan.

The bot is a generic machine (loop, orders, state, portfolio ceilings).
Each strategy selects a risk-profile preset from the shared library.
Everything market-specific lives here: params, AI persona, hard vetoes,
post-AI geometry, signals, optional manage_trade.

Subclass and override the hooks below. Defaults are intentionally neutral
so a new strategy that only implements generate_signal still runs safely.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional

import pandas as pd


class BaseStrategy(ABC):
    """Base class for all NovaBot strategies (plan ownership)."""

    # Optional class-level AI persona text. Prefer get_ai_persona() in subclasses.
    AI_PERSONA: Optional[str] = None

    def __init__(self, config=None):
        self.name = self.__class__.__name__
        self.config = config or {}
        self.params = self.config.get("params", {})
        self.last_rejection_reason = None

    # ==========================
    # DYNAMIC PARAM ACCESS
    # ==========================

    def get_param(self, key, default=None):
        """
        Always read a parameter from the LIVE self.config["params"] dict.

        Rationale:
        - The API endpoint POST /api/engine/config/strategy-params mutates
          strategy.config["params"] at runtime.
        - Subclasses that cache params in __init__ will not see those updates
          until the engine is rebuilt. Using get_param() inside
          generate_signal()/calculate_progress() guarantees hot-edit support.
        """
        try:
            params = self.config.get("params") or {}
            if key in params:
                return params[key]
            return default
        except Exception:
            return default

    def refresh_params(self):
        """
        Best-effort sync of self.params with self.config['params'].
        Called by the API after strategy-params updates to keep the legacy
        'self.params' attribute in sync for any consumer that still reads it.
        """
        try:
            self.params = self.config.get("params", {}) or {}
        except Exception:
            self.params = {}

    # ==========================
    # PLAN CONTRACT (AI / VETO / GEOMETRY)
    # ==========================

    def get_ai_persona(self) -> Optional[str]:
        """Return strategy-owned AI persona text (1 strategy = 1 persona)."""
        return getattr(self, "AI_PERSONA", None) or None

    def get_ai_validation_criteria(self) -> Optional[str]:
        """
        Optional extra validation criteria block injected into the AI prompt.
        Return None to use the bot's generic criteria.
        """
        return None

    def check_hard_veto(self, signal: str, market_context: dict) -> Optional[str]:
        """
        Pre-AI entry guards owned by this strategy.

        Return a reason string to block the trade, or None to allow.
        Default: no strategy-level veto (bot stays a dumb machine).

        Strategies that want a PASS/BLOCK breakdown for logs may fill
        ``last_veto_report`` (list of {name, blocked, detail}) during this call.
        """
        return None

    def format_veto_report(self) -> Optional[str]:
        """Compact PASS/BLOCK line from ``last_veto_report``, or None."""
        rows = getattr(self, "last_veto_report", None)
        if not rows:
            return None
        parts = []
        for row in rows:
            if not isinstance(row, dict):
                continue
            name = str(row.get("name") or "check")
            tag = "BLOCK" if row.get("blocked") else "PASS"
            detail = str(row.get("detail") or "").strip()
            parts.append(f"{name} {tag}" + (f" ({detail})" if detail else ""))
        return " | ".join(parts) if parts else None

    def post_ai_adjust(
        self,
        signal: Dict[str, Any],
        ai_result: Dict[str, Any],
        market_context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Strategy-owned post-AI geometry (e.g. trim TP to swing).

        Called by the IA hard-constraint layer before R:R / volume checks.
        Must return the (possibly mutated) ai_result dict.
        Default: no-op.
        """
        return ai_result

    def get_min_volume_ratio_pct(self) -> Optional[float]:
        """
        Optional volume floor (%) for post-AI WEAK_VOLUME hard gate.
        None → IA uses its default helper constant.
        """
        return None

    def get_rr_epsilon(self) -> float:
        """Tolerance when comparing post-trim R:R to the strategy risk-profile min."""
        return 0.02

    def get_risk_profile(self, account_default: Optional[str] = None) -> str:
        """Effective risk profile preset for this strategy plan."""
        from app.core.risk_profiles import resolve_strategy_risk_profile

        key = getattr(self, "name", None)
        return resolve_strategy_risk_profile(
            self.config,
            account_default,
            strategy_key=str(key) if key else None,
        )

    # ==========================
    # SCAN (strategy-owned universe ranking)
    # ==========================
    # The bot ScannerJob fetches OHLCV + merges boards; each strategy scores
    # candidates on its own timeframe. Default: no scan participation.

    def get_scan_timeframe(self) -> str:
        """OHLCV interval for ranking (from config timeframe, default 15m)."""
        try:
            tf = str((self.config or {}).get("timeframe") or "15m").strip().lower()
            return tf or "15m"
        except Exception:
            return "15m"

    def get_scan_interval_minutes(self) -> float:
        """
        How often this strategy's scan lane should refresh.
        Prefer params.scan_interval_minutes; else derive from timeframe (1h→60).
        """
        try:
            raw = self.get_param("scan_interval_minutes", None)
            if raw is not None:
                return max(1.0, float(raw))
        except (TypeError, ValueError):
            pass
        tf = self.get_scan_timeframe()
        if tf in ("1h", "60m", "60"):
            return 60.0
        if tf in ("4h", "240m"):
            return 240.0
        return 15.0

    def score_scan_candidate(
        self,
        df: pd.DataFrame,
        *,
        symbol: str,
        meta: Optional[Dict[str, Any]] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Rank one symbol for this strategy's plan.

        Return None to skip, or a dict with at least:
          score (float), bias (LONG|SHORT), symbol, and optional adx/rsi/reasons/armed.
        Default: not scannable (None).
        """
        return None

    # ==========================
    # ENTRY COOLDOWN / SAME-BAR
    # ==========================
    # `_last_entry_time` is FILL-only (set by the bot after a confirmed entry).
    # `_last_signal_bar` is the last closed candle we already emitted — prevents
    # AI spam every loop tick after a reject. Do not start fill-cooldown on signal.

    @staticmethod
    def _naive_ts(ts):
        """Best-effort timezone-stripped timestamp for comparisons."""
        try:
            t = pd.Timestamp(ts)
            if t is None or pd.isna(t):
                return None
            if t.tzinfo is not None:
                t = t.tz_convert("UTC").tz_localize(None)
            return t
        except Exception:
            return None

    def mark_entry_fill(self, ts=None) -> None:
        """Arm fill-cooldown after a confirmed entry (bot machine calls this)."""
        self._last_entry_time = ts if ts is not None else pd.Timestamp.now()

    def _cooldown_ok(self, now_ts, cooldown_minutes: int):
        """True if fill-cooldown has elapsed. Uses wall clock vs last FILL."""
        del now_ts  # candle ts is for same-bar; fill cooldown is wall-clock
        if cooldown_minutes <= 0:
            return True
        last = getattr(self, "_last_entry_time", None)
        last_n = self._naive_ts(last)
        if last_n is None:
            return True
        now_n = self._naive_ts(pd.Timestamp.now())
        if now_n is None:
            return True
        try:
            return (now_n - last_n) >= pd.Timedelta(minutes=int(cooldown_minutes))
        except Exception:
            return True

    def _same_bar_already_signaled(self, now_ts) -> bool:
        bar = getattr(self, "_last_signal_bar", None)
        now_n = self._naive_ts(now_ts)
        bar_n = self._naive_ts(bar)
        if now_n is None or bar_n is None:
            return False
        return now_n == bar_n

    def _mark_signal_bar(self, now_ts) -> None:
        if now_ts is None:
            return
        try:
            if pd.isna(now_ts):
                return
        except Exception:
            return
        self._last_signal_bar = now_ts

    @abstractmethod
    def generate_signal(self, df, extra_data=None):
        """
        Generate signal from dataframe.

        Args:
            df: Primary dataframe (typically the strategy's main timeframe)
            extra_data: Optional dict with additional dataframes (e.g., {"1m": df_1m, "1h": df_1h})
        """
        pass

    def add_indicators(self, df):
        """Add indicators to the dataframe. Should be overridden by subclasses."""
        pass

    # ==========================
    # DYNAMIC ANALYSIS HELPERS
    # ==========================

    def get_adx_slope(self, df, period=14):
        """
        Calculate ADX Slope (Current - Previous).
        Returns: float (Positive = Strengthening, Negative = Weakening)
        """
        if "ADX_14" not in df.columns:
            return 0

        try:
            current = df["ADX_14"].iloc[-1]
            prev = df["ADX_14"].iloc[-2]
            return current - prev
        except Exception:
            return 0

    def get_rsi_delta(self, df, period=14):
        """
        Calculate RSI Delta (Current - Previous).
        Returns: float (>0 = Momentum increasing)
        """
        col = f"RSI_{period}"
        if col not in df.columns:
            return 0

        try:
            current = df[col].iloc[-1]
            prev = df[col].iloc[-2]
            return current - prev
        except Exception:
            return 0

    def detect_bearish_divergence(self, df, rsi_col="RSI_14", lookback=5):
        """
        Detect Bearish Divergence: Price HH but RSI LH.
        Returns: bool
        """
        if rsi_col not in df.columns or len(df) < lookback:
            return False

        try:
            recent = df.iloc[-lookback:]

            price_high_idx = recent["high"].idxmax()
            rsi_high_idx = recent[rsi_col].idxmax()

            current_idx = df.index[-1]

            if price_high_idx == current_idx and rsi_high_idx != current_idx:
                return True

            return False
        except Exception:
            return False

    def manage_trade(self, trade, current_price, df=None, extra_data=None):
        """
        Optional: Override trade management logic (Trailing SL, TP, etc).

        Args:
            trade (dict): Active trade data from bot context
            current_price (float): Current market price
            df (pd.DataFrame): Current market data

        Returns:
            dict or None:
                - If None: Use default bot management (fallback)
                - If dict: Updates to apply (e.g., {"sl": 1234.5})
                    - Return empty dict {} to signal "I handled it, do nothing else"
        """
        return None

    # ==========================
    # IN-TRADE THESIS (strategy-owned plan monitoring)
    # ==========================
    # The bot fetches OHLCV on get_thesis_timeframe(), then calls
    # evaluate_trade_thesis. Return None when data is insufficient this tick.

    def supports_trade_thesis(self) -> bool:
        """True when this strategy monitors open-trade plan invalidation."""
        return False

    def get_thesis_timeframe(self) -> str:
        """OHLCV interval for in-trade thesis checks (defaults to scan TF)."""
        return self.get_scan_timeframe()

    def evaluate_trade_thesis(
        self,
        trade: Dict[str, Any],
        current_price: float,
        *,
        df: pd.DataFrame,
        extra_data: Optional[Dict[str, Any]] = None,
    ):
        """
        Classify whether the open trade's entry thesis still holds.

        Return a ThesisVerdict from app.core.trade_thesis, or None to skip
        this tick (missing data / plan context not on trade yet).
        """
        return None

    def _reject(self, reason: str):
        """Set a human-readable rejection reason for diagnostics and return None."""
        self.last_rejection_reason = reason
        return None
