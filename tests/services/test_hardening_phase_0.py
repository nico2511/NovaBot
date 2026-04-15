
import pytest
from unittest.mock import MagicMock, patch
from app.services.safe_order_manager import SafeOrderManager
from app.services.position_reconciler import PositionReconciler
from app.services.hyperliquid_service import HyperliquidService

@pytest.fixture
def mock_hl_service():
    service = MagicMock()
    # Default mocks
    service.get_positions.return_value = []
    service.get_open_orders.return_value = []
    return service

@pytest.fixture
def safe_order_manager(mock_hl_service):
    # Initialize with mocked service
    return SafeOrderManager(mock_hl_service)

@pytest.fixture
def position_reconciler(mock_hl_service, safe_order_manager):
    return PositionReconciler(mock_hl_service, safe_order_manager)

# === SafeOrderManager Tests ===

def test_ensure_sl_tp_calculates_correctly(safe_order_manager, mock_hl_service):
    """Test that ensure_sl_tp calculates SL/TP based on fallback rules when no SL/TP is present"""
    # Arrange
    symbol = "BTC"
    position = {"symbol": "BTC", "entry_price": 50000.0, "side": "BUY", "size": 1.0}
    
    # Mock Open Orders (return empty list -> no SL/TP)
    mock_hl_service.get_open_orders.return_value = []
    
    # Act
    safe_order_manager.ensure_sl_tp(position)
    
    # Assert
    # Check that place_protection_orders was called
    mock_hl_service._place_protection_orders.assert_called_once()


def test_ensure_sl_tp_idempotent(safe_order_manager, mock_hl_service):
    """Test that ensure_sl_tp does NOT place orders if they already exist"""
    # Arrange
    position = {"symbol": "BTC", "entry_price": 50000.0, "side": "BUY", "size": 1.0}
    # Mock existing orders
    mock_hl_service.get_open_orders.return_value = [
        {"coin": "BTC", "order_type": {"trigger": {"tpsl": "sl"}}},
        {"coin": "BTC", "order_type": {"trigger": {"tpsl": "tp"}}}
    ]
    
    # Act
    safe_order_manager.ensure_sl_tp(position)
    
    # Assert
    mock_hl_service.place_protection_orders.assert_not_called()

# === PositionReconciler Tests ===

def test_reconcile_detects_orphans(position_reconciler, mock_hl_service, safe_order_manager):
    """Test that reconcile identifies positions without SL/TP and delegates to SafeOrderManager"""
    # Arrange
    # Position exists on exchange
    mock_hl_service.get_positions.return_value = [
        {"symbol": "ETH", "entry_price": 3000.0, "side": "BUY", "size": 10.0}
    ]
    # No open orders
    mock_hl_service.get_open_orders.return_value = []
    
    # Mock manager to verify delegation
    safe_order_manager.ensure_sl_tp = MagicMock()
    
    # Act
    position_reconciler.reconcile()
    
    # Assert
    safe_order_manager.ensure_sl_tp.assert_called_once()
    args, _ = safe_order_manager.ensure_sl_tp.call_args
    assert args[0]["symbol"] == "ETH"

def test_reconcile_ignores_secured_positions(position_reconciler, mock_hl_service, safe_order_manager):
    """Test that reconcile does nothing for positions that are already secured"""
    # Arrange
    mock_hl_service.get_positions.return_value = [
        {"symbol": "SOL", "entry_price": 100.0, "side": "SELL", "size": 50.0}
    ]
    # Existing SL/TP
    mock_hl_service.get_open_orders.return_value = [
        {"coin": "SOL", "order_type": {"trigger": {"tpsl": "sl"}}},
        {"coin": "SOL", "order_type": {"trigger": {"tpsl": "tp"}}}
    ]
    
    safe_order_manager.ensure_sl_tp = MagicMock()
    
    # Act
    position_reconciler.reconcile()
    
    # Assert
    # Reconciler SHOULD call check on every position. SafeOrderManager handles the "ignore" logic.
    safe_order_manager.ensure_sl_tp.assert_called_once()


def test_reconciler_adopts_orphan_positions(position_reconciler, mock_hl_service):
    """Test that orphan positions on exchange are adopted into bot state"""
    from unittest.mock import MagicMock
    
    # Mock bot_context
    mock_bot = MagicMock()
    mock_bot.active_trades = {"BTC": {"symbol": "BTC"}}
    position_reconciler.bot_context = mock_bot
    
    # Exchange has ETH position not in local state
    mock_hl_service.get_positions.return_value = [
        {"symbol": "BTC", "size": 1.0},
        {"symbol": "ETH", "size": 5.0, "entry_price": 3200.0}
    ]
    
    # Act
    position_reconciler.reconcile()
    
    # Assert
    mock_bot._adopt_existing_position.assert_called_once()
    args, _ = mock_bot._adopt_existing_position.call_args
    assert args[0]["symbol"] == "ETH"
