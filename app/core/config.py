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
        
        # Fallback: data/bot_state.json (Operational State fallback)
        state_file = Path("data/bot_state.json")
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

def _normalize_symbol(raw: str) -> str:
    return str(raw or "").upper().replace("-USD", "").replace("-USDC", "").strip()


def bootstrap_active_symbol(settings: dict | None = None) -> str:
    """Cold-start focus symbol before the scanner runs. Not a trading constraint."""
    settings = settings or _state_settings
    for raw in (settings.get("scanner") or {}).get("whitelist") or []:
        sym = _normalize_symbol(raw)
        if sym:
            return sym
    legacy = _normalize_symbol(os.getenv("TRADING_SYMBOL", ""))
    return legacy or "BTC"


def _parse_csv_env(name: str, default: str) -> list:
    """Parse a comma-separated env var into a list of stripped non-empty values."""
    raw = os.getenv(name, default) or ""
    return [item.strip() for item in raw.split(",") if item.strip()]


@dataclass
class Config:
    OPENROUTER_API_KEY: str = os.getenv("OPENROUTER_API_KEY")
    # Optional management/provisioning key for GET /api/v1/credits (account balance).
    # Chat calls keep using OPENROUTER_API_KEY; leave empty to try the chat key first.
    OPENROUTER_MANAGEMENT_API_KEY: str = os.getenv("OPENROUTER_MANAGEMENT_API_KEY", "") or ""
    AI_MODEL_NAME: str = _state_settings.get('ai_config', {}).get('model_name') or os.getenv("AI_MODEL_NAME", "deepseek/deepseek-v3.2")
    AI_PROVIDER: str = "openrouter"  # Always openrouter
    # Credit probe: startup + this interval (0 = startup only). Default hourly.
    OPENROUTER_CREDIT_CHECK_INTERVAL_SEC: int = int(os.getenv("OPENROUTER_CREDIT_CHECK_INTERVAL_SEC", "3600"))
    OPENROUTER_CREDIT_WARN_USD: float = float(os.getenv("OPENROUTER_CREDIT_WARN_USD", "1.0"))
    OPENROUTER_CREDIT_MIN_USD: float = float(os.getenv("OPENROUTER_CREDIT_MIN_USD", "0.10"))
    
    # Hyperliquid
    HL_PRIVATE_KEY: str = os.getenv("HL_PRIVATE_KEY")
    HL_ACCOUNT_ADDRESS: str = os.getenv("HL_ACCOUNT_ADDRESS")
    HYPERLIQUID_API_URL: str = os.getenv("HYPERLIQUID_API_URL", "https://api.hyperliquid.xyz")
    
    # Notifications (from bot_state.json or .env fallback)
    DISCORD_WEBHOOK_ALERTS: str = _state_settings.get('notifications', {}).get('discord_webhook_alerts') or os.getenv("DISCORD_WEBHOOK_URL_ALERTS", "")
    DISCORD_WEBHOOK_LOGS: str = _state_settings.get('notifications', {}).get('discord_webhook_logs') or os.getenv("DISCORD_WEBHOOK_URL_LOGS", "")
    LOG_LEVEL: str = _state_settings.get('operations', {}).get('log_level') or os.getenv("LOG_LEVEL", "INFO")
    
    # AI payload debug (logs what is sent/received from AI)
    AI_PAYLOAD_DEBUG: bool = (
        _state_settings.get('operations', {}).get('ai_payload_debug')
        if _state_settings.get('operations', {}).get('ai_payload_debug') is not None
        else (os.getenv("AI_PAYLOAD_DEBUG", "false").lower() == "true")
    )
    AI_PAYLOAD_DEBUG_DISCORD: bool = (
        _state_settings.get('operations', {}).get('ai_payload_debug_discord')
        if _state_settings.get('operations', {}).get('ai_payload_debug_discord') is not None
        else (os.getenv("AI_PAYLOAD_DEBUG_DISCORD", "false").lower() == "true")
    )
    AI_PAYLOAD_DEBUG_MAX_CHARS: int = int(os.getenv("AI_PAYLOAD_DEBUG_MAX_CHARS", "1800"))

    # Risk Defaults (from bot_state.json or .env fallback)
    DEFAULT_MAX_POSITIONS: int = _state_settings.get('risk_defaults', {}).get('max_positions') or int(os.getenv("DEFAULT_MAX_POSITIONS", "2"))
    DEFAULT_DAILY_STOP_LOSS: float = _state_settings.get('risk_defaults', {}).get('daily_stop_loss') or float(os.getenv("DEFAULT_DAILY_STOP_LOSS", "50.0"))
    # Account UI ceiling for live trade leverage (clamps strategy risk-profile max_leverage)
    DEFAULT_LEVERAGE: int = int(
        _state_settings.get("risk_defaults", {}).get("default_leverage")
        or os.getenv("DEFAULT_LEVERAGE", "10")
    )
    MAX_NOTIONAL_CAP_MULTIPLIER: float = float(
        _state_settings.get('risk_defaults', {}).get('max_notional_cap_multiplier')
        or os.getenv("MAX_NOTIONAL_CAP_MULTIPLIER", "1")
    )
    
    # Operations (from bot_state.json or .env fallback)
    AUTO_START_TRADING: bool = _state_settings.get('operations', {}).get('auto_start_trading') if _state_settings.get('operations', {}).get('auto_start_trading') is not None else (os.getenv("AUTO_START_TRADING", "false").lower() == "true")
    
    # Deprecated: use bootstrap_active_symbol() — scanner whitelist drives markets.
    TRADING_SYMBOL: str = bootstrap_active_symbol()
    
    # Scanner Settings (New in v2 - from user_settings.json)
    SCANNER_ENABLED: bool = _state_settings.get('scanner', {}).get('enabled', True)
    SCANNER_INTERVAL: int = _state_settings.get('scanner', {}).get('interval', 15)
    SCANNER_MIN_SCORE: int = _state_settings.get('scanner', {}).get('min_score', 55)
    SCANNER_AUTO_SWITCH: bool = _state_settings.get('scanner', {}).get('auto_switch', False)

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
    # API_KEY_REQUIRED: if "true", every protected endpoint must send the key in the
    # X-API-Key header. Defaults to "false" so local dev keeps working transparently.
    API_KEY: str = os.getenv("API_KEY", "")
    API_KEY_REQUIRED: bool = os.getenv("API_KEY_REQUIRED", "false").lower() == "true"

    # CORS: comma-separated origins. Use "*" only when explicitly set (dev only).
    CORS_ALLOWED_ORIGINS: list = None  # set in __post_init__


    def __post_init__(self):
        # Parsed at instance-level to keep dataclass defaults immutable/safe.
        self.CORS_ALLOWED_ORIGINS = _parse_csv_env(
            "CORS_ALLOWED_ORIGINS",
            "http://localhost:3000,http://localhost:5173"
        )

config = Config()
