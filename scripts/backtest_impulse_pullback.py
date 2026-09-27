"""
PROXY compare: cascade baseline A (rocket / waterfall) vs impulse pullback E.

Does not enable the live plan. Reads data/ohlcv_proxy (Binance USDT-M).

    python3 scripts/backtest_impulse_pullback.py
    python3 -m app.core.proxy_ohlcv --symbols BTC ETH SOL BNB ARB OP --out data/ohlcv_proxy
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core.causal_backtest import chronological_holdout, summarize_trades
from app.core.strategy_backtest import (
    load_config,
    render_report,
    run_backtest,
    trades_frame,
)

SYMBOLS = ("BTC", "ETH", "SOL", "BNB", "ARB", "OP")
STRATEGIES = ("rocket", "waterfall", "impulse_pullback")
# Nicolas filter used on the cascade threshold draft (PR #30), applied per side.
MIN_N = 40
MIN_HIT = 0.45
MIN_HIT_LIFT = 0.08
MIN_AVG_R = 0.0
MIN_PF = 1.1


def _fmt_pct(value) -> str:
    if value is None:
        return "—"
    return f"{100.0 * float(value):.1f}%"


def _fmt_r(value) -> str:
    if value is None:
        return "—"
    return f"{float(value):.3f}"


def _fmt_pf(stats) -> str:
    if stats.n < 5:
        return "n/a (n<5)"
    if stats.profit_factor is None:
        return "inf"
    return f"{stats.profit_factor:.2f}"


def _chase_pct(trades) -> str:
    vals = [float(t.chase_atr) for t in trades if t.chase_atr is not None]
    if not vals:
        return "—"
    series = pd.Series(vals)
    return f"{100.0 * float((series > 0.35).mean()):.1f}%"


def _side_trades(trades, strategy: str, side: str):
    return [t for t in trades if t.strategy == strategy and t.side == side]


def _passes(stats, base_hit) -> bool:
    if stats.n < MIN_N or stats.hit_rate is None or stats.avg_net_r is None:
        return False
    if stats.hit_rate < MIN_HIT:
        return False
    if base_hit is not None and stats.hit_rate < base_hit + MIN_HIT_LIFT:
        return False
    if stats.avg_net_r < MIN_AVG_R:
        return False
    pf = stats.profit_factor
    if pf is None:
        return stats.n >= 5 and stats.n_losses == 0
    return pf >= MIN_PF


def _comparison(trades) -> str:
    rows = []
    long_base = summarize_trades(_side_trades(trades, "rocket", "BUY"))
    short_base = summarize_trades(_side_trades(trades, "waterfall", "SELL"))
    long_e = summarize_trades(_side_trades(trades, "impulse_pullback", "BUY"))
    short_e = summarize_trades(_side_trades(trades, "impulse_pullback", "SELL"))
    specs = (
        ("A", "rocket", "long", long_base, _side_trades(trades, "rocket", "BUY"), None),
        ("A", "waterfall", "short", short_base, _side_trades(trades, "waterfall", "SELL"), None),
        ("E", "impulse_pullback", "long", long_e, _side_trades(trades, "impulse_pullback", "BUY"), long_base.hit_rate),
        ("E", "impulse_pullback", "short", short_e, _side_trades(trades, "impulse_pullback", "SELL"), short_base.hit_rate),
    )
    lines = [
        "## A vs E (PROXY)",
        "",
        "A = rocket (long) and waterfall (short) on `main` params, 5m decision clock, 15m regime gate.",
        "E = `impulse_pullback` (enabled stays false in live JSON), 1m decision clock, no 15m regime gate.",
        "Same cost model as the proxy harness: HL taker 4.50 bp/side + 1 bp slip, Binance prices.",
        "",
        "| variante | plan | side | n | hit rate | avg net R | PF | max DD (R) | % chase>0.35 |",
        "|---|---|---|---:|---:|---:|---:|---:|---:|",
    ]
    verdicts = {}
    for label, name, side, stats, bucket, base_hit in specs:
        lines.append(
            f"| {label} | {name} | {side} | {stats.n} | {_fmt_pct(stats.hit_rate)} | "
            f"{_fmt_r(stats.avg_net_r)} | {_fmt_pf(stats)} | {_fmt_r(stats.max_dd_r)} | {_chase_pct(bucket)} |"
        )
        if label == "E":
            verdicts[side] = _passes(stats, base_hit)
            rows.append(
                {
                    "variant": label,
                    "strategy": name,
                    "side": side,
                    "n": stats.n,
                    "hit_rate": stats.hit_rate,
                    "avg_net_r": stats.avg_net_r,
                    "profit_factor": stats.profit_factor,
                    "max_dd_r": stats.max_dd_r,
                    "passes_filter": verdicts[side],
                }
            )
        else:
            rows.append(
                {
                    "variant": label,
                    "strategy": name,
                    "side": side,
                    "n": stats.n,
                    "hit_rate": stats.hit_rate,
                    "avg_net_r": stats.avg_net_r,
                    "profit_factor": stats.profit_factor,
                    "max_dd_r": stats.max_dd_r,
                    "passes_filter": "",
                }
            )
    lines.append("")
    lines.append(
        f"Filtre (les deux côtés): n ≥ {MIN_N}, hit ≥ {100 * MIN_HIT:.0f}% et "
        f"+{100 * MIN_HIT_LIFT:.0f} pts vs la baseline du même côté, avg net R ≥ 0, PF ≥ {MIN_PF}."
    )
    both = bool(verdicts.get("long") and verdicts.get("short"))
    lines.append("")
    if both:
        lines.append("**Verdict: le filtre passe sur le long et le short.** Merge seulement si Nicolas confirme.")
    else:
        failed = [side for side, ok in verdicts.items() if not ok]
        lines.append(
            "**Verdict: NON, ne pas merger.** Le filtre ne passe pas sur: "
            + ", ".join(failed or ["long", "short"])
            + ". Live `impulse_pullback` reste `enabled: false`."
        )
    lines.append("")
    lines.append("Holdout (dernier tiers du calendrier, pas de refit):")
    for strategy, side_name, side in (
        ("rocket", "long", "BUY"),
        ("waterfall", "short", "SELL"),
        ("impulse_pullback", "long", "BUY"),
        ("impulse_pullback", "short", "SELL"),
    ):
        bucket = _side_trades(trades, strategy, side)
        if len(bucket) < 2:
            lines.append(f"- {strategy} {side_name}: n={len(bucket)}")
            continue
        start = min(pd.Timestamp(t.entry_time) for t in bucket)
        end = max(pd.Timestamp(t.entry_time) for t in bucket)
        _train, hold, _cut = chronological_holdout(bucket, span_start=start, span_end=end)
        lines.append(
            f"- {strategy} {side_name}: holdout n={hold.n}, hit {_fmt_pct(hold.hit_rate)}, "
            f"avg net R {_fmt_r(hold.avg_net_r)}"
        )
    lines.append("")
    return "\n".join(lines), pd.DataFrame(rows)


def main() -> None:
    config_path = ROOT / "data" / "config" / "strategies.json"
    config = load_config(config_path)
    cache = ROOT / "data" / "ohlcv_proxy"
    out = ROOT / "reports" / "strategy_backtest_impulse_pullback.md"
    trades_path = ROOT / "reports" / "strategy_backtest_impulse_pullback_trades.csv"
    summary_path = ROOT / "reports" / "strategy_backtest_impulse_pullback.csv"
    reports = run_backtest(
        symbols=list(SYMBOLS),
        strategies=list(STRATEGIES),
        config=config,
        cache_dir=cache,
        fetch=False,
        days=None,
        context_bars=300,
        trigger_bars=120,
        taker=0.00045,
        slip=0.0001,
        verbose=True,
    )
    body = render_report(
        reports,
        symbols=list(SYMBOLS),
        config_path=str(config_path),
        taker=0.00045,
        slip=0.0001,
        note=(
            "LABEL: PROXY. Compare A (rocket/waterfall, live baseline) vs E "
            "(impulse_pullback, off in strategies.json). Universe BTC ETH SOL BNB ARB OP."
        ),
        source="proxy",
    )
    trades = [trade for report in reports for trade in report.trades]
    comparison, summary = _comparison(trades)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(comparison + "\n" + body)
    frame = trades_frame(trades)
    frame.to_csv(trades_path, index=False)
    summary.to_csv(summary_path, index=False)
    print(comparison)
    print(f"[bt] wrote {out}")
    print(f"[bt] wrote {trades_path}")
    print(f"[bt] wrote {summary_path}")


if __name__ == "__main__":
    main()
