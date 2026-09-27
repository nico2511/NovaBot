# PROXY — seuils cascade rocket / waterfall

LABEL: PROXY. Prix Binance USDT-M (`data.binance.vision`), pas Hyperliquid. Ne pas lire ces fills comme des fills HL.

Fenêtre : cache `data/ohlcv_proxy` reconstruit le 2026-09-27, 2026-03-01 → 2026-09-26. Le rapport proxy précédent (25 coins) s'arrêtait au 25 septembre (le fichier du 26 était en 404). Ici le 26 est présent, 0 trou 1m/15m. Coûts : taker HL 4,50 bp/côté + slip 1 bp, via `net_r`. Funding Binance 8h quand le cache couvre le hold. IA non rejouée. Un signal qui passe la géométrie et `check_hard_veto` est pris. Livres indépendants (pas de top-K scanner, pas de `max_positions`).

Les params live (`data/config/strategies.json`) restent la baseline A. B/C/D sont des overlays de ce script. Trend LT, Range LT, SuperTrend, spark et ember ne sont pas rejoués.

Symboles dans ce tableau (6) : ETH, SOL, BNB, BTC, ARB, OP.

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
| A | rocket | 27 | 37.0% | 0.069 | 1.28 | 2.469 | 63.0% | 0.458 | cascade=27 |
| A | waterfall | 15 | 26.7% | -0.262 | 0.43 | 4.174 | 73.3% | 0.432 | cascade=15 |
| B | rocket | 6 | 50.0% | 0.602 | 8.12 | 0.473 | 0.0% | 0.000 | cascade=6 |
| B | waterfall | 4 | 0.0% | -0.564 | n/a (n<5) | 2.257 | 0.0% | -0.115 | cascade=4 |
| C | rocket | 25 | 28.0% | -0.132 | 0.68 | 4.777 | 0.0% | -0.326 | cascade=25 |
| C | waterfall | 24 | 20.8% | -0.251 | 0.35 | 6.138 | 0.0% | -0.630 | cascade=24 |
| D | rocket | 7 | 42.9% | 0.439 | 3.92 | 0.543 | 0.0% | 0.000 | cascade=6, early_break=1 |
| D | waterfall | 5 | 0.0% | -0.610 | 0.00 | 3.050 | 0.0% | 0.000 | cascade=4, early_break=1 |

## Verdict

- **A** — baseline de comparaison, pas un candidat de merge.
- **B — NON, ne pas merger.** rocket: n=6 < 40 (pas concluant) | waterfall: n=4 < 40 (pas concluant); hit 0.0% (seuil ≥ max(45%, baseline 26.7% + 8 pts)); avg net R -0.564 < 0; PF non mesurable
- **C — NON, ne pas merger.** rocket: n=25 < 40 (pas concluant); hit 28.0% (seuil ≥ max(45%, baseline 37.0% + 8 pts)); avg net R -0.132 < 0; PF 0.68 < 1.1 | waterfall: n=24 < 40 (pas concluant); hit 20.8% (seuil ≥ max(45%, baseline 26.7% + 8 pts)); avg net R -0.251 < 0; PF 0.35 < 1.1
- **D — NON, ne pas merger.** rocket: n=7 < 40 (pas concluant); hit 42.9% (seuil ≥ max(45%, baseline 37.0% + 8 pts)) | waterfall: n=5 < 40 (pas concluant); hit 0.0% (seuil ≥ max(45%, baseline 26.7% + 8 pts)); avg net R -0.610 < 0; PF 0.00 < 1.1

**Recommandation : ne pas merger de nouveaux seuils.** Aucune variante n'a à la fois un winrate nettement meilleur et un avg net R / PF tenables sur rocket et waterfall. La détection cascade reste celle de `main`.

## Holdout (dernier tiers calendaire, pas un walk-forward)

- A rocket: cut 2026-07-19T06:36:40+00:00 — earlier n=23 hit=34.8% avg=0.037 PF=1.13; holdout n=4 hit=50.0% avg=0.255 PF=n/a (n<5)
- A waterfall: cut 2026-07-19T06:36:40+00:00 — earlier n=9 hit=33.3% avg=-0.144 PF=0.69; holdout n=6 hit=16.7% avg=-0.439 PF=0.02
- B rocket: cut 2026-07-19T06:36:40+00:00 — earlier n=4 hit=75.0% avg=1.022 PF=n/a (n<5); holdout n=2 hit=0.0% avg=-0.237 PF=n/a (n<5)
- B waterfall: cut 2026-07-19T06:36:40+00:00 — earlier n=3 hit=0.0% avg=-0.672 PF=n/a (n<5); holdout n=1 hit=0.0% avg=-0.241 PF=n/a (n<5)
- C rocket: cut 2026-07-19T08:04:20+00:00 — earlier n=17 hit=35.3% avg=0.057 PF=1.21; holdout n=8 hit=12.5% avg=-0.535 PF=0.23
- C waterfall: cut 2026-07-19T06:29:20+00:00 — earlier n=18 hit=27.8% avg=-0.146 PF=0.55; holdout n=6 hit=0.0% avg=-0.567 PF=0.00
- D rocket: cut 2026-07-19T06:36:40+00:00 — earlier n=5 hit=60.0% avg=0.709 PF=7.14; holdout n=2 hit=0.0% avg=-0.237 PF=n/a (n<5)
- D waterfall: cut 2026-07-19T06:36:40+00:00 — earlier n=4 hit=0.0% avg=-0.702 PF=n/a (n<5); holdout n=1 hit=0.0% avg=-0.241 PF=n/a (n<5)

## Diagnostics (décisions du replay)

- A rocket: decisions=361440, signals=31, hard_veto=4, regime_skips=98172, errors=0
- A waterfall: decisions=361440, signals=23, hard_veto=8, regime_skips=98315, errors=0
- B rocket: decisions=361440, signals=10, hard_veto=4, regime_skips=98319, errors=0
- B waterfall: decisions=361440, signals=8, hard_veto=4, regime_skips=98360, errors=0
- C rocket: decisions=127155, signals=103, hard_veto=78, regime_skips=0, errors=0
- C waterfall: decisions=124950, signals=96, hard_veto=72, regime_skips=0, errors=0
- D rocket: decisions=361440, signals=11, hard_veto=4, regime_skips=98319, errors=0
- D waterfall: decisions=361440, signals=9, hard_veto=4, regime_skips=98360, errors=0

## Ce que ça ne dit pas

Un hit rate plus haut sur n < 200 n'est pas un edge HL. Le max DD est en R (1R par trade à la clôture), pas en % d'équity. Le spread Binance n'est pas celui d'Hyperliquid.
