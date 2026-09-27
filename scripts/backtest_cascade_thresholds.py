"""PROXY comparison of rocket/waterfall threshold variants.

Reads the Binance USDT-M cache in ``data/ohlcv_proxy``. Does not call
Hyperliquid. Live ``strategies.json`` is not modified: overlays exist only
inside this process.

    python scripts/backtest_cascade_thresholds.py
    python scripts/backtest_cascade_thresholds.py --symbols BTC --variants A
"""
from __future__ import annotations

import argparse
import copy
import sys
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence

# `python scripts/backtest_cascade_thresholds.py` does not put the repo root on path.
_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import numpy as np
import pandas as pd

from app.core.causal_backtest import ClosedTrade, chronological_holdout, summarize_trades
from app.core.hl_ohlcv import SCANNER_WHITELIST, ensure_symbol_cache
from app.core.strategy_backtest import (
    SPECS,
    build_adx_series,
    build_decisions,
    build_regime_table,
    load_config,
    make_strategy,
    regime_threshold,
    replay_symbol,
    warmup_bars,
)
from strategies.cascade_rider import detect_bear_cascade, detect_bull_cascade, ensure_cascade_emas

# Same knobs on rocket and waterfall. Defaults in strategies.json stay at A.
VARIANT_B = {
    "max_1m_chase_atr": 0.35,
    "reject_bb_extreme_at_fill": True,
    "reject_fill_extension": True,
}
VARIANT_C = {
    **VARIANT_B,
    "require_1m_new_extreme": False,
    "scan_interval_minutes": 1,
    "scan_interval_active_minutes": 1,
}
VARIANT_D = {
    **VARIANT_B,
    "early_break_enabled": True,
    "early_break_lookback": 16,
}

VARIANTS = (
    {
        "id": "A",
        "label": "A baseline",
        "step": "5m",
        "overlay": {},
        "rule": (
            "Params `main` : pas de cap de chase, extension seulement sur le close 15m, "
            "1m exige un nouveau HH (rocket) ou LL (waterfall), horloge 5m, lane early-break off."
        ),
    },
    {
        "id": "B",
        "label": "B reject chase",
        "step": "5m",
        "overlay": VARIANT_B,
        "rule": (
            "Même horloge 5m et même trigger HH/LL. Rejette le fill s'il est à plus de 0,35 ATR "
            "au-delà du close 15m confirmé, s'il dépasse `max_extension_atr` depuis l'EMA9, "
            "ou s'il est ABOVE_UPPER (long) / BELOW_LOWER (short) sur la Bollinger 20/2 des bougies fermées. "
            "Un pullback (chase négatif) reste accepté. Pas d'entrée plus tôt."
        ),
    },
    {
        "id": "C",
        "label": "C faster fill",
        "step": "1m",
        "overlay": VARIANT_C,
        "rule": (
            "B, plus un fill plus tôt : horloge 1m (scan armé serré à 1 min ; le scan de base passe aussi à 1 min "
            "dans l'overlay) et bougie 1m dans le sens sans nouveau HH/LL. "
            "Les minutes sans cascade 15m confirmée ne sont pas visitées (la lane early-break est off) ; "
            "la sortie, elle, marche quand même toutes les bougies 1m jusqu'au prochain passage."
        ),
    },
    {
        "id": "D",
        "label": "D early break",
        "step": "5m",
        "overlay": VARIANT_D,
        "rule": (
            "B, plus une lane early-break en plus de la cascade (horloge 5m). "
            "La cascade confirmée reste prioritaire. La lane ne s'ouvre que si le détecteur cascade est off."
        ),
    },
)

MIN_N = 40
HIT_LIFT = 0.08
MIN_HIT = 0.45
MIN_PF = 1.1


def _apply_overlay(config: Mapping[str, Any], overlay: Mapping[str, Any]) -> dict:
    out = copy.deepcopy(dict(config))
    for name in ("rocket", "waterfall"):
        block = out.setdefault(name, {})
        params = dict(block.get("params") or {})
        params.update(overlay)
        block["params"] = params
        out[name] = block
    return out


def cascade_active_1m_decisions(
    frames: Mapping[str, pd.DataFrame],
    spec,
    strategy,
    detect_fn,
    *,
    context_bars: int,
) -> pd.DatetimeIndex:
    """1m timestamps whose confirmed 15m bar is an active cascade.

    Variant C does not arm the early-break lane, so a minute with no cascade
    cannot fill. Exit walks still run up to the next visited timestamp.
    """
    df_15m = frames.get("15m")
    full = build_decisions(frames, spec, warmup_bars(spec.name, strategy), step="1m")
    if df_15m is None or getattr(df_15m, "empty", True) or len(full) == 0:
        return full
    flags = np.zeros(len(df_15m), dtype=bool)
    start_i = 50
    for i in range(start_i, len(df_15m)):
        window = df_15m.iloc[max(0, i + 1 - int(context_bars)) : i + 1]
        if len(window) < 50:
            continue
        active, _ = detect_fn(ensure_cascade_emas(window), use_live=False)
        flags[i] = bool(active)
    pos = df_15m.index.searchsorted(full, side="right") - 1
    keep = np.zeros(len(full), dtype=bool)
    valid = pos >= 0
    keep[valid] = flags[pos[valid]]
    return pd.DatetimeIndex(full[keep])


def _replay_symbol(payload: Mapping[str, Any]) -> Dict[str, Any]:
    symbol = str(payload["symbol"])
    cache_dir = Path(payload["cache_dir"])
    frames = ensure_symbol_cache(
        symbol,
        ("15m", "1m"),
        cache_dir,
        fetch=False,
    )
    missing = [
        tf
        for tf in ("15m", "1m")
        if frames.get(tf) is None or getattr(frames.get(tf), "empty", True)
    ]
    if missing:
        return {"symbol": symbol, "error": f"missing {', '.join(missing)}", "rows": []}
    regime_table = build_regime_table(frames["15m"], float(payload["threshold"]))
    primary_adx = build_adx_series(frames["15m"])
    rows: List[Dict[str, Any]] = []
    for variant in payload["variants"]:
        config = variant["config"]
        for name in ("rocket", "waterfall"):
            spec = SPECS[name]
            strategy = make_strategy(name, config)
            decisions = None
            params = (config.get(name) or {}).get("params") or {}
            # C steps every 1m but cannot fill without a live cascade. Skip the rest.
            if variant["step"] == "1m" and not bool(params.get("early_break_enabled")):
                detect_fn = detect_bull_cascade if name == "rocket" else detect_bear_cascade
                decisions = cascade_active_1m_decisions(
                    frames,
                    spec,
                    strategy,
                    detect_fn,
                    context_bars=int(payload["context_bars"]),
                )
            trades, diag, span_start, span_end = replay_symbol(
                strategy,
                spec,
                symbol,
                frames,
                config,
                funding=frames.get("funding"),
                regime_table=regime_table,
                bb_table=None,
                primary_adx=primary_adx,
                context_bars=int(payload["context_bars"]),
                trigger_bars=int(payload["trigger_bars"]),
                taker=float(payload["taker"]),
                slip=float(payload["slip"]),
                verbose=False,
                decision_step=variant["step"],
                decisions=decisions,
            )
            rows.append(
                {
                    "variant": variant["id"],
                    "strategy": name,
                    "symbol": symbol,
                    "trades": trades,
                    "diag": diag,
                    "span_start": span_start,
                    "span_end": span_end,
                }
            )
    return {"symbol": symbol, "error": "", "rows": rows}


def _pct_chase(trades: Sequence[ClosedTrade], cap: float = 0.35) -> Optional[float]:
    chase = [float(trade.chase_atr) for trade in trades if trade.chase_atr is not None]
    if not chase:
        return None
    return sum(1 for value in chase if value > cap) / len(chase)


def _median_chase(trades: Sequence[ClosedTrade]) -> Optional[float]:
    chase = [float(trade.chase_atr) for trade in trades if trade.chase_atr is not None]
    if not chase:
        return None
    return float(pd.Series(chase).median())


def _lane_counts(trades: Sequence[ClosedTrade]) -> str:
    counts: Dict[str, int] = {}
    for trade in trades:
        key = str(trade.entry_lane or "cascade")
        counts[key] = counts.get(key, 0) + 1
    if not counts:
        return "—"
    return ", ".join(f"{key}={counts[key]}" for key in sorted(counts))


def _row(variant: str, strategy: str, trades: Sequence[ClosedTrade]) -> Dict[str, Any]:
    stats = summarize_trades(trades)
    return {
        "variant": variant,
        "strategy": strategy,
        "n": stats.n,
        "hit_rate": stats.hit_rate,
        "avg_gross_r": stats.avg_gross_r,
        "avg_net_r": stats.avg_net_r,
        "sum_net_r": stats.sum_net_r,
        "profit_factor": stats.profit_factor,
        "max_dd_r": stats.max_dd_r,
        "pct_chase_gt_035": _pct_chase(trades),
        "median_chase_atr": _median_chase(trades),
        "lanes": _lane_counts(trades),
    }


def _fmt_pct(value: Optional[float]) -> str:
    if value is None:
        return "—"
    return f"{100.0 * value:.1f}%"


def _fmt_r(value: Optional[float]) -> str:
    if value is None:
        return "—"
    return f"{value:.3f}"


def _fmt_pf(n: int, value: Optional[float]) -> str:
    if n < 5:
        return "n/a (n<5)"
    if value is None:
        return "inf"
    return f"{value:.2f}"


def _gate(row: Mapping[str, Any], baseline_hit: Optional[float]) -> tuple[bool, str]:
    """Nicolas: hit rate nettement mieux, et avg net R / PF pas pourris."""
    reasons: List[str] = []
    n = int(row["n"])
    if n < MIN_N:
        reasons.append(f"n={n} < {MIN_N} (pas concluant)")
    hit = row["hit_rate"]
    base = baseline_hit if baseline_hit is not None else 0.0
    if hit is None or hit < base + HIT_LIFT or hit < MIN_HIT:
        base_txt = "—" if baseline_hit is None else f"{100.0 * baseline_hit:.1f}%"
        hit_txt = "—" if hit is None else f"{100.0 * hit:.1f}%"
        reasons.append(
            f"hit {hit_txt} (seuil ≥ max({100.0 * MIN_HIT:.0f}%, baseline {base_txt} + {100.0 * HIT_LIFT:.0f} pts))"
        )
    avg = row["avg_net_r"]
    if avg is None or avg < 0:
        reasons.append(f"avg net R {_fmt_r(avg)} < 0")
    pf = row["profit_factor"]
    if n < 5:
        reasons.append("PF non mesurable")
    elif pf is not None and pf < MIN_PF:
        reasons.append(f"PF {_fmt_pf(n, pf)} < {MIN_PF:.1f}")
    if reasons:
        return False, "; ".join(reasons)
    return True, "passe le filtre chiffré"


def _markdown(
    *,
    rows: Sequence[Mapping[str, Any]],
    diags: Mapping[str, Mapping[str, int]],
    holdouts: Mapping[str, str],
    symbols: Sequence[str],
    errors: Sequence[str],
    selected: Sequence[str],
) -> str:
    by_key = {(row["variant"], row["strategy"]): row for row in rows}
    shown = [variant for variant in VARIANTS if variant["id"] in selected]
    lines = [
        "# PROXY — seuils cascade rocket / waterfall",
        "",
        "LABEL: PROXY. Prix Binance USDT-M (`data.binance.vision`), pas Hyperliquid. "
        "Ne pas lire ces fills comme des fills HL.",
        "",
        "Fenêtre et univers : cache `data/ohlcv_proxy` reconstruit le 2026-09-27, whitelist scanner, "
        "2026-03-01 → 2026-09-26. Le rapport proxy précédent s'arrêtait au 25 septembre "
        "(le fichier du 26 était en 404). Ici le 26 est présent, 0 trou 1m/15m. "
        "Coûts : taker HL 4,50 bp/côté + slip 1 bp, via `net_r`. Funding Binance 8h quand le cache couvre le hold. "
        "IA non rejouée. Un signal qui passe la géométrie et `check_hard_veto` est pris. "
        "Livres indépendants (pas de top-K scanner, pas de `max_positions`).",
        "",
        "Les params live (`data/config/strategies.json`) restent la baseline A. "
        "B/C/D sont des overlays de ce script. Trend LT, Range LT, SuperTrend, spark et ember ne sont pas rejoués.",
        "",
        f"Symboles : {', '.join(symbols)}.",
        "",
        "## Règles",
        "",
    ]
    for variant in shown:
        lines.append(f"- **{variant['label']}** — décision `{variant['step']}`. {variant['rule']}")
    lines.extend(
        [
            "",
            "### Lane D — early break (documentée)",
            "",
            "Bougie signal = dernière bougie 15m fermée (`iloc[-2]`). "
            "Base = les `early_break_lookback` bougies fermées juste avant (défaut 16, soit 4 h).",
            "",
            "- Long : close > plus haut de la base, bougie verte, close > EMA9.",
            "- Short : close < plus bas de la base, bougie rouge, close < EMA9.",
            "- Pas de stack EMA9 > EMA20, pas de double bougie, pas de HH/LL contre la bougie précédente. "
            "Le break de la base est l'événement de structure.",
            "- La lane ne remplace pas la cascade : si `detect_bull_cascade` / `detect_bear_cascade` est vrai, "
            "le chemin cascade (HH/LL 1m inclus) gagne.",
            "- Filtres anti-extension, tous actifs sur D : extension du close 15m ≤ `max_extension_atr` (1,5), "
            "extension du fill 1m vs EMA9 ≤ le même cap, chase du fill ≤ 0,35 ATR, "
            "fill pas au-delà de la Bollinger 20/2 (ABOVE_UPPER / BELOW_LOWER).",
            "- Le 1m de cette lane est seulement dans le sens (vert / rouge), sans nouveau HH/LL.",
            "- Volume, RSI, wick trap et le clear-through d'un plus haut/bas plus ancien (`struct_lookback` 96, "
            "`breakout_clear_pct` 0,6) restent en place. Le régime moteur `type: trend` aussi : "
            "un break en RANGE pur n'est pas évalué.",
            "",
            "## Filtre Nicolas (merge)",
            "",
            "Un overlay ne se merge que si **rocket et waterfall** passent tous les deux :",
            "",
            f"- n ≥ {MIN_N} (en dessous le signe n'est pas concluant sur cette fenêtre ; n ≥ 200 reste hors d'atteinte du baseline)",
            f"- hit rate ≥ {100.0 * MIN_HIT:.0f}% et au moins +{100.0 * HIT_LIFT:.0f} points vs la baseline de la même stratégie",
            "- avg net R ≥ 0",
            f"- profit factor ≥ {MIN_PF:.1f}",
            "",
            "Hit rate « nettement mieux » sans R/PF tenable ne passe pas. "
            "Un seul des deux plans au-dessus du filtre ne suffit pas : les knobs sont partagés.",
            "",
            "## Résultats",
            "",
            "| variante | stratégie | n | hit rate | avg net R | PF | max DD (R) | % chase>0.35 | chase médian | lanes |",
            "|---|---|---:|---:|---:|---:|---:|---:|---:|---|",
        ]
    )
    for variant in shown:
        for name in ("rocket", "waterfall"):
            row = by_key[(variant["id"], name)]
            lines.append(
                f"| {variant['id']} | {name} | {row['n']} | {_fmt_pct(row['hit_rate'])} | "
                f"{_fmt_r(row['avg_net_r'])} | {_fmt_pf(row['n'], row['profit_factor'])} | "
                f"{_fmt_r(row['max_dd_r'])} | {_fmt_pct(row['pct_chase_gt_035'])} | "
                f"{_fmt_r(row['median_chase_atr'])} | {row['lanes']} |"
            )
    lines.extend(["", "## Verdict", ""])
    any_merge = False
    for variant in shown:
        if variant["id"] == "A":
            lines.append("- **A** — baseline de comparaison, pas un candidat de merge.")
            continue
        passed = []
        failed = []
        for name in ("rocket", "waterfall"):
            base_row = by_key.get(("A", name))
            base = None if base_row is None else base_row["hit_rate"]
            ok, why = _gate(by_key[(variant["id"], name)], base)
            if ok:
                passed.append(name)
            else:
                failed.append(f"{name}: {why}")
        if len(passed) == 2:
            any_merge = True
            lines.append(
                f"- **{variant['id']} — OUI, candidat merge** (les deux plans passent le filtre). "
                + " ".join(holdouts.get(f"{variant['id']}:{name}", "") for name in ("rocket", "waterfall"))
            )
        else:
            lines.append(
                f"- **{variant['id']} — NON, ne pas merger.** " + " | ".join(failed)
            )
    lines.append("")
    if any_merge:
        lines.append(
            "Recommandation : merger uniquement la variante marquée OUI, en draft tant que le holdout "
            "ci-dessous n'est pas du même signe. Ce rapport ne merge rien."
        )
    else:
        lines.append(
            "**Recommandation : ne pas merger de nouveaux seuils.** "
            "Aucune variante n'a à la fois un winrate nettement meilleur et un avg net R / PF tenables "
            "sur rocket et waterfall. La détection cascade reste celle de `main`."
        )
    lines.extend(["", "## Holdout (dernier tiers calendaire, pas un walk-forward)", ""])
    for variant in shown:
        for name in ("rocket", "waterfall"):
            key = f"{variant['id']}:{name}"
            lines.append(f"- {variant['id']} {name}: {holdouts.get(key, '—')}")
    lines.extend(["", "## Diagnostics (décisions du replay)", ""])
    for variant in shown:
        for name in ("rocket", "waterfall"):
            diag = diags.get(f"{variant['id']}:{name}") or {}
            lines.append(
                f"- {variant['id']} {name}: decisions={diag.get('decisions', 0)}, "
                f"signals={diag.get('signals', 0)}, hard_veto={diag.get('hard_veto', 0)}, "
                f"regime_skips={diag.get('regime_skips', 0)}, errors={diag.get('errors', 0)}"
            )
    if errors:
        lines.extend(["", "## Trous", ""])
        lines.extend(f"- {err}" for err in errors)
    lines.extend(
        [
            "",
            "## Ce que ça ne dit pas",
            "",
            "Un hit rate plus haut sur n < 200 n'est pas un edge HL. "
            "Le max DD est en R (1R par trade à la clôture), pas en % d'équity. "
            "Le spread Binance n'est pas celui d'Hyperliquid.",
            "",
        ]
    )
    return "\n".join(lines)


def main(argv: Optional[Sequence[str]] = None) -> None:
    parser = argparse.ArgumentParser(description="PROXY cascade threshold comparison (no HL fetch)")
    parser.add_argument("--symbols", nargs="+", default=list(SCANNER_WHITELIST))
    parser.add_argument("--variants", nargs="+", default=["A", "B", "C", "D"])
    parser.add_argument("--config", default="data/config/strategies.json")
    parser.add_argument("--cache-dir", default="data/ohlcv_proxy")
    parser.add_argument("--out", default="reports/strategy_backtest_cascades_thresholds.md")
    parser.add_argument("--csv", default="reports/strategy_backtest_cascades_thresholds.csv")
    parser.add_argument("--trades-out", default="reports/strategy_backtest_cascades_thresholds_trades.csv")
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--context-bars", type=int, default=300)
    parser.add_argument("--trigger-bars", type=int, default=120)
    parser.add_argument("--taker", type=float, default=0.00045)
    parser.add_argument("--slip", type=float, default=0.0001)
    args = parser.parse_args(argv)

    selected = [item.upper() for item in args.variants]
    unknown = [item for item in selected if item not in {v["id"] for v in VARIANTS}]
    if unknown:
        raise SystemExit(f"unknown variants: {unknown}")
    config = load_config(Path(args.config))
    threshold = regime_threshold(config)
    variants = []
    for variant in VARIANTS:
        if variant["id"] not in selected:
            continue
        variants.append(
            {
                "id": variant["id"],
                "step": variant["step"],
                "config": _apply_overlay(config, variant["overlay"]),
            }
        )
    symbols = [s.upper() for s in args.symbols]
    payloads = [
        {
            "symbol": symbol,
            "cache_dir": args.cache_dir,
            "variants": variants,
            "threshold": threshold,
            "context_bars": args.context_bars,
            "trigger_bars": args.trigger_bars,
            "taker": args.taker,
            "slip": args.slip,
        }
        for symbol in symbols
    ]
    grouped: Dict[tuple, List[ClosedTrade]] = {}
    diags: Dict[str, Dict[str, int]] = {}
    spans: Dict[str, Dict[str, Any]] = {}
    errors: List[str] = []
    workers = max(1, int(args.workers))
    print(f"[thresholds] PROXY {len(symbols)} symbols, variants={selected}, workers={workers}")
    if workers == 1:
        results = [_replay_symbol(payload) for payload in payloads]
    else:
        results = []
        with ProcessPoolExecutor(max_workers=workers) as pool:
            futures = {pool.submit(_replay_symbol, payload): payload["symbol"] for payload in payloads}
            for future in as_completed(futures):
                symbol = futures[future]
                try:
                    results.append(future.result())
                    print(f"[thresholds] done {symbol}", flush=True)
                except Exception as exc:
                    errors.append(f"{symbol}: {exc}")
                    print(f"[thresholds] FAIL {symbol}: {exc}")
    for result in results:
        if result.get("error"):
            errors.append(f"{result['symbol']}: {result['error']}")
            continue
        for row in result["rows"]:
            key = (row["variant"], row["strategy"])
            grouped.setdefault(key, []).extend(row["trades"])
            bucket = diags.setdefault(f"{row['variant']}:{row['strategy']}", {})
            for name, value in (row["diag"] or {}).items():
                bucket[name] = int(bucket.get(name, 0)) + int(value)
            span = spans.setdefault(f"{row['variant']}:{row['strategy']}", {})
            start, end = row["span_start"], row["span_end"]
            if start is not None and (span.get("start") is None or start < span["start"]):
                span["start"] = start
            if end is not None and (span.get("end") is None or end > span["end"]):
                span["end"] = end

    summary_rows = []
    holdouts: Dict[str, str] = {}
    for variant in VARIANTS:
        if variant["id"] not in selected:
            continue
        for name in ("rocket", "waterfall"):
            trades = grouped.get((variant["id"], name), [])
            summary_rows.append(_row(variant["id"], name, trades))
            span = spans.get(f"{variant['id']}:{name}") or {}
            if trades and span.get("start") is not None and span.get("end") is not None:
                earlier, later, cut = chronological_holdout(
                    trades, span_start=span["start"], span_end=span["end"]
                )
                holdouts[f"{variant['id']}:{name}"] = (
                    f"cut {pd.Timestamp(cut).isoformat()} — "
                    f"earlier n={earlier.n} hit={_fmt_pct(earlier.hit_rate)} avg={_fmt_r(earlier.avg_net_r)} "
                    f"PF={_fmt_pf(earlier.n, earlier.profit_factor)}; "
                    f"holdout n={later.n} hit={_fmt_pct(later.hit_rate)} avg={_fmt_r(later.avg_net_r)} "
                    f"PF={_fmt_pf(later.n, later.profit_factor)}"
                )
            else:
                holdouts[f"{variant['id']}:{name}"] = "pas de trades"

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    text = _markdown(
        rows=summary_rows,
        diags=diags,
        holdouts=holdouts,
        symbols=symbols,
        errors=errors,
        selected=selected,
    )
    out.write_text(text)
    csv_path = Path(args.csv)
    pd.DataFrame(summary_rows).to_csv(csv_path, index=False)
    trade_rows = []
    for (variant, strategy), trades in grouped.items():
        for trade in trades:
            trade_rows.append(
                {
                    "variant": variant,
                    "strategy": trade.strategy,
                    "symbol": trade.symbol,
                    "side": trade.side,
                    "entry_time": pd.Timestamp(trade.entry_time).isoformat(),
                    "exit_time": pd.Timestamp(trade.exit_time).isoformat(),
                    "entry": trade.entry,
                    "exit": trade.exit,
                    "net_r": trade.net_r,
                    "gross_r": trade.gross_r,
                    "exit_reason": trade.exit_reason,
                    "regime": trade.regime,
                    "chase_atr": trade.chase_atr,
                    "entry_delay_min": trade.entry_delay_min,
                    "entry_lane": trade.entry_lane,
                }
            )
    trades_path = Path(args.trades_out)
    pd.DataFrame(trade_rows).to_csv(trades_path, index=False)
    print(text)
    print(f"[thresholds] wrote {out} {csv_path} {trades_path}")


if __name__ == "__main__":
    main()
