#!/bin/bash

# Script de monitoring des logs du bot
LOG_FILE="logs/prod-bot-out.log"

echo "=== Monitoring Bot Logs ==="
echo "Watching: $LOG_FILE"
echo "Press Ctrl+C to stop"
echo ""

while true; do
    clear
    echo "=== Last 30 lines @ $(date) ==="
    echo ""
    
    # Show last 30 lines with key events highlighted
    tail -30 "$LOG_FILE" | grep --color=always -E "ENTRY|ERROR|Failed|executed|phantom|SYNC|trading_enabled|Signal|BUY|SELL|🚨|❌|✅|⚠️|$"
    
    echo ""
    echo "=== Waiting 10 seconds... ==="
    sleep 10
done
