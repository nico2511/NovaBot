from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional

class Settings(BaseSettings):
    PROJECT_NAME: str = "NovaBot"
    VERSION: str = "2.0.0"
    API_V1_STR: str = "/api/v1"

    # Database
    DATABASE_URL: str = "sqlite:///./novabot.db"

    # Hyperliquid
    HL_PRIVATE_KEY: Optional[str] = None
    HL_ACCOUNT_ADDRESS: Optional[str] = None
    HYPERLIQUID_API_URL: str = "https://api.hyperliquid.xyz"

    # AI Providers
    GEMINI_API_KEY: Optional[str] = None
    OPENROUTER_API_KEY: Optional[str] = None
    AI_MODEL_NAME: str = "meta-llama/llama-3.1-8b-instruct"
    AI_PROVIDER: str = "openrouter"

    # Logging / Notifications
    DISCORD_WEBHOOK_URL_ALERTS: Optional[str] = None
    DISCORD_WEBHOOK_URL_LOGS: Optional[str] = None
    LOG_LEVEL: str = "INFO"

    # Trading Defaults
    TRADING_TIMEFRAME: str = "15m"
    BOT_PERSONA: str = "Conservative Scalper"
    RISK_PROFILE: str = "Capital Preservation First"
    API_KEY: str = "dev_secret_change_in_production"

    model_config = SettingsConfigDict(env_file=".env", env_ignore_empty=True, extra="ignore")

settings = Settings()
