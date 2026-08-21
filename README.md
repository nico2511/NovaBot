# NovaBot

Bot de trading automatisé sur **Hyperliquid** avec validation IA (OpenRouter) et notifications Discord. Mode "launch-and-forget" : tu le déploies sur Coolify, tu surveilles via Discord, tu t'occupes d'autre chose.

---

## Sommaire

1. [Ce que fait le bot](#ce-que-fait-le-bot)
2. [Tester en local](#tester-en-local)
3. [Déployer sur Coolify](#déployer-sur-coolify)
4. [Vérifier que ça tourne](#vérifier-que-ça-tourne)
5. [Quand quelque chose cloche](#quand-quelque-chose-cloche)
6. [Variables d'environnement](#variables-denvironnement)
7. [Structure du projet](#structure-du-projet)

---

## Ce que fait le bot

- **Bot = machine** : boucle 24/7, ordres Hyperliquid, state, Discord, appétit capital (`risk_profile`).
- **Stratégie = plan** : aujourd’hui SuperTrend (`strategies/supertrend.py`) — params, persona IA, hard veto, géométrie TP/SL.
- Chaque signal passe : filtres strat → hard veto strat → validation IA (persona strat + plancher R:R du profil capital).
- Entrées / sorties atomiques, SL/TP sur l’exchange, trailing / thesis follow-up.
- Reconciliation périodique : positions manuelles, ghost trades.
- État persisté (`data/bot_state.json`) → survit aux redémarrages.

Pour **ajouter une stratégie** (framework) : voir [`strategies/README.md`](./strategies/README.md).

**Pas de frontend.** Interaction via Discord et API REST (clé en production).

---

## Tester en local

Prérequis : Python 3.12, un `.env` rempli avec au minimum `HL_PRIVATE_KEY`, `HL_ACCOUNT_ADDRESS`, `OPENROUTER_API_KEY`.

```bash
# 1. Installer les dépendances
pip install -r requirements.txt

# 2. Copier et remplir le .env
cp .env.example .env
# édite .env avec tes clés

# 3. Lancer le bot
python main.py
```

Le bot ouvre une API sur `http://localhost:3001`. Teste :

```bash
curl http://localhost:3001/health
```

Tu devrais voir `bot_connected: true` et un `last_heartbeat_age_sec` qui reste sous 120.

**Conseils sécurité locale :**

- `AUTO_START_TRADING=false` dans `.env` pour démarrer en mode observation — tu actives ensuite via `POST /api/trading/enable`.
- `API_KEY_REQUIRED=false` est OK en local. Passe à `true` dès que tu exposes l'API sur Internet.

---

## Déployer sur Coolify

Voir `[DEPLOYMENT_COOLIFY.md](./DEPLOYMENT_COOLIFY.md)` pour le pas à pas complet. Résumé :

1. Dans Coolify → **New Resource → Docker Compose** → pointe sur ton repo GitHub.
2. Onglet **Environment Variables** : ajoute toutes les clés de la section [Variables d'environnement](#variables-denvironnement) ci-dessous. **En production, mets `API_KEY_REQUIRED=true` et génère une `API_KEY` aléatoire.**
3. Onglet **Storage** : vérifie que `/app/data` et `/app/logs` sont bien des volumes persistants (sinon tu perds l'état à chaque redéploiement).
4. **Deploy**.

Le `Dockerfile` inclut un `HEALTHCHECK` sur `/health` toutes les 30s. Si le bot freeze (loop non réactive), Coolify le redémarre automatiquement après 3 échecs consécutifs.

---

## Vérifier que ça tourne

### Discord

C'est ton tableau de bord. Si Discord est silencieux plus de quelques heures en heures ouvrées, quelque chose est probablement bloqué.

### Endpoint `/health`

```bash
# Sans auth en local :
curl http://localhost:3001/health

# Avec auth activée :
curl -H "X-API-Key: ta_clé" https://ton-domaine.coolify/health
```

Réponse attendue (bot OK) :

```json
{
  "status": "healthy",
  "bot_connected": true,
  "is_running": true,
  "trading_enabled": true,
  "active_trades": 1,
  "loop_responsive": true,
  "last_heartbeat_age_sec": 12,
  "api_auth_enabled": true,
  "reason": null
}
```

HTTP **200** si `healthy` ou `degraded` (moteur volontairement arrêté). HTTP **503** si `unhealthy` (bot absent ou boucle figée) — c’est ce qui déclenche le restart Docker/Coolify.

Ce qu'il faut regarder :


| Champ                    | Valeur saine                      | Si anormal                                                                    |
| ------------------------ | --------------------------------- | ----------------------------------------------------------------------------- |
| `status`                 | `healthy`                         | `unhealthy` → 503 + restart ; `degraded` → moteur stoppé volontairement       |
| `bot_connected`          | `true`                            | L'API tourne mais le bot n'est pas initialisé → regarde les logs au démarrage |
| `is_running`             | `true`                            | La boucle de trading est arrêtée → `POST /api/engine/start` ou redémarrer     |
| `trading_enabled`        | `true` ou `false` selon ton choix | `false` = mode observation (pas d'entrées)                                    |
| `loop_responsive`        | `true`                            | La boucle freeze depuis >2 min → HTTP 503 / restart                           |
| `last_heartbeat_age_sec` | `< 120`                           | Heartbeat stale → HTTP 503 / restart                                          |


### Logs

- **Coolify** : onglet Logs, sortie console temps réel.
- **Fichier** : `logs/novabot.log` (rotation 5 MB × 3), pour l'historique détaillé.
- **Activité** : `logs/bot_activity.log`, liste chronologique des événements "métier" (entrées, sorties, régimes).

---

## Quand quelque chose cloche

### Le bot redémarre en boucle sur Coolify

- Vérifie l'onglet Logs au démarrage : il y a forcément une exception avant le crash.
- Causes fréquentes : `.env` incomplet, `HL_PRIVATE_KEY` invalide, `OPENROUTER_API_KEY` expirée.

### `/health` répond `503` / `unhealthy`

Bot absent ou boucle figée — Coolify devrait redémarrer tout seul après 3 échecs. Si ça boucle, regarde les logs de démarrage.

### `/health` répond `degraded` (`is_running: false`)

Le thread de trading s'est arrêté volontairement ou a été stoppé. Relance via :

```bash
curl -X POST -H "X-API-Key: ..." https://.../api/engine/restart
```

Ou redéploie depuis Coolify.

### Positions fantômes ou désynchronisation

Le reconciler tourne toutes les 30s et rétablit normalement l'état. Si le problème persiste :

```bash
curl -X POST -H "X-API-Key: ..." https://.../api/force_sync
```

### L'IA rejette systématiquement

- Circuit breaker déclenché (quota OpenRouter dépassé) : attends 10 min, il se réarme tout seul.
- Vérifie `OPENROUTER_API_KEY` dans les env vars Coolify.
- Solde OpenRouter trop bas : le bot sonde le crédit au démarrage puis toutes les heures (`GET /health` → `openrouter.remaining_usd`). Recharge sur https://openrouter.ai/settings/credits. Seuil d'alerte `OPENROUTER_CREDIT_WARN_USD` (défaut 1 USD), arrêt des appels IA sous `OPENROUTER_CREDIT_MIN_USD` (défaut 0.10 USD). Si `remaining_usd` reste `null`, définis un plafond de dépense sur la clé OpenRouter **ou** `OPENROUTER_MANAGEMENT_API_KEY` (lecture du solde compte via `/credits`).

### Trop de signaux / pas assez

Ajuste dans `data/config/user_settings.json` (volume persistant) — les changements sont rechargés à chaud sans redémarrer. Les clés importantes :

- `risk_defaults.risk_profile` : profil **compte par défaut** (fallback si une stratégie n’en déclare pas). Chaque stratégie choisit son preset dans `data/config/strategies.json` → `risk_profile` (ex. rocket → High Volatility Hunter).
- `risk_defaults.bot_persona` : tempérament capital UI (ne remplace pas `AI_PERSONA` de la strat).
- `risk_defaults.max_positions` : nombre max de positions simultanées.
- `scanner.leverage` : levier demandé (borné par le profil).
- `scanner.enabled` / `auto_switch` / `min_score` : scanner SuperTrend (rotation de symbole quand flat).

### Scanner SuperTrend

Le bot peut scorer l'universe Hyperliquid avec les **mêmes params** que la stratégie `supertrend` (period, multiplier, EMA filter, ADX, volume/RSI), puis basculer `active_symbol` si `auto_switch=true` et qu'aucune position n'est ouverte.

```bash
# Activer (persisté dans data/config/user_settings.json)
curl -X POST -H "X-API-Key: ..." -H "Content-Type: application/json" \
  https://.../api/settings/update \
  -d '{"section":"scanner","data":{"enabled":true,"auto_switch":true,"interval":15,"min_score":60}}'

# Scan manuel
curl -X POST -H "X-API-Key: ..." https://.../api/scanner/scan

# Derniers résultats
curl -H "X-API-Key: ..." https://.../api/scanner/opportunities
```

Par défaut le scanner est **désactivé** (`enabled=false`). L'hystérésis de switch est de 10 points pour éviter de tourner en rond.

Timeline debug (signal / AI / entry / exit filtrable) :

```bash
curl -H "X-API-Key: ..." "https://.../api/history/timeline?symbol=ETH&limit=100"
# aussi: trade_id=...  trace_id=...
```

Stratégies : SuperTrend 15m + Trend LT 1h — voir [`strategies/README.md`](strategies/README.md).

---

## Variables d'environnement

Copie `.env.example` en `.env` et remplis. **Obligatoires** :


| Clé                  | Usage                                         |
| -------------------- | --------------------------------------------- |
| `HL_PRIVATE_KEY`     | Clé privée Hyperliquid (agent API, sans `0x`) |
| `HL_ACCOUNT_ADDRESS` | Adresse du portefeuille                       |
| `OPENROUTER_API_KEY` | Validation IA                                 |
| `OPENROUTER_CREDIT_CHECK_INTERVAL_SEC` | Sonde crédit IA (défaut `3600` = 1h ; `86400` = 1j ; `0` = démarrage seul) |
| `OPENROUTER_CREDIT_WARN_USD` | Alerte Discord sous ce solde (défaut `1.0`) |
| `OPENROUTER_CREDIT_MIN_USD` | Suspend les appels IA sous ce solde (défaut `0.10`) |
| `TRADING_SYMBOL`     | Symbole tradé (ex: `HYPE`, `BTC`)             |


**Fortement recommandées** :


| Clé                          | Usage                                     |
| ---------------------------- | ----------------------------------------- |
| `DISCORD_WEBHOOK_URL_ALERTS` | Notifications trades (entrée/sortie)      |
| `DISCORD_WEBHOOK_URL_LOGS`   | Logs bot (moins verbeux que le fichier)   |
| `AUTO_START_TRADING`         | `false` pour démarrer en mode observation |


**Production (Coolify)** :


| Clé                    | Usage                                                           |
| ---------------------- | --------------------------------------------------------------- |
| `API_KEY`              | Chaîne aléatoire longue (32+ car.) pour l'authentification API  |
| `API_KEY_REQUIRED`     | `true` pour forcer le header `X-API-Key` sur tous les endpoints |
| `CORS_ALLOWED_ORIGINS` | Vide ou liste CSV de domaines si un front appelle l'API         |
| `LOG_LEVEL`            | `INFO` par défaut, `DEBUG` pour investiguer                     |


---

## Structure du projet

```
app/
├── api/               FastAPI routers + auth
├── core/              Machine bot (orchestration, risk capital, state)
│   ├── bot.py         BotContext — loop / orders / délégation à la strat
│   ├── veto_checker.py    Helpers veto réutilisables (appelés par les strats)
│   ├── trailing_logic.py / trade_thesis.py / …
│   └── prompts.py     Prompt global neutre + risk_profile capital
├── services/          HL, IA, Discord, storage, …
strategies/            Plans de trading (SuperTrend + base/engine + template)
strategies/README.md   Comment écrire une nouvelle stratégie
tests/
data/                  bot_state, configs, history
logs/
```

Guide stratégie : [`strategies/README.md`](./strategies/README.md).  
Déploiement Coolify : [`DEPLOYMENT_COOLIFY.md`](./DEPLOYMENT_COOLIFY.md).

Tests : `python -m pytest`.

