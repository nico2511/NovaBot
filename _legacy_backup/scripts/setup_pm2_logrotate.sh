#!/bin/bash
# PM2 Log Rotation Setup Script
# Configures pm2-logrotate module with 2-day retention

echo "🔧 Setting up PM2 Log Rotation..."

# Check if PM2 is installed
if ! command -v pm2 &> /dev/null; then
    echo "❌ PM2 is not installed. Please install PM2 first:"
    echo "   npm install -g pm2"
    exit 1
fi

# Install pm2-logrotate module
echo "📦 Installing pm2-logrotate module..."
pm2 install pm2-logrotate

# Wait for installation
sleep 3

# Configure rotation settings
echo "⚙️ Configuring log rotation settings..."

# Max file size before rotation (10MB)
pm2 set pm2-logrotate:max_size 10M

# Number of rotated logs to keep (2 days worth)
pm2 set pm2-logrotate:retain 2

# Compress rotated logs
pm2 set pm2-logrotate:compress true

# Rotation interval (every day at 00:00)
pm2 set pm2-logrotate:rotateInterval '0 0 * * *'

# Date format for rotated files
pm2 set pm2-logrotate:dateFormat 'YYYY-MM-DD_HH-mm-ss'

# Rotate even if size limit not reached (daily)
pm2 set pm2-logrotate:rotateModule true

echo ""
echo "✅ PM2 Log Rotation configured successfully!"
echo ""
echo "📋 Current settings:"
pm2 conf pm2-logrotate

echo ""
echo "💡 Logs will be:"
echo "   - Rotated when they reach 10MB"
echo "   - Rotated daily at midnight"
echo "   - Compressed (.gz)"
echo "   - Kept for 2 days (older logs auto-deleted)"
echo ""
echo "🔍 To check rotation status:"
echo "   pm2 ls"
echo "   pm2 logs pm2-logrotate"
