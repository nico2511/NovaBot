# 🧹 Fresh Deployment Guide

## Pourquoi repartir de zéro ?

- 💾 **Récupérer de l'espace disque** (vieux node_modules, .venv, logs, etc.)
- 🧹 **Nettoyer les fichiers obsolètes**
- ✅ **Installation propre** avec les dernières dépendances
- 🔧 **Corriger les problèmes de configuration**

---

## 📊 Espace Typique Utilisé

```
/var/www/novabot/
├── .venv/              ~200-300 MB (Python packages)
├── frontend/
│   ├── node_modules/   ~400-500 MB (Node packages)
│   └── .next/          ~50-100 MB (Build cache)
├── logs/               ~10-50 MB (peut grossir)
└── .git/               ~50-100 MB

Total: ~800 MB - 1.2 GB
```

**Après fresh install:** ~600-800 MB (sans logs anciens)

---

## 🚀 Déploiement Fresh

### Sur le serveur de production:

```bash
# 1. Copier le script
cd /tmp
wget https://raw.githubusercontent.com/nico2511/NovaBot/master/deploy_fresh.sh
chmod +x deploy_fresh.sh

# 2. Lancer le déploiement
sudo ./deploy_fresh.sh
```

**Le script fait automatiquement:**
1. ⏸️ Stop PM2
2. 🗑️ Supprime `/var/www/novabot`
3. 📥 Clone depuis GitHub
4. 🐍 Crée nouveau venv Python
5. 📦 Installe dépendances Python
6. ⚛️ Installe et build frontend
7. ⚙️ Configure PM2
8. 🚀 Démarre les services

---

## ⚠️ Avant de Lancer

### 1. Sauvegarder les données importantes

```bash
# Sauvegarder la config si modifiée
cp /var/www/novabot/strategies.json ~/strategies.json.backup

# Sauvegarder les logs si nécessaire
cp -r /var/www/novabot/logs ~/logs_backup

# Sauvegarder la base de données
cp /var/www/novabot/data/*.db ~/db_backup/
```

### 2. Vérifier l'espace disque

```bash
df -h
# Assurez-vous d'avoir au moins 2 GB libres
```

### 3. Vérifier les credentials

Le script clone depuis GitHub. Assurez-vous que:
- Le repo est public OU
- Vous avez configuré SSH keys OU
- Vous avez un token GitHub

---

## 🔧 Alternative: Nettoyage Manuel

Si vous ne voulez pas tout supprimer:

```bash
cd /var/www/novabot

# Nettoyer Python
rm -rf .venv
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Nettoyer Frontend
cd frontend
rm -rf node_modules .next
npm install
npm run build
cd ..

# Nettoyer logs
rm -rf logs/*
mkdir -p logs

# Nettoyer git
git clean -fdx
git pull

# Restart
pm2 restart all
```

---

## 📝 Après le Déploiement

### 1. Vérifier les services

```bash
pm2 status
pm2 logs hl-bot-engine --lines 20
pm2 logs hl-frontend --lines 20
```

### 2. Tester l'API

```bash
curl http://localhost:8000/api/status
curl http://localhost:8000/api/scanner/best
```

### 3. Tester le Frontend

```bash
curl http://localhost:3000
# Ou ouvrir dans le navigateur
```

### 4. Restaurer la config si nécessaire

```bash
cp ~/strategies.json.backup /var/www/novabot/strategies.json
pm2 restart hl-bot-engine
```

---

## 💡 Optimisations d'Espace

### Après l'installation:

```bash
# Nettoyer pip cache
pip cache purge

# Nettoyer npm cache
npm cache clean --force

# Supprimer les logs anciens (garder 7 jours)
find /var/www/novabot/logs -name "*.log" -mtime +7 -delete

# Compresser les logs anciens
gzip /var/www/novabot/logs/*.log
```

### Rotation automatique des logs:

Ajouter dans `ecosystem.config.js`:

```javascript
{
  max_size: '10M',           // Taille max par fichier
  max_files: 5,              // Nombre de fichiers à garder
  compress: true             // Compresser les anciens logs
}
```

---

## 🔍 Vérifier l'Espace Récupéré

```bash
# Avant
du -sh /var/www/novabot

# Après fresh install
du -sh /var/www/novabot

# Détails par dossier
du -h --max-depth=1 /var/www/novabot | sort -hr
```

---

## ⚡ Quick Commands

```bash
# Fresh deploy
cd /tmp && wget https://raw.githubusercontent.com/nico2511/NovaBot/master/deploy_fresh.sh && chmod +x deploy_fresh.sh && sudo ./deploy_fresh.sh

# Check status
pm2 status && pm2 logs --lines 10

# Check disk
df -h && du -sh /var/www/novabot

# Restart all
pm2 restart all
```

---

## 🆘 Troubleshooting

### "No space left on device"

```bash
# Trouver ce qui prend de la place
du -h / | sort -hr | head -20

# Nettoyer apt cache
sudo apt clean

# Nettoyer journald logs
sudo journalctl --vacuum-time=7d
```

### "Permission denied"

```bash
# Donner les bonnes permissions
sudo chown -R $USER:$USER /var/www/novabot
```

### "PM2 not found"

```bash
# Réinstaller PM2
npm install -g pm2
```

---

**Prêt pour un fresh start !** 🚀
