# NovaBot - Quick Start Guide

## 🚀 Getting Started in 5 Minutes

### 1. Backend Setup

```bash
cd novabot

# Install dependencies
pip install fastapi uvicorn sqlalchemy pydantic-settings pytest pytest-asyncio httpx

# Start server
python main.py
```

Server running at: `http://localhost:8000`

### 2. Frontend Setup

```bash
cd frontend

# Install dependencies
npm install

# Start dev server
npm run dev
```

Frontend running at: `http://localhost:3000`

### 3. Test the API

```bash
# Health check
curl http://localhost:8000/health

# Calculate tier
curl -X POST http://localhost:8000/api/v1/gamification/calculate-tier \
  -H "Content-Type: application/json" \
  -d '{"equity": 250}'

# Expected: {"equity": 250, "tier": "PROTOSTAR"}
```

### 4. Test WebSocket

Open browser console at `http://localhost:3000`:

```javascript
const ws = new WebSocket('ws://localhost:8000/ws/gamification')
ws.onmessage = (e) => console.log(JSON.parse(e.data))
// Should see: {type: "CONNECTED", message: "..."}
```

---

## 📚 Full Documentation

See [`walkthrough.md`](file:///C:/Users/User/.gemini/antigravity/brain/79cf2554-791d-4819-a5a4-2c8ab667e31a/walkthrough.md) for complete documentation.

---

## 🧪 Run Tests

```bash
# All tests
pytest tests/ -v

# Specific test
pytest tests/test_tier_calculator.py -v
```

---

## 🎯 Key Endpoints

| Endpoint | Method | Example |
|----------|--------|---------|
| Calculate Tier | POST | `/api/v1/gamification/calculate-tier` |
| Check Access | POST | `/api/v1/gamification/check-access` |
| Log Decision | POST | `/api/v1/audit/log-decision` |
| Get Decisions | GET | `/api/v1/audit/decisions` |
| Override Tier | POST | `/api/v1/admin/override-tier` |
| WebSocket | WS | `/ws/gamification` |

---

## 🏗️ Project Structure

```
novabot/
├── app/                    # Backend (new clean core)
│   ├── core/              # Config, database
│   ├── gamification/      # Tier logic
│   ├── services/          # Audit, business logic
│   └── api/routes/        # FastAPI endpoints
├── frontend/              # Next.js 14 app
│   ├── app/              # Pages
│   ├── components/       # React components
│   ├── hooks/            # Custom hooks
│   └── contexts/         # Theme context
├── tests/                # Pytest suite
├── main.py               # Entry point
└── novabot.db            # SQLite database
```

---

## ⚡ Quick Commands

```bash
# Backend
python main.py                    # Start server
pytest tests/ -v                  # Run tests

# Frontend
npm run dev                       # Start dev server
npm run build                     # Build for production

# Database
sqlite3 novabot.db ".tables"     # List tables
sqlite3 novabot.db "SELECT * FROM users;"  # Query users
```

---

## 🎨 Tier System

| Tier | Equity Range | Color | Icon |
|------|-------------|-------|------|
| NEBULA | < $100 | Gray | ◆ |
| PROTOSTAR | $100-$500 | Silver | ◇ |
| SUPERNOVA | ≥ $500 | Gold | ◈ |

---

## 📊 Implementation Stats

- **Stories:** 10/10 ✅
- **Tests:** 28+ passing ✅
- **Code:** ~2,900 lines
- **Time:** ~8 hours

---

**Need help?** See full walkthrough or check troubleshooting section.
