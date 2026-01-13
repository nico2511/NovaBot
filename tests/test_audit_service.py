import pytest
from app.services.audit_service import AuditService
from app.core.database import SessionLocal, init_db
from app.services.models import DecisionLog
import asyncio

# Initialize DB before tests
init_db()

class TestAuditService:
    """Test suite for AuditService."""
    
    def test_log_decision_sync_creates_entry(self):
        """Test that log_decision_sync creates a database entry."""
        # Prepare test data
        indicators = {
            "rsi": 45.5,
            "ema_20": 100.5,
            "ema_50": 98.2,
            "volume": 1500000
        }
        
        # Log decision
        log_id = AuditService.log_decision_sync(
            strategy_name="TestStrategy",
            ai_persona="Conservative Trader",
            verdict="HOLD",
            reasoning="RSI neutral, waiting for confirmation",
            indicators_snapshot=indicators
        )
        
        # Verify entry was created
        assert log_id is not None
        assert log_id > 0
        
        # Verify data in database
        db = SessionLocal()
        try:
            log_entry = db.query(DecisionLog).filter(DecisionLog.id == log_id).first()
            assert log_entry is not None
            assert log_entry.strategy_name == "TestStrategy"
            assert log_entry.ai_persona == "Conservative Trader"
            assert log_entry.verdict == "HOLD"
            assert log_entry.reasoning == "RSI neutral, waiting for confirmation"
            assert log_entry.indicators_snapshot == indicators
            assert log_entry.timestamp is not None
        finally:
            db.close()
    
    def test_log_decision_stores_complete_snapshot(self):
        """Test that complete indicator snapshot is stored as JSON."""
        # Complex indicator snapshot
        indicators = {
            "price": 50000.5,
            "rsi": 65.3,
            "macd": {"value": 150, "signal": 145, "histogram": 5},
            "bollinger": {"upper": 51000, "middle": 50000, "lower": 49000},
            "volume": 2500000,
            "trend": "bullish"
        }
        
        log_id = AuditService.log_decision_sync(
            strategy_name="ComplexStrategy",
            ai_persona="Aggressive Scalper",
            verdict="BUY",
            reasoning="Strong bullish momentum with RSI confirmation",
            indicators_snapshot=indicators
        )
        
        # Verify complete snapshot is stored
        db = SessionLocal()
        try:
            log_entry = db.query(DecisionLog).filter(DecisionLog.id == log_id).first()
            assert log_entry.indicators_snapshot == indicators
            assert "macd" in log_entry.indicators_snapshot
            assert log_entry.indicators_snapshot["macd"]["histogram"] == 5
        finally:
            db.close()
    
    def test_verdict_normalized_to_uppercase(self):
        """Test that verdict is normalized to uppercase."""
        log_id = AuditService.log_decision_sync(
            strategy_name="TestStrategy",
            ai_persona="Test Persona",
            verdict="buy",  # lowercase
            reasoning="Test",
            indicators_snapshot={"test": 1}
        )
        
        db = SessionLocal()
        try:
            log_entry = db.query(DecisionLog).filter(DecisionLog.id == log_id).first()
            assert log_entry.verdict == "BUY"  # Should be uppercase
        finally:
            db.close()
    
    @pytest.mark.asyncio
    async def test_async_log_decision(self):
        """Test async version of log_decision."""
        indicators = {"rsi": 50, "price": 45000}
        
        log_id = await AuditService.log_decision(
            strategy_name="AsyncStrategy",
            ai_persona="Async Trader",
            verdict="SELL",
            reasoning="Async test",
            indicators_snapshot=indicators
        )
        
        assert log_id is not None
        assert log_id > 0
