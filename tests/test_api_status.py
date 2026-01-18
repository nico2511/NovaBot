import pytest
from fastapi.testclient import TestClient
from backend.api import app, bot_state
import json
import os

client = TestClient(app)

# Mock bot_state.json content
MOCK_STATE = {
    "active_trade": None,
    "trading_enabled": True,
    "is_running": True,
    "active_symbol": "BTC",
    "last_updated": "2026-01-17 12:00:00",
    "risk_state": {
        "daily_pnl": 123.45,
        "open_positions": 2,
        "is_stop_mode": False,
        "stop_reason": ""
    }
}

@pytest.fixture
def mock_bot_state_file(tmp_path):
    # Setup: Create a temporary bot_state.json
    state_file = tmp_path / "bot_state.json"
    state_file.write_text(json.dumps(MOCK_STATE))
    
    # Patch the BASE_DIR or file path in BotState if possible, 
    # but since it's hardcoded to os.getcwd() or similar, we might need to mock os.path.exists/open
    # For simplicity in this environment, we will try to mock the load_state method or the file read.
    return state_file

def test_get_status_structure():
    """FR1: Morning Check Dashboard - Data Structure"""
    response = client.get("/api/status")
    assert response.status_code == 200
    data = response.json()
    
    # Check existing fields
    assert "is_running" in data
    assert "trading_enabled" in data
    
    # Check NEW fields (Should FAIL initially)
    assert "daily_pnl" in data, "daily_pnl not found in response"
    assert "active_positions" in data, "active_positions not found in response"
    assert "last_updated" in data, "last_updated not found in response"
    
    # Validate types
    if "daily_pnl" in data:
        assert isinstance(data["daily_pnl"], float)
    if "active_positions" in data:
        assert isinstance(data["active_positions"], int)
