import pytest
from fastapi.testclient import TestClient
from main import app
from app.core.database import init_db

# Initialize database before tests
init_db()

client = TestClient(app)

class TestIntegration:
    """Integration tests for Epic 1 components."""
    
    def test_calculate_tier_endpoint(self):
        """Test tier calculation via API."""
        response = client.post(
            "/api/v1/gamification/calculate-tier",
            json={"equity": 250}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["equity"] == 250
        assert data["tier"] == "PROTOSTAR"
    
    def test_check_access_endpoint(self):
        """Test access control via API."""
        response = client.post(
            "/api/v1/gamification/check-access",
            json={"user_tier": "NEBULA", "strategy_name": "premium_strategy"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["has_access"] == False
        
        # Test with higher tier
        response = client.post(
            "/api/v1/gamification/check-access",
            json={"user_tier": "SUPERNOVA", "strategy_name": "premium_strategy"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["has_access"] == True
    
    def test_log_decision_endpoint(self):
        """Test decision logging via API."""
        response = client.post(
            "/api/v1/audit/log-decision",
            json={
                "strategy_name": "IntegrationTestStrategy",
                "ai_persona": "Test Persona",
                "verdict": "BUY",
                "reasoning": "Integration test",
                "indicators_snapshot": {"rsi": 70, "price": 50000}
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert "log_id" in data
        assert data["message"] == "Decision logged successfully"
    
    def test_get_decisions_endpoint(self):
        """Test retrieving decision logs via API."""
        # First log a decision
        client.post(
            "/api/v1/audit/log-decision",
            json={
                "strategy_name": "TestStrategy",
                "ai_persona": "Test",
                "verdict": "HOLD",
                "reasoning": "Test",
                "indicators_snapshot": {"test": 1}
            }
        )
        
        # Then retrieve decisions
        response = client.get("/api/v1/audit/decisions?limit=5")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) > 0
        assert "strategy_name" in data[0]
        assert "verdict" in data[0]
    
    def test_full_integration_flow(self):
        """Test complete flow: calculate tier → check access → log decision."""
        # Step 1: Calculate tier
        tier_response = client.post(
            "/api/v1/gamification/calculate-tier",
            json={"equity": 600}
        )
        assert tier_response.status_code == 200
        tier = tier_response.json()["tier"]
        assert tier == "SUPERNOVA"
        
        # Step 2: Check access
        access_response = client.post(
            "/api/v1/gamification/check-access",
            json={"user_tier": tier, "strategy_name": "premium_strategy"}
        )
        assert access_response.status_code == 200
        assert access_response.json()["has_access"] == True
        
        # Step 3: Log decision
        log_response = client.post(
            "/api/v1/audit/log-decision",
            json={
                "strategy_name": "premium_strategy",
                "ai_persona": "Premium Trader",
                "verdict": "BUY",
                "reasoning": "Full integration test",
                "indicators_snapshot": {"equity": 600, "tier": tier}
            }
        )
        assert log_response.status_code == 200
        assert "log_id" in log_response.json()
