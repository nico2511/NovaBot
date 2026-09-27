# PROXY — seuils cascade rocket / waterfall — PARTIEL

LABEL: PARTIEL / PROXY. Prix Binance USDT-M (`data.binance.vision`), pas Hyperliquid. Ne pas lire ces fills comme des fills HL.

Fenêtre : cache `data/ohlcv_proxy` reconstruit le 2026-09-27, 2026-03-01 → 2026-09-26. Le rapport proxy précédent (25 coins) s'arrêtait au 25 septembre (le fichier du 26 était en 404). Ici le 26 est présent, 0 trou 1m/15m. Coûts : taker HL 4,50 bp/côté + slip 1 bp, via `net_r`. Funding Binance 8h quand le cache couvre le hold. IA non rejouée. Un signal qui passe la géométrie et `check_hard_veto` est pris. Livres indépendants (pas de top-K scanner, pas de `max_positions`).

Les params live (`data/config/strategies.json`) restent la baseline A. B/C/D sont des overlays de ce script. Trend LT, Range LT, SuperTrend, spark et ember ne sont pas rejoués.

Symboles dans ce tableau (4) : ETH, SOL, BNB, BTC. En attente : ARB, OP.

Univers ciblé, pas les 25 coins de la whitelist. Retenus : **BTC, ETH, SOL, BNB** (grosses caps) et **ARB, OP** (L2 majeurs). STRK, POL, MATIC, MANTA, BLAST ne sont pas dans la whitelist ni dans le cache proxy. Exclus de ce replay : SUI, APT, AVAX, LINK, UNI, AAVE, ADA, NEAR, INJ, TIA, DOT, ATOM, LTC, BCH, XRP, TRX, HYPE, DOGE, ZEC.

## Règles

- **A baseline** — décision `5m`. Params `main` : pas de cap de chase, extension seulement sur le close 15m, 1m exige un nouveau HH (rocket) ou LL (waterfall), horloge 5m, lane early-break off.
- **B reject chase** — décision `5m`. Même horloge 5m et même trigger HH/LL. Rejette le fill s'il est à plus de 0,35 ATR au-delà du close 15m confirmé, s'il dépasse `max_extension_atr` depuis l'EMA9, ou s'il est ABOVE_UPPER (long) / BELOW_LOWER (short) sur la Bollinger 20/2 des bougies fermées. Un pullback (chase négatif) reste accepté. Pas d'entrée plus tôt.
- **C faster fill** — décision `1m`. B, plus un fill plus tôt : horloge 1m (scan armé serré à 1 min ; le scan de base passe aussi à 1 min dans l'overlay) et bougie 1m dans le sens sans nouveau HH/LL. Les minutes sans cascade 15m confirmée ne sont pas visitées (la lane early-break est off) ; la sortie, elle, marche quand même toutes les bougies 1m jusqu'au prochain passage.
- **D early break** — décision `5m`. B, plus une lane early-break en plus de la cascade (horloge 5m). La cascade confirmée reste prioritaire. La lane ne s'ouvre que si le détecteur cascade est off.

### Lane D — early break (documentée)

Bougie signal = dernière bougie 15m fermée (`iloc[-2]`). Base = les `early_break_lookback` bougies fermées juste avant (défaut 16, soit 4 h).

- Long : close > plus haut de la base, bougie verte, close > EMA9.
- Short : close < plus bas de la base, bougie rouge, close < EMA9.
- Pas de stack EMA9 > EMA20, pas de double bougie, pas de HH/LL contre la bougie précédente. Le break de la base est l'événement de structure.
- La lane ne remplace pas la cascade : si `detect_bull_cascade` / `detect_bear_cascade` est vrai, le chemin cascade (HH/LL 1m inclus) gagne.
- Filtres anti-extension, tous actifs sur D : extension du close 15m ≤ `max_extension_atr` (1,5), extension du fill 1m vs EMA9 ≤ le même cap, chase du fill ≤ 0,35 ATR, fill pas au-delà de la Bollinger 20/2 (ABOVE_UPPER / BELOW_LOWER).
- Le 1m de cette lane est seulement dans le sens (vert / rouge), sans nouveau HH/LL.
- Volume, RSI, wick trap et le clear-through d'un plus haut/bas plus ancien (`struct_lookback` 96, `breakout_clear_pct` 0,6) restent en place. Le régime moteur `type: trend` aussi : un break en RANGE pur n'est pas évalué.

## Filtre Nicolas (merge)

Un overlay ne se merge que si **rocket et waterfall** passent tous les deux :

- n ≥ 40 (en dessous le signe n'est pas concluant sur cette fenêtre ; n ≥ 200 reste hors d'atteinte du baseline)
- hit rate ≥ 45% et au moins +8 points vs la baseline de la même stratégie
- avg net R ≥ 0
- profit factor ≥ 1.1

Hit rate « nettement mieux » sans R/PF tenable ne passe pas. Un seul des deux plans au-dessus du filtre ne suffit pas : les knobs sont partagés.

## Résultats

| variante | stratégie | n | hit rate | avg net R | PF | max DD (R) | % chase>0.35 | chase médian | lanes |
|---|---|---:|---:|---:|---:|---:|---:|---:|---|
| A | rocket | 13 | 23.1% | -0.154 | 0.58 | 2.674 | 61.5% | 0.456 | cascade=13 |
| A | waterfall | 13 | 30.8% | -0.211 | 0.52 | 2.985 | 69.2% | 0.432 | cascade=13 |
| B | rocket | 4 | 50.0% | 0.560 | n/a (n<5) | 0.473 | 0.0% | 0.000 | cascade=4 |
| B | waterfall | 4 | 0.0% | -0.564 | n/a (n<5) | 2.257 | 0.0% | -0.115 | cascade=4 |
| C | rocket | 15 | 20.0% | -0.126 | 0.68 | 2.059 | 0.0% | -0.419 | cascade=15 |
| C | waterfall | 14 | 21.4% | -0.282 | 0.11 | 4.062 | 0.0% | -0.797 | cascade=14 |
| D | rocket | 5 | 40.0% | 0.340 | 2.67 | 0.543 | 0.0% | 0.000 | cascade=4, early_break=1 |
| D | waterfall | 5 | 0.0% | -0.610 | 0.00 | 3.050 | 0.0% | 0.000 | cascade=4, early_break=1 |

## Verdict

**Verdict merge suspendu.** Ce tableau est PARTIEL : faits = ETH, SOL, BNB, BTC ; encore en cours = ARB, OP. Pas de oui/non tant que BTC, ETH, SOL, BNB, ARB et OP ne sont pas tous dans le replay.


## Holdout (dernier tiers calendaire, pas un walk-forward)

- A rocket: cut 2026-07-19T06:36:40+00:00 — earlier n=10 hit=20.0% avg=-0.155 PF=0.64; holdout n=3 hit=33.3% avg=-0.148 PF=n/a (n<5)
- A waterfall: cut 2026-07-19T06:36:40+00:00 — earlier n=8 hit=37.5% avg=-0.069 PF=0.84; holdout n=5 hit=20.0% avg=-0.437 PF=0.03
- B rocket: cut 2026-07-19T06:36:40+00:00 — earlier n=2 hit=100.0% avg=1.357 PF=n/a (n<5); holdout n=2 hit=0.0% avg=-0.237 PF=n/a (n<5)
- B waterfall: cut 2026-07-19T06:36:40+00:00 — earlier n=3 hit=0.0% avg=-0.672 PF=n/a (n<5); holdout n=1 hit=0.0% avg=-0.241 PF=n/a (n<5)
- C rocket: cut 2026-07-19T08:44:20+00:00 — earlier n=12 hit=25.0% avg=-0.025 PF=0.93; holdout n=3 hit=0.0% avg=-0.532 PF=n/a (n<5)
- C waterfall: cut 2026-07-19T04:29:20+00:00 — earlier n=11 hit=27.3% avg=-0.277 PF=0.14; holdout n=3 hit=0.0% avg=-0.298 PF=n/a (n<5)
- D rocket: cut 2026-07-19T06:36:40+00:00 — earlier n=3 hit=66.7% avg=0.724 PF=n/a (n<5); holdout n=2 hit=0.0% avg=-0.237 PF=n/a (n<5)
- D waterfall: cut 2026-07-19T06:36:40+00:00 — earlier n=4 hit=0.0% avg=-0.702 PF=n/a (n<5); holdout n=1 hit=0.0% avg=-0.241 PF=n/a (n<5)

## Diagnostics (décisions du replay)

- A rocket: decisions=240960, signals=16, hard_veto=3, regime_skips=64409, errors=0
- A waterfall: decisions=240960, signals=21, hard_veto=8, regime_skips=64460, errors=0
- B rocket: decisions=240960, signals=7, hard_veto=3, regime_skips=64482, errors=0
- B waterfall: decisions=240960, signals=8, hard_veto=4, regime_skips=64505, errors=0
- C rocket: decisions=90030, signals=63, hard_veto=48, regime_skips=0, errors=0
- C waterfall: decisions=83640, signals=69, hard_veto=55, regime_skips=0, errors=0
- D rocket: decisions=240960, signals=8, hard_veto=3, regime_skips=64482, errors=0
- D waterfall: decisions=240960, signals=9, hard_veto=4, regime_skips=64505, errors=0

## Ce que ça ne dit pas

Chiffres PARTIELS. Un hit rate sur un sous-ensemble de symboles n'est pas le verdict. LABEL: PARTIEL / PROXY.
