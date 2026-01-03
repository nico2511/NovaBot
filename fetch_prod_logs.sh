#!/bin/bash
# Script to fetch production logs from remote server
# Usage: ./fetch_prod_logs.sh [lines]

LINES=${1:-100}  # Default 100 lines

echo "📥 Fetching last $LINES lines from production logs..."
echo ""

# Fetch bot engine logs
echo "🤖 Bot Engine Logs:"
echo "===================="
ssh root@10.10.20.76 "pm2 logs hl-bot-engine --lines $LINES --nostream"

echo ""
echo ""

# Fetch API logs
echo "🌐 API Logs:"
echo "===================="
ssh root@10.10.20.76 "pm2 logs hl-bot-api --lines $LINES --nostream"

echo ""
echo ""

# Fetch frontend logs
echo "🎨 Frontend Logs:"
echo "===================="
ssh root@10.10.20.76 "pm2 logs hl-bot-frontend --lines $LINES --nostream"
