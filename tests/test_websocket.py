import pytest
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

class TestWebSocketAndCompatibility:
    """Test WebSocket and compatibility endpoints."""
    
    def test_legacy_gamification_status_endpoint(self):
        """Test legacy compatibility endpoint."""
        response = client.get("/api/v1/gamification/status")
        assert response.status_code == 200
        
        data = response.json()
        assert data["status"] == "success"
        assert "gamification" in data
        
        gam = data["gamification"]
        assert "level" in gam
        assert gam["level"] in ["Goblin", "Mercenary", "Whale"]
        assert "balance" in gam
        assert "progress" in gam
    
    def test_legacy_tier_mapping(self):
        """Test that new tiers are mapped to old names."""
        response = client.get("/api/v1/gamification/status")
        data = response.json()
        
        # With mock_equity = 250, should be PROTOSTAR → Mercenary
        assert data["gamification"]["level"] == "Mercenary"
        assert data["gamification"]["balance"] == 250.0
    
    def test_websocket_connection(self):
        """Test WebSocket connection."""
        with client.websocket_connect("/ws/gamification") as websocket:
            # Should receive connection confirmation
            data = websocket.receive_json()
            assert data["type"] == "CONNECTED"
            assert "message" in data
            
            # Test echo
            websocket.send_text("test")
            response = websocket.receive_json()
            assert response["type"] == "ECHO"
            assert response["data"] == "test"
