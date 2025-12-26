#!/bin/bash

# Quick deployment script for production
# Run this after 'git pull' to update everything

echo "🚀 Deploying updates..."

# Stop services
echo "⏸️ Stopping services..."
pm2 stop all

# Activate venv and update Python dependencies
echo "📦 Updating Python dependencies..."
source .venv/bin/activate
pip install -r requirements.txt

# Update frontend
echo "⚛️ Updating frontend..."
cd frontend
npm install
npm run build
cd ..

# Restart services
echo "🔄 Restarting services..."
pm2 restart all

# Show status
echo ""
echo "✅ Deployment complete!"
pm2 status

echo ""
echo "📝 Check logs:"
echo "   pm2 logs hl-bot-engine --lines 20"
echo "   pm2 logs hl-frontend --lines 20"
