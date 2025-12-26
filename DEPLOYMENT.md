# 🚀 Déploiement en Production

## Scanner Hyperliquid Implémenté ✅

Le scanner de tokens Hyperliquid est maintenant opérationnel !

### Fonctionnalités

- 📊 Scanne **224 tokens** sur Hyperliquid
- 🔍 Filtre par volume (min $1M)
- 📈 Analyse technique (ATR, RSI, Momentum, Trend)
- ⭐ Scoring intelligent (0-100 points)
- 🎯 Identifie les meilleures opportunités

### Résultats du Premier Scan

**Top 3 Opportunités:**
1. **SOL** - Score: 60/100 ⭐⭐ ($402.7M volume, -1.29% momentum)
2. **INIT** - Score: 59/100 ⭐ ($1.4M volume, +11.52% momentum, RSI 73)
3. **HYPE** - Score: 59/100 ⭐ ($118.9M volume, -0.42% momentum)

---

## Déploiement sur le Serveur de Production

### Option 1: Script Automatique (Recommandé)

```bash
# Sur le serveur de production
cd /var/www/novabot
git pull
chmod +x deploy_prod.sh
./deploy_prod.sh
```

Le script `deploy_prod.sh` fait automatiquement:
- ✅ Pull du code
- ✅ Installation des dépendances Python
- ✅ Build du frontend
- ✅ Configuration PM2 avec le bon Python path
- ✅ Redémarrage des services

### Option 2: Manuel

```bash
# 1. Pull code
cd /var/www/novabot
git pull origin master

# 2. Python dependencies
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 3. Build frontend
cd frontend
npm install
npm run build
cd ..

# 4. Fix PM2 config
# Éditer ecosystem.config.js:
# Changer: interpreter: './.venv/bin/python3'
# Par:     interpreter: 'python3'

# 5. Restart
pm2 delete all
pm2 start ecosystem.config.js
pm2 save
```

---

## Problème Résolu: Python Interpreter

**Erreur rencontrée:**
```
[PM2][ERROR] Interpreter ./.venv/bin/python3 is NOT AVAILABLE in PATH
```

**Solution:**
Le fichier `ecosystem.config.js` a été mis à jour pour utiliser `python3` système au lieu du chemin `.venv`:

```javascript
{
  name: 'hl-bot-engine',
  script: 'main_nextjs.py',
  interpreter: 'python3',  // ✅ Utilise python3 système
  env: {
    PYTHONPATH: '/var/www/novabot',
    VIRTUAL_ENV: '/var/www/novabot/.venv'  // ✅ Pointe vers venv
  }
}
```

---

## Utilisation du Scanner

### Via l'Interface Web

1. Ouvrir l'interface: `http://votre-serveur:3000`
2. Cliquer sur l'onglet **🔍 Scanner**
3. Sélectionner le nombre de résultats (5, 10, 20)
4. Cliquer sur **🚀 Scan Now**
5. Attendre 30-60 secondes
6. Voir les résultats avec scores et métriques

### Via API

```bash
# Top 10 opportunités
curl http://localhost:8000/api/scanner/opportunities?top_n=10

# Meilleur asset uniquement
curl http://localhost:8000/api/scanner/best
```

### Via Python

```python
from app.services.token_scanner import HyperliquidScanner

scanner = HyperliquidScanner()
opportunities = scanner.scan(top_n=10)

best_asset = opportunities[0]['symbol']
print(f"Best asset to trade: {best_asset}")
```

---

## Configuration du Scanner

Dans `app/services/token_scanner.py`:

```python
self.min_volume_24h = 1_000_000  # $1M minimum
self.min_atr_pct = 3.0           # Volatilité min
self.max_atr_pct = 8.0           # Volatilité max
self.min_momentum_pct = 5.0      # Momentum min
```

---

## Prochaines Étapes

### 1. Auto-Switching (Optionnel)

Faire switcher automatiquement le bot vers le meilleur asset:

```python
# Dans main_nextjs.py
import schedule

@schedule.every(1).hours.do
def auto_switch_asset():
    scanner = HyperliquidScanner()
    best_asset = scanner.get_best_asset()
    
    if best_asset != current_asset:
        print(f"🔄 Switching to {best_asset}")
        bot.switch_asset(best_asset)
```

### 2. Multi-Asset Trading

Trader les 3 meilleurs assets simultanément:

```python
opportunities = scanner.scan(top_n=3)

for opp in opportunities:
    bot.trade_asset(
        symbol=opp['symbol'],
        allocation=0.33  # 33% du capital chacun
    )
```

### 3. Notifications Discord

Envoyer les résultats du scan sur Discord:

```python
from common.utils.discord import send_discord_message

opportunities = scanner.scan(top_n=5)
message = f"🔍 Top 5 Opportunities:\n"
for i, opp in enumerate(opportunities, 1):
    message += f"{i}. {opp['symbol']} - Score: {opp['score']}\n"

send_discord_message(message)
```

---

## Vérification

```bash
# Status PM2
pm2 status

# Logs bot
pm2 logs hl-bot-engine --lines 50

# Logs frontend
pm2 logs hl-frontend --lines 50

# Test API
curl http://localhost:8000/api/status
curl http://localhost:8000/api/scanner/best
```

---

## Troubleshooting

### Bot ne démarre pas

```bash
# Vérifier Python
which python3
python3 --version

# Vérifier venv
source .venv/bin/activate
pip list | grep hyperliquid

# Logs détaillés
pm2 logs hl-bot-engine --err
```

### Frontend ne build pas

```bash
cd frontend
rm -rf .next node_modules
npm install
npm run build
```

### Scanner timeout

Le scanner peut prendre 30-60s pour analyser 60+ tokens. C'est normal.
Pour accélérer, réduire `min_volume_24h` dans le code.

---

## État Actuel

✅ Scanner implémenté et testé  
✅ Frontend avec onglet Scanner  
✅ API endpoints fonctionnels  
✅ Script de déploiement créé  
✅ Code pushé sur GitHub  
⏳ Déploiement en production  

**Prêt pour le déploiement !** 🚀
