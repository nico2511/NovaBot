# 🤖 NovaBot - AI-Powered Trading Bot for Hyperliquid

[![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![Next.js](https://img.shields.io/badge/Next.js-14-black.svg)](https://nextjs.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-green.svg)](https://fastapi.tiangolo.com/)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

**NovaBot** is an advanced algorithmic trading bot designed for the [Hyperliquid](https://hyperliquid.xyz/) DEX. It combines professional trading strategies, AI-powered signal validation, and a modern Next.js dashboard for real-time monitoring and control.

---

## ✨ Key Features

### 🎯 Trading Strategies
- **Trend Following**: EMA crossover with RSI confirmation
- **Mean Reversion**: Smart oversold/overbought detection with safety filters
- **Chart Patterns**: Double Top/Bottom, Bull Flags, Head & Shoulders (NEW!)
- **Regime Detection**: Automatic TREND vs RANGE market classification

### 🤖 AI Integration
- **Signal Validation**: Every trade is validated by AI before execution
- **Risk Analysis**: Professional risk assessment for active positions
- **Market Commentary**: Real-time analysis with technical indicators

### 📊 Advanced Features
- **Token Scanner**: Automatic discovery of high-momentum opportunities
- **Gamification System**: Progressive leverage unlocking based on performance
- **State Persistence**: Crash-proof with atomic JSON state management
- **Discord Notifications**: Real-time alerts for entries, exits, and risks

### 🎨 Modern UI
- **Next.js 14 Dashboard**: Real-time monitoring with beautiful dark theme
- **Strategy Monitor**: Live progress tracking with dynamic conditions
- **Active Trade Card**: Integrated AI risk analysis and PnL tracking
- **Config Page**: Centralized settings for size, leverage, and execution mode

---

## 🚀 Quick Start

### Prerequisites
- **Python 3.11+**
- **Node.js 18+**
- **PM2** (for process management)
- **Hyperliquid Account** with API keys

### Installation

1. **Clone the repository**
```bash
git clone https://github.com/nico2511/NovaBot.git
cd NovaBot
```

2. **Install Python dependencies**
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

3. **Install Frontend dependencies**
```bash
cd frontend
npm install
npm run build
cd ..
```

4. **Configure Environment**

Create a `.env` file in the root directory:
```env
# Hyperliquid API Keys
HYPERLIQUID_PRIVATE_KEY=your_private_key_here
HYPERLIQUID_WALLET_ADDRESS=your_wallet_address_here

# AI Integration (Optional but recommended)
OPENROUTER_API_KEY=your_openrouter_key_here

# Discord Notifications (Optional)
DISCORD_WEBHOOK_URL=your_webhook_url_here
```

5. **Start the Bot**

**Option A: Using PM2 (Recommended for production)**
```bash
npx pm2 start ecosystem.config.js
npx pm2 logs  # View logs
```

**Option B: Manual Start (Development)**
```bash
# Terminal 1: Start Backend
python main_nextjs.py

# Terminal 2: Start Frontend
cd frontend
npm run dev
```

6. **Access the Dashboard**
- **Frontend**: http://localhost:3000
- **Backend API**: http://localhost:8001

---

## 📖 Documentation

- **[CONTEXT.md](docs/CONTEXT.md)**: Project overview, architecture, and technical decisions
- **[SETUP_GUIDE.md](docs/SETUP_GUIDE.md)**: Detailed installation guide
- **[STRATEGIES.md](docs/STRATEGIES.md)**: Strategy descriptions and parameters
- **[SECURITY_WARNING.md](docs/SECURITY_WARNING.md)**: Security best practices

---

## 🎯 Usage

### Basic Workflow

1. **Configure Settings** (`/config` page)
   - Set trade size (Fixed USDC or % of balance)
   - Choose leverage (1x-20x, gamification-capped)
   - Select execution mode (Simulation or Live)

2. **Start the Engine**
   - Click "START ENGINE" to begin market analysis
   - Bot will detect regime and activate appropriate strategies

3. **Enable Trading** (Optional)
   - Click "ENABLE TRADING" to allow trade execution
   - Signals will be validated by AI before execution

4. **Monitor Performance**
   - View active strategies and their progress
   - Check AI risk analysis for open positions
   - Review recent signals and PnL

### Strategy Configuration

Edit `strategies.json` to enable/disable strategies:

```json
{
    "strategies": {
        "scalp_ema_rsi": {
            "enabled": true,
            "type": "trend",
            "params": {
                "ema_fast": 9,
                "ema_slow": 21,
                "rsi_period": 14
            }
        },
        "double_bottom": {
            "enabled": false,
            "type": "pattern",
            "params": {
                "pivot_order": 5,
                "tolerance": 0.02,
                "min_rr": 1.5
            }
        }
    }
}
```

---

## 🏗️ Architecture

```
NovaBot/
├── app/                    # Core bot logic
│   ├── services/          # Exchange, AI, indicators
│   ├── core/              # Risk management, state
│   └── utils/             # Helpers, token metadata
├── backend/               # FastAPI server
│   ├── api.py            # REST endpoints
│   └── routes/           # Modular routes
├── frontend/              # Next.js dashboard
│   ├── app/              # Pages (v1, v2, config)
│   └── components/       # React components
├── strategies/            # Trading strategies
│   ├── base.py           # Base strategy class
│   ├── scalp_ema_rsi.py  # Trend strategy
│   ├── double_bottom.py  # Pattern recognition
│   └── engine.py         # Strategy orchestration
├── main_nextjs.py         # Bot entry point
└── strategies.json        # Strategy configuration
```

---

## 🔧 Advanced Configuration

### Pattern Recognition Strategies

Enable chart pattern detection by setting `"enabled": true` in `strategies.json`:

- **Double Bottom**: Bullish reversal (2 lows + neckline breakout)
- **Double Top**: Bearish reversal (2 highs + neckline breakout)
- **Bull Flag**: Continuation pattern (impulse + consolidation)
- **Head & Shoulders**: Major bearish reversal

All patterns include:
- Pivot detection with configurable window size
- Volume confirmation filters
- Minimum R:R ratio enforcement (default 1.5:1)
- Real-time progress tracking in UI

### AI Signal Validation

The bot uses AI to validate every signal before execution:

```python
# Automatic validation with configurable thresholds
MIN_CONFIDENCE = 75  # Reject signals below this confidence
REQUIRE_APPROVAL = True  # AI must explicitly approve
```

AI analyzes:
- Signal alignment with market bias
- Entry price logic (support/resistance)
- SL/TP placement quality
- Volume confirmation
- RSI extremes
- Overall risk/reward

---

## 📊 Performance & Monitoring

### Metrics Tracked
- **Win Rate**: Percentage of profitable trades
- **Average R:R**: Risk/Reward ratio per trade
- **Max Drawdown**: Largest peak-to-trough decline
- **Sharpe Ratio**: Risk-adjusted returns

### Logs & Debugging
```bash
# View bot logs
npx pm2 logs hl-bot-engine

# View frontend logs
npx pm2 logs hl-frontend

# Restart after code changes
npx pm2 restart hl-bot-engine
```

---

## ⚠️ Risk Disclaimer

**IMPORTANT**: This bot is provided for educational purposes only. Trading cryptocurrencies involves substantial risk of loss.

- **Never risk more than you can afford to lose**
- **Start with small position sizes**
- **Test thoroughly in simulation mode first**
- **Monitor the bot regularly**
- **Keep your private keys secure**

The authors are not responsible for any financial losses incurred while using this software.

---

## 🤝 Contributing

Contributions are welcome! Please:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

---

## 📝 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

## 🙏 Acknowledgments

- [Hyperliquid](https://hyperliquid.xyz/) for the DEX platform
- [OpenRouter](https://openrouter.ai/) for AI integration
- [Next.js](https://nextjs.org/) for the amazing frontend framework
- [FastAPI](https://fastapi.tiangolo.com/) for the blazing-fast backend

---

## 📞 Support

- **Issues**: [GitHub Issues](https://github.com/nico2511/NovaBot/issues)
- **Discussions**: [GitHub Discussions](https://github.com/nico2511/NovaBot/discussions)
- **Documentation**: [docs/](docs/)

---

**Made with ❤️ by the NovaBot Team**
