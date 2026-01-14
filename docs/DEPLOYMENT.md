# 🐧 NovaBot: Procédure de Déploiement "Propre" (Debian/Proxmox)

Ce guide détaille la procédure pour effacer une ancienne installation et redéployer proprement la dernière version `main` depuis GitHub.

---

## 🚫 1. Arrêter et Nettoyer

Sur votre serveur (via SSH ou Shell Proxmox) :

```bash
# 1. Arrêter le bot (si lancé via PM2)
pm2 stop hl-bot-engine
pm2 delete hl-bot-engine

# 2. SAUVEGARDER LA CONFIGURATION (CRITIQUE)
# Copiez vos fichiers de secrets hors du dossier
cp novabot/.env ~/.env.backup.novabot
# (Optionnel) Sauvegarder l'état
cp novabot/bot_state.json ~/.bot_state.json.backup

# 3. Supprimer le dossier existant
rm -rf novabot
```

---

## 📥 2. Réinstallation Propre

```bash
# 1. Cloner le dépôt (Branche main par défaut)
git clone https://github.com/nico2511/NovaBot.git
cd novabot

# 2. Restaurer la configuration (CRITIQUE)
cp ~/.env.backup.novabot .env
# (Optionnel) Restaurer l'état si souhaité
# cp ~/.bot_state.json.backup bot_state.json

# 3. Installer les dépendances système (Si pas déjà fait)
sudo apt update && sudo apt install -y python3 python3-venv python3-pip nodejs npm dos2unix

# 4. Préparer l'environnement
# Convertir le script de lancement (Format Linux)
dos2unix start_integrated.sh
bash start_integrated.sh
```

---

## 🚀 3. Vérification

Le script `start_integrated.sh` va automatiquement :
1.  Créer l'environnement virtuel `.venv`.
2.  Installer les librairies Python.
3.  Lancer le bot avec PM2.

Vérifiez que tout tourne :
```bash
pm2 list
pm2 logs hl-bot-engine
```

Si tout est vert, c'est gagné ! ✅
