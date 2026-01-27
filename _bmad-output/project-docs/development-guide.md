# Development & Operations Guide - NovaBot

This guide provides instructions for setting up, developing, and deploying NovaBot.

## 🛠 Prerequisites
- **Python**: 3.10 or higher.
- **Node.js**: 18.x or higher (for frontend).
- **Hyperliquid Account**: Mainnet API Key or Testnet Key.
- **Discord Webhook** (Optional): For alerts.

---

## 🚀 Local Development

### 1. Backend & Bot Engine
```bash
# Setup Virtual Environment
python -m venv venv
source venv/bin/activate  # Or `venv\Scripts\activate` on Windows

# Install Dependencies
pip install -r requirements.txt

# Configure Environment
cp .env.template .env
# Edit .env with your HL_PRIVATE_KEY and HL_ACCOUNT_ADDRESS

# Run the API & Bot
python main_integrated.py # Or use the startup script
```

### 2. Frontend
```bash
cd frontend-v3
npm install
npm run dev
```
The dashboard will be available at `http://localhost:3000`.

---

## 📦 Deployment
NovaBot is designed to run 24/7 on a VPS.

### PM2 (Recommended)
Use `pm2` to manage the lifecycle of both the backend and frontend.
```bash
# Start with ecosystem config
pm2 start ecosystem.config.js
```

### Docker (Optional)
A `Dockerfile` is provided for containerized environments.

---

## 🧪 Testing
- **Backend**: Run `pytest ./tests` for unit and integration tests.
- **Frontend**: Standard `npm run lint` and `next build` validation.
