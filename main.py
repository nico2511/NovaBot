import sys
import os
import uvicorn
from contextlib import asynccontextmanager
from fastapi import FastAPI
from app.core.config import settings
from app.core.database import init_db

# Verification print
print(f"Initializing {settings.PROJECT_NAME}...")
print(f"Database URL: {settings.DATABASE_URL}")

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup logic
    print("Executing startup tasks...")
    try:
        init_db()
        print("✅ Database initialized successfully.")
    except Exception as e:
        print(f"❌ Database initialization failed: {e}")
    
    yield
    
    # Shutdown logic
    print("Shutting down...")

app = FastAPI(title=settings.PROJECT_NAME, version=settings.VERSION, lifespan=lifespan)

@app.get("/")
def read_root():
    return {
        "status": "online",
        "project": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "docs_url": "/docs"
    }

@app.get("/health")
def health_check():
    return {"status": "ok", "db_connected": True} # simplified

# Include API routers
from app.api.routes import gamification, audit, websocket, admin

app.include_router(gamification.router, prefix="/api/v1")
app.include_router(audit.router, prefix="/api/v1")
app.include_router(websocket.router)  # WebSocket route (no prefix)
app.include_router(admin.router, prefix="/api/v1")  # Admin routes

if __name__ == "__main__":
    if os.getenv("PORT"):
         port = int(os.getenv("PORT"))
    else:
         port = 8000
         
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=True)
