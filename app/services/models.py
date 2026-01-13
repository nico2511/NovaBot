from sqlalchemy import Column, Integer, String, JSON, DateTime
from sqlalchemy.sql import func
from app.core.database import Base

class DecisionLog(Base):
    __tablename__ = "decision_logs"
    
    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime(timezone=True), server_default=func.now())
    strategy_name = Column(String, index=True)
    ai_persona = Column(String)
    verdict = Column(String)  # BUY, SELL, HOLD
    reasoning = Column(String)
    indicators_snapshot = Column(JSON)  # Full snapshot of indicators at T
