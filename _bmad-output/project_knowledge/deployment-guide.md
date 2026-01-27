# Deployment Guide

## Overview
NovaBot is deployed as a consolidated Application process managed by **PM2**.
It requires a **Python 3.10+** environment and **Node.js** (for PM2 management).

## Development vs Production
- **Development**: Run directly via Python or use the provided shell script for integration testing.
- **Production**: Always run via PM2 to ensure auto-restart and log management.

## Prerequisites
- **OS**: Linux (Debian/Ubuntu recommended) or Windows (via WSL2 or PowerShell).
- **Runtime**:
  - Python 3.10+
  - Node.js 18+ (for PM2)
- **Dependencies**:
  - `pm2` (Global or Local): `npm install -g pm2`

## Deployment Steps

### 1. Environment Configuration
Create a `.env` file at the project root based on `.env.template`:
```ini
HL_ACCOUNT_ADDRESS=0x...
HL_PRIVATE_KEY=...
OPENROUTER_API_KEY=...
DISCORD_WEBHOOK_URL=...
```

### 2. Startup Script (`start_integrated.sh`)
This script handles dependency checks, venv activation, and PM2 startup.
```bash
./start_integrated.sh
```

### 3. Process Management (PM2)
The ecosystem is defined in `ecosystem.config.js`.

**Start/Restart:**
```bash
pm2 start ecosystem.config.js
```

**Stop:**
```bash
pm2 stop all
```

**View Logs:**
```bash
pm2 logs hl-bot-engine
```

## PM2 Configuration (`ecosystem.config.js`)
```javascript
module.exports = {
    apps: [
        {
            name: 'hl-bot-engine',
            script: 'main_nextjs.py', # Application Entry Point
            interpreter: './.venv/Scripts/python.exe', # Windows Config
            env: {
                PYTHONPATH: process.cwd()
            },
            autorestart: true,
            max_restarts: 10
        }
    ]
}
```
**Note:** The `interpreter` path in `ecosystem.config.js` is currently set for Windows (`./.venv/Scripts/python.exe`). Update this for Linux (`./.venv/bin/python`) if deploying to a Linux server.

## Troubleshooting
- **Import Errors**: Ensure `.venv` is active and `requirements.txt` is installed.
- **Permission Denied**: Run `chmod +x start_integrated.sh`.
- **API Connection Failed**: Check `.env` keys and internet connection.
