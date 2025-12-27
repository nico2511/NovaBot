#!/bin/bash

# Universal Deployment Script for PyBot
# Handles fresh install, updates, and zero-downtime reloads

set -e # Exit on error

echo "🚀 Starting PyBot Deployment..."

# Function to check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# 1. Environment Setup
if [ ! -d ".venv" ]; then
    echo "🐍 Creating Python virtual environment..."
    python3 -m venv .venv
    source .venv/bin/activate
    pip install --upgrade pip
else
    source .venv/bin/activate
fi

# 2. Dependencies
echo "📦 Checking dependencies..."
pip install -r requirements.txt

# 3. Frontend Build
echo "⚛️ Building Frontend..."
cd frontend
if [ ! -d "node_modules" ]; then
    npm install
fi
npm run build
cd ..

# 4. Process Management (PM2)
echo "⚙️ Configuring PM2..."

# Ensure we have a valid ecosystem config
cat > ecosystem.config.js << 'EOF'
module.exports = {
  apps: [
    {
      name: 'hl-bot-engine',
      script: 'main_nextjs.py',
      interpreter: 'python3',
      cwd: process.cwd(),
      env: {
        PYTHONPATH: process.cwd(),
        VIRTUAL_ENV: process.cwd() + '/.venv'
      },
      error_file: './logs/bot-error.log',
      out_file: './logs/bot-out.log',
      log_date_format: 'YYYY-MM-DD HH:mm:ss',
      autorestart: true,
      max_restarts: 10,
      min_uptime: '10s'
    },
    {
      name: 'hl-frontend',
      script: 'node_modules/next/dist/bin/next',
      args: 'start -p 3000',
      cwd: './frontend',
      error_file: './logs/frontend-error.log',
      out_file: './logs/frontend-out.log',
      autorestart: true
    }
  ]
}
EOF

# Create logs directory if not exists
mkdir -p logs

# Start or Reload
if command_exists pm2; then
    if pm2 list | grep -q "hl-bot-engine"; then
        echo "🔄 Reloading existing processes..."
        pm2 reload ecosystem.config.js
    else
        echo "🚀 Starting processes..."
        pm2 start ecosystem.config.js
    fi
    pm2 save
else
    echo "⚠️ PM2 not found. Please install it with: npm install -g pm2"
    echo "   Running in foreground for now..."
    python3 main_nextjs.py
fi

echo "✅ Deployment Success!"
echo "   GUI: http://localhost:3000"
echo "   API: http://localhost:8000"
