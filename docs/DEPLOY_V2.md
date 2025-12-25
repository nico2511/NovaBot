# 🚀 Guide de Déploiement - Version 2.0 (Integrated)

Ce guide détaille la procédure pour déployer la version finale du **HyperLiquid AI Trader** (Python Bot + FastAPI Backend + Next.js Frontend) sur un serveur de production (ex: Proxmox/Ubuntu).

---

## 1. Pré-requis Système

Assurez-vous que votre serveur dispose de :
- **Python 3.10+**
- **Node.js 18+** & **npm**
- **PM2** (Process Manager pour Node/Python) : `npm install -g pm2`
- **Git**

## 2. Installation / Mise à jour

### Cloner ou Pull le repo
```bash
cd /votre/chemin/PyBot
git pull origin main  # ou master
```

### Installation des dépendances (Script Automatisé)
Nous avons créé un script qui gère tout (Python & Node).
```bash
./start_integrated.sh
```
*Laissez le script tourner une fois pour installer toutes les libs Python et compiler le Frontend Next.js. Une fois que tout est vert, faites `Ctrl+C` pour arrêter.*

Ou manuellement :
```bash
# Python
pip install -r requirements.txt
pip install -r backend/requirements.txt
pip install discord-webhook  # Important pour les notifs V2

# Frontend
cd frontend
npm install
npm run build  # Optimisation pour la prod
cd ..
```

## 3. Configuration

Vérifiez votre fichier `.env` à la racine :
```bash
nano .env
```
Assurez-vous d'avoir :
```ini
HL_ACCOUNT_ADDRESS=0x...
HL_PRIVATE_KEY=0x...
DISCORD_WEBHOOK_ALERTS=https://discord.com/api/webhooks/...
DISCORD_WEBHOOK_LOGS=https://discord.com/api/webhooks/...
```

## 4. Lancement en Production (PM2)

Pour une exécution robuste (redémarrage auto en cas de crash, lancement au boot), utilisez PM2.

### A. Créer un fichier `ecosystem.config.js` à la racine
(Nous l'avons préparé ci-dessous, copiez-le)

```javascript
module.exports = {
  apps : [
    {
      name: "hl-bot-engine",
      script: "main_nextjs.py",
      interpreter: "python3",
      autorestart: true,
      watch: false,
      env: {
        PYTHONUNBUFFERED: "1"
      }
    },
    {
      name: "hl-frontend",
      script: "npm",
      args: "start",
      cwd: "./frontend",
      autorestart: true,
      watch: false,
      env: {
        PORT: 3000,
        NODE_ENV: "production"
      }
    }
  ]
}
```

### B. Lancer les services
```bash
pm2 start ecosystem.config.js
pm2 save      # Sauvegarde pour le reboot
pm2 startup   # Génère la commande pour lancer au boot (à exécuter)
```

## 5. Monitoring & Maintenance

- **Voir les logs** : 
  `pm2 logs` ou `pm2 logs hl-bot-engine`
- **Voir le statut** : 
  `pm2 status`
- **Arrêter** : 
  `pm2 stop all`
- **Redémarrer** : 
  `pm2 restart all`

## 6. Vérification

1. Accédez à `http://IP_DU_SERVEUR:3000`
2. Vérifiez que "Live" est vert.
3. Vérifiez les logs dans l'UI.
4. Testez une notification Discord (via un trade ou démarrage).

---
**Note sur les Ports :**
- Frontend : 3000 (accessible publiquement si besoin)
- Backend API : 8000 (utilisé par le frontend, pas besoin d'exposer sauf si accès externe voulu)
