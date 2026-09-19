# Audit Hyperliquid — NovaBot

**Date:** 2026-09-19  
**Contexte:** le bot **ne s’exécute qu’en local** (pas Coolify / pas d’Internet). Ça relègue l’auth API en P2, **pas** les bugs de fill/SL/liq.  
**Périmètre:** execution live (`hyperliquid_service`, `bot.py`, `live_guards`, reconciler, WS, secrets)

---

## 1. Résumé exécutif

| | |
|---|---|
| **Note globale** | **6.5 / 10** (était ~4/10 au départ de l’audit) |
| **Niveau de risque** | **Moyen-Élevé** (était **Critique**) |

**Verdict local:** canary Isolated + clé **agent** + petit notional + tu surveilles Discord. Pas du launch-and-forget.

Les couches « machine » (sizing ÷N, cap notional = equity, daily stop HL, ghost close uniquement après fill Close, WS reconnect) sont réelles. Avant ce PR, les chemins d’ordres pouvaient **doubler une position** ou **ouvrir un reverse**.

### 3 points restants (local)

1. **Retry manuel / pas de query-by-cloid** — un `cloid` est maintenant posé sur l’entrée IOC, mais on ne re-query pas encore `orderStatus` après timeout. Ne pas relancer une entrée à la main.
2. **Auth API off** — secondaire en local-only, **utile** si `0.0.0.0:3001` est joignable sur le LAN familial.
3. **WS user fills toujours absents** — manage/exit restent en poll REST 10s.

---

## 2. Analyse détaillée par catégorie

### 2.1 Sécurité & secrets

#### [Élevé] Clé privée = clé master possible
- **Localisation:** `app/services/hyperliquid_service.py` (`Account.from_key` + `Exchange(..., account_address=HL_ACCOUNT_ADDRESS)`)
- **Impact:** si `HL_PRIVATE_KEY` est la clé du wallet principal (même adresse que `HL_ACCOUNT_ADDRESS`), une fuite `.env` / logs Coolify = **withdraw possible**. Le pattern Agent API est documenté mais **jamais imposé**.
- **Correctif de ce PR:** `RuntimeError` au boot si clé = master, sauf `HL_ALLOW_MASTER_KEY=true`.

#### [Élevé → atténué local] API de trading ouverte sans clé
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

#### [Élevé → corrigé ici] Fenêtre nue `sync_sl_tp` (cancel ALL puis replace)
- **Avant:** cancel all puis replace → gap nu entre les deux.
- **Correctif:** `modify_order` in-place sur l’oid SL/TP existant ; place seulement si absent. Fetch failed → refuse le sync (pas de cancel). Modify fail → **garde** le SL existant.

#### [Élevé] IOC cancel traité comme succès (corrigé)
- Un IOC non matché n’a pas toujours `error` ; `canceled` sans `filled` est un miss. Avant: `return success` puis « position NOT confirmed after 5s » — SL/TP `normalTpsl` orphelins possibles.
- **Correctif:** canceled sans fill = error.

#### [Élevé → partiel] `cloid` posé, pas encore re-query
- IOC d’entrée porte un `Cloid` 16 bytes. Même cloid réutilisé après timeout ; nouveau cloid seulement après cancel/reject **confirmé**.
- **Reste:** pas de `query_order_by_cloid` après timeout réseau (l’opérateur ne doit pas relancer l’entrée à la main).

#### [Moyen → corrigé ici] Partial fills
- **Avant:** SL/TP du bulk = qty demandée.
- **Correctif:** `confirm_or_place_sl` post-fill utilise `pos['size']` / `filled_sz` et **modify** le SL si l’écart de taille > 5%. Reduce-only tronque encore un SL trop gros ; un SL trop petit est réaligné.

#### [Moyen → corrigé ici] Orphan adoption default BUY
- **Avant:** `side` absent + pas de `szi` → BUY.
- **Correctif:** skip adoption (log error). `get_positions` pose déjà BUY/SELL ; le skip ne couvre que des dicts bruts.

#### [Moyen] PnL de close bot = mid, pas fill
- `execute_exit_atomically` calcule PnL sur `get_current_price` (mid WS). Fees ignorées. Daily stop côté `record_trade_close` peut diverger ; `apply_exchange_daily_pnl` rattrape (bien).

#### Positif
- Entrée atomique `grouping="normalTpsl"` (le bon pattern HL).
- Rounding tick 5 sig figs (incident BCH documenté + tests).
- `can_open_trade` bloque le même symbole (netting HL).
- Close externe uniquement après fill `dir=Close` (`close_pnl.py`).

---

### 2.3 Gestion du risque

#### [Critique → corrigé ici] Liquidation guard seulement à l’adoption
- **Avant:** clamp liq uniquement à l’adoption. Entrées stratégie nues vs Isolated 10×.
- **Correctif:** `live_guards.clamp_sl_inside_liquidation` **avant sizing** (après ATR floor) **et** dans `execute_entry`. Heuristique Isolated `entry*(1±1/lev)` + buffer 15%. Live **exige un SL**. Exception du guard = **blocage** (fail-closed). Cross reste dangereux (formule Isolated).

#### [Élevé → corrigé ici] Slippage 5%
- **Avant:** SDK default 5% sur tout market.
- **Correctif:** IOC 0.8% BTC/ETH/SOL, 1.5% alts. Post-fill abort+close si `avgPx` dévie > max(2× configured, 1.5%). `market_open` CASE 2 passe aussi ce slip (plus le 5% SDK).

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
- Beaucoup de tests (`test_live_guards`, `test_hyperliquid_order_safety`, reconciler). `trailing_logic`, `risk_manager`, `close_pnl`, `trade_book` sont testables.
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
8. **Orphan short manuel** sans `side` dans un dict custom → **skip** (plus de default BUY). *(unitaire)*
9. **API_KEY_REQUIRED=false** exposé — POST `/api/trading/enable` depuis l’extérieur.
10. **Testnet URL dans `.env`** — confirmer Info + WS + Exchange (ce PR).
11. **Partial fill 40%** puis SL à 100% qty — `confirm_or_place_sl` modify si écart > 5%.
12. **Trailing BE** pendant un spike : modify in-place (plus de cancel-all). Vérifier quand même un modify fail (SL conservé).
13. **Deux coins, levier 3× puis entrée Hunter 10×** — l’autre coin reste-t-il à 3× ?
14. **Daily stop** : fills > pagination `user_fills`, PnL jour sous-estimé → pas de stop.
15. **IOC unfillable** (slippage trop petit après baisse du slip) — miss, pas de position fantôme.

---

## 4. Checklist Hyperliquid

| Critère | Statut | Commentaire |
|--------------------------------|------------|-----------|
| Gestion sécurisée des clés | **OK local** | Master key **refusée** au boot (`HL_ALLOW_MASTER_KEY` override). Agent recommandé. |
| Idempotence des ordres | **Partiel** | No retry after fill + `cloid` sur l’IOC. Pas encore de query-by-cloid post-timeout. |
| Gestion correcte des positions | **OK** | SoT exchange, close reduce-only, SL à la taille filled, orphan sans side = skip. |
| Protection liquidation | **OK** | Guard **entrée** (`live_guards`) + confirm SL post-fill (close si nu). |
| Reconnexion WebSocket | **OK** | Backoff, seed REST, stale 30s. Prix only, pas user fills. |
| Gestion des rate limits | **Partiel** | 429 init + retry. Limiter local incomplet. Open-orders fail-closed. |
| Séparation live / paper | **Partiel** | Dry Run bloque les **entrées**. Pas de paper ledger. Défaut Live. |
| Logging clair des décisions | **OK** | Sizing, veto, AI trace, Discord, liq guard, slippage abort. |

---

## 5. Correctifs livrés dans ce PR

**Vague 1 (anti-catastrophe)**
- `execute_order` : classify fill/cancel/error ; **no retry after fill**.
- `close_position` : `market_close` reduce-only ; refuse snapshot stale.
- `get_open_orders` fail-closed ; Dry Run bloque les entrées ; `HYPERLIQUID_API_URL` REST+WS.

**Vague 2 (plan local P0/P1)**
- Master key = **RuntimeError au boot** (plus avalé par `except Exception`) sauf `HL_ALLOW_MASTER_KEY=true`.
- Slippage IOC 0.8% majors / 1.5% alts ; abort+close si fill > max(2×slip, 1.5%).
- `live_guards.clamp_sl_inside_liquidation` sur **chaque entrée** (après ATR floor) ; exception = skip/block.
- Live entry **exige un SL** ; post-fill `confirm_or_place_sl` (taille filled) ; close si SL absent.
- `cloid` sur l’IOC : réutilisé après timeout, nouveau après cancel confirmé.
- `sync_sl_tp` = **modify in-place** (plus de cancel-all).
- Orphan sans side : **pas d’adoption BUY**.
- Tests : `test_live_guards.py`, `test_hyperliquid_order_safety.py`, reconciler unknown-side.

## 6. Encore dû (P2 local)

1. Query `orderStatus` by cloid après timeout réseau.
2. `API_KEY_REQUIRED=true` si le LAN voit le port 3001.
3. Brancher pre-validate marge réelle (withdrawable).
4. Paper = testnet URL, pas un bool oublié.
5. WS user fills.
6. Daily stop en % equity / UTC / `user_fills_by_time`.
7. Retry decorator : 429/5xx only.

---

**Canary local:** Isolated, agent key, `AUTO_START_TRADING=false`, enable seulement quand tu es là, 1 position, levier ≤ 3 le temps de valider un fill+SL sur HL. Cross / 10× / clé master = non.
