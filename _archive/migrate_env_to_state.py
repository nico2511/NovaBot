"""
Migration Script: .env → bot_state.json
Extracts non-secret settings from .env and updates bot_state.json
"""
import os
import json
from pathlib import Path
from dotenv import load_dotenv

# Load current .env
load_dotenv()

# Define migration mapping
MIGRATION_MAP = {
    "notifications": {
        "discord_webhook_alerts": os.getenv("DISCORD_WEBHOOK_URL_ALERTS", ""),
        "discord_webhook_logs": os.getenv("DISCORD_WEBHOOK_URL_LOGS", "")
    },
    "operations": {
        "log_level": os.getenv("LOG_LEVEL", "INFO"),
        "auto_start_trading": os.getenv("AUTO_START_TRADING", "false").lower() == "true",
        "trading_timeframe": os.getenv("TRADING_TIMEFRAME", "15m")
    },
    "risk_defaults": {
        "max_positions": int(os.getenv("DEFAULT_MAX_POSITIONS", "1")),
        "daily_stop_loss": float(os.getenv("DEFAULT_DAILY_STOP_LOSS", "50.0")),
        "bot_persona": os.getenv("BOT_PERSONA", "Conservative Scalper"),
        "risk_profile": os.getenv("RISK_PROFILE", "Capital Preservation First")
    },
    "ai_config": {
        "model_name": os.getenv("AI_MODEL_NAME", "deepseek/deepseek-v3.2"),
        "provider": os.getenv("AI_PROVIDER", "openrouter"),
        "call_cooldown": int(os.getenv("AI_CALL_COOLDOWN", "2")),
        "conf_threshold_high": int(os.getenv("AI_CONF_THRESHOLD_HIGH", "101")),
        "conf_threshold_medium": int(os.getenv("AI_CONF_THRESHOLD_MEDIUM", "55")),
        "conf_threshold_low": int(os.getenv("AI_CONF_THRESHOLD_LOW", "101"))
    }
}

def migrate():
    state_file = Path("data/bot_state.json")
    
    # Load existing state or create new
    if state_file.exists():
        with open(state_file, 'r') as f:
            state = json.load(f)
        print("✅ Loaded existing bot_state.json")
    else:
        state = {}
        print("📝 Creating new bot_state.json")
    
    # Merge migration data
    for section, values in MIGRATION_MAP.items():
        if section not in state:
            state[section] = {}
        state[section].update(values)
        print(f"✅ Migrated section: {section}")
    
    # Save updated state
    state_file.parent.mkdir(exist_ok=True)
    with open(state_file, 'w') as f:
        json.dump(state, f, indent=2)
    
    print(f"\n🎉 Migration complete! Updated: {state_file}")
    print("\n📋 Summary:")
    for section in MIGRATION_MAP.keys():
        print(f"  - {section}: {len(state[section])} settings")
    
    return state

if __name__ == "__main__":
    print("🔄 Starting .env → bot_state.json migration...\n")
    migrate()
