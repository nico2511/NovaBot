import os
from dotenv import load_dotenv
from dataclasses import dataclass

load_dotenv()

@dataclass
class Config:
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY")
    OPENROUTER_API_KEY: str = os.getenv("OPENROUTER_API_KEY")
    AI_MODEL_NAME: str = os.getenv("AI_MODEL_NAME", "meta-llama/llama-3.1-8b-instruct")
    AI_PROVIDER: str = os.getenv("AI_PROVIDER", "openrouter") # Force openrouter default
    # Hyperliquid
    HL_PRIVATE_KEY: str = os.getenv("HL_PRIVATE_KEY")
    HL_ACCOUNT_ADDRESS: str = os.getenv("HL_ACCOUNT_ADDRESS")
    HYPERLIQUID_API_URL: str = os.getenv("HYPERLIQUID_API_URL", "https://api.hyperliquid.xyz")
    
    DISCORD_WEBHOOK_ALERTS: str = os.getenv("DISCORD_WEBHOOK_URL_ALERTS")
    DISCORD_WEBHOOK_LOGS: str = os.getenv("DISCORD_WEBHOOK_URL_LOGS")
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")

    # Risk Defaults
    DEFAULT_MAX_POSITIONS: int = 1
    DEFAULT_DAILY_STOP_LOSS: float = 50.0  # USDC
    DEFAULT_LEVERAGE: int = 1
    
    # Operations
    AUTO_START_TRADING: bool = os.getenv("AUTO_START_TRADING", "false").lower() == "true"
    
    # ==============================================================================
    # 🧠 AI MODULAR CONFIGURATION (Added via Prompt)
    # ==============================================================================
    
    # Timeframe principal pour l'analyse de structure (Défaut: 15m)
    TRADING_TIMEFRAME: str = os.getenv("TRADING_TIMEFRAME", "15m")
    
    # Personnalité du Bot (Défaut: Conservative Scalper)
    # Voir TRADING_PROFILES.md pour les options
    BOT_PERSONA: str = os.getenv("BOT_PERSONA", "Conservative Scalper")
    
    # Profil de Risque (Défaut: Capital Preservation)
    # Voir TRADING_PROFILES.md pour les options
    RISK_PROFILE: str = os.getenv("RISK_PROFILE", "Capital Preservation First")
    
    # AI Call Cooldown (seconds) - Prevents excessive API calls
    AI_CALL_COOLDOWN: int = int(os.getenv("AI_CALL_COOLDOWN", "300"))  # 5 minutes default
    
    # ==============================================================================
    # 🎯 AI CONFIDENCE THRESHOLDS (Hybrid Approach)
    # ==============================================================================
    # Minimum confidence % required for AI to approve a trade, per risk level.
    # Set to 0 to disable confidence filtering (only use approved=true/false)
    AI_CONF_THRESHOLD_HIGH: int = int(os.getenv("AI_CONF_THRESHOLD_HIGH", "70"))
    AI_CONF_THRESHOLD_MEDIUM: int = int(os.getenv("AI_CONF_THRESHOLD_MEDIUM", "55"))
    AI_CONF_THRESHOLD_LOW: int = int(os.getenv("AI_CONF_THRESHOLD_LOW", "40"))
    
    # API Security
    API_KEY: str = os.getenv("API_KEY", "dev_secret_change_in_production")

config = Config()
