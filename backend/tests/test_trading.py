from unittest.mock import patch

def test_enable_trading(client, mock_bot):
    """Test enabling trading"""
    response = client.post("/api/trading/enable")
    
    assert response.status_code == 200
    assert response.json()["status"] == "enabled"
    
    assert mock_bot.trading_enabled is True
    # Verify state save called
    # (We could mock StateManager, but verify_called on bot logic is sufficient usually)

def test_disable_trading(client, mock_bot):
    """Test disabling trading"""
    mock_bot.trading_enabled = True
    response = client.post("/api/trading/disable")
    
    assert response.status_code == 200
    assert response.json()["status"] == "disabled"
    
    assert mock_bot.trading_enabled is False

def test_switch_symbol_success(client, mock_bot):
    """Test successful symbol switch"""
    # Mock metadata containing target symbol
    with patch("app.services.hyperliquid_service.hyperliquid_service._fetch_metadata") as mock_meta:
        mock_meta.return_value = {"universe": [{"name": "BTC"}, {"name": "ETH"}, {"name": "SOL"}]}
        
        mock_bot.active_symbol = "BTC"
        
        response = client.post("/api/switch_symbol", json={"symbol": "SOL"})
        
        assert response.status_code == 200
        assert response.json()["status"] == "success"
        
        mock_bot.switch_active_symbol.assert_called_with("SOL")

def test_switch_symbol_invalid(client, mock_bot):
    """Test switching to non-existent symbol"""
    with patch("app.services.hyperliquid_service.hyperliquid_service._fetch_metadata") as mock_meta:
        mock_meta.return_value = {"universe": [{"name": "BTC"}]}
        
        response = client.post("/api/switch_symbol", json={"symbol": "FAKECOIN"})
        
        assert response.status_code == 400
        assert "not found" in response.json()["detail"]

def test_get_positions(client, mock_bot):
    """Test positions retrieval delegate"""
    with patch("app.services.hyperliquid_service.hyperliquid_service.get_positions") as mock_pos:
        mock_pos.return_value = [{"coin": "BTC", "entryPx": "50000", "szi": "0.1"}]
        
        response = client.get("/api/positions")
        
        assert response.status_code == 200
        data = response.json()
        assert "positions" in data
        assert data["positions"][0]["coin"] == "BTC"

def test_force_sync(client, mock_bot):
    """Test force sync endpoint"""
    mock_bot.force_sync.return_value = {"status": "synced"}
    
    response = client.post("/api/force_sync")
    
    assert response.status_code == 200
    assert response.json()["status"] == "synced"
    mock_bot.force_sync.assert_called_once()
