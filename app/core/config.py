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

config = Config()
