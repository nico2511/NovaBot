import os
from dotenv import load_dotenv
from dataclasses import dataclass
import json
from pathlib import Path

load_dotenv()

def _load_bot_state_settings():
    """Load settings from user_settings.json if available, otherwise use .env defaults"""
    try:
        # Priority: data/config/user_settings.json (Dedicated config)
        config_file = Path("data/config/user_settings.json")
        if config_file.exists():
             with open(config_file, 'r') as f:
                return json.load(f)
        
        # Fallback: bot_state.json (Legacy/Migration)
        state_file = Path("bot_state.json")
        if state_file.exists():
            with open(state_file, 'r') as f:
                state = json.load(f)
                return {
                    'notifications': state.get('notifications', {}),
                    'operations': state.get('operations', {}),
                    'risk_defaults': state.get('risk_defaults', {}),
                    'ai_config': state.get('ai_config', {})
                }
    except Exception as e:
        print(f"⚠️ Could not load settings: {e}")
    return {}

_state_settings = _load_bot_state_settings()

@dataclass
class Config:
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY")
    OPENROUTER_API_KEY: str = os.getenv("OPENROUTER_API_KEY")
    AI_MODEL_NAME: str = _state_settings.get('ai_config', {}).get('model_name') or os.getenv("AI_MODEL_NAME", "deepseek/deepseek-v3.2")
    AI_PROVIDER: str = "openrouter"  # Always openrouter
    
    # Hyperliquid
    HL_PRIVATE_KEY: str = os.getenv("HL_PRIVATE_KEY")
    HL_ACCOUNT_ADDRESS: str = os.getenv("HL_ACCOUNT_ADDRESS")
    HYPERLIQUID_API_URL: str = os.getenv("HYPERLIQUID_API_URL", "https://api.hyperliquid.xyz")
    
    # Notifications (from bot_state.json or .env fallback)
    DISCORD_WEBHOOK_ALERTS: str = _state_settings.get('notifications', {}).get('discord_webhook_alerts') or os.getenv("DISCORD_WEBHOOK_URL_ALERTS", "")
    DISCORD_WEBHOOK_LOGS: str = _state_settings.get('notifications', {}).get('discord_webhook_logs') or os.getenv("DISCORD_WEBHOOK_URL_LOGS", "")
    LOG_LEVEL: str = _state_settings.get('operations', {}).get('log_level') or os.getenv("LOG_LEVEL", "INFO")

    # Risk Defaults (from bot_state.json or .env fallback)
    DEFAULT_MAX_POSITIONS: int = _state_settings.get('risk_defaults', {}).get('max_positions') or int(os.getenv("DEFAULT_MAX_POSITIONS", "1"))
    DEFAULT_DAILY_STOP_LOSS: float = _state_settings.get('risk_defaults', {}).get('daily_stop_loss') or float(os.getenv("DEFAULT_DAILY_STOP_LOSS", "50.0"))
    DEFAULT_LEVERAGE: int = 1
    
    # Operations (from bot_state.json or .env fallback)
    AUTO_START_TRADING: bool = _state_settings.get('operations', {}).get('auto_start_trading') if _state_settings.get('operations', {}).get('auto_start_trading') is not None else (os.getenv("AUTO_START_TRADING", "false").lower() == "true")
    
    # Scanner Settings (New in v2 - from user_settings.json)
    SCANNER_ENABLED: bool = _state_settings.get('scanner', {}).get('enabled', True)
    SCANNER_INTERVAL: int = _state_settings.get('scanner', {}).get('interval', 5)
    SCANNER_MIN_SCORE: int = _state_settings.get('scanner', {}).get('min_score', 60)
    SCANNER_AUTO_SWITCH: bool = _state_settings.get('scanner', {}).get('auto_switch', True)
    SCANNER_GAMIFICATION: bool = _state_settings.get('scanner', {}).get('gamification_enabled', False)

    # ==============================================================================
    # 🧠 AI MODULAR CONFIGURATION
    # ==============================================================================
    
    # Timeframe principal (from bot_state.json or .env fallback)
    TRADING_TIMEFRAME: str = _state_settings.get('operations', {}).get('trading_timeframe') or os.getenv("TRADING_TIMEFRAME", "15m")
    
    # Bot Persona (from bot_state.json or .env fallback)
    BOT_PERSONA: str = _state_settings.get('risk_defaults', {}).get('bot_persona') or os.getenv("BOT_PERSONA", "Conservative Scalper")
    
    # Risk Profile (from bot_state.json or .env fallback)
    RISK_PROFILE: str = _state_settings.get('risk_defaults', {}).get('risk_profile') or os.getenv("RISK_PROFILE", "Capital Preservation First")
    
    # AI Call Cooldown (from bot_state.json or .env fallback)
    AI_CALL_COOLDOWN: int = _state_settings.get('ai_config', {}).get('call_cooldown') or int(os.getenv("AI_CALL_COOLDOWN", "2"))
    
    # ==============================================================================
    # 🎯 AI CONFIDENCE THRESHOLDS
    # ==============================================================================
    AI_CONF_THRESHOLD_HIGH: int = _state_settings.get('ai_config', {}).get('conf_threshold_high') or int(os.getenv("AI_CONF_THRESHOLD_HIGH", "75"))
    AI_CONF_THRESHOLD_MEDIUM: int = _state_settings.get('ai_config', {}).get('conf_threshold_medium') or int(os.getenv("AI_CONF_THRESHOLD_MEDIUM", "55"))
    AI_CONF_THRESHOLD_LOW: int = _state_settings.get('ai_config', {}).get('conf_threshold_low') or int(os.getenv("AI_CONF_THRESHOLD_LOW", "40"))
    
    # API Security
    API_KEY: str = os.getenv("API_KEY", "dev_secret_change_in_production")

config = Config()
