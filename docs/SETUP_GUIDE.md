# 📥 Guide de Récupération & Installation (Nouveau PC)

Ce guide t'explique comment récupérer le projet depuis GitHub et l'installer sur une nouvelle machine (Linux/Mac/WSL).

## 1. Pré-requis

Assure-toi d'avoir installé :
- **Git** : `sudo apt install git`
- **Python 3.10+** : `sudo apt install python3 python3-venv python3-pip`
- **Node.js 18+ & npm** : (Via NVM recommandé ou apt)
- **PM2** : `npm install -g pm2`

## 2. Cloner le Projet

Ouvre un terminal dans le dossier de ton choix et lance :

```bash
# Récupérer le code
git clone https://github.com/nico2511/NovaBot.git

# Entrer dans le dossier
cd NovaBot
```

## 3. Configuration de l'Environnement Python

Il faut recréer l'environnement virtuel et installer les dépendances.

```bash
# 1. Créer le venv
python3 -m venv .venv

# 2. Activer le venv
source .venv/bin/activate

# 3. Installer les libs
pip install -r requirements.txt
pip install google-generativeai # Au cas où il manque
```

## 4. Configuration Node.js (Frontend)

```bash
# Aller dans le dossier frontend (si applicable) ou installer à la racine si c'est un monorepo config
npm install
```
*(Note : Vu la structure actuelle, `package.json` est à la racine, donc `npm install` à la racine suffit).*

## 5. Configuration des Clés (.env)

Tu dois recréer ton fichier `.env` car il n'est pas sur GitHub (sécurité).
Crée un fichier `.env` à la racine et mets-y tes clés :

```bash
nano .env
```

**Exemple de contenu :**
```ini
# Hyperliquid
HL_ACCOUNT_ADDRESS=0xTonAdresse...
HL_PRIVATE_KEY=TaClePrivee...

# Google Gemini
GEMINI_API_KEY=TaCleGemini...

# Discord
DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/...
```

## 6. Lancement

Tu peux maintenant tout lancer via PM2 :

```bash
# Démarrer le backend et le frontend
npx pm2 start ecosystem.config.js

# Vérifier les logs
npx pm2 logs
```

## 7. Vérification

- Ouvre `http://localhost:3000` (ou le port configuré) pour voir le Dashboard.
- Vérifie que le bot se connecte bien ("STARTUP SYNC: Checking Hyperliquid positions..." dans les logs).

---
**Note** : Si tu as des erreurs de permission, vérifie que tu es bien propriétaire des fichiers (`chown -R $USER:$USER .`).
