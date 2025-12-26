#!/bin/bash

# Deployment script for production server
# Fixes Python interpreter path issue

echo "🚀 Deploying to production..."

# Stop PM2 processes
echo "⏸️ Stopping PM2 processes..."
pm2 stop all

# Pull latest code
echo "📥 Pulling latest code..."
git pull origin master

# Install Python dependencies
echo "📦 Installing Python dependencies..."
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Build frontend
echo "🏗️ Building frontend..."
cd frontend
npm install
npm run build
cd ..

# Update PM2 ecosystem file with correct Python path
echo "⚙️ Updating PM2 configuration..."
cat > ecosystem.config.js << 'EOF'
module.exports = {
  apps: [
    {
      name: 'hl-bot-engine',
      script: 'main_nextjs.py',
      interpreter: 'python3',  // Use system python3, not .venv
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

# Create logs directory
mkdir -p logs

# Restart PM2
echo "🔄 Restarting PM2..."
pm2 delete all
pm2 start ecosystem.config.js
pm2 save

# Show status
echo ""
echo "✅ Deployment complete!"
echo ""
echo "📊 Status:"
pm2 status

echo ""
echo "📝 Logs:"
echo "   Bot:      pm2 logs hl-bot-engine"
echo "   Frontend: pm2 logs hl-frontend"
