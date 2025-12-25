#!/bin/bash
echo "🧹 Killing all project processes..."
pkill -f "python3 main_nextjs.py"
pkill -f "next-server"
pkill -f "next dev"
fuser -k 3000/tcp 2>/dev/null
fuser -k 3001/tcp 2>/dev/null
fuser -k 3002/tcp 2>/dev/null
fuser -k 3003/tcp 2>/dev/null
fuser -k 3004/tcp 2>/dev/null
fuser -k 3005/tcp 2>/dev/null
fuser -k 8000/tcp 2>/dev/null
echo "✅ All clean! You can now run ./start_integrated.sh"
