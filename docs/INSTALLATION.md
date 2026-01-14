# 🤖 NovaBot - Guide d'Installation Rapide

## 📋 Prérequis

- **Python 3.10+** ([Télécharger](https://www.python.org/downloads/))
- **Node.js 18+** (pour le frontend Next.js) ([Télécharger](https://nodejs.org/))
- **Git** (optionnel) ([Télécharger](https://git-scm.com/))

---

## 🚀 Installation Automatique (Recommandé)

### Windows (PowerShell)

```powershell
# 1. Ouvrir PowerShell dans le dossier novabot
cd C:\Users\User\Desktop\novabot

# 2. Autoriser l'exécution de scripts (si nécessaire)
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser

# 3. Lancer l'installation
.\install.ps1
```

---

## 🛠️ Installation Manuelle

### 1. Créer un environnement virtuel

```powershell
python -m venv venv
```

### 2. Activer l'environnement virtuel

```powershell
.\venv\Scripts\Activate.ps1
```

### 3. Mettre à jour pip

```powershell
python -m pip install --upgrade pip
```

### 4. Installer les dépendances

```powershell
pip install -r requirements.txt
```

### 5. Configurer les variables d'environnement

Créez un fichier `.env` à la racine du projet:

```env
# Hyperliquid Configuration
HL_ACCOUNT_ADDRESS=votre_adresse_wallet
HL_PRIVATE_KEY=votre_clé_privée

# OpenRouter (IA)
OPENROUTER_API_KEY=votre_clé_openrouter

# Discord (Notifications - Optionnel)
DISCORD_WEBHOOK_URL=votre_webhook_discord

# Bot Configuration
AUTO_START_TRADING=false
DEFAULT_MAX_POSITIONS=1
DEFAULT_LEVERAGE=5
TRADING_TIMEFRAME=15m

# AI Configuration
AI_MODEL_NAME=deepseek/deepseek-v3.2
BOT_PERSONA=conservative
RISK_PROFILE=medium
AI_CALL_COOLDOWN=60
```

---

## 🎯 Lancement du Bot

### Démarrer le bot

```powershell
python main_nextjs.py
```

### Accéder au Dashboard

- **Frontend:** http://localhost:3000
- **API Docs:** http://localhost:8001/docs

---

## 📦 Dépendances Principales

| Package | Version | Description |
|---------|---------|-------------|
| `fastapi` | 0.115.5 | Framework API |
| `pandas` | 2.2.3 | Analyse de données |
| `pandas-ta` | 0.3.14b0 | Indicateurs techniques |
| `openai` | 1.57.4 | Client OpenRouter |
| `websockets` | 14.1 | WebSocket Hyperliquid |
| `eth-account` | 0.13.4 | Signature transactions |

---

## 🔧 Commandes Utiles

### Activer l'environnement virtuel

```powershell
.\venv\Scripts\Activate.ps1
```

### Désactiver l'environnement virtuel

```powershell
deactivate
```

### Mettre à jour les dépendances

```powershell
pip install -r requirements.txt --upgrade
```

### Vérifier les dépendances installées

```powershell
pip list
```

### Générer un nouveau requirements.txt

```powershell
pip freeze > requirements.txt
```

---

## 🧪 Tests

### Installer les dépendances de test

```powershell
pip install pytest pytest-asyncio pytest-cov
```

### Lancer les tests

```powershell
pytest
```

### Lancer les tests avec couverture

```powershell
pytest --cov=app --cov-report=html
```

---

## 🐛 Dépannage

### Erreur: "Python n'est pas reconnu"

- Vérifiez que Python est installé et dans le PATH
- Redémarrez PowerShell après l'installation de Python

### Erreur: "pip n'est pas reconnu"

```powershell
python -m ensurepip --upgrade
```

### Erreur: "Cannot be loaded because running scripts is disabled"

```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

### Erreur: "ModuleNotFoundError"

```powershell
pip install -r requirements.txt --force-reinstall
```

### Le bot ne démarre pas

1. Vérifiez que le fichier `.env` existe et est configuré
2. Vérifiez que l'environnement virtuel est activé
3. Vérifiez les logs dans `bot_activity.log`

---

## 📁 Structure du Projet

```
novabot/
├── app/                    # Code principal du bot
│   ├── core/              # Logique centrale
│   ├── services/          # Services (IA, Hyperliquid, Discord)
│   └── utils/             # Utilitaires
├── backend/               # API FastAPI
├── strategies/            # Stratégies de trading
├── docs/                  # Documentation
├── logs/                  # Fichiers de logs
├── data/                  # Données (cache, historique)
├── .env                   # Configuration (à créer)
├── requirements.txt       # Dépendances Python
├── install.ps1           # Script d'installation
└── main_nextjs.py        # Point d'entrée
```

---

## 🔐 Sécurité

⚠️ **IMPORTANT:**

- **Ne commitez JAMAIS** votre fichier `.env` sur Git
- Gardez vos clés privées **secrètes**
- Utilisez des wallets de test pour les premiers essais
- Activez l'authentification 2FA sur vos comptes

---

## 📚 Ressources

- **Documentation Hyperliquid:** https://hyperliquid.gitbook.io/
- **OpenRouter:** https://openrouter.ai/
- **FastAPI:** https://fastapi.tiangolo.com/
- **Pandas-TA:** https://github.com/twopirllc/pandas-ta

---

## 🆘 Support

En cas de problème:

1. Vérifiez les logs: `bot_activity.log`
2. Consultez la documentation dans `docs/`
3. Vérifiez que toutes les dépendances sont installées
4. Assurez-vous que le fichier `.env` est correctement configuré

---

## ✅ Checklist Post-Installation

- [ ] Python 3.10+ installé
- [ ] Environnement virtuel créé et activé
- [ ] Dépendances installées (`pip list`)
- [ ] Fichier `.env` configuré avec vos clés
- [ ] Dossiers `logs/`, `data/`, `docs/` créés
- [ ] Bot démarre sans erreur
- [ ] Dashboard accessible sur http://localhost:3000
- [ ] API accessible sur http://localhost:8001/docs

---

**Bon trading! 🚀**
