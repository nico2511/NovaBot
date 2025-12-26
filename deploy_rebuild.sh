#!/bin/bash

# Fresh deployment script - SIMPLIFIED VERSION
# No authentication required - uses existing directory

echo "🧹 FRESH DEPLOYMENT - Clean rebuild in place..."
echo "⚠️  This will clean and rebuild /var/www/novabot"
read -p "Continue? (y/n) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]
then
    exit 1
fi

# Navigate to project
cd /var/www/novabot || {
    echo "❌ Directory /var/www/novabot not found!"
    echo "Please clone the repo first:"
    echo "  cd /var/www"
    echo "  git clone https://github.com/nico2511/NovaBot.git novabot"
    exit 1
}

# Stop PM2
echo "⏸️ Stopping PM2..."
pm2 delete all 2>/dev/null || true

# Pull latest code
echo "📥 Pulling latest code..."
git fetch origin
git reset --hard origin/master
git clean -fdx

# Clean Python environment
echo "🐍 Rebuilding Python environment..."
rm -rf .venv
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

# Clean and rebuild Frontend
echo "⚛️ Rebuilding Frontend..."
cd frontend
rm -rf node_modules .next
npm install
npm run build
cd ..

# Clean logs
echo "🧹 Cleaning logs..."
rm -rf logs/*
mkdir -p logs

# Create PM2 ecosystem config
echo "⚙️ Creating PM2 config..."
cat > ecosystem.config.js << 'EOF'
module.exports = {
  apps: [
    {
      name: 'hl-bot-engine',
      script: 'main_nextjs.py',
      interpreter: 'python3',
      cwd: '/var/www/novabot',
      env: {
        PYTHONPATH: '/var/www/novabot',
        VIRTUAL_ENV: '/var/www/novabot/.venv'
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
      cwd: '/var/www/novabot/frontend',
      error_file: './logs/frontend-error.log',
      out_file: './logs/frontend-out.log',
      autorestart: true
    }
  ]
}
EOF

# Start services
echo "🚀 Starting services..."
pm2 start ecosystem.config.js
pm2 save

# Show status
echo ""
echo "✅ Fresh deployment complete!"
echo ""
echo "📊 Status:"
pm2 status

echo ""
echo "📝 Logs:"
echo "   Bot:      pm2 logs hl-bot-engine"
echo "   Frontend: pm2 logs hl-frontend"
echo ""
echo "💾 Disk usage:"
du -sh /var/www/novabot
