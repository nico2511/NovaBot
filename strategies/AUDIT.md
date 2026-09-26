# Audit quantitatif — stratégies NovaBot (Hyperliquid perps)

Date: 2026-09-19  
Périmètre: logique de stratégie uniquement (entrée, sortie, sizing, filtres, thesis, risque interne).  
Sources: `strategies/*.py`, `strategies/engine.py`, `data/config/strategies.json`, `app/core/risk_profiles.py`, `app/core/trade_thesis.py`, `app/core/trailing_logic.py`.

Les trois modes demandés sont dans ce document:

1. **Standard** — structure imposée, par stratégie puis book
2. **Capital** — review avant capital réel (section 7)
3. **Stats** — validation statistique / backtest (section 8)

## Statut post-audit (2026-09-19 / 2026-09-20)

Ce document est le **snapshot d’audit** (findings + notes). Une partie du §9 est déjà livrée sur `main` :

| §9 | Livré | PR |
|----|-------|-----|
| Config: Spark/Ember off, weekend pause 1h+cascades, funding filter ON | Oui | [#23](https://github.com/nico2511/NovaBot/pull/23) |
| Engine: cascade confirmée, plus de bypass RANGE 5m, ADX régime = SuperTrend | Oui | #23 |
| Cascade: `use_live=False`, `min_rr` 1.5, Balanced (pas HVH 10×), DEAD flatten, `max_extension_atr` 1.5 | Oui | #23 |
| Range LT: box ancrée, TP mid, flatten DEAD rouge | Oui | #23 + [#24](https://github.com/nico2511/NovaBot/pull/24) |
| ST/LT: indicateurs sur closes, veto funding, trailing en R | Oui | #24 |
| Harness backtest causal (pas OOS 2024–2026) | Runner + dump HL whitelist | `reports/hl_ohlcv_whitelist_2026-09-26.tar.gz` + `reports/hl_ohlcv_manifest.json` (rétention `candleSnapshot`, pas 2024–2026 en 15m) |
| Walk-forward n≥200 / réactiver HVH | Non | Replay whitelist 2026-09-26 : `reports/strategy_backtest.md` — n ≪ 200 |

Les notes /10 et le verdict book **4.0** décrivent l’état **avant** #23/#24. Relire le code pour le risque live actuel ; ne pas traiter les tables « look-ahead déjà présent » comme encore vraies sans croiser ce statut.

---

# 0. Verdict book (toutes stratégies `enabled: true`)

## 1. Résumé exécutif (portefeuille)

| | |
|--|--|
| **Note globale** | **4.0 / 10** |
| **Type** | Mix non orthogonal: trend-following (ST + Trend LT) + mean-reversion (Range LT) + 4 momentum-cascade riders (Rocket / Waterfall / Spark / Ember) |
| **Risque global** | **Très élevé** |
| **Verdict** | **Trop dangereuse en l’état** tant que les 7 plans tournent ensemble avec profils HVH + `signal_score_bonus` cascade |

Le book n’est pas un portefeuille diversifié. C’est **quatre chasseurs de continuation ultra-courts** (score 115–120) qui **gagnent le tie-break** contre SuperTrend (bonus 0) et Range LT (bonus 50), plus Trend LT (bonus 100) qui peut encore passer. Les edges sont **antagonistes** (fade 1h vs chase 5m/15m) sur le **même symbole netté** (Hyperliquid = 1 position / coin).

Hypothèse non robuste (Critique book): *« plus de stratégies = plus d’edge »*. Ici plus de stratégies = plus de façons d’entrer **tard** dans un move déjà étendu, avec `min_rr` 1.0 et levier jusqu’à 10×.

| Stratégie | Note | Type | Risque | Verdict isolé |
|-----------|------|------|--------|----------------|
| SuperTrend | 6.5 | Trend following pullback/reclaim 15m | Moyen | Viable |
| Trend LT | 6.5 | Trend following swing 1h | Moyen | Viable |
| Range LT | 5.5 | Mean reversion box 1h | Élevé | À retravailler |
| Rocket | 4.5 | Momentum cascade long 15m | Très élevé | À retravailler |
| Waterfall | 4.5 | Momentum cascade short 15m | Très élevé | À retravailler |
| Spark | 3.5 | Momentum cascade long 5m | Très élevé | Trop dangereuse en l’état |
| Ember | 3.5 | Momentum cascade short 5m | Très élevé | Trop dangereuse en l’état |

**Capital déployable aujourd’hui (recommandation dure):** SuperTrend + Trend LT seuls, profil Balanced, `max_positions=1` ou 2, funding filter ON. Spark/Ember OFF. Rocket/Waterfall paper ou quota 1 trade/jour jusqu’à stats.

---

# SuperTrend (`strategies/supertrend.py`)

## 1. Résumé exécutif

- **Note:** 6.5 / 10  
- **Type:** trend following (EMA200 + SuperTrend 15m, trigger 1m pullback → reclaim)  
- **Risque:** Moyen  
- **Verdict:** Stratégie viable  

Plan le plus cohérent du repo: biais 15m, location (pas de chase mid-impulse), SL structurel, `min_rr` 2.0, barres confirmées `iloc[-2]`, thesis ST/EMA/ADX. L’edge est **classique et identifiable** (continuer après retracement vers la bande), pas magique. Expectancy réelle **non mesurée**.

## 2. Analyse de la logique

**Entrée LONG:** close 15m > EMA filter ET ST direction +1, ADX ≥ 22, pente ADX ≥ `min_adx_slope` (−0.55 live), RSI ≤ 60 (70 en strong-trend), extension vs ST ≤ 1.4 ATR, volume ≥ 80% MA50 (55% strong-trend), pullback 1m qui tag la bande 15m puis close 1m **au-dessus** du ST 15m.

**Entrée SHORT:** miroir (EMA, ST −1, RSI ≥ 40 / 30 strong-trend).

**Sortie:** SL = min(ST 15m, entry − 2×ATR, entry − 0.8%) donc **le plus large** des candidats sous l’entrée (protection noise, pas tight scalp). TP = `min_rr` × risk (2.0), ensuite **trim swing** dans `post_ai_adjust` — si le trim casse `min_rr`, veto géométrie **avant IA**. Thesis: DEAD si ST flip / prix à travers ST / pente ADX < `min_adx_slope`; WEAK si EMA perdue ou ADX mou. Overlay near-TP + DEAD drift. Trailing bot: BE à 75% du chemin vers TP ou +2% PnL long.

**Sizing / levier:** pas dans la strat. Profil **Balanced Growth**: risk 3.5% equity, levier max 5×, cap notional = equity × 1.0 / `max_positions`. Split slots ≈ risque réel ~1–1.75%/trade si SL 2–6%.

**Filtres:** ADX, pente ADX, RSI chase, extension ATR, volume confirmé, cooldown 15 min, same-bar, option `require_recent_flip` **OFF**. Veto pré-IA: RSI 80/30, ADX runaway 75, MACD, volume. Engine: type `trend` (besoin régime TREND / cascade). BB anti-chase 15m **actif** (peut tuer un reclaim légitime collé à la bande). Funding: lu au scan, **jamais un veto**.

**Multi-positions:** pas de pyramiding. 1 coin = 1 net. Sticky `looking_for_entry` par (strat, symbol).

## 3. Points faibles

| Gravité | Problème | Impact | Correction |
|---------|----------|--------|------------|
| Élevé | `min_rr` 2.0 + trim swing → beaucoup de setups tués **ou** TP trop loin si pas de swing | Soit sous-trading, soit TP mécanique au-delà de la structure si swing manquant | TP1 = swing, TP2 = 2R runner; ou `min_rr` 1.5 post-trim |
| Élevé | Indicateurs SuperTrend/ADX calculés sur le DF **avec bougie live**, puis lecture `iloc[-2]` | Repaint léger de la ligne ST / ATR sur la barre confirmée | Calculer ST/ADX/ATR sur `df.iloc[:-1]` puis aligner |
| Moyen | `should_panic_close` utilise ADX **live** `iloc[-1]` alors que l’entrée utilise −2 ; ne ferme **pas** les positions | Faux bloquages / nom mensonger | Panic sur barre confirmée ; ou thesis DEAD seulement |
| Moyen | Funding ignoré (hold 15m–plusieurs heures) | Longs payeurs en funding extrême mangent 2R | Hard veto \|funding\| > X%/h selon côté |
| Moyen | `strong_trend_relax` lâche RSI 70/30 et volume 55% | Chase autorisé le jour où ça fait le plus mal | Relax volume OK ; garder cap RSI ou exiger pullback plus profond |
| Faible | BB engine 15m peut rejeter un reclaim près de la bande | Faux négatifs | `skip_bb` seulement si extension ATR < 0.5 |

## 4. Stress / régimes

| Régime | Comportement | Edge / fragile |
|--------|--------------|----------------|
| Forte tendance bull/bear | C’est le plan. Pullback+reclaim. | **Edge** |
| Range / mean-reversion | ADX gate + panic ADX<20 + type `trend` idle. | Plutôt **protégé** |
| Haute vol / gaps | SL 2×ATR large → sizing baisse. Gap > SL → perte > risk_pct si stop logiciel | Fragile aux gaps alts |
| Funding extrême | Aucun gate | Fragile |
| Faible liquidité | Volume 80% aide ; alts HL restent slippy | Fragile |
| Whipsaw / fakeouts | Pullback+reclaim réduit le chase ; ST flip = thesis DEAD | Moins fragile que les cascades ; encore des stop-runs sur la bande |

## 5. Améliorations (priorité)

1. Recalculer indicateurs sur barres **closes uniquement**.  
2. Veto funding (ex. bloquer LONG si funding hourly > 0.01%).  
3. Split TP structure / runner.  
4. Ne pas relaxer le cap RSI en strong-trend sans confirmation 1h.  
5. Aligner panic close sur `iloc[-2]` ou supprimer le helper.

## 6. Checklist Hyperliquid

| Critère | Statut | Commentaire |
|---------|--------|-------------|
| Entrée claire | OK | EMA+ST+pullback+reclaim, params nommés |
| Sortie complète | OK | SL/TP + thesis + trailing ; DEAD ne close que si vert ≥ 0.25% |
| Sizing cohérent | PARTIEL | Délégué au profil ; cap 1× equity borne le 3.5% |
| Protection liquidation | PARTIEL | Levier 5× + SL large ; guard liq surtout sur **adoption** de position, pas au signal |
| Funding | KO | Pas de règle d’entrée/sortie |
| Fakeouts | OK | Meilleur du book |
| Look-ahead | PARTIEL | Signal sur −2 ; ST calculé avec live |
| Edge identifiable | OK | Continuation après pullback — **non backtesté** |

---

# Trend LT (`strategies/trend_lt.py`)

## 1. Résumé exécutif

- **Note:** 6.5 / 10  
- **Type:** trend following swing 1h (même géométrie que ST, TF plus lent)  
- **Risque:** Moyen  
- **Verdict:** Stratégie viable  

Cohérent: `always_active` donc **pas** gateé par l’ADX 15m (correct). Veto MTF 1h/4h + pente RSI. `min_sl_pct` 1.2%, `min_rr` 2.0. Hold long → funding et overnight crypto plus critiques qu’en ST.

## 2. Analyse de la logique

**Entrée:** 1h close vs EMA200 + ST, ADX ≥ 18 (live json), pente ≥ −0.5 (−1.0 strong-trend), RSI ≤ 65 / ≥ 35 (72/28 strong), extension ≤ 2.0 ATR, pullback 12 barres 1h dans 1.2 ATR de la bande, reclaim close confirmé, volume ≥ 50% (45% strong). Bonus score 100.

**Sortie:** même schéma ST (SL = ST 1h élargi ATR / 1.2%). Thesis 1h. Trailing **calibré ST 15m** (BE 75% vers TP) — trop tard **ou** trop tôt selon la largeur 1h.

**Sizing:** Balanced 3.5% / 5×. SL 2–8% → notional souvent borné par le cap 0.5× equity/slot (`max_positions=2`).

**Filtres:** veto RSI 85/20, ADX runaway 85, MACD, MTF (relaxable en strong-trend — **dangereux**), pente RSI ±4. Pas de funding.

**Pyramiding:** non.

## 3. Points faibles

| Gravité | Problème | Impact | Correction |
|---------|----------|--------|------------|
| Élevé | `strong_trend_relax_mtf_veto: true` | En tendance 1h « forte », on **désactive** le filtre 4h — pile le moment d’un retournement HTF | Ne jamais relaxer le conflit 4h |
| Élevé | Funding + hold 4–48h | Un long 5× avec funding +0.03%/h ≈ 0.7%/jour | Veto + time-stop / reduce si funding contre |
| Moyen | Trailing 75% TP pensé scalp ST | BE trop tard sur un 2R 1h (donner trop) ou trop tôt si TP trimé | Trailing en R (1R → BE, 1.5R → 0.5R) **par stratégie** |
| Moyen | ADX 18 vs defaults 20 (drift json/default) | Plus de trades 1h marginaux | Une source de vérité |
| Faible | Volume 50% trop permissif en 1h | Entrées thin | 70% ou dollar volume HL |

## 4. Stress / régimes

- **Tendance propre 1h:** edge.  
- **Range:** ADX 18 laisse passer du chop → **fragile** (plus que ST 15m type=trend).  
- **Gaps weekend:** `weekend_pause` existe mais `enabled: false` → **très fragile**.  
- **Whipsaw 1h:** pullback lookback 12h peut « taguer » une bande ancienne et reclaimer un fakeout.

## 5. Améliorations

1. Interdire relax MTF 4h.  
2. Activer weekend pause pour LT.  
3. Time-stop (ex. 24–36 bougies 1h) + funding veto.  
4. Trailing en multiple de R, pas % de TP générique.  
5. Sync `adx_threshold` json vs default.

## 6. Checklist

| Critère | Statut | Commentaire |
|---------|--------|-------------|
| Entrée claire | OK | |
| Sortie complète | PARTIEL | Thesis OK ; trailing non-TF-aware |
| Sizing | PARTIEL | SL large → risque $ parfois < profil (cap notional) |
| Liquidation | PARTIEL | 5× + SL 6% souvent avant liq ; 5× alt gap non |
| Funding | KO | |
| Fakeouts | PARTIEL | Reclaim 1h = 1 close, pas 2 |
| Look-ahead | OK | `iloc[-2]` 1h |
| Edge | OK | Continuation 1h — non validé |

---

# Range LT (`strategies/range_lt.py`)

## 1. Résumé exécutif

- **Note:** 5.5 / 10  
- **Type:** mean reversion / fade de box Donchian 1h  
- **Risque:** Élevé  
- **Verdict:** À retravailler  

Le **métier** est clair (fade extrême, pas breakout). L’**hypothèse** « Donchian 48–72h + ADX<18 + EMA50 plate = range tradable » n’est **pas robuste** sur perps alts: les boxes meurent en expansion, pas en ADX poli. Fade + levier 3× + SL au-delà de la box = ruin path classique (breakout contre le fade).

## 2. Analyse de la logique

**Entrée LONG:** ADX≤18, pente ADX≤0.4, EMA50 slope ≤ 0.0004, largeur 2–12%, ≥2 touches chaque bord, loc proche du low, **rejection**: wick tag low + close rentré (inner 8% width), floor pas en expansion, 4h EMA pas en dump. SHORT: miroir + plafond non expanding + high 1h **≤ range_high** (pas de mèche hors box).

**Sortie:** SL = hors box (max(0.4 ATR, 12% width, 0.4% prix)). TP = borne opposée. Si reward/risk < 2.0 → **pas de signal**. Thesis DEAD si close 1h hors box (breakout ou drift wrong-side). WEAK si ADX s’expand.

**Sizing:** Capital Preservation 1.5% / 3×. Si SL ~1% au-delà du low, risque $ proche du profil. Si le breakout gappe le SL → perte >> 1.5%.

**Filtres:** volume 50%, RSI veto **inversé** (bloque BUY si RSI>58 — i.e. pas un fade oversold mid-range). `always_active` en parallèle de Trend LT.

**Pyramiding:** non. Conflit Trend LT même symbole: Trend gagne au score si les deux firent.

## 3. Points faibles

| Gravité | Problème | Impact | Correction |
|---------|----------|--------|------------|
| Critique | Fade d’un Donchian naïf: le high du lookback **est** souvent le début du breakout | Shorts au high d’expansion = couteau | Box = swings confirmés (2+ rejects) **fixes** jusqu’à invalidation ; pas rolling high |
| Élevé | `generate_signal` évalue le setup avec `require_rejection=False` puis attend reject — arming sticky | État armé peut survivre un régime qui se tend | Désarmer si ADX_slope>0.2 ou 4h slope |
| Élevé | min_rr 2.0 vs TP = autre borne: largeur 2% et SL 0.4%+buffer → souvent **aucun trade** ; largeur 8%+SL serré → R:R artificiel si on n’atteint jamais l’autre bord | Soit silence, soit TP irréaliste mid-range | TP = mid (0.5R–1R) + runner optionnel ; ne pas exiger 2.0 jusqu’à l’opposé |
| Élevé | Thesis DEAD close hors box mais `CLOSE_IF_PROFIT` seulement si PnL ≥ 0.25% | Breakout contre le fade **rouge** → on **garde** jusqu’au SL | DEAD + rouge = close immédiat (c’est le kill du plan) |
| Moyen | Volume 50% + fade | Absorption / breakout dry-up mal distingués | Volume **hausse** à l’extrême = breakout, pas fade |
| Faible | Score bonus 50 vs cascades 120 | Rarement prioritaire — peut être un bien |

## 4. Stress / régimes

- **Range honnête, ADX mort:** edge théorique.  
- **Tendance / expansion:** **fragile — ruin regime**.  
- **Gaps:** SL hors box sauté → liquidation 3× possible sur alt −8%.  
- **Funding:** fade long sous funding élevé = payer pour attendre le mean-revert.  
- **Whipsaw:** un reject 1h puis breakout la barre suivante = 1R perdu, souvent.

## 5. Améliorations

1. Invalidation: close hors box **→ flatten immédiat**, pas wait-for-green.  
2. Ancrer la box (ne plus reculer le high/low chaque heure).  
3. TP mid-box par défaut.  
4. Bloquer fade si volume spike dans le sens du breakout.  
5. Ne pas co-activer avec Spark/Ember/Rocket sur le même univers sans mutex régime 1h.

## 6. Checklist

| Critère | Statut | Commentaire |
|---------|--------|-------------|
| Entrée claire | OK | Rejection rules précises |
| Sortie complète | KO | DEAD rouge non flatten |
| Sizing | PARTIEL | 3× OK si SL honoré |
| Liquidation | KO | Breakout gap vs 3× |
| Funding | KO | |
| Fakeouts | PARTIEL | Wick intact aide ; rolling box trahit |
| Look-ahead | OK | confirmed `iloc[:-1]` |
| Edge | FAIBLE | Mean-revert 1h crypto n’est pas un edge gratuit |

---

# Rocket (`strategies/rocket.py`) + Waterfall (`waterfall.py`)

(Symétriques. Différences notées.)

## 1. Résumé exécutif

- **Note:** 4.5 / 10 chacun  
- **Type:** momentum / cascade rider (pas un pullback). Long-only (Rocket) / short-only (Waterfall). Détection 15m **live**, trigger 1m.  
- **Risque:** Très élevé  
- **Verdict:** À retravailler (isolé) ; **Trop dangereuse** si les deux + Spark/Ember + HVH 10× tournent  

Hypothèse: *double bougie + EMA9>EMA20 + HH/LL = continuation avec edge après frais*. Sur HL alts c’est surtout du **chase de move déjà étendu**. Les gardes (structure prior, wick trap, vol slope, range exhaustion) sont réelles — elles ne transforment pas un R:R 1.0 en expectancy positive.

## 2. Analyse de la logique

**Entrée Rocket:** `detect_bull_cascade(..., use_live=True)`: close live > EMA9 > EMA20, 2 vertes, close > high précédent. Extension EMA9 ≤ 3.5 ATR, RSI live ≤ 72, wick trap, volume ≥ 120% **ou** spike, vol_slope ≥ −30%, 1m close confirmé vert + HH, close 15m **à travers** le prior high (+0.60%) sinon reject plafond. Waterfall: miroir, RSI ≥ 28, breakdown −0.60%.

**Sortie:** SL = min(swing lookback **incluant live**, EMA9 − 0.5 ATR), floor 0.4%. TP = 1.0R. Thesis: DEAD si close **live** perd EMA9 (Rocket) / reclaim EMA9 (Waterfall). Soft close seulement si vert ≥ 0.25%. Trailing générique 75% de 1R = BE très tôt (~0.3% si SL 0.4%).

**Sizing:** High Volatility Hunter **7% risk / 10×**. Avec SL 0.4%, le notional théorique explose puis **clamp** à 0.5× equity/slot → risque $ réel ~0.2%/trade **si** le stop est fillé. Si le stop n’est pas fillé (gap, wick 5m), 10× + notional 50% equity ≈ distance liq ~8–12%. **C’est le vrai risque**, pas le 0.4% papier.

**Filtres:** skip BB anti-chase (volontaire). Engine type `trend` **ou** overlay cascade live 15m qui **force** TREND_*_STRONG et réveille aussi SuperTrend. Scan 5 min / 2 min armed. Score bonus **120** (priorité max).

**Pyramiding:** non. Mais Spark peut viser le même pump 5m plus tôt, puis Rocket 15m — mutex symbole, le **premier fill gagne**.

## 3. Points faibles

| Gravité | Problème | Impact | Correction |
|---------|----------|--------|------------|
| Critique | Détection `use_live=True` (bougie 15m **non close**) | Signal sur fake green/red qui se fait manger avant close | Détecter sur `use_live=False` ; 1m = trigger seulement |
| Critique | `min_rr` 1.0 après taker HL (~0.045–0.07% RT) + slip alts | Edge brut ≤ 0 après coûts si hit-rate < ~55–60% | Exiger 1.5R **structure** ou ne pas trader |
| Critique | Profil 10× + SL 0.4% : le risque n’est pas le SL, c’est **liq / gap** | Un wick 8% = compte | HVH interdit sur cascade ; levier ≤ 3× ; SL exchange-native |
| Élevé | SL swing `iloc[-lookback:]` **inclut la barre live** | SL qui se resserre pendant la bougie = stop hunt | Swing sur `iloc[:-1]` |
| Élevé | Thesis DEAD sur `iloc[-1]` EMA9 ; rouge → on **reste** | Cascade morte, on attend le SL | Flatten DEAD sans condition de profit |
| Élevé | `skip_bb_anti_chase` + RSI 72 | Blow-off range (partiellement couvert si regime RANGE) ; si engine a mis TREND_BULL_STRONG **live**, le veto range **ne s’applique plus** | Ne pas laisser une cascade live retirer le régime RANGE pour le veto |
| Moyen | 1m confirm **après** 15m live = souvent **plus tard**, pas plus sûr | Fill au pire prix de la 1m | Soit late-reject si 1m déjà +0.8 ATR, soit skip 1m et size plus petit |
| Moyen | Waterfall short vs funding négatif extrême (shorts paient) | Même problème miroir que Rocket | Veto funding signé |
| Faible | `get_rr_epsilon` 0.05 vs 0.02 ST | Laisse passer des 0.95R | Aligner 0.02 |

## 4. Stress / régimes

| Régime | Rocket / Waterfall |
|--------|---------------------|
| Tendance impulsive avec volume | **Edge conditionnel** (le seul) |
| Range | Fragile ; veto range si régime encore RANGE — **contourné** par overlay cascade engine |
| Haute vol / gaps | **Ruin path** 10× |
| Funding extrême | Fragile (hold court mais 1R = 0.4%) |
| Faible liq | Slip + wick trap partiel |
| Whipsaw | **Régime natif de la détection live** |

## 5. Améliorations

1. `use_live=False` pour l’armement 15m.  
2. Levier max 3×, profil Balanced ou Preservation, `min_rr` 1.5.  
3. DEAD → close market, toujours.  
4. Découpler régime engine (ne pas promouvoir TREND_*_STRONG depuis une barre live).  
5. Un seul rider par direction (Rocket **ou** Spark, pas les deux).  
6. Max extension 1.5 ATR (3.5 = late chase).

## 6. Checklist

| Critère | Statut | Commentaire |
|---------|--------|-------------|
| Entrée claire | OK | Règles nettes, mais live |
| Sortie | KO | 1R mécanique + DEAD conditionnel |
| Sizing | KO | 7%/10× vs SL 0.4% incohérent ; clamp cache le danger liq |
| Liquidation | KO | |
| Funding | KO | |
| Fakeouts | KO | Live cascade = fakeout machine |
| Look-ahead | KO | Live bar = non causal en backtest ; en live = look-*inside*-bar |
| Edge | FAIBLE | Momentum continuation, coûts > edge probable |

---

# Spark (`spark.py`) + Ember (`ember.py`)

## 1. Résumé exécutif

- **Note:** 3.5 / 10 chacun  
- **Type:** scalping momentum 5m (même géométrie cascade, plus court)  
- **Risque:** Très élevé  
- **Verdict:** Trop dangereuse en l’état  

Spark/Ember existent pour « attraper le pump avant le 15m ». C’est **exactement** le trade le plus adversarié sur HL (latency, wick 5m, liq alts, frais / R). En plus: engine les active **même en RANGE 15m** si cascade 5m live (`_live_5m_cascade`). Donc ils **bypassent** le régime qui devait protéger SuperTrend.

## 2. Analyse de la logique

Comme Rocket/Waterfall avec: TF 5m, `max_extension_atr` 2.5, `cascade_fresh_bars_max` 3, SL 0.45 ATR / `min_sl_pct` 0.35%, cooldown 7 min, scan 3 min / 1.5 armed, RSI veto 74 / 26, struct lookback 48 (5m × 48 ≈ 4h). Trigger 1m identique.

**Activation:** type `trend` **OU** cascade 5m live. C’est un trou dans le modèle « 1 strat = 1 régime ».

## 3. Points faibles

| Gravité | Problème | Impact | Correction |
|---------|----------|--------|------------|
| Critique | Activation en RANGE 15m via 5m live | Fade/chop 15m + chase 5m | Interdire `fast_5m` hors TREND 15m **et** 1h bias aligné |
| Critique | SL 0.35% sur alts 5m | Noise > SL, hit-rate écrasé ; ou size énorme jusqu’au cap | `min_sl_pct` ≥ 0.8% et levier ≤ 2× |
| Critique | Même book que Rocket: deux longs chase le même flow | Premier fill (souvent Spark, plus noisy) occupe le symbole | Mutex: Spark XOR Rocket par direction |
| Élevé | 1m confirm sur un setup 5m déjà live | Double lag vs le move 5m | Soit marketable 5m close, soit abandonner 5m |
| Élevé | Thesis 5m sur `iloc[-1]` | DEAD/WEAK bruité toutes les minutes | Thesis sur 5m **close** seulement |
| Moyen | Frais / 1R 0.35% | Round-trip ~15–25% du R | `min_rr` ≥ 2.0 post-fees |

## 4. Stress / régimes

Edge **uniquement** sur ignition 5m ultra-liquide (BTC/ETH) avec fill < 1–2s. Sur le reste de l’univers scanner: **fragile partout**, surtout range, whipsaw, thin liq, funding (moins grave, hold court) et gaps (ruin).

## 5. Améliorations

1. Disable par défaut (`enabled: false`).  
2. Universe = top 5 coins par volume 24h seulement.  
3. Levier 2×, min_sl 0.8%, min_rr 2.0, confirmed 5m only.  
4. Kill-switch: 3 losses / jour → OFF.  
5. Pas de coexistence Rocket/Spark.

## 6. Checklist

| Critère | Statut | Commentaire |
|---------|--------|-------------|
| Entrée claire | OK | Copie Rocket |
| Sortie | KO | Idem cascade + TF plus bruité |
| Sizing | KO | HVH 10× + 0.35% SL |
| Liquidation | KO | |
| Funding | N/A court | Secondaire vs wick |
| Fakeouts | KO | |
| Look-ahead | KO | Live 5m |
| Edge | NON | Non identifiable après coûts |

---

# Book — problèmes transverses (gravité)

| Gravité | Problème | Impact | Correction |
|---------|----------|--------|------------|
| Critique | 7 stratégies ON, edges opposés, tie-break cascade | Le bot **est** un chasseur de cascade avec ST/LT en décor | Enable-list: ST + Trend LT ; le reste opt-in |
| Critique | `_regime_adx_threshold()` = **max** des `adx_threshold` de toutes les strats trend/always_active | Couplage caché (Range LT n’a pas le key → default 22) | Seuil régime **propriété engine / ST seulement** |
| Critique | Overlay cascade **live** 15m réécrit `regime` → TREND_*_STRONG | SuperTrend + Rocket s’allument sur une mèche | Overlay sur barre **confirmée** |
| Élevé | Trailing unique (`trailing_logic.py`) pour ST 15m, LT 1h, cascade 1R | Mauvaise extraction d’edge partout | `manage_trade` par stratégie |
| Élevé | Funding filter scanner **off** par défaut (`bot.py`) | Univers toxique funding | ON + veto strat |
| Élevé | AI system prompt: « Do not default to reject » / « we need execution » | Contredit les personas strictes | Prompt exécution neutre |
| Élevé | HVH `min_conf` 48 + confidence floor assoupli | IA rubber-stamp cascades | Confiance min 62 même HVH |
| Moyen | `weekend_pause.enabled: false` | LT/Range weekend = piège | Enable pour 1h |
| Moyen | Drift `strategies.json` vs `strategies.default.json` (ADX slope ST, ADX LT) | Comportement live ≠ defaults tests | Une pipeline de sync |
| Faible | `cascade_exhaustion.py` n’est pas une stratégie engine — OK | — | Garder helpers only |

---

# 7. Version capital — « avant de mettre de l’argent réel »

Règle: on ne déploie **pas** un plan dont le ruin path est plus clair que l’edge.

### Ruin paths (quantitatifs, ordre de gravité)

1. **Spark/Ember + 10× + SL 0.35% + activation RANGE.** Un alt −8% en 2 minutes (courant HL) → liquidation avant le stop logiciel. **Kill:** `enabled: false` jusqu’à levier ≤ 2× et 5m confirmé.  
2. **Rocket/Waterfall live 15m + skip BB + régime forcé TREND_*_STRONG.** Fill late, 1R=0.4%, thesis ne coupe pas le rouge. **Kill:** `use_live=False`, levier ≤ 3×, DEAD flatten.  
3. **Range LT fade + breakout gap.** DEAD rouge = on garde. **Kill:** flatten on box break, toujours.  
4. **Book entier.** Deux slots, le plus haut score = cascade. Equity path = série de 1R noise stops. **Kill:** retirer bonus 115–120 ou désactiver riders.

### Conditions de mise sous capital (go / no-go)

| Plan | Go live? | Condition |
|------|----------|-----------|
| SuperTrend | **Oui, petit** | 3× max, funding filter ON, 1 position, paper 2 semaines d’abord si pas d’OOS |
| Trend LT | **Oui, petit** | Idem + weekend pause ON, pas de relax MTF 4h |
| Range LT | **Non** | Box ancrée + flatten breakout d’abord |
| Rocket / Waterfall | **Non** | Confirmed bar + levier 3× + stats 100+ trades OOS |
| Spark / Ember | **Non** | Ne pas activer sur compte réel |

### Taille de compte

Sur HL, notional cap 1× equity / 2 slots = 50% notional. À 10×, margin 5%/slot. Ça **n’empêche pas** la liq: ça empêche seulement de lever 17×. Un compte $1,000 avec Spark n’est pas « small enough to be safe » — le % DD est le même.

### Kill-switch compte (pas « surveiller »)

- Daily stop déjà au risk manager: **garder**.  
- En plus: **3 losses cascade consécutifs → disable rocket/waterfall/spark/ember pour 24h** (n’existe pas).  
- Drawdown −8% equity → OFF toutes les HVH.  
- Funding hourly > 0.02% contre la position → flatten LT/Range.

Verdict capital: **paper le book actuel**. Live éventuellement **SuperTrend + Trend LT** seulement.

---

# 8. Version stats — backtest / validation

**État actuel:** le runner causal est dans `app/core/strategy_backtest.py` (frais/slip du harness, sorties SL/TP/thesis, pas d’appel IA). Le dump réel du 26 Sep 2026 (whitelist scanner d’exemple, 25 coins, 1m/15m/1h/4h + funding) est `reports/hl_ohlcv_whitelist_2026-09-26.tar.gz` ; les dates exactes sont dans `reports/hl_ohlcv_manifest.json`. Le replay de ce dump est `reports/strategy_backtest.md` (ST 0, trend_lt 6, range_lt 39, rocket 2, waterfall 1). L’API ne garde que ~5000 bougies par intervalle, donc ce n’est pas l’OOS 2024–2026 du design ci-dessous, et **aucun plan n’atteint n≥200**. L’edge reste **unvalidated**. Les unit tests vérifient des invariants de code, **pas** l’expectancy.

### Hypothèses à tester (une phrase chacune)

| Strat | H0 (pas d’edge) | H1 |
|-------|-----------------|----|
| ST | Pullback+reclaim 15m, net de frais, E[R] ≤ 0 | E[R] > 0 sur TREND ADX>22, 2024–2026 OOS |
| Trend LT | Idem 1h | E[R] > 0 hors weekends |
| Range LT | Fade Donchian 1h E[R] ≤ 0 | E[R] > 0 seulement si ADX<16 **et** volume down à l’extrême |
| Rocket | Cascade live 15m E[R] ≤ 0 après 2 ticks slip | E[R] > 0 seulement confirmed + extension < 1.5 ATR + BTC/ETH |
| Spark | 5m cascade E[R] < 0 après frais | — (hypothèse: rester H0) |

### Design d’expérience (minimum)

1. **Barres:** toujours `iloc[-2]` / `use_live=False`. Toute perf avec live bar est **invalide**.  
2. **Coûts:** taker 0.045% × 2 + 1 tick slip (alts: 5–10 bps) + funding hourly × hold médian.  
3. **Sample:** ≥ 200 trades OOS **par** stratégie, split 2024 / 2025 / 2026, univers = coins du scanner (pas BTC only).  
4. **Walk-forward:** 3 mois train / 1 mois test, pas de re-fit RSI 72 vs 74 en cours de test.  
5. **Métriques kill:** profit factor < 1.1 après coûts ; max DD > 15% ; time-under-water > 30j ; hit-rate < 40% sur ST (2R) ou < 58% sur cascade (1R).  
6. **Look-ahead checklist:** SuperTrend calculé sur `df[:-1]` ; volume = barre close / MA50 closes ; pas de scan score qui utilise la close live pour un fill à cette close.  
7. **Régimes:** reporter E[R] | TREND vs RANGE vs cascade overlay. Si 80% du PnL vient de 10 trades, ce n’est pas un edge.

### Taille d’échantillon (ordre de grandeur)

- ST `min_rr` 2.0, hit-rate vraie 40%: E[R] brut = 0.4×2 − 0.6×1 = +0.2R avant frais. Après 0.03R frais, +0.17R. **CI 95%** sur 50 trades encore compatible avec E[R]=0. Il faut **n ≥ 200**.  
- Cascade 1.0R, hit-rate 52%: E[R] = 0.04R brut − 0.08R coûts ≈ **négatif**. Pour « prouver » +0.1R net il faut hit-rate ~58%+ **et** n ≥ 300 (wicks).  
- Spark 0.35% SL: le bruit d’estimation est plus grand que l’edge. **Ne pas optimiser** RSI 74 vs 72 sans hold-out.

### Look-ahead déjà présent (à corriger avant tout backtest)

- `detect_*_cascade(use_live=True)` engine + generate_signal.  
- Rocket/Waterfall/Spark/Ember RSI/extension/wick/SL swing sur `iloc[-1]`.  
- Thesis cascade `work.iloc[-1]`.  
- SuperTrend `add_indicators(df)` full frame.  
- `should_panic_close` ADX `iloc[-1]`.  
- Scan cascade hybride: live **or** confirmed — un fill backtest à la close live overfit.

Tant que ces points existent, **toute courbe de perf live ou replay est suspecte**.

---

# 9. Priorité d’implémentation (actionnable)

1. ~~**Config live:** `spark` + `ember` `enabled: false`. `weekend_pause.enabled: true`. Scanner `funding_filter_enabled: true`.~~ → **fait (#23)**  
2. ~~**Engine:** régime cascade sur barre confirmée ; retirer `_live_5m_cascade` hors TREND. `_regime_adx_threshold` ne lit plus les always_active.~~ → **fait (#23)**  
3. ~~**Cascade:** `use_live=False`, `min_rr` 1.5, levier profil Balanced, DEAD flatten, swing SL `iloc[:-1]`, `max_extension_atr` 1.5.~~ → **fait (#23)** (swing SL confirmé via entrée `iloc[-2]`)  
4. ~~**Range LT:** flatten DEAD rouge ; box ancrée ; TP mid.~~ → **fait (#23 DEAD + #24 box/mid)**  
5. ~~**ST/LT:** indicateurs sur closes ; veto funding ; trailing en R.~~ → **fait (#24)**  
6. **Ne pas** baisser les veto « pour avoir plus de trades ».  
7. **Backtest** OOS causal (n≥200) avant de réactiver HVH — runner + dump whitelist livrés ; l’échantillon API reste trop court (1m ~3.5 j, 1h ~208 j, voir `reports/strategy_backtest.md`). Ne pas réactiver HVH sur ce run.

---

*Audit code-only. Aucun historique de trades live n’a été utilisé ; s’il existe, il faut le recouper avec la section 8 (coûts, régimes, n).*
