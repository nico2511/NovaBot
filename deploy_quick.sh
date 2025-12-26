#!/bin/bash

# Ultra-fast deployment for code-only changes
# Use this when you only changed Python/JS code (no dependencies)

echo "⚡ Quick deploy (code only)..."

# Activate venv
source .venv/bin/activate

# Hot reload services (zero-downtime)
echo "🔄 Hot reloading services..."
pm2 reload all

echo ""
echo "✅ Quick deploy complete!"
pm2 status

echo ""
echo "💡 Tip: Use ./deploy.sh for full deployment with dependency checks"
