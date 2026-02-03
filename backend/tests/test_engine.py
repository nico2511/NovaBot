from unittest.mock import patch, MagicMock

def test_get_status_success(client, mock_bot):
    """Test standard status retrieval"""
    mock_bot.is_running = True
    
    # Mock services import inside route
    with patch("app.services.hyperliquid_service.hyperliquid_service.get_positions", return_value=[]), \
         patch("app.services.hyperliquid_service.hyperliquid_service.get_account_balance", return_value={"status": "success", "total_equity": 1000.0}):
        
        response = client.get("/api/status")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "running"
        assert data["balance"] == 1000.0

def test_engine_start(client, mock_bot):
    """Test start command"""
    response = client.post("/api/engine/start")
    
    assert response.status_code == 200
    assert response.json()["status"] == "started"
    
    mock_bot.start.assert_called_once()
    assert mock_bot.trading_enabled is True

def test_engine_stop(client, mock_bot):
    """Test stop command"""
    mock_bot.is_running = True
    response = client.post("/api/engine/stop")
    
    assert response.status_code == 200
    assert response.json()["status"] == "stopped"
    
    mock_bot.stop.assert_called_once()
    assert mock_bot.trading_enabled is False

def test_engine_restart(client, mock_bot):
    """Test restart command"""
    mock_bot.is_running = True
    
    with patch("time.sleep"): # Fast travel
        response = client.post("/api/engine/restart")
    
    assert response.status_code == 200
    mock_bot.stop.assert_called_once()
    mock_bot.start.assert_called_once()

def test_engine_panic(client, mock_bot):
    """Test panic button"""
    response = client.post("/api/engine/panic")
    
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "panic_executed"
    
    mock_bot.stop.assert_called_once()
    assert mock_bot.trading_enabled is False

def test_disconnected_503(client, mock_bridge):
    """Test that API returns 503 when bot is disconnected"""
    # Simulate disconnection
    mock_bridge.is_connected.return_value = False
    
    endpoints = [
        ("POST", "/api/engine/start"),
        ("POST", "/api/engine/stop"),
        ("GET", "/api/status"),
        ("POST", "/api/engine/panic")
    ]
    
    for method, url in endpoints:
        if method == "POST":
            response = client.post(url)
        else:
            response = client.get(url)
            
        assert response.status_code == 503, f"Endpoint {url} should be 503"
        assert "not connected" in response.json()["detail"]
