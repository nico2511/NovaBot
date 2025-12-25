#!/bin/bash

echo "🚀 Deploying HyperLiquid Trading Bot (PM2 Mode)"
echo ""

# Activate venv if exists
if [ -d ".venv" ]; then
    echo "🐍 Activating virtual environment (.venv)..."
    source .venv/bin/activate
elif [ -d "venv" ]; then
    echo "🐍 Activating virtual environment (venv)..."
    source venv/bin/activate
fi

# Check Python dependencies
echo "📦 Checking Python dependencies..."
if ! python3 -c "import pandas; import dotenv; import eth_account; import hyperliquid; import discord_webhook" 2>/dev/null; then
    echo "📦 Installing Python dependencies..."
    # If in venv, no need for break-system-packages (usually), but keeping it safe if user is root without venv
    if [ -n "$VIRTUAL_ENV" ]; then
        pip install -q pandas numpy python-dotenv eth-account hyperliquid-python-sdk discord-webhook aiohttp pydantic fastapi uvicorn
    else
        pip install -q pandas numpy python-dotenv eth-account hyperliquid-python-sdk discord-webhook aiohttp pydantic fastapi uvicorn --break-system-packages
    fi
fi

# Build Frontend
echo "🏗️  Building Next.js Frontend..."
cd frontend
# Install only if missing (speed up)
if [ ! -d "node_modules" ]; then
    echo "📦 Installing Frontend dependencies..."
    npm install
fi
npm run build
cd ..

echo "🔄 Redémarrage de PM2..."
# Delete existing processes to ensure clean config reload
pm2 delete ecosystem.config.js 2>/dev/null || pm2 delete hl-bot-engine hl-frontend 2>/dev/null || true

# Start fresh
pm2 start ecosystem.config.js
pm2 save

echo ""
echo "✅ Déploiement terminé!"
echo ""
echo "📊 Vérification:"
pm2 list
echo ""
echo "📝 Pour voir les logs:"
echo "   Global:   pm2 logs"
echo "   Bot:      pm2 logs hl-bot-engine"
echo "   UI:       pm2 logs hl-frontend"
