#!/bin/bash

echo "🚀 Starting HyperLiquid Trading Bot - FULL INTEGRATION"
echo ""
echo "This will start:"
echo "  1. Trading Bot (Python)"
echo "  2. FastAPI Backend"
echo "  3. Next.js Frontend"
echo ""

# Check Python dependencies
if ! python3 -c "import pandas; import dotenv; import eth_account; import hyperliquid; import pandas_ta; import discord_webhook" 2>/dev/null; then
    echo "📦 Installing Python dependencies..."
    pip install -q pandas numpy python-dotenv eth-account hyperliquid-python-sdk pandas_ta discord-webhook aiohttp pydantic fastapi uvicorn --break-system-packages
fi

# Check backend dependencies
if ! python3 -c "import fastapi" 2>/dev/null; then
    echo "📦 Installing backend dependencies..."
    pip install -q -r backend/requirements.txt --break-system-packages
fi

# Check frontend dependencies
if [ ! -d "frontend/node_modules" ]; then
    echo "📦 Installing frontend dependencies..."
    cd frontend
    npm install
    cd ..
fi

echo ""
echo "✅ All dependencies installed!"
echo ""

# Start the integrated bot + API
echo "🤖 Starting integrated bot with API..."
python3 main_nextjs.py &
BOT_PID=$!

# Wait for API to start
sleep 5

# Start frontend
echo "🎨 Starting Next.js frontend..."
cd frontend
npm run dev &
FRONTEND_PID=$!
cd ..

echo ""
echo "✅ All services running!"
echo ""
echo "📊 Next.js UI: http://localhost:3000"
echo "🔧 API Docs: http://localhost:8000/docs"
echo "💡 Streamlit (backup): streamlit run main.py"
echo ""
echo "Press Ctrl+C to stop all services"
echo ""

# Wait for Ctrl+C
trap "kill $BOT_PID $FRONTEND_PID 2>/dev/null; exit" INT
wait
