# Development Guide

## Environment Setup

### 1. Requirements
- **Python**: 3.10 or higher
- **Node.js**: 18+ (for PM2 management)
- **Git**: For version control

### 2. Installation
Clone the repository and enter the directory:
```bash
git clone https://github.com/nico2511/NovaBot.git
cd NovaBot
```

### 3. Virtual Environment
It is strictly recommended to use a virtual environment to avoid dependency conflicts.

**Windows (PowerShell):**
```powershell
python -m venv .venv
.\.venv\Scripts\Activate
pip install -r requirements.txt
```

**Linux/WSL:**
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 4. Configuration
Duplicate `.env.template` to `.env` and fill in your keys:
```bash
cp .env.template .env
```
Key variables:
- `HL_ACCOUNT_ADDRESS`: Your Hyperliquid Wallet Address
- `HL_PRIVATE_KEY`: Your Wallet Private Key (Keep Secret!)
- `OPENROUTER_API_KEY`: For AI Analysis features

## Running Locally

### Backend (FastAPI + Bot Engine)
To run the bot logic and API:
```bash
# Ensure venv is active
python main_nextjs.py
```
This starts:
- REST API on `http://localhost:8001`
- Trading Bot Loop (in background thread)

### Strategy Development
Strategies are located in `strategies/`.
To add a new strategy:
1. Create a file in `strategies/` (e.g., `my_strategy.py`).
2. Inherit from `BaseStrategy`.
3. Implement `analyze()` method.
4. Register it in `strategies.json` configuration.

## Testing
Unit tests are located in `utils/tests/`.
Run tests via:
```bash
python -m pytest utils/tests/
# OR
pytest
```

## Common Commands
- **Linting**: `flake8 app/`
- **Dependency Update**: `pip freeze > requirements.txt` (Be careful with cross-platform compatibility)
