# NovaBot - Déploiement Coolify

Procédure courte pour déployer le backend sur Coolify. Architecture : **bot = machine**, **stratégie = plan** (voir [`strategies/README.md`](./strategies/README.md) et le [`README.md`](./README.md)).

## 1. Prérequis GitHub

Vérifiez que ces fichiers sont à la racine de votre dépôt :

- `Dockerfile`
- `docker-compose.yaml`
- `.dockerignore`
- `requirements-prod.txt` (installé dans l'image Docker)
- `requirements.txt` (local / CI = prod + pytest)
- `main.py`

## 2. Configuration sur Coolify

### Étape 1 : Création de la ressource

1. Dans Coolify, allez dans **Resources** > **Create New**.
2. Choisissez **Docker Compose**.
3. Sélectionnez votre dépôt GitHub `nico2511/NovaBot`.
4. Laissez Coolify analyser le fichier `docker-compose.yaml`.

### Étape 2 : Variables d'Environnement (VITAL)

Dans l'onglet **Environment Variables** de Coolify, ajoutez les clés suivantes en copiant les valeurs de votre `.env` local :


| Clé                          | Usage                                   |
| ---------------------------- | --------------------------------------- |
| `HL_PRIVATE_KEY`             | Clé de l'Agent API                      |
| `HL_ACCOUNT_ADDRESS`         | Adresse de votre portefeuille principal |
| `OPENROUTER_API_KEY`         | Clé pour l'analyse IA                   |
| `OPENROUTER_CREDIT_CHECK_INTERVAL_SEC` | Optionnel — sonde crédit (défaut 3600s) |
| `OPENROUTER_CREDIT_WARN_USD` | Optionnel — alerte Discord (défaut 1.0) |
| `OPENROUTER_CREDIT_MIN_USD`  | Optionnel — stop IA sous ce solde (0.10)|
| `DISCORD_WEBHOOK_URL_ALERTS` | Webhook pour les trades                 |
| `DISCORD_WEBHOOK_URL_LOGS`   | Webhook pour les logs                   |
| `PORT`                       | `3001`                                  |
| `API_KEY` + `API_KEY_REQUIRED` | Auth API en production                |

Symbole, timeframe, scanner, risk → **`data/config/user_settings.json`** (pas dans Coolify env).

### Journal web

Après déploiement : `https://votre-domaine/journal` — positions + historique bot (lecture seule, même processus que l'API).


### Étape 3 : Volumes Persistants

Vérifiez dans l'onglet **Storage** que les volumes sont bien configurés :

- `/app/data` : Pour conserver vos analyses et l'état du bot.
- `/app/logs` : Pour garder l'historique des logs de trading.

## 3. Déploiement et Suivi

1. Cliquez sur **Deploy**.
2. **Logs** : Surveillez l'onglet **Logs** de Coolify. Vous devriez voir les messages d'initialisation de NovaBot.
3. **Vérification** : Si les webhooks Discord sont configurés, vous recevrez une notification au démarrage du bot.

---

> [!NOTE]
> Interaction principale : logs, Discord, et **`/journal`** (positions + historique bot, lecture seule, sans front séparé).