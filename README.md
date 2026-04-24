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

- Tourne en boucle 24/7 sur un symbole Hyperliquid (par défaut `HYPE`).
- Applique une ou plusieurs stratégies techniques (`strategies/`).
- Chaque signal est validé par une IA (OpenRouter) avec une contrainte **R:R minimum** mécanique.
- Entrées / sorties atomiques, SL/TP placés sur l'exchange, trailing stops automatiques.
- Reconciliation toutes les 30s : détecte les positions manuelles, nettoie les "ghost trades".
- Notifications Discord à chaque événement important (entrée, sortie, break-even, erreurs).
- État persisté sur disque (`data/bot_state.json`) → survit aux redémarrages.

**Pas de frontend.** Toute l'interaction passe par Discord et éventuellement par l'API REST (sécurisée par clé en production).

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

Réponse attendue :

```json
{
  "status": "healthy",
  "bot_connected": true,
  "is_running": true,
  "trading_enabled": true,
  "active_trades": 1,
  "loop_responsive": true,
  "last_heartbeat_age_sec": 12
}
```

Ce qu'il faut regarder :


| Champ                    | Valeur saine                      | Si anormal                                                                    |
| ------------------------ | --------------------------------- | ----------------------------------------------------------------------------- |
| `bot_connected`          | `true`                            | L'API tourne mais le bot n'est pas initialisé → regarde les logs au démarrage |
| `is_running`             | `true`                            | La boucle de trading est arrêtée → `POST /api/engine/start` ou redémarrer     |
| `trading_enabled`        | `true` ou `false` selon ton choix | `false` = mode observation (pas d'entrées)                                    |
| `loop_responsive`        | `true`                            | La boucle freeze depuis >2 min → restart recommandé                           |
| `last_heartbeat_age_sec` | `< 120`                           | La boucle ne tourne plus → restart                                            |


### Logs

- **Coolify** : onglet Logs, sortie console temps réel.
- **Fichier** : `logs/novabot.log` (rotation 5 MB × 3), pour l'historique détaillé.
- **Activité** : `logs/bot_activity.log`, liste chronologique des événements "métier" (entrées, sorties, régimes).

---

## Quand quelque chose cloche

### Le bot redémarre en boucle sur Coolify

- Vérifie l'onglet Logs au démarrage : il y a forcément une exception avant le crash.
- Causes fréquentes : `.env` incomplet, `HL_PRIVATE_KEY` invalide, `OPENROUTER_API_KEY` expirée.

### `/health` répond mais `is_running: false`

Le thread de trading s'est arrêté. Redémarre via :

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

### Trop de signaux / pas assez

Ajuste dans `data/config/user_settings.json` (volume persistant) — les changements sont rechargés à chaud sans redémarrer. Les clés importantes :

- `risk_defaults.risk_profile` : `"Capital Preservation First"` (conservateur) / `"Balanced Growth"` / `"High Volatility Hunter"` (agressif).
- `risk_defaults.max_positions` : nombre max de positions simultanées.
- `scanner.leverage` : levier utilisé par défaut.

---

## Variables d'environnement

Copie `.env.example` en `.env` et remplis. **Obligatoires** :


| Clé                  | Usage                                         |
| -------------------- | --------------------------------------------- |
| `HL_PRIVATE_KEY`     | Clé privée Hyperliquid (agent API, sans `0x`) |
| `HL_ACCOUNT_ADDRESS` | Adresse du portefeuille                       |
| `OPENROUTER_API_KEY` | Validation IA                                 |
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
├── api/               FastAPI : routers (engine, trading, market, settings, history) + auth
├── core/              Logique métier
│   ├── bot.py         BotContext : orchestration boucle trading
│   ├── risk_manager.py    Gestion du risque (stop-loss quotidien, max positions, sizing)
│   ├── veto_checker.py    Gardes techniques (RSI/ADX/volume)
│   ├── trailing_logic.py  Décisions trailing-stop (pure logic)
│   ├── state_manager.py   Persistance atomique bot_state.json
│   ├── trade_recorder.py  Journal CSV des trades clôturés
│   └── config.py      Chargement env + user_settings.json
├── services/          Services externes
│   ├── hyperliquid_service.py    Wrapper Hyperliquid SDK
│   ├── ia.py                     IAService : validation IA + circuit breaker
│   ├── position_reconciler.py    Cleanup ghosts / adoption orphelins
│   ├── safe_order_manager.py     Garantit SL/TP présents sur exchange
│   ├── discord_service.py        Notifications Discord
│   └── storage.py                Storage paths centralisés
└── utils/             Helpers market data, websocket
strategies/            Stratégies techniques (pluggable)
tests/                 Unit + integration (73 tests)
data/                  Persistance (bot_state, trade_history.csv, user_settings.json)
logs/                  novabot.log (rotation 5MB x3)
```

Tests : `python -m pytest`. Les 73 tests doivent passer avant tout déploiement.