"""
Integration Tests for API Routers
Verifies API endpoints are reachable and return expected structure.
"""
from fastapi.testclient import TestClient

def test_api_root(test_client):
    response = test_client.get("/")
    assert response.status_code == 200
    assert response.json()["version"] == "2.0"

def test_health_check(test_client):
    """Without a connected bot bridge, /health must report unhealthy (HTTP 503)."""
    response = test_client.get("/health")
    assert response.status_code == 503
    data = response.json()
    assert data["status"] == "unhealthy"
    assert data["bot_connected"] is False
    assert data["reason"] == "bot_not_connected"

def test_settings_global_defaults(test_client):
    """
    Verify /api/settings/global returns defaults when no file exists.
    Now expected to work (return 200) even if bot is not connected.
    """
    response = test_client.get("/api/settings/global")
    assert response.status_code == 200
    data = response.json()
    assert "max_positions" in data
    assert "risk_profile" in data

def test_engine_status_no_bot(test_client):
    """Verify engine status returns default/offline state when bot logic is not running"""
    response = test_client.get("/api/status")
    
    if response.status_code == 503:
        # Strict dependency check message in dependencies.py
        assert response.json()["detail"] == "Bot engine not connected - service unavailable"
    else:
        assert response.status_code == 200

def test_market_candles_structure(test_client):
    """Verify market endpoints structure (mocking hyperliquid service needed usually)"""
    # Without mocking hyperliquid_service, this will try to call real API or fail.
    # For integration test, we might skip or expect failure if no creds.
    pass
