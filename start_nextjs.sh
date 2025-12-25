#!/bin/bash

echo "🚀 Starting HyperLiquid Trading Bot (Next.js Version)"
echo ""

# Check if backend dependencies are installed
if [ ! -d ".venv" ]; then
    echo "📦 Creating virtual environment..."
    python3 -m venv .venv
fi

echo "📦 Installing backend dependencies..."
source .venv/bin/activate
pip install -q -r backend/requirements.txt

# Check if frontend dependencies are installed
if [ ! -d "frontend/node_modules" ]; then
    echo "📦 Installing frontend dependencies..."
    cd frontend
    npm install
    cd ..
fi

echo ""
echo "✅ Dependencies installed!"
echo ""
echo "Starting services..."
echo ""

# Start backend in background
echo "🔧 Starting FastAPI backend on http://localhost:8000"
source .venv/bin/activate
cd backend
python api.py &
BACKEND_PID=$!
cd ..

# Wait a bit for backend to start
sleep 3

# Start frontend
echo "🎨 Starting Next.js frontend on http://localhost:3000"
cd frontend
npm run dev &
FRONTEND_PID=$!
cd ..

echo ""
echo "✅ Both services are running!"
echo ""
echo "📊 Frontend: http://localhost:3000"
echo "🔧 Backend API: http://localhost:8000"
echo "📚 API Docs: http://localhost:8000/docs"
echo ""
echo "Press Ctrl+C to stop all services"
echo ""

# Wait for Ctrl+C
trap "kill $BACKEND_PID $FRONTEND_PID; exit" INT
wait
