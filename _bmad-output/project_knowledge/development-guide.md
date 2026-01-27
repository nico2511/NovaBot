# Development & Deployment Guide

## Prerequisites
- **Python**: 3.10+
- **Node.js**: 18+ (for Frontend)
- **PM2**: Process Manager (`npm install -g pm2`)

## 🚀 Quick Start
 The project includes a master script that handles setup and startup:

```bash
./start_integrated.sh
```
**This script acts as a "One-Click" launcher:**
1.  Creates/Activates Python virtual environment (`.venv`)
2.  Installs Python dependencies (`requirements.txt`)
3.  Builds the Frontend (`frontend-v3`) with `npm install` & `npm run build`
4.  Starts both Backend and Frontend using PM2

## Manual Setup

### 1. Backend (Python)
```bash
# Create venv
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# Install deps
pip install -r requirements.txt
```

### 2. Frontend (Next.js)
```bash
cd frontend-v3
npm install
npm run dev  # accessible at http://localhost:3000
```

## 🏗️ Production Deployment
The project uses **PM2** for process management.

**Configuration:** `ecosystem.config.js`

| App Name | Port | Entry Script |
| :--- | :--- | :--- |
| `novabot-backend` | **8001** | `backend/api.py` |
| `novabot-frontend` | **3000** | `next start` |

**Control Commands:**
```bash
pm2 status
pm2 logs
pm2 restart all
pm2 stop all
```
