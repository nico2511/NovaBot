#!/bin/bash

# Quick deployment script for production
# Run this after 'git pull' to update everything

echo "🚀 Deploying updates..."

# Activate venv
source .venv/bin/activate

# Check if requirements changed (only install if needed)
if git diff HEAD@{1} HEAD --name-only | grep -q "requirements.txt"; then
    echo "📦 Requirements changed - updating Python dependencies..."
    pip install -r requirements.txt
else
    echo "✅ Python dependencies up to date (requirements.txt unchanged)"
fi

# Update frontend only if package.json or source files changed
if git diff HEAD@{1} HEAD --name-only | grep -qE "frontend/(package.json|components|app|public)"; then
    echo "⚛️ Frontend changed - rebuilding..."
    cd frontend
    
    # Only npm install if package.json changed
    if git diff HEAD@{1} HEAD --name-only | grep -q "frontend/package.json"; then
        echo "📦 Installing frontend dependencies..."
        npm install
    fi
    
    npm run build
    cd ..
else
    echo "✅ Frontend up to date (no changes detected)"
fi

# Use reload instead of restart (zero-downtime)
echo "🔄 Reloading services (zero-downtime)..."
pm2 reload all

# Show status
echo ""
echo "✅ Deployment complete!"
pm2 status

echo ""
echo "📝 Check logs:"
echo "   pm2 logs hl-bot-engine --lines 20"
echo "   pm2 logs hl-frontend --lines 20"
