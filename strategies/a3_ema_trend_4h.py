"""
A3 — EMA 20/100 trend on 4H UTC with 4×ATR stop and chandelier trailing.

Systematic plan: crossover entries only, inverse-cross exit, no fixed TP target.
Sizing and portfolio limits are handled by the bot risk engine (not this module).
"""
from __future__ import annotations

from typing import Any, Dict, Optional

import numpy as np
import pandas as pd

from app.core.a3_ema_trend_logic import (
    A3_UNIVERSE_DEFAULT,
    atr_on_signal_bar,
    compute_a3_indicators,
    detect_crossover_on_closed_bar,
    entry_open_price,
    initial_stop,
    update_trailing_stop,
)
from app.core.trade_thesis import (
    ACTION_CLOSE,
    THESIS_DEAD,
    ThesisVerdict,
)
from strategies.base import BaseStrategy

A3_STRATEGY_ID = "a3_ema_trend_4h"


class StrategyA3EmaTrend4h(BaseStrategy):
    AI_PERSONA = """
    CODENAME: "A3 EMA-TREND 4H"

    ROLE:
    Systematic 4H EMA 20/100 crossover trend follower. Approve when the signal
    matches a fresh crossover on the closed 4H bar and stops are at 4×ATR20.

    RULES:
    1. Only crossover-bar entries (no late chase).
    2. Initial SL = 4×ATR20; trailing tightens on closed 4H bars only.
    3. Exit on stop or inverse EMA cross (no fixed TP edge requirement).
    """

    AI_VALIDATION_CRITERIA = """=== VALIDATION CRITERIA (A3 4H) ===
APPROVE when the setup is a fresh EMA 20/100 crossover on the closed 4H bar
and SL is placed at 4×ATR20 from the entry open reference.
REJECT if the signal is not on the crossover bar or symbol is outside the A3 universe.
"""

    def __init__(self, config=None):
        super().__init__(config)
        self._suppress_reentry_after_exit = False
        self._last_exit_cross_side: Optional[str] = None

    def get_ai_validation_criteria(self):
        return self.AI_VALIDATION_CRITERIA

    def pre_ai_geometry_veto(self, signal, market_context=None):
        """No structural TP trim — plan uses trailing + inverse cross."""
        return dict(signal or {}), None

    def _universe(self) -> set[str]:
        raw = self.get_param("symbols", list(A3_UNIVERSE_DEFAULT))
        if not isinstance(raw, (list, tuple)):
            return {str(x).upper() for x in A3_UNIVERSE_DEFAULT}
        out = {str(x).upper().strip() for x in raw if str(x).strip()}
        return out or {str(x).upper() for x in A3_UNIVERSE_DEFAULT}

    def check_hard_veto(self, signal: str, market_context: dict) -> Optional[str]:
        ctx = market_context or {}
        sym = str(ctx.get("symbol") or "").upper().replace("-USD", "").replace("-USDC", "")
        if sym.startswith("K") and len(sym) > 2:
            sym = sym[1:]
        allowed = self._universe()
        if sym and sym not in allowed:
            return f"HARD VETO (A3): {sym} not in A3 universe ({len(allowed)} coins)"
        return None

    def _df_4h(self, df, extra_data=None) -> Optional[pd.DataFrame]:
        extra = extra_data or {}
        d4 = extra.get("4h")
        if d4 is not None and not getattr(d4, "empty", True):
            return d4
        tf = str((self.config or {}).get("timeframe") or "4h").lower()
        if tf in ("4h", "240m") and df is not None and not getattr(df, "empty", True):
            return df
        return None

    def _indicators(self, df_4h: pd.DataFrame) -> pd.DataFrame:
        return compute_a3_indicators(
            df_4h,
            ema_fast=int(self.get_param("ema_fast", 20) or 20),
            ema_slow=int(self.get_param("ema_slow", 100) or 100),
            atr_period=int(self.get_param("atr_period", 20) or 20),
        )

    def generate_signal(self, df, extra_data=None):
        df_4h = self._df_4h(df, extra_data)
        if df_4h is None or getattr(df_4h, "empty", True):
            return self._reject("Missing 4H OHLCV")

        min_warmup = int(self.get_param("min_warmup_bars", 300) or 300)
        if len(df_4h) < min_warmup + 2:
            return self._reject(f"Need ≥{min_warmup}+2 4H bars (have {len(df_4h)})")

        ind = self._indicators(df_4h)
        side = detect_crossover_on_closed_bar(ind, min_warmup=min_warmup)
        if side is None:
            return self._reject("No EMA crossover on closed 4H bar")

        if self._suppress_reentry_after_exit:
            self._suppress_reentry_after_exit = False
            return self._reject("Flat after inverse cross — no same-bar reversal")

        if side == "BUY" and not bool(self.get_param("allow_longs", True)):
            return self._reject("Longs disabled")
        if side == "SELL" and not bool(self.get_param("allow_shorts", True)):
            return self._reject("Shorts disabled")

        entry = entry_open_price(df_4h)
        atr_sig = atr_on_signal_bar(ind)
        if entry is None or atr_sig is None:
            return self._reject("Missing entry open or ATR on signal bar")

        atr_mult = float(self.get_param("atr_stop_mult", 4.0) or 4.0)
        sl = initial_stop(side, entry, atr_sig, atr_mult=atr_mult)
        if sl is None:
            return self._reject("Could not compute initial 4×ATR stop")

        sig_idx = -2 if len(ind) >= 2 else -1
        ts = str(ind.index[sig_idx])
        if self._same_bar_already_signaled(ts):
            return self._reject("Same 4H bar already signaled")
        self._mark_signal_bar(ts)

        # Dummy far TP — exits are stop / thesis (inverse cross), not TP.
        if side == "BUY":
            tp = entry * 1.5
        else:
            tp = entry * 0.5

        return {
            "signal": side,
            "price": float(entry),
            "sl": float(sl),
            "tp": float(tp),
            "comment": f"A3 EMA cross {side} @ 4H {ts}",
            "a3_peak_close": float(ind["close"].iloc[sig_idx]),
            "a3_trough_close": float(ind["close"].iloc[sig_idx]),
            "a3_atr_entry": float(atr_sig),
        }

    def score_scan_candidate(self, df, *, symbol: str, meta=None):
        df_4h = df
        if df_4h is None or getattr(df_4h, "empty", True) or len(df_4h) < 120:
            return None
        sym = str(symbol or "").upper()
        if sym not in self._universe():
            return None
        ind = self._indicators(df_4h)
        try:
            ef = float(ind["EMAf"].iloc[-2])
            es = float(ind["EMAs"].iloc[-2])
            atr = float(ind["ATR20"].iloc[-2])
            close = float(ind["close"].iloc[-2])
        except (TypeError, ValueError, KeyError):
            return None
        if any(np.isnan(x) for x in (ef, es, atr, close)) or atr <= 0:
            return None
        spread = abs(ef - es) / atr
        bias = "LONG" if ef > es else "SHORT"
        score = float(max(10.0, min(95.0, 80.0 - spread * 8.0)))
        return {
            "score": score,
            "bias": bias,
            "symbol": sym,
            "reasons": [f"EMA20 vs EMA100 spread {spread:.2f}×ATR"],
        }

    def supports_trade_thesis(self) -> bool:
        return True

    def get_thesis_timeframe(self) -> str:
        return "4h"

    def evaluate_trade_thesis(self, trade, current_price, *, df, extra_data=None):
        df_4h = self._df_4h(df, extra_data)
        if df_4h is None or getattr(df_4h, "empty", True):
            return None
        min_warmup = int(self.get_param("min_warmup_bars", 300) or 300)
        ind = self._indicators(df_4h)
        cross = detect_crossover_on_closed_bar(ind, min_warmup=min_warmup)
        if cross is None:
            return None
        side = str(trade.get("side") or "").upper()
        is_long = side in ("BUY", "LONG")
        side_u = str(trade.get("side") or "BUY").upper()
        entry = float(trade.get("entry") or trade.get("entry_price") or 0)
        pnl_pct = 0.0
        if entry > 0 and current_price:
            from app.core.trade_thesis import _pnl_pct

            pnl_pct = _pnl_pct(side_u, entry, float(current_price))
        sig_idx = -2 if len(ind) >= 2 else -1
        close_bar = float(ind["close"].iloc[sig_idx])
        if is_long and cross == "SELL":
            self._suppress_reentry_after_exit = True
            return ThesisVerdict(
                status=THESIS_DEAD,
                action=ACTION_CLOSE,
                reasons=("A3 inverse EMA cross (long → exit at next open)",),
                adx=0.0,
                adx_slope=0.0,
                st_direction=0,
                close=close_bar,
                supertrend=0.0,
                pnl_pct=pnl_pct,
            )
        if not is_long and cross == "BUY":
            self._suppress_reentry_after_exit = True
            return ThesisVerdict(
                status=THESIS_DEAD,
                action=ACTION_CLOSE,
                reasons=("A3 inverse EMA cross (short → exit at next open)",),
                adx=0.0,
                adx_slope=0.0,
                st_direction=0,
                close=close_bar,
                supertrend=0.0,
                pnl_pct=pnl_pct,
            )
        return None

    def manage_trade(self, trade, current_price, df=None, extra_data=None):
        del current_price
        df_4h = self._df_4h(df, extra_data)
        if df_4h is None or getattr(df_4h, "empty", True) or len(df_4h) < 3:
            return {}
        ind = self._indicators(df_4h)
        sig_idx = -2
        try:
            last_close = float(ind["close"].iloc[sig_idx])
            atr_c = float(ind["ATR20"].iloc[sig_idx])
        except (TypeError, ValueError, KeyError):
            return {}
        if atr_c <= 0 or np.isnan(atr_c):
            return {}

        meta = trade.get("metadata") or {}
        peak = float(meta.get("a3_peak_close") or trade.get("a3_peak_close") or last_close)
        trough = float(meta.get("a3_trough_close") or trade.get("a3_trough_close") or last_close)
        side = str(trade.get("side") or "").upper()
        is_long = side in ("BUY", "LONG")
        sig_side = "BUY" if is_long else "SELL"
        cur_sl = float(trade.get("sl") or 0)
        if cur_sl <= 0:
            return {}

        atr_mult = float(self.get_param("atr_stop_mult", 4.0) or 4.0)
        new_sl, new_peak, new_trough = update_trailing_stop(
            sig_side,
            current_stop=cur_sl,
            atr_current=atr_c,
            last_close=last_close,
            peak_close=peak,
            trough_close=trough,
            atr_mult=atr_mult,
        )
        updates: Dict[str, Any] = {}
        if (is_long and new_sl > cur_sl + 1e-12) or (not is_long and new_sl < cur_sl - 1e-12):
            updates["sl"] = new_sl
        updates["metadata"] = {
            **meta,
            "a3_peak_close": new_peak,
            "a3_trough_close": new_trough,
        }
        return updates if updates.get("sl") is not None else {"metadata": updates["metadata"]}
