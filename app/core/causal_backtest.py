"""
Causal replay helpers — confirmed bars only, with Hyperliquid-like costs.

``walk_closed_bars`` is the signal harness. ``simulate_bracket`` / ``summarize_trades``
turn those signals into expectancy after SL/TP/thesis. This module does not
download data and does not refit parameters.

Callers must pass OHLCV that already respects look-ahead: a signal at decision
time t uses bars with open time <= t, and the last row is the forming bar.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

import pandas as pd

# HL taker ~0.045% per side.
TAKER_FEE = 0.00045
DEFAULT_SLIP_FRAC = 0.0001  # 1 bp per fill


@dataclass(frozen=True)
class ReplayFill:
    index: Any
    side: str
    price: float
    sl: float
    tp: float
    strategy: str


def round_trip_cost_frac(*, taker: float = TAKER_FEE, slip: float = DEFAULT_SLIP_FRAC) -> float:
    """Round-trip cost as a fraction of price (entry + exit, fees + slip)."""
    return (2.0 * float(taker)) + (2.0 * float(slip))


def net_r(
    gross_r: float,
    *,
    sl_frac: float,
    taker: float = TAKER_FEE,
    slip: float = DEFAULT_SLIP_FRAC,
) -> float:
    """Convert a gross R result into net R after round-trip costs."""
    if sl_frac <= 0:
        return float(gross_r)
    cost_r = round_trip_cost_frac(taker=taker, slip=slip) / float(sl_frac)
    return float(gross_r) - cost_r


def walk_closed_bars(
    df: pd.DataFrame,
    strategy,
    *,
    extra_data_fn: Optional[Callable[[pd.DataFrame, int], Dict[str, Any]]] = None,
    warmup: int = 80,
) -> List[ReplayFill]:
    """
    Replay ``generate_signal`` causally.

    At index ``i`` the strategy sees ``df.iloc[: i + 1]`` (last row = forming bar)
    and any extra frames from ``extra_data_fn``. A fill, if any, is tagged on the
    confirmed bar ``iloc[-2]``.
    """
    fills: List[ReplayFill] = []
    if df is None or getattr(df, "empty", True) or len(df) < warmup + 2:
        return fills
    name = getattr(strategy, "name", strategy.__class__.__name__)
    for i in range(warmup, len(df)):
        window = df.iloc[: i + 1]
        extra = extra_data_fn(window, i) if extra_data_fn else None
        sig = strategy.generate_signal(window, extra_data=extra)
        if not isinstance(sig, dict):
            continue
        side = str(sig.get("signal") or "")
        if side not in ("BUY", "SELL"):
            continue
        try:
            price = float(sig["price"])
            sl = float(sig["sl"])
            tp = float(sig["tp"])
        except (KeyError, TypeError, ValueError):
            continue
        fills.append(
            ReplayFill(
                index=window.index[-2],
                side=side,
                price=price,
                sl=sl,
                tp=tp,
                strategy=str(sig.get("strategy") or name),
            )
        )
    return fills


def sl_fraction(entry: float, initial_sl: float) -> float:
    """Initial risk as a fraction of entry price."""
    if entry <= 0:
        return 0.0
    return abs(float(entry) - float(initial_sl)) / float(entry)


def gross_r(side: str, entry: float, exit_price: float, initial_sl: float) -> float:
    """R versus the original stop, not a trailed stop."""
    if side == "BUY":
        risk = float(entry) - float(initial_sl)
        move = float(exit_price) - float(entry)
    elif side == "SELL":
        risk = float(initial_sl) - float(entry)
        move = float(entry) - float(exit_price)
    else:
        return 0.0
    if risk <= 0:
        return 0.0
    return move / risk


def valid_bracket(side: str, price: float, sl: float, tp: float) -> bool:
    """True when SL and TP sit on the correct sides of a positive entry."""
    try:
        price_f, sl_f, tp_f = float(price), float(sl), float(tp)
    except (TypeError, ValueError):
        return False
    if min(price_f, sl_f, tp_f) <= 0:
        return False
    if side == "BUY":
        return sl_f < price_f < tp_f
    if side == "SELL":
        return tp_f < price_f < sl_f
    return False


def bar_bracket_exit(
    side: str,
    open_: float,
    high: float,
    low: float,
    sl: float,
    tp: float,
) -> Optional[Tuple[float, str]]:
    """
    Intrabar SL/TP outcome.

    The path inside the bar is unknown. A gap through the stop fills at the
    open. If both stops are touched, the stop-loss wins.
    """
    try:
        open_f, high_f, low_f = float(open_), float(high), float(low)
        sl_f, tp_f = float(sl), float(tp)
    except (TypeError, ValueError):
        return None
    if side == "BUY":
        hit_sl = low_f <= sl_f
        hit_tp = high_f >= tp_f
        if open_f <= sl_f:
            return open_f, "sl_gap"
        if open_f >= tp_f and not hit_sl:
            return open_f, "tp_gap"
        if hit_sl:
            return sl_f, "sl_same_bar" if hit_tp else "sl"
        if hit_tp:
            return tp_f, "tp"
        return None
    if side == "SELL":
        hit_sl = high_f >= sl_f
        hit_tp = low_f <= tp_f
        if open_f >= sl_f:
            return open_f, "sl_gap"
        if open_f <= tp_f and not hit_sl:
            return open_f, "tp_gap"
        if hit_sl:
            return sl_f, "sl_same_bar" if hit_tp else "sl"
        if hit_tp:
            return tp_f, "tp"
    return None


def funding_drag_r(
    side: str,
    entry_time: Any,
    exit_time: Any,
    sl_frac: float,
    funding: Optional[pd.DataFrame],
) -> Tuple[float, bool]:
    """
    Funding paid by this side, in R.

    ``funding`` is indexed by settlement time with a ``funding_rate`` column
    (Hyperliquid hourly rate, decimal per hour). Longs pay a positive rate.
    Returns ``(drag_r, covered)``. Missing rows → ``(0, False)``.
    """
    if funding is None or getattr(funding, "empty", True) or sl_frac <= 0:
        return 0.0, False
    if "funding_rate" not in funding.columns:
        return 0.0, False
    start = pd.Timestamp(entry_time)
    end = pd.Timestamp(exit_time)
    idx = funding.index
    if getattr(idx, "tz", None) is not None:
        if start.tzinfo is None:
            start = start.tz_localize("UTC")
        else:
            start = start.tz_convert(idx.tz)
        if end.tzinfo is None:
            end = end.tz_localize("UTC")
        else:
            end = end.tz_convert(idx.tz)
    window = funding[(funding.index > start) & (funding.index <= end)]
    if window.empty:
        return 0.0, False
    rate_sum = float(pd.to_numeric(window["funding_rate"], errors="coerce").fillna(0.0).sum())
    signed = rate_sum if str(side).upper() == "BUY" else -rate_sum
    return signed / float(sl_frac), True


@dataclass(frozen=True)
class ClosedTrade:
    strategy: str
    symbol: str
    side: str
    entry_time: Any
    exit_time: Any
    entry: float
    exit: float
    initial_sl: float
    initial_tp: float
    gross_r: float
    net_r: float
    net_r_funding: float
    funding_r: float
    funding_covered: bool
    sl_frac: float
    exit_reason: str
    regime: str
    bars_held: int
    exit_tf: str


@dataclass(frozen=True)
class TradeStats:
    n: int
    n_wins: int
    n_losses: int
    n_eod: int
    n_funding: int
    hit_rate: Optional[float]
    avg_gross_r: Optional[float]
    avg_net_r: Optional[float]
    sum_net_r: Optional[float]
    avg_net_r_funding: Optional[float]
    profit_factor: Optional[float]
    max_dd_r: Optional[float]
    max_tuw_days: Optional[float]


def _mean(values: Sequence[float]) -> Optional[float]:
    if not values:
        return None
    return float(sum(values) / len(values))


def max_drawdown_r(net_rs: Sequence[float]) -> float:
    """Peak-to-trough of a cumulative net-R curve. Trades must already be ordered."""
    equity = 0.0
    peak = 0.0
    worst = 0.0
    for value in net_rs:
        equity += float(value)
        if equity > peak:
            peak = equity
        worst = max(worst, peak - equity)
    return float(worst)


def max_time_under_water_days(trades: Sequence[ClosedTrade]) -> Optional[float]:
    """Longest stretch, in days, from an equity peak until net R makes a new high."""
    ordered = sorted(trades, key=lambda t: pd.Timestamp(t.exit_time))
    if not ordered:
        return None
    equity = 0.0
    peak = 0.0
    peak_time = pd.Timestamp(ordered[0].entry_time)
    underwater_since: Optional[pd.Timestamp] = None
    longest = 0.0
    for trade in ordered:
        equity += float(trade.net_r)
        exit_ts = pd.Timestamp(trade.exit_time)
        if equity >= peak - 1e-12:
            if underwater_since is not None:
                longest = max(longest, (exit_ts - underwater_since).total_seconds() / 86400.0)
                underwater_since = None
            peak = equity
            peak_time = exit_ts
        elif underwater_since is None:
            underwater_since = peak_time
    if underwater_since is not None:
        last = pd.Timestamp(ordered[-1].exit_time)
        longest = max(longest, (last - underwater_since).total_seconds() / 86400.0)
    return float(longest)


def summarize_trades(trades: Sequence[ClosedTrade]) -> TradeStats:
    ordered = sorted(trades, key=lambda t: pd.Timestamp(t.exit_time))
    n = len(ordered)
    if n == 0:
        return TradeStats(
            n=0,
            n_wins=0,
            n_losses=0,
            n_eod=0,
            n_funding=0,
            hit_rate=None,
            avg_gross_r=None,
            avg_net_r=None,
            sum_net_r=None,
            avg_net_r_funding=None,
            profit_factor=None,
            max_dd_r=None,
            max_tuw_days=None,
        )
    nets = [float(t.net_r) for t in ordered]
    gross = [float(t.gross_r) for t in ordered]
    nets_f = [float(t.net_r_funding) for t in ordered]
    wins = [v for v in nets if v > 0]
    losses = [v for v in nets if v < 0]
    profit_factor: Optional[float]
    if not losses:
        profit_factor = None
    else:
        profit_factor = sum(wins) / abs(sum(losses)) if wins else 0.0
    return TradeStats(
        n=n,
        n_wins=len(wins),
        n_losses=len(losses),
        n_eod=sum(1 for t in ordered if t.exit_reason == "eod"),
        n_funding=sum(1 for t in ordered if t.funding_covered),
        hit_rate=len(wins) / n,
        avg_gross_r=_mean(gross),
        avg_net_r=_mean(nets),
        sum_net_r=float(sum(nets)),
        avg_net_r_funding=_mean(nets_f),
        profit_factor=profit_factor,
        max_dd_r=max_drawdown_r(nets),
        max_tuw_days=max_time_under_water_days(ordered),
    )


def sample_size_note(n: int) -> str:
    """Honest reading of n against the audit minimum (200 trades)."""
    if n <= 0:
        return "No closed trades. Expectancy is unknown."
    if n < 30:
        return (
            f"n={n} is too small to estimate expectancy. "
            "The audit minimum is 200 closed trades; this window cannot support a hit-rate claim."
        )
    if n < 200:
        return (
            f"n={n} is below the audit minimum of 200. "
            "A confidence interval on mean R at this size still includes zero even when the point estimate does not."
        )
    return (
        f"n={n} meets the audit minimum of 200. "
        "This is still one frozen-parameter window, not a refit walk-forward."
    )


def group_stats(trades: Sequence[ClosedTrade], key_fn: Callable[[ClosedTrade], str]) -> List[Tuple[str, TradeStats]]:
    buckets: Dict[str, List[ClosedTrade]] = {}
    for trade in trades:
        buckets.setdefault(str(key_fn(trade)), []).append(trade)
    rows = [(key, summarize_trades(rows_)) for key, rows_ in buckets.items()]
    rows.sort(key=lambda item: (-item[1].n, item[0]))
    return rows


def chronological_holdout(
    trades: Sequence[ClosedTrade],
    *,
    span_start: Any,
    span_end: Any,
    test_frac: float = 1.0 / 3.0,
) -> Tuple[TradeStats, TradeStats, Any]:
    """
    Freeze params. Last ``test_frac`` of the calendar span is the holdout.

    This is not a refit walk-forward: nothing is optimized on the first slice.
    """
    start = pd.Timestamp(span_start)
    end = pd.Timestamp(span_end)
    if end <= start:
        cut = start
    else:
        cut = start + (end - start) * (1.0 - float(test_frac))
    earlier = [t for t in trades if pd.Timestamp(t.entry_time) < cut]
    later = [t for t in trades if pd.Timestamp(t.entry_time) >= cut]
    return summarize_trades(earlier), summarize_trades(later), cut
