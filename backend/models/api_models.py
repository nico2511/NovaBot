"""
Pydantic Models for NovaBot FastAPI Backend
All request and response models for API endpoints
"""
from typing import Optional, Dict, Any, List, Union
from pydantic import BaseModel


class BotStatus(BaseModel):
    """Response model for /api/status endpoint"""
    is_running: bool
    trading_enabled: bool
    active_symbol: str
    active_trade: Optional[Dict[str, Any]]
    daily_pnl: float = 0.0
    active_positions: int = 0
    last_updated: Optional[str] = None
    logs: List[Union[str, Dict[str, Any]]] = []
    
    # Health Metrics
    margin_usage: float = 0.0
    win_rate: float = 0.0
    max_drawdown: float = 0.0
    
    # Market Analysis
    market_analysis: Optional[Dict[str, Any]] = None
    
    # Positions
    open_positions: List[Dict[str, Any]] = []


class GlobalSettingsModel(BaseModel):
    """Model for global bot settings"""
    max_positions: int
    daily_stop_loss: float
    trading_timeframe: str
    bot_persona: str
    risk_profile: str
    ai_thresholds: Dict[str, int]
    available_personas: Optional[List[str]] = None
    available_risk_profiles: Optional[List[str]] = None
    default_leverage: int = 1
    default_margin_type: str = "ISOLATED"
    auto_start_trading: bool = False
    notifications: Dict[str, str] = {}


class ScannerSettingsModel(BaseModel):
    """Model for scanner configuration settings"""
    enabled: bool
    interval: int
    min_score: int
    auto_switch: bool
    gamification_enabled: bool
    max_funding_long: float = 0.001
    min_funding_short: float = -0.001
    funding_filter_enabled: bool = True


class StrategySelectModel(BaseModel):
    """Request model for strategy selection"""
    strategy_id: str


class SwitchSymbolRequest(BaseModel):
    """Request model for switching trading symbol"""
    symbol: str


class ManualTradeRequest(BaseModel):
    """Request model for manual trade execution"""
    symbol: str
    side: str  # "long" or "short"
    size: float
    leverage: Optional[int] = None
