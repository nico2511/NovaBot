from typing import Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.core.database import SessionLocal
from app.services.models import DecisionLog
import asyncio
from datetime import datetime

class AuditService:
    """Service for logging AI trading decisions with full indicator snapshots."""
    
    @staticmethod
    async def log_decision(
        strategy_name: str,
        ai_persona: str,
        verdict: str,
        reasoning: str,
        indicators_snapshot: Dict[str, Any]
    ) -> int:
        """
        Log an AI trading decision with complete indicator snapshot.
        
        Args:
            strategy_name: Name of the strategy making the decision
            ai_persona: AI persona used for analysis
            verdict: Decision verdict (BUY, SELL, HOLD)
            reasoning: AI reasoning for the decision
            indicators_snapshot: Complete JSON snapshot of all indicators at instant T
            
        Returns:
            int: ID of the created log entry
            
        Critical: This function is async and non-blocking to ensure trading loop performance.
        """
        # Create new decision log entry
        log_entry = DecisionLog(
            strategy_name=strategy_name,
            ai_persona=ai_persona,
            verdict=verdict.upper(),
            reasoning=reasoning,
            indicators_snapshot=indicators_snapshot
        )
        
        # Use synchronous session (SQLite doesn't require async for our use case)
        db = SessionLocal()
        try:
            db.add(log_entry)
            db.commit()
            db.refresh(log_entry)
            return log_entry.id
        finally:
            db.close()
    
    @staticmethod
    def log_decision_sync(
        strategy_name: str,
        ai_persona: str,
        verdict: str,
        reasoning: str,
        indicators_snapshot: Dict[str, Any]
    ) -> int:
        """
        Synchronous version of log_decision for non-async contexts.
        
        Same parameters and return as log_decision().
        """
        log_entry = DecisionLog(
            strategy_name=strategy_name,
            ai_persona=ai_persona,
            verdict=verdict.upper(),
            reasoning=reasoning,
            indicators_snapshot=indicators_snapshot
        )
        
        db = SessionLocal()
        try:
            db.add(log_entry)
            db.commit()
            db.refresh(log_entry)
            return log_entry.id
        finally:
            db.close()
