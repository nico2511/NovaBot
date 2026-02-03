from unittest.mock import patch

def test_get_global_settings(client, mock_bot):
    """Test retrieving global settings"""
    response = client.get("/api/settings/global")
    assert response.status_code == 200
    
    data = response.json()
    assert "max_positions" in data
    assert "risk_profile" in data
    assert data["max_positions"] == 1 # Default from mock or storage

def test_update_global_settings(client, mock_bot):
    """Test updating global settings"""
    payload = {
        "max_positions": 5,
        "daily_stop_loss": 100.0,
        "trading_timeframe": "1h",
        "bot_persona": "Sniper",
        "risk_profile": "High Volatility Hunter",
        "ai_thresholds": {"high": 90, "medium": 60, "low": 30},
        "default_leverage": 10,
        "default_margin_type": "CROSS",
        "auto_start_trading": True,
        "notifications": {}
    }
    
    # Mock storage to avoid real IO and allow verification
    with patch("backend.services.storage.storage_service.load_settings", return_value={}), \
         patch("backend.services.storage.storage_service.save_settings") as mock_save:
        
        response = client.post("/api/settings/global", json=payload)
        
        assert response.status_code == 200
        assert response.json()["status"] == "success"
        
        # Verify bot context updated
        assert mock_bot.global_settings["risk_defaults"]["max_positions"] == 5
        assert mock_bot.global_settings["risk_defaults"]["default_leverage"] == 10
        
        # Verify storage save called
        mock_save.assert_called_once()    

def test_get_scanner_settings(client, mock_bot):
    """Test retrieving scanner settings"""
    mock_bot.scanner_settings = {
        "enabled": True, 
        "interval": 15,
        "min_score": 88,
        "auto_switch": False,
        "gamification_enabled": True,
        "max_funding_long": 0.001,
        "min_funding_short": -0.001,
        "funding_filter_enabled": True
    }
    
    response = client.get("/api/settings/scanner")

    assert response.status_code == 200
    assert response.json()["min_score"] == 88

def test_update_scanner_settings(client, mock_bot):
    """Test updating scanner settings"""
    payload = {
        "enabled": False,
        "interval": 30,
        "min_score": 60,
        "auto_switch": True,
        "gamification_enabled": False,
        "max_funding_long": 0.002,
        "min_funding_short": -0.002,
        "funding_filter_enabled": True
    }
    
    with patch("backend.services.storage.storage_service.load_settings", return_value={}), \
         patch("backend.services.storage.storage_service.save_settings") as mock_save:
         
        response = client.post("/api/settings/scanner", json=payload)
        
        assert response.status_code == 200
        assert mock_bot.scanner_settings["min_score"] == 60
        mock_save.assert_called_once()

def test_legacy_update_adapter(client, mock_bot):
    """Test legacy /update endpoint behavior"""
    
    # 1. Update Scanner via legacy
    payload_scanner = {
        "section": "scanner",
        "data": {
            "enabled": True,
            "interval": 60,
            "min_score": 99,
            "auto_switch": False,
            "gamification_enabled": True,
             "max_funding_long": 0.001,
            "min_funding_short": -0.001,
            "funding_filter_enabled": True
        }
    }
    
    with patch("backend.services.storage.storage_service.load_settings", return_value={}), \
         patch("backend.services.storage.storage_service.save_settings"):
         
        response = client.post("/api/settings/update", json=payload_scanner)
        assert response.status_code == 200
        assert mock_bot.scanner_settings["min_score"] == 99
    
    # 2. Update Risk via legacy
    payload_risk = {
        "section": "risk_defaults",
        "data": {
            "max_positions": 10,
            "daily_stop_loss": 200
        }
    }
    
    # We need to ensure load_settings returns current state for patching
    with patch("backend.services.storage.storage_service.load_settings", return_value={}), \
         patch("backend.services.storage.storage_service.save_settings") as mock_save:
         
        response = client.post("/api/settings/update", json=payload_risk)
        assert response.status_code == 200
        
        # Verify it got mapped to global settings on bot
        # The legacy adapter updates the bot.global_settings
        assert mock_bot.global_settings["risk_defaults"]["max_positions"] == 10
        mock_save.assert_called_once()
