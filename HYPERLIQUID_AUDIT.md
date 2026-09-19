# Audit Hyperliquid — NovaBot

**Date:** 2026-09-19  
**Périmètre:** execution live (`app/services/hyperliquid_service.py`, `app/core/bot.py`, `risk_manager`, `safe_order_manager`, `position_reconciler`, API, WS, secrets)  
**Correctifs inclus dans ce PR:** retry anti-double entrée, close reduce-only, snapshot stale, Dry Run réel, `HYPERLIQUID_API_URL`, alerte clé master, open-orders fail-closed.

---

## 1. Résumé exécutif

| | |
|---|---|
| **Note globale** | **5.5 / 10** (était ~4/10 avant les correctifs de ce PR) |
| **Niveau de risque** | **Élevé** (était **Critique**) |

**Verdict:** ce bot ne doit pas être lancé en live « launch-and-forget » tant que les points ci-dessous ne sont pas traités. Un run isolé, clé **agent** sans withdraw, `API_KEY_REQUIRED=true`, Isolated, notional cap 1×, daily stop serré, et surveillance Discord 24/7, est le *maximum* acceptable — et seulement après les correctifs de ce PR.

Les couches « machine » (sizing ÷N, cap notional = equity, daily stop HL, ghost close uniquement après fill Close, WS reconnect) sont réelles. Elles ne compensent pas des chemins d’ordres qui, avant ce PR, pouvaient **doubler une position** ou **ouvrir un reverse** sur un close raté.

### 3 points les plus dangereux à corriger en priorité

1. **Idempotence des ordres encore incomplète (pas de `cloid`)** — ce PR refuse de retry après un fill / état ambigu, mais un timeout CloudFront + fill réel + snapshot positions encore vide peut toujours laisser un opérateur relancer à la main, et `sync_sl_tp` reste un cancel-then-replace **nu**. Sans client order id Hyperliquid, l’idempotence n’est pas garantie.
2. **Auth API off par défaut + `/docs` + close/enable trading** — `API_KEY_REQUIRED=false`. Quiconque atteint le port 3001 peut activer le trading, closer, forcer BE, changer le levier. En Coolify mal firewallé = drain du compte.
3. **Slippage d’entrée 5% + SL exchange non garanti à l’entrée** — `MARKET_SLIPPAGE = 0.05`. Sur un alt illiquide l’IOC peut fill 5% contre toi. Si la jambe SL du `bulk_orders` est rejetée, tu es en position **sans stop** jusqu’au reconciler (30s). Le liquidation guard n’existe que sur **adoption**, pas sur les entrées bot.

---

## 2. Analyse détaillée par catégorie

### 2.1 Sécurité & secrets

#### [Élevé] Clé privée = clé master possible
- **Localisation:** `app/services/hyperliquid_service.py` (`Account.from_key` + `Exchange(..., account_address=HL_ACCOUNT_ADDRESS)`)
- **Impact:** si `HL_PRIVATE_KEY` est la clé du wallet principal (même adresse que `HL_ACCOUNT_ADDRESS`), une fuite `.env` / logs Coolify = **withdraw possible**. Le pattern Agent API est documenté mais **jamais imposé**.
- **Correctif de ce PR:** log `ERROR` si l’adresse dérivée de la clé == `HL_ACCOUNT_ADDRESS`.
- **Reste à faire:** refuser de signer si master key, ou require `HL_AGENT_ONLY=true` + exit process.

```python
# Recommandé — fail closed
if account.address.lower() == master.lower():
    raise SystemExit("Refusing master wallet key. Use a Hyperliquid API Agent.")
```

#### [Élevé] API de trading ouverte sans clé
- **Localisation:** `app/core/config.py` (`API_KEY_REQUIRED` défaut `false`), `app/api/auth.py`, `app/api/main.py` (`/docs`, `/health`), `app/api/routers/trading.py` (`/trading/enable`, `/close_position`, `/force_breakeven`)
- **Impact:** enable live, close, BE, switch symbol sans auth. `secrets.compare_digest` casse aussi si les longueurs de clé diffèrent (500 au lieu de 401).
- **Correction:** défaut `true` dès qu’un bind public est détecté ; hasher/comparer en constant-time après pad ; désactiver `/docs` en prod.

#### [Moyen] Webhooks Discord en clair via GET `/api/settings/global`
- **Localisation:** `app/api/routers/settings.py`
- **Impact:** vol de webhook → spam / phishing du canal ops. `user_settings.json` est gitignoré, bien ; l’API le ressert entier.
- **Correction:** rédacter `https://discord.com/api/webhooks/...` en `https://discord.com/api/webhooks/***` sur GET.

#### [Moyen] `HYPERLIQUID_API_URL` était ignoré (corrigé)
- Config lisait l’URL, Info/Exchange/WS étaient **hardcodés mainnet**. Un opérateur qui croit être en testnet était en **mainnet réel**.
- **Ce PR:** REST + WS dérivés de `HYPERLIQUID_API_URL`.

#### [Faible] Conteneur root, secrets en env
- `Dockerfile` tourne en root. Env Coolify est le bon endroit (pas le git). Pas de rotation, pas de sealed-secret.
- **Correction:** user non-root ; agent key uniquement ; jamais de clé master dans Coolify.

#### Positif
- `.env` gitignoré, `user_settings.json` gitignoré, agent pattern documenté dans `DEPLOYMENT_COOLIFY.md`.
- Auth header `X-API-Key` existe et est correctement branchée **si** on l’active.

---

### 2.2 Logique de trading & ordres

#### [Critique → corrigé ici] Retry `execute_order` après fill = double position
- **Localisation:** `execute_order` (retry 3× sur *toute* erreur de statut, y compris SL rejeté alors que l’entrée est filled).
- **Impact:** `bulk_orders` fill l’entrée, la jambe SL error → retry du **bulk entier** → 2× la taille, netting HL, levier réel doublé, SL/TP désalignés.
- **Correctif:** `_classify_order_statuses` ; si `filled` → success, **jamais** retry ; si positions API down après exception → pas de retry (état ambigu).

#### [Critique → corrigé ici] `close_position` via `market_open` sans reduce-only
- **Avant:** cancel SL/TP **puis** `market_open` du côté inverse. Retry + snapshot stale (position déjà fermée mais cache dit encore open) = **ouverture d’un reverse**.
- **Impact:** liquidation / PnL inverse, compte à découvert mental.
- **Correctif:** `exchange.market_close(..., sz=)` (reduce-only SDK) ; refus si snapshot stale/failed ; cancel des triggers **après** close confirmé ; déjà-flat = success no-op.

#### [Critique → corrigé ici] `get_open_orders` renvoyait `[]` sur 429
- **Impact:** `SafeOrderManager.ensure_sl_tp` croyait « pas de SL » → **duplicate triggers**. Sur HL, des SL/TP en double + taille restante = chaos de fills partiels.
- **Correctif:** cache + flag `_open_orders_fetch_failed` ; placement SL sauté si fetch failed.

#### [Élevé] Fenêtre nue `sync_sl_tp` (cancel ALL puis replace)
- **Localisation:** `hyperliquid_service.sync_sl_tp`, appelé par trailing / thesis / `_verify_and_enforce_sl_tp`
- **Impact:** entre le cancel et le replace, un gap de prix → **pas de SL**. En cascade 1m c’est la recette pour se faire liquider.
- **Correction:** `batch_modify` / replace in-place ; au minimum cancel **uniquement** les oid SL/TP ciblés dans le même `bulk` que les nouveaux. Ce PR refuse le sync si open-orders fetch failed, mais la fenêtre reste.

#### [Élevé] IOC cancel traité comme succès (corrigé)
- Un IOC non matché n’a pas toujours `error` ; `canceled` sans `filled` est un miss. Avant: `return success` puis « position NOT confirmed after 5s » — SL/TP `normalTpsl` orphelins possibles.
- **Correctif:** canceled sans fill = error.

#### [Élevé] Pas de `cloid`
- HL supporte `Cloid` 16 bytes sur `order` / `market_open` / `market_close`.
- Sans ça, un retry réseau n’est **pas** idempotent au niveau exchange.
- **Correction:**

```python
from hyperliquid.utils.types import Cloid
cloid = Cloid.from_str("0x" + uuid.uuid4().hex)
# persist cloid in trade.metadata before submit; reuse on retry
```

#### [Moyen] Partial fills
- Taille SL/TP = qty **demandée**, pas qty **filled**. Un fill partiel laisse un SL trop gros (reduce-only tronque) ou trop petit (reste nu).
- **Correction:** après fill, relire `szi` exchange et `sync` SL/TP à la taille réelle (le bot copie `pos['size']` en mémoire, bien ; `execute_order` envoie encore la qty signal).

#### [Moyen] Orphan adoption default BUY
- **Localisation:** `position_reconciler.py` si `side` absent et pas de `szi`.
- **Impact:** un short manuel adopté en BUY → SL/TP du **mauvais côté** → ils ne protègent pas, ou prennent l’autre sens.
- **Correction:** ne pas adopter ; alerter Discord « side inconnu ». Le service `get_positions` pose déjà `side` BUY/SELL — le défaut n’est atteint que si un autre chemin injecte un dict brut.

#### [Moyen] PnL de close bot = mid, pas fill
- `execute_exit_atomically` calcule PnL sur `get_current_price` (mid WS). Fees ignorées. Daily stop côté `record_trade_close` peut diverger ; `apply_exchange_daily_pnl` rattrape (bien).

#### Positif
- Entrée atomique `grouping="normalTpsl"` (le bon pattern HL).
- Rounding tick 5 sig figs (incident BCH documenté + tests).
- `can_open_trade` bloque le même symbole (netting HL).
- Close externe uniquement après fill `dir=Close` (`close_pnl.py`).

---

### 2.3 Gestion du risque

#### [Critique] Liquidation guard seulement à l’adoption
- **Localisation:** `bot.py` `_adopt_existing_position` (~liquidation_price, buffer 15% du gap). **Les entrées stratégie n’utilisent pas `liquidationPx`.**
- **Impact:** Isolated 10× (High Volatility Hunter) + SL trop large / SL non posé → liq avant le stop. Cross (si mal config) → **wipe du compte**.
- **Correction:** avant tout `execute_order`, fetch `liquidationPx` projeté ou heuristique `entry * (1 - 0.8/lev)` et **exiger** `SL` strictement avant liq + buffer. Bloquer l’entrée sinon.

#### [Élevé] Slippage 5%
- SDK HL default = 5%. Sur BTC le fill est near-mid ; sur un perp 50k$ vol / 2M$ OI tu **achètes** 5% plus haut. Le risk_pct est calculé sur le **signal price**, pas le fill.
- **Correction:** 0.5–1.0% majors, 1.5% alts ; abort si `avgPx` dévie > X% du signal.

#### [Élevé] High Volatility Hunter = 10× / 7% risk
- `risk_profiles.py`. Cap notional = equity / max_positions (bon). 10× isolated sur un slot 0.5× equity = ~5% margin, liq ~10% adverse. Un SL 2% ATR tient ; un SL manquant ne tient pas.
- **Correction:** plafonner live à 3–5× tant que SL n’est pas confirmé `waitingForTrigger`.

#### [Moyen] Isolated vs Cross
- Settings default `ISOLATED` (bien). `_enforce_leverage` fallback string `"Cross"` si la clé manque. `scanner.margin_type` peut override. Comparaison **case-sensitive** `== "Cross"`.
- Levier sync **uniquement** `self.active_symbol` — une 2e position sur un autre coin peut rester à l’ancien levier HL (persisté par coin).
- **Correction:** `update_leverage` sur le coin de l’entrée, toujours ; never Cross en prod small account.

#### [Moyen] Daily stop en $ absolu, reset `date.today()` local vs PnL UTC
- `RiskManager._check_reset` = date locale ; `get_daily_pnl` = minuit UTC + `user_fills` (fenêtre récente, `break` suppose tri desc). Un fill ancien aujourd’hui peut être **omis**. Stop $15 sur $10k est cosmétique ; sur $200 c’est 7.5%.
- **Correction:** UTC everywhere ; `user_fills_by_time` ; stop en **% equity**.

#### [Moyen] Funding
- Filtre scanner optionnel (`funding_filter_enabled`, défaut **false** dans le bot, **true** dans l’example JSON — divergence). Pas de close si funding extrême une fois en position.
- **Correction:** veto entrée si funding hourly > seuil * contre * le sens ; alerter in-trade.

#### [Faible] `pre_validate_order` mort + était fail-open
- Jamais appelé. Ce PR le passe fail-closed, mais ça ne change rien tant que `execute_entry` ne l’appelle pas. Le check `accountValue < 50` est trop naïf (bloque un compte $40, laisse passer $51 + 10×).

#### Positif
- Sizing `risk_pct` / split `max_positions` / cap `equity × multiplier` (défaut 1.0) + min HL $12.
- Daily stop alimenté par PnL exchange (realized + unrealized).
- Trailing / thesis en modules testables.
- Weekend pause rocket/waterfall.

---

### 2.4 Robustesse / résilience

#### [Élevé] WS prix only (`allMids`), pas user events
- Reconnect + backoff OK (`websocket_manager.py`). Stale 30s → REST fallback. **Aucun** channel `user` / `orderUpdates` / `userFills`.
- Pendant une déco, le bot poll REST 10s. `_check_local_exits` peut closer au mid si le trigger exchange n’a pas encore fill — désormais refusé si snapshot stale (ce PR).
- **Correction:** WS `userEvents` pour fills ; heartbeat métier.

#### [Moyen] Rate limiter local ≠ HL
- 30 calls / 60s **par nom d’endpoint**. `execute_order` n’enregistre **rien**. HL est ~1200 weight/min. Le limiter n’empêche pas les 429 de `bulk_orders`.
- Retry decorator retry **toutes** les Exception (marge insuffisante incluse) — spam + éventuel fill retardé.
- **Correction:** retry seulement 429/5xx/timeout ; circuit breaker ; weight budget global.

#### [Moyen] `get_daily_pnl` + `user_fills` tronqué
- `user_fills` n’est pas l’historique complet du jour. `break` au premier fill `< start_of_day` suppose un tri strict.

#### [Faible] Healthcheck Coolify 503 si loop > 120s
- Bien pour un freeze. Mal si un retry 32s × N pendant un 429 → restart **pendant** un close. Le close reduce-only mitige le reverse.

#### Positif
- Positions: jamais de livre plat inventé (cache + `_positions_fetch_failed`).
- Ghost close: wait for Close fill.
- Info init retry 429.
- Ce PR: entries/exits refusés sur snapshot stale.

---

### 2.5 Performance & architecture

#### [Élevé] `EXECUTION_MODE` n’était pas un paper mode (corrigé pour les **entrées**)
- Défaut `"Live"`. Seul `close_active_trade` regardait `"Dry Run"`. `execute_entry_atomically` envoyait du live.
- **Ce PR:** `_is_live_execution()` bloque les entrées. Les **exits** live restent possibles (positions réelles). Ce n’est **pas** un paper exchange : pas de fill simulé, pas de testnet auto.
- **Correction restante:** mode `Paper` = jamais `Exchange` signé ; ou forcer testnet URL.

#### [Moyen] Slippage / IOC / loop 30s
- Latence entrée = boucle + IA (45s cooldown) + REST. Inadapté au scalp 1m en stress. WS mids OK pour manage, pas pour l’entrée (prix signal bougie).

#### [Moyen] Logs
- Discord WARNING+ = bruit (WS reconnect était INFO, bien). `print()` encore dans engine/retry. `add_log` métier est clair (entry/exit/sizing).

#### [Faible] Live / backtest
- Pas de backtest dans le runtime. `backtest_lab/` gitignoré. Séparation conceptuelle OK, pas de paper ledger.

#### Architecture
- `bot.py` ~4100 lignes : machine + sizing + adoption + thesis + Discord. Fragile. Les stratégies sont correctement externalisées (`strategies/`).

---

### 2.6 Qualité de code

#### Positif
- Beaucoup de tests (469 passent). `trailing_logic`, `risk_manager`, `close_pnl`, `trade_book` sont testables.
- Typage partiel, dataclasses risk.

#### [Élevé] Tests Phase 0 mentaient
- `test_ensure_sl_tp_idempotent` assertait `place_protection_orders` (mauvais nom) et des orders **sans** `reduceOnly`/`triggerPx`. Le code réel n’aurait **pas** détecté les SL. **Corrigé** dans ce PR.

#### [Moyen]
- `pre_validate_order` mort.
- `max_sl_drift = 0.12` jamais utilisé.
- `except: pass` encore présent (entry oid parse).
- Retry decorator `print` pas logger.
- `BotContext` trop gros pour review de risque.

---

## 3. Scénarios de stress à tester

1. **Fill + SL reject** — `bulk_orders` entry filled, trigger SL `error`. Vérifier : 1 seule position, reconciler pose SL, **pas** de 2e entrée. *(couvert unitaire via classify ; besoin d’un test d’intégration mock bulk)*
2. **Timeout après submit** — exception réseau, positions API 429. Vérifier : pas de retry. Relire le book 10s plus tard.
3. **Close pendant que le SL exchange fill** — race. Reduce-only doit no-op / error, pas reverse.
4. **429 storm CloudFront 2 min** — loop health 120s, Coolify restart mid-close.
5. **WS down 45s** — prix stale, local TP short à 0 **ne doit pas** closer (déjà guard `price<=0` + stale).
6. **Gap -8% candle** — SL trigger market 5% slip ; isolated 10× vs liq.
7. **Funding +0.1%/h** contre un long overnight weekend (pause rocket seulement).
8. **Orphan short manuel** sans `side` dans un dict custom → default BUY.
9. **API_KEY_REQUIRED=false** exposé — POST `/api/trading/enable` depuis l’extérieur.
10. **Testnet URL dans `.env`** — confirmer Info + WS + Exchange (ce PR).
11. **Partial fill 40%** puis SL à 100% qty.
12. **Trailing BE** pendant un spike : cancel-replace, gap, naked 200ms.
13. **Deux coins, levier 3× puis entrée Hunter 10×** — l’autre coin reste-t-il à 3× ?
14. **Daily stop** : fills > pagination `user_fills`, PnL jour sous-estimé → pas de stop.
15. **IOC unfillable** (slippage trop petit après baisse du slip) — miss, pas de position fantôme.

---

## 4. Checklist Hyperliquid

| Critère | Statut | Commentaire |
|--------------------------------|------------|-----------|
| Gestion sécurisée des clés | **Partiel** | Env + gitignore OK. Master key encore acceptée (warning only). Agent non forcé. |
| Idempotence des ordres | **Partiel** | Plus de retry-après-fill. Toujours **pas de cloid**. |
| Gestion correcte des positions | **Partiel** | Exchange SoT, ghost fill-gated. Close reduce-only. Orphan BUY default. Partial fills SL. |
| Protection liquidation | **Échec** | Guard adoption only. SL manquant = liq isolée 10×. |
| Reconnexion WebSocket | **OK** | Backoff, seed REST, stale 30s. Prix only, pas user fills. |
| Gestion des rate limits | **Partiel** | 429 init + retry. Limiter local incomplet. Open-orders plus fail-open. |
| Séparation live / paper | **Partiel** | Dry Run bloque les **entrées**. Pas de paper ledger / testnet auto. Défaut Live. |
| Logging clair des décisions | **OK** | Sizing, veto, AI trace, Discord. Bruit WARNING encore possible. |

---

## 5. Correctifs livrés dans ce PR

- `execute_order` : classify fill/cancel/error ; **no retry after fill** ; no retry si book illisible.
- `close_position` : `market_close` reduce-only ; refuse snapshot stale ; cancel triggers **après** close.
- `get_open_orders` : cache + fail-closed ; SafeOrderManager ne pose plus de SL sur un livre vide fantôme.
- Entries / local exits abort si positions stale/failed.
- `EXECUTION_MODE != Live` bloque `execute_entry_atomically`.
- `HYPERLIQUID_API_URL` honore REST + WS.
- Warning si clé = adresse master.
- `pre_validate_order` fail-closed (toujours mort — à brancher).
- Tests : `tests/unit/test_hyperliquid_order_safety.py` + hardening Phase 0 réel.

## 6. Correctifs encore dus avant un live sérieux

1. `cloid` persisté + reuse on retry.
2. `API_KEY_REQUIRED=true` par défaut en image prod ; `/docs` off.
3. Refuse master key au boot.
4. Liquidation guard **sur chaque entrée** ; confirmer SL `waitingForTrigger` avant de lâcher le trade.
5. Slippage 0.5–1.5% selon liquidité ; abort si fill vs signal > seuil.
6. Replace SL in-place (pas cancel-all).
7. Brancher pre-validate marge réelle (withdrawable vs notional/lev).
8. Paper = testnet ou ledger simulé, jamais un bool oublié.
9. WS user fills.
10. Non-root Docker.

---

**Ce bot ne doit pas être lancé en live** en mode launch-and-forget. Après ce PR, un compte **Isolated + agent key + auth API + petit notional** peut servir de canary **supervisé**. Un compte Cross, 10×, API ouverte, ou clé master reste une perte de capital en attente.
