# NovaBot - Procédure de Déploiement Local sur Coolify (Proxmox)

Ce document décrit les étapes pour déployer NovaBot sur une instance Coolify hébergée sur Proxmox, accessible uniquement via votre réseau local.

## 1. Préparation du Dépôt GitHub

Assurez-vous que les fichiers suivants sont présents à la racine de votre dépôt :
- `Dockerfile.backend`
- `frontend-v3/Dockerfile`
- `docker-compose.yml`
- `.dockerignore`
- `requirements.txt`
- `frontend-v3/next.config.js` (avec `output: 'standalone'`)

## 2. Configuration sur Coolify

### Étape 1 : Ajouter une Nouvelle Ressource
1. Dans votre instance Coolify, allez dans **Resources** > **Create New**.
2. Choisissez **Docker Compose**.
3. Sélectionnez votre source GitHub et le dépôt **nico2511/NovaBot**.
4. Sélectionnez la branche principale (ex: `main`).

### Étape 2 : Configuration du Docker Compose
Coolify devrait détecter automatiquement votre fichier `docker-compose.yml`. Si ce n'est pas le cas, copiez-collez le contenu de votre fichier local dans l'interface de Coolify.

### Étape 3 : Variables d'Environnement
Dans l'onglet **Environment Variables** de votre projet Coolify, ajoutez les variables nécessaires (copiez le contenu de votre `.env` local) :
- `HL_PRIVATE_KEY`
- `HL_ACCOUNT_ADDRESS`
- `GEMINI_API_KEY`
- `OPENROUTER_API_KEY`
- `DISCORD_WEBHOOK_URL_ALERTS`
- `DISCORD_WEBHOOK_URL_LOGS`
- `API_KEY` (pour la sécurité de l'API)
- `PORT=3001` (Backend)
- `PORT=3002` (Frontend)

### Étape 4 : Stockage Persistant (Volumes)
Coolify créera automatiquement des volumes basés sur le `docker-compose.yml`. Vérifiez que les chemins suivants sont persistants pour conserver vos données :
- `/app/data` (Backend) : contient vos configurations et états.
- `/app/logs` (Backend) : contient les logs de trading.

### Étape 5 : Accès Local et Ports
1. **Accès IP** : L'application sera accessible via l'adresse IP de votre instance Proxmox/Coolify.
2. **Ports** :
   - Interface : `http://<IP_COOLIFY>:3002`
   - API : `http://<IP_COOLIFY>:3001`
3. **Domaines Locaux** : Si vous utilisez un DNS local (Pi-hole, AdGuard, ou host file), vous pouvez configurer un FQDN comme `novabot.local`.

#### Configuration AdGuard Home :
- Connectez-vous à votre interface **AdGuard Home**.
- Allez dans **Filtres** (Filters) -> **Réécritures DNS** (DNS Rewrites).
- Cliquez sur **Ajouter une réécriture DNS**.
- **Nom de domaine** : `novabot.local` (ou celui de votre choix).
- **Adresse IP** : L'adresse IP de votre instance Proxmox/Coolify.
- Cliquez sur **Enregistrer**.

*Note : Vous devrez toujours ajouter le port dans votre navigateur, par exemple `http://novabot.local:3002`, à moins d'utiliser un reverse proxy qui redirige le trafic HTTP standard.*

## 3. Déploiement

Cliquez sur **Deploy** dans l'interface Coolify.

## 4. Vérification

- **Logs** : Surveillez les logs dans Coolify pour vérifier que le bot démarre et que le frontend est construit correctement.
- **Accès** : Rendez-vous sur `http://<IP_LOCALE>:3002` (ou votre domaine local) pour accéder à l'interface NovaBot.
- **API** : Vérifiez que le frontend communique bien avec le backend via le réseau Docker interne.

---

> [!TIP]
> Si le frontend ne parvient pas à contacter le backend, vérifiez la variable `NEXT_PUBLIC_API_URL` dans le `docker-compose.yml`. Par défaut, elle est réglée sur `http://novabot-backend:3001` pour la communication interne au réseau Docker.
