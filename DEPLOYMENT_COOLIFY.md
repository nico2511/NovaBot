# NovaBot - Déploiement Headless sur Coolify

Ce document décrit la procédure simplifiée pour déployer NovaBot (Backend uniquement) sur Coolify.

## 1. Prérequis GitHub
Vérifiez que ces fichiers sont à la racine de votre dépôt :
- `Dockerfile`
- `docker-compose.yaml`
- `.dockerignore`
- `requirements.txt`
- `main.py`

## 2. Configuration sur Coolify

### Étape 1 : Création de la ressource
1. Dans Coolify, allez dans **Resources** > **Create New**.
2. Choisissez **Docker Compose**.
3. Sélectionnez votre dépôt GitHub `nico2511/NovaBot`.
4. Laissez Coolify analyser le fichier `docker-compose.yaml`.

### Étape 2 : Variables d'Environnement (VITAL)
Dans l'onglet **Environment Variables** de Coolify, ajoutez les clés suivantes en copiant les valeurs de votre `.env` local :

| Clé | Usage |
| :--- | :--- |
| `HL_PRIVATE_KEY` | Clé de l'Agent API (sans 0x) |
| `HL_ACCOUNT_ADDRESS` | Adresse de votre portefeuille principal |
| `OPENROUTER_API_KEY` | Clé pour l'analyse IA |
| `DISCORD_WEBHOOK_URL_ALERTS` | Webhook pour les trades |
| `DISCORD_WEBHOOK_URL_LOGS` | Webhook pour les logs |
| `TRADING_SYMBOL` | Symbole à trader (ex: HYPE, BTC) |
| `PORT` | `3001` |

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
> Puisqu'il n'y a plus d'interface graphique (frontend), toute l'interaction se fait via les logs et les alertes Discord. C'est le mode le plus stable pour une utilisation 24/7.
