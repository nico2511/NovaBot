#!/bin/bash
# Installation script for production deployment

echo "🚀 Installing Hyperliquid Trading Bot Dependencies..."

# Check Python version
python_version=$(python3 --version 2>&1 | awk '{print $2}')
echo "✓ Python version: $python_version"

# Install Python packages
echo "📦 Installing Python packages..."
pip install -r requirements.txt

# Install additional required packages
echo "📦 Installing additional dependencies..."
pip install eth-account>=0.8.0
pip install pandas-ta  # If pandas-ta-openbb doesn't work

echo "✅ Python dependencies installed!"

# Check Node.js
node_version=$(node --version 2>&1)
echo "✓ Node.js version: $node_version"

# Install frontend dependencies
echo "📦 Installing frontend dependencies..."
cd frontend
npm install
cd ..

echo "✅ All dependencies installed!"
echo ""
echo "Next steps:"
echo "1. Copy .env.example to .env"
echo "2. Fill in your API keys and credentials"
echo "3. Run: ./start_integrated.sh"
