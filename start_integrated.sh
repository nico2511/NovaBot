#!/bin/bash

echo "🚀 Deploying HyperLiquid Trading Bot (PM2 Mode)"
echo ""

# Check and Create venv if missing
if [ ! -d ".venv" ] && [ ! -d "venv" ]; then
    echo "🐍 Creating virtual environment (.venv)..."
    python3 -m venv .venv
fi

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
        pip install -q pandas numpy python-dotenv eth-account hyperliquid-python-sdk discord-webhook aiohttp pydantic fastapi uvicorn google-generativeai openai
    else
        pip install -q pandas numpy python-dotenv eth-account hyperliquid-python-sdk discord-webhook aiohttp pydantic fastapi uvicorn google-generativeai openai --break-system-packages
    fi
fi

# Frontend skipped (Phasing out legacy frontend)
# echo "🏗️  Building Next.js Frontend..."
# cd frontend
# npm install --no-audit --prefer-offline
# npm run build
# cd ..

# Check PM2 availability
if ! command -v pm2 &> /dev/null; then
    echo "⚠️ PM2 not found globally. Checking local..."
    if [ ! -f "node_modules/.bin/pm2" ]; then
        echo "📦 Installing PM2 locally..."
        npm install pm2
    fi
    PM2_CMD="npx pm2"
else
    PM2_CMD="pm2"
fi

echo "🔄 Redémarrage de PM2..."
# Delete existing processes to ensure clean config reload
$PM2_CMD delete ecosystem.config.js 2>/dev/null || $PM2_CMD delete hl-bot-engine 2>/dev/null || true

# Start fresh
$PM2_CMD start ecosystem.config.js
$PM2_CMD save

echo ""
echo "✅ Déploiement terminé!"
echo ""
echo "📊 Vérification:"
$PM2_CMD list
echo ""
echo "📝 Pour voir les logs:"
echo "   Global:   $PM2_CMD logs"
echo "   Bot:      $PM2_CMD logs hl-bot-engine"
echo "   UI:       $PM2_CMD logs hl-frontend"
