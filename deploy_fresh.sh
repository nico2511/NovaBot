#!/bin/bash

# Fresh deployment script - Clean install from scratch
# Use this to start fresh and recover disk space

echo "🧹 FRESH DEPLOYMENT - Starting from scratch..."
echo "⚠️  This will delete everything in /var/www/novabot"
read -p "Continue? (y/n) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]
then
    exit 1
fi

# Stop and delete all PM2 processes
echo "⏸️ Stopping PM2..."
pm2 delete all 2>/dev/null || true
pm2 kill

# Clean up old installation
echo "🗑️ Removing old installation..."
cd /var/www
rm -rf novabot

# Clone fresh from GitHub
echo "📥 Cloning from GitHub..."
git clone https://github.com/nico2511/NovaBot.git novabot
cd novabot

# Python setup
echo "🐍 Setting up Python environment..."
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

# Frontend setup
echo "⚛️ Setting up Frontend..."
cd frontend
npm install
npm run build
cd ..

# Create necessary directories
echo "📁 Creating directories..."
mkdir -p logs
mkdir -p data

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
pm2 startup

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
echo "🌐 Access:"
echo "   Frontend: http://$(hostname -I | awk '{print $1}'):3000"
echo "   API:      http://$(hostname -I | awk '{print $1}'):8000"
echo ""
echo "💾 Disk usage:"
du -sh /var/www/novabot
