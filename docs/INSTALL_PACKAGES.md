# 📦 Installation Packages Production

## Commande Rapide

```bash
# Installation complète
pip install -r requirements.txt
```

## Packages Critiques

### Core Trading
```bash
pip install hyperliquid-python-sdk
pip install eth-account>=0.8.0
pip install ccxt>=4.4.1
```

### Data & Analysis
```bash
pip install pandas>=2.1.0
pip install pandas-ta-openbb  # ou pandas-ta si problème
pip install numpy>=1.24.0
pip install plotly==5.24.0
```

### Backend API
```bash
pip install fastapi>=0.104.0
pip install uvicorn[standard]>=0.24.0
pip install pydantic>=2.0.0
pip install python-multipart>=0.0.6
pip install websockets>=12.0
pip install aiohttp>=3.10.11
```

### AI & Notifications
```bash
pip install google-generativeai==0.8.3
pip install openai>=1.0.0
pip install discord-webhook==1.3.0
```

### Configuration
```bash
pip install python-dotenv==1.0.0
```

## Vérification Installation

```bash
# Vérifier packages installés
pip list | grep -E "hyperliquid|fastapi|pandas|discord"

# Tester imports critiques
python3 -c "from hyperliquid.info import Info; from hyperliquid.exchange import Exchange; print('✅ Hyperliquid OK')"
python3 -c "import fastapi; import uvicorn; print('✅ FastAPI OK')"
python3 -c "import pandas; import pandas_ta; print('✅ Pandas OK')"
```

## Problèmes Courants

### pandas_ta
Si `pandas-ta-openbb` ne fonctionne pas:
```bash
pip uninstall pandas-ta-openbb
pip install pandas-ta
```

### eth-account
Requis pour Hyperliquid:
```bash
pip install eth-account
```

### uvicorn
Installer avec extras pour performance:
```bash
pip install "uvicorn[standard]"
```

## Frontend (Node.js)

```bash
cd frontend
npm install
npm run build
```

## Script Automatique

Utilisez le script fourni:
```bash
chmod +x install_dependencies.sh
./install_dependencies.sh
```

## Ordre d'Installation Recommandé

1. **Python core** (pandas, numpy)
2. **Hyperliquid SDK** (hyperliquid-python-sdk, eth-account)
3. **Backend** (fastapi, uvicorn)
4. **AI** (google-generativeai, openai)
5. **Utilities** (discord-webhook, python-dotenv)
6. **Frontend** (npm install dans /frontend)

## Versions Testées

- Python: 3.10+
- Node.js: 18+
- pip: 23+
- npm: 9+
