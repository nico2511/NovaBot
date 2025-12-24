import os
from dotenv import load_dotenv
from dataclasses import dataclass

load_dotenv()

@dataclass
class Config:
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY")
    HL_PRIVATE_KEY: str = os.getenv("HL_PRIVATE_KEY")
    HL_ACCOUNT_ADDRESS: str = os.getenv("HL_ACCOUNT_ADDRESS")
    DISCORD_WEBHOOK_ALERTS: str = os.getenv("DISCORD_WEBHOOK_URL_ALERTS")
    DISCORD_WEBHOOK_LOGS: str = os.getenv("DISCORD_WEBHOOK_URL_LOGS")
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")

    # Risk Defaults
    DEFAULT_MAX_POSITIONS: int = 1
    DEFAULT_DAILY_STOP_LOSS: float = 50.0  # USDC
    DEFAULT_LEVERAGE: int = 1

config = Config()
