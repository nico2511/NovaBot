"""
Pure A3 EMA-Trend 4H logic (backtest spec) — no I/O.

Causal bar model:
- Decisions on the last **closed** 4H bar (confirmed).
- Entry / inverse-exit prices use the **open** of the forming bar (next bar).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Optional, Tuple

import numpy as np
import pandas as pd

Side = Literal["LONG", "SHORT"]
SignalSide = Literal["BUY", "SELL"]

A3_UNIVERSE_DEFAULT = (
    "BTC",
    "ETH",
    "SOL",
    "BNB",
    "XRP",
    "DOGE",
    "AVAX",
    "LINK",
    "ARB",
    "OP",
    "SUI",
    "LTC",
    "ADA",
    "DOT",
    "ATOM",
    "NEAR",
    "APT",
    "INJ",
)


def compute_a3_indicators(
    df: pd.DataFrame,
    *,
    ema_fast: int = 20,
    ema_slow: int = 100,
    atr_period: int = 20,
) -> pd.DataFrame:
    """Add EMAf, EMAs, ATR20 columns on 4H OHLCV (closes for EMA)."""
    out = df.copy()
    close = out["close"].astype(float)
    out["EMAf"] = close.ewm(span=int(ema_fast), adjust=False).mean()
    out["EMAs"] = close.ewm(span=int(ema_slow), adjust=False).mean()
    high = out["high"].astype(float)
    low = out["low"].astype(float)
    prev_close = close.shift(1)
    tr = pd.concat(
        [
            high - low,
            (high - prev_close).abs(),
            (low - prev_close).abs(),
        ],
        axis=1,
    ).max(axis=1)
    out["ATR20"] = tr.rolling(int(atr_period)).mean()
    return out


def _cross_up(ema_f: float, ema_s: float, ema_f_prev: float, ema_s_prev: float) -> bool:
    return ema_f > ema_s and ema_f_prev <= ema_s_prev


def _cross_down(ema_f: float, ema_s: float, ema_f_prev: float, ema_s_prev: float) -> bool:
    return ema_f < ema_s and ema_f_prev >= ema_s_prev


def detect_crossover_on_closed_bar(
    ind: pd.DataFrame,
    *,
    min_warmup: int = 300,
) -> Optional[SignalSide]:
    """
    Crossover on the last closed bar only (iloc[-2] when last row is forming).

    Returns BUY/SELL or None. Requires >= min_warmup closed bars before signal bar.
    """
    if ind is None or getattr(ind, "empty", True) or len(ind) < 3:
        return None
    # Last row may be forming; confirmed signal bar is -2 when len>=2
    sig_idx = -2 if len(ind) >= 2 else -1
    if len(ind) + (1 if sig_idx == -2 else 0) < min_warmup + 1:
        return None
    row = ind.iloc[sig_idx]
    prev = ind.iloc[sig_idx - 1]
    ef, es = float(row["EMAf"]), float(row["EMAs"])
    efp, esp = float(prev["EMAf"]), float(prev["EMAs"])
    if any(np.isnan(x) for x in (ef, es, efp, esp, float(row.get("ATR20", np.nan)))):
        return None
    if _cross_up(ef, es, efp, esp):
        return "BUY"
    if _cross_down(ef, es, efp, esp):
        return "SELL"
    return None


def entry_open_price(df: pd.DataFrame) -> Optional[float]:
    """Open of the forming bar (execution reference after signal close)."""
    if df is None or getattr(df, "empty", True):
        return None
    try:
        px = float(df["open"].iloc[-1])
        return px if px > 0 else None
    except (TypeError, ValueError, KeyError):
        return None


def initial_stop(
    side: SignalSide,
    entry: float,
    atr_at_signal: float,
    *,
    atr_mult: float = 4.0,
) -> Optional[float]:
    if entry <= 0 or atr_at_signal <= 0 or atr_mult <= 0:
        return None
    dist = float(atr_mult) * float(atr_at_signal)
    if side == "BUY":
        return entry - dist
    return entry + dist


def update_trailing_stop(
    side: SignalSide,
    *,
    current_stop: float,
    atr_current: float,
    last_close: float,
    peak_close: float,
    trough_close: float,
    atr_mult: float = 4.0,
) -> Tuple[float, float, float]:
    """
    Trailing at 4×ATR on extreme close since entry; stop never loosens.

    Returns (new_stop, new_peak_close, new_trough_close).
    """
    dist = float(atr_mult) * float(atr_current)
    peak = max(float(peak_close), float(last_close))
    trough = min(float(trough_close), float(last_close))
    if side == "BUY":
        candidate = peak - dist
        new_sl = max(float(current_stop), candidate)
    else:
        candidate = trough + dist
        new_sl = min(float(current_stop), candidate)
    return new_sl, peak, trough


def atr_on_signal_bar(ind: pd.DataFrame) -> Optional[float]:
    if ind is None or len(ind) < 2:
        return None
    sig_idx = -2 if len(ind) >= 2 else -1
    try:
        v = float(ind["ATR20"].iloc[sig_idx])
        return v if v > 0 and not np.isnan(v) else None
    except (TypeError, ValueError, KeyError):
        return None


def closed_bar_extremes(ind: pd.DataFrame) -> Tuple[Optional[float], Optional[float]]:
    """Close of last closed bar."""
    if ind is None or len(ind) < 2:
        return None, None
    sig_idx = -2
    try:
        c = float(ind["close"].iloc[sig_idx])
        return c, c
    except (TypeError, ValueError, KeyError):
        return None, None


@dataclass(frozen=True)
class A3PaperStopFlags:
    drawdown_breach: bool
    profit_factor_breach: bool
    slippage_breach: bool
    trade_count: int
    max_drawdown_pct: float
    profit_factor: float
    avg_slippage_pct_per_side: float


def compute_paper_stop_flags(
    closed_trades: list,
    *,
    equity_start: float = 10000.0,
    dd_limit_pct: float = 20.0,
    min_trades_for_pf: int = 150,
    pf_floor: float = 1.0,
    slippage_limit_pct: float = 0.1,
) -> A3PaperStopFlags:
    """Stop criteria from spec (paper observation)."""
    eq = float(equity_start)
    peak = eq
    max_dd = 0.0
    wins = 0.0
    losses = 0.0
    slips: list[float] = []
    n = 0
    for t in closed_trades or []:
        if not isinstance(t, dict):
            continue
        pnl = float(t.get("pnl_usd") or t.get("pnl") or 0)
        eq += pnl
        peak = max(peak, eq)
        if peak > 0:
            dd = (peak - eq) / peak * 100.0
            max_dd = max(max_dd, dd)
        n += 1
        if pnl >= 0:
            wins += pnl
        else:
            losses += abs(pnl)
        slip = t.get("slippage_pct_per_side")
        if slip is not None:
            try:
                slips.append(abs(float(slip)))
            except (TypeError, ValueError):
                pass
    pf = (wins / losses) if losses > 0 else (float("inf") if wins > 0 else 0.0)
    avg_slip = float(np.mean(slips)) if slips else 0.0
    return A3PaperStopFlags(
        drawdown_breach=max_dd > float(dd_limit_pct),
        profit_factor_breach=n >= min_trades_for_pf and pf < pf_floor,
        slippage_breach=avg_slip > float(slippage_limit_pct) if slips else False,
        trade_count=n,
        max_drawdown_pct=max_dd,
        profit_factor=pf if np.isfinite(pf) else 0.0,
        avg_slippage_pct_per_side=avg_slip,
    )
