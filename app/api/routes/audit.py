from fastapi import APIRouter, Query
from pydantic import BaseModel
from typing import Dict, Any, List
from app.services.audit_service import AuditService
from app.core.database import SessionLocal
from app.services.models import DecisionLog

router = APIRouter(prefix="/audit", tags=["audit"])

class LogDecisionRequest(BaseModel):
    strategy_name: str
    ai_persona: str
    verdict: str
    reasoning: str
    indicators_snapshot: Dict[str, Any]

class LogDecisionResponse(BaseModel):
    log_id: int
    message: str

class DecisionLogResponse(BaseModel):
    id: int
    timestamp: str
    strategy_name: str
    ai_persona: str
    verdict: str
    reasoning: str
    indicators_snapshot: Dict[str, Any]

@router.post("/log-decision", response_model=LogDecisionResponse)
def log_decision(request: LogDecisionRequest):
    """
    Log an AI trading decision with indicator snapshot.
    
    Example:
        POST /api/v1/audit/log-decision
        {
            "strategy_name": "TestStrategy",
            "ai_persona": "Conservative Trader",
            "verdict": "BUY",
            "reasoning": "Strong bullish signal",
            "indicators_snapshot": {"rsi": 65, "price": 50000}
        }
    """
    log_id = AuditService.log_decision_sync(
        strategy_name=request.strategy_name,
        ai_persona=request.ai_persona,
        verdict=request.verdict,
        reasoning=request.reasoning,
        indicators_snapshot=request.indicators_snapshot
    )
    
    return LogDecisionResponse(
        log_id=log_id,
        message="Decision logged successfully"
    )

@router.get("/decisions", response_model=List[DecisionLogResponse])
def get_decisions(limit: int = Query(default=10, le=100)):
    """
    Retrieve recent decision logs.
    
    Example:
        GET /api/v1/audit/decisions?limit=5
    """
    db = SessionLocal()
    try:
        decisions = db.query(DecisionLog).order_by(
            DecisionLog.timestamp.desc()
        ).limit(limit).all()
        
        return [
            DecisionLogResponse(
                id=d.id,
                timestamp=d.timestamp.isoformat(),
                strategy_name=d.strategy_name,
                ai_persona=d.ai_persona,
                verdict=d.verdict,
                reasoning=d.reasoning,
                indicators_snapshot=d.indicators_snapshot
            )
            for d in decisions
        ]
    finally:
        db.close()
