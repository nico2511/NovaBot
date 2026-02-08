"""
Settings Router - Configuration Endpoints
Handles global settings, scanner settings, and strategy configuration
"""
from fastapi import APIRouter, Depends, HTTPException
from backend.api.dependencies import get_bot_context, get_bot_context_optional
from backend.models.api_models import GlobalSettingsModel, ScannerSettingsModel
from backend.services import storage
import logging

logger = logging.getLogger("SettingsRouter")

router = APIRouter(prefix="/api/settings", tags=["settings"])


@router.get("/global", response_model=GlobalSettingsModel)
def get_global_settings(bot=Depends(get_bot_context_optional)):
    """Get global bot settings"""
    try:
        # 1. Try Live Bot Context (for real-time values)
        if bot and hasattr(bot, 'global_settings') and bot.global_settings:
            # Flatten structure to match GlobalSettingsModel
            risk = bot.global_settings.get("risk_defaults", {})
            ops = bot.global_settings.get("operations", {})
            ai_config = bot.global_settings.get("ai_config", {})
            notifications = bot.global_settings.get("notifications", {})
            
            # Ensure notifications fallback to disk if empty (rare)
            if not notifications:
                 settings = storage.storage_service.load_settings()
                 notifications = settings.get("notifications", {})

            return {
                "max_positions": risk.get("max_positions", 1),
                "daily_stop_loss": risk.get("daily_stop_loss", 50.0),
                "trading_timeframe": ops.get("trading_timeframe", "15m"),
                "bot_persona": risk.get("bot_persona", "Conservative Scalper"),
                "risk_profile": risk.get("risk_profile", "Capital Preservation First"),
                "ai_thresholds": {
                    "high": ai_config.get("conf_threshold_high", 101),
                    "medium": ai_config.get("conf_threshold_medium", 55),
                    "low": ai_config.get("conf_threshold_low", 101)
                },
                "available_personas": risk.get("available_personas", ["Conservative Scalper", "Aggressive Day Trader", "Sniper"]),
                "available_risk_profiles": risk.get("available_risk_profiles", ["Capital Preservation First", "Balanced Growth", "High Volatility Hunter"]),
                "default_leverage": risk.get("default_leverage", 1),
                "default_margin_type": risk.get("default_margin_type", "ISOLATED"),
                "auto_start_trading": ops.get("auto_start_trading", False),
                "notifications": notifications
            }


        # 2. Read from storage (Source of Truth)
        settings = storage.storage_service.load_settings()
        
        # Build global_settings from user_settings structure
        risk_defaults = settings.get("risk_defaults", {})
        operations = settings.get("operations", {})
        ai_config = settings.get("ai_config", {})
        
        return {
            "max_positions": risk_defaults.get("max_positions", 1),
            "daily_stop_loss": risk_defaults.get("daily_stop_loss", 50.0),
            "trading_timeframe": operations.get("trading_timeframe", "15m"),
            "bot_persona": risk_defaults.get("bot_persona", "Conservative Scalper"),
            "risk_profile": risk_defaults.get("risk_profile", "Capital Preservation First"),
            "ai_thresholds": {
                "high": ai_config.get("conf_threshold_high", 101),
                "medium": ai_config.get("conf_threshold_medium", 55),
                "low": ai_config.get("conf_threshold_low", 101)
            },
            "available_personas": ["Conservative Scalper", "Aggressive Day Trader", "Sniper"],
            "available_risk_profiles": ["Capital Preservation First", "Balanced Growth", "High Volatility Hunter"],
            "default_leverage": risk_defaults.get("default_leverage", 1),
            "default_margin_type": risk_defaults.get("default_margin_type", "ISOLATED"),
            "auto_start_trading": operations.get("auto_start_trading", False),
            "notifications": settings.get("notifications", {})
        }
    except Exception as e:
        logger.error(f"Error loading global settings: {e}")
        # Default Fallback
        return {
            "max_positions": 1, 
            "daily_stop_loss": 50.0,
            "trading_timeframe": "15m",
            "bot_persona": "Conservative Scalper",
            "risk_profile": "Capital Preservation First",
            "ai_thresholds": {"high": 101, "medium": 55, "low": 101},
            "available_personas": ["Conservative Scalper", "Aggressive Day Trader", "Sniper"],
            "available_risk_profiles": ["Capital Preservation First", "Balanced Growth", "High Volatility Hunter"],
            "default_leverage": 1,
            "default_margin_type": "ISOLATED",
            "notifications": {}
        }


@router.post("/global")
def update_global_settings(settings: GlobalSettingsModel, bot=Depends(get_bot_context_optional)):
    """Update global bot settings"""
    try:
        # 1. Update user_settings.json (Source of Truth)
        full_settings = storage.storage_service.load_settings()
        new_flat = settings.model_dump()
        
        # operations
        if "operations" not in full_settings: full_settings["operations"] = {}
        full_settings["operations"]["trading_timeframe"] = new_flat.get("trading_timeframe", "15m")
        full_settings["operations"]["auto_start_trading"] = new_flat.get("auto_start_trading", False)
        
        # risk_defaults
        if "risk_defaults" not in full_settings: full_settings["risk_defaults"] = {}
        full_settings["risk_defaults"]["max_positions"] = new_flat.get("max_positions", 1)
        full_settings["risk_defaults"]["daily_stop_loss"] = new_flat.get("daily_stop_loss", 50.0)
        full_settings["risk_defaults"]["bot_persona"] = new_flat.get("bot_persona", "Conservative Scalper")
        full_settings["risk_defaults"]["risk_profile"] = new_flat.get("risk_profile", "Capital Preservation First")
        full_settings["risk_defaults"]["default_leverage"] = new_flat.get("default_leverage", 1)
        full_settings["risk_defaults"]["default_margin_type"] = new_flat.get("default_margin_type", "ISOLATED")

        # ai_config
        if "ai_config" not in full_settings: full_settings["ai_config"] = {}
        thresholds = new_flat.get("ai_thresholds", {})
        full_settings["ai_config"]["conf_threshold_high"] = thresholds.get("high", 101)
        full_settings["ai_config"]["conf_threshold_medium"] = thresholds.get("medium", 55)
        full_settings["ai_config"]["conf_threshold_low"] = thresholds.get("low", 101)

        # notifications
        full_settings["notifications"] = new_flat.get("notifications", {})

        storage.storage_service.save_settings(full_settings)
        
        # 2. Update Runtime State (if bot connected)
        if bot:
            # Assign the NESTED structure (not the flat model dump)
            bot.global_settings = full_settings
            
            bot.add_log(f"⚙️ Global Settings Updated: Persona={settings.bot_persona}, Risk={settings.risk_profile}")

            # 3. Trigger Leverage Re-sync in Bot Loop
            bot._leverage_synced = False
            bot.add_log(f"⚙️ Global Settings Updated: Persona={settings.bot_persona}, Risk={settings.risk_profile}")
            bot.add_log("🔄 Settings Sync: Triggering leverage re-sync...")

            # Save State
            try:
                from app.core.state_manager import StateManager
                StateManager.save_state(bot)
            except Exception as e:
                logger.warning(f"Failed to save state: {e}")
        else:
            logger.info("ℹ️ Bot offline - Settings saved to disk only")

        return {"status": "success", "message": "Settings updated", "settings": new_flat}
        
    except Exception as e:
        logger.error(f"Error updating global settings: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to update settings: {str(e)}")


@router.get("/scanner", response_model=ScannerSettingsModel)
def get_scanner_settings(bot=Depends(get_bot_context_optional)):
    """Get scanner settings"""
    try:
        # 1. Try Live Bot Context
        if bot and hasattr(bot, 'scanner_settings') and bot.scanner_settings:
            return bot.scanner_settings
            
        # 2. Read from storage
        settings = storage.storage_service.load_settings()
        if "scanner" in settings:
            return settings["scanner"]
            
        # 3. Default Fallback
        return {
            "enabled": False,
            "interval": 15,
            "min_score": 50,
            "auto_switch": False,
            "gamification_enabled": True,
            "max_funding_long": 0.001,
            "min_funding_short": -0.001,
            "funding_filter_enabled": True
        }
    except Exception as e:
        logger.error(f"Error loading scanner settings: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to load scanner settings: {str(e)}")


@router.post("/scanner")
def update_scanner_settings(settings: ScannerSettingsModel, bot=Depends(get_bot_context_optional)):
    """Update scanner settings"""
    try:
        new_settings = settings.model_dump()
        
        # 1. Update user_settings.json
        full_settings = storage.storage_service.load_settings()
        full_settings["scanner"] = new_settings
        storage.storage_service.save_settings(full_settings)
        
        # 2. Update Runtime State (if bot connected)
        if bot:
            bot.scanner_settings = new_settings
            bot.add_log(f"🕵️ Scanner Settings Updated: Min Score={settings.min_score}")
            
            # Save State
            try:
                from app.core.state_manager import StateManager
                StateManager.save_state(bot)
            except Exception as e:
                logger.warning(f"Failed to save state: {e}")
        else:
             logger.info("ℹ️ Bot offline - Scanner settings saved to disk only")
            
        return {"status": "success", "message": "Scanner settings updated", "settings": new_settings}
        
    except Exception as e:
        logger.error(f"Error updating scanner settings: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to update scanner settings: {str(e)}")


# ==========================================
# LEGACY ADAPTER (Frontend Compatibility)
# ==========================================

@router.get("/all")
def get_all_settings(bot=Depends(get_bot_context_optional)):
    """Get ALL settings aggregated (Monolithic view)"""
    try:
        # Load sub-components
        glob_sets = get_global_settings(bot)
        scan_sets = get_scanner_settings(bot)
        
        # Merge into flattened structure expected by frontend v3
        return {
            "notifications": glob_sets.get("notifications", {
                "discord_webhook_alerts": "",
                "discord_webhook_logs": ""
            }),
            "operations": {
                "trading_timeframe": glob_sets.get("trading_timeframe"),
                "auto_start_trading": glob_sets.get("auto_start_trading", False),
                "log_level": "INFO"
            },
            "risk_defaults": {
                "max_positions": glob_sets.get("max_positions"),
                "daily_stop_loss": glob_sets.get("daily_stop_loss"),
                "bot_persona": glob_sets.get("bot_persona"),
                "risk_profile": glob_sets.get("risk_profile"),
                "default_leverage": glob_sets.get("default_leverage"),
                "default_margin_type": glob_sets.get("default_margin_type")
            },
            "ai_config": {
                "model_name": "deepseek/deepseek-v3.2",
                "call_cooldown": 2,
                "conf_threshold_high": glob_sets.get("ai_thresholds", {}).get("high"),
                "conf_threshold_medium": glob_sets.get("ai_thresholds", {}).get("medium"),
                "conf_threshold_low": glob_sets.get("ai_thresholds", {}).get("low")
            },
            "scanner": scan_sets
        }
    except Exception as e:
        logger.error(f"Error aggregating settings: {e}")
        return {}

from pydantic import BaseModel

class UpdateSettingsRequest(BaseModel):
    section: str
    data: dict

@router.post("/update")
def update_legacy_settings(
    payload: UpdateSettingsRequest, 
    bot=Depends(get_bot_context_optional)
):
    """Update settings via legacy Adapter (Section Router)"""
    try:
        section = payload.section
        data = payload.data
        
        logger.info(f"📝 Legacy Update: Section={section}")
        
        if section == "scanner":
            # Map dict to model
            model = ScannerSettingsModel(**data)
            return update_scanner_settings(model, bot)
            
        elif section in ["risk_defaults", "operations", "ai_config", "notifications"]:
            # These map to GlobalSettings
            # We need to fetch current global, patch it, and save
            current = get_global_settings(bot)
            
            # Patching logic
            if section == "risk_defaults":
                current["max_positions"] = data.get("max_positions", current.get("max_positions", 1))
                current["daily_stop_loss"] = data.get("daily_stop_loss", current.get("daily_stop_loss", 50.0))
                current["bot_persona"] = data.get("bot_persona", current.get("bot_persona", "Conservative Scalper"))
                current["risk_profile"] = data.get("risk_profile", current.get("risk_profile", "Capital Preservation First"))
                current["default_leverage"] = data.get("default_leverage", current.get("default_leverage", 1))
                current["default_margin_type"] = data.get("default_margin_type", current.get("default_margin_type", "ISOLATED"))
                
            elif section == "operations":
                current["trading_timeframe"] = data.get("trading_timeframe", current.get("trading_timeframe", "15m"))
                current["auto_start_trading"] = data.get("auto_start_trading", current.get("auto_start_trading", False))
            
            elif section == "ai_config":
                 # Patch thresholds
                 thresholds = current.get("ai_thresholds", {})
                 thresholds["high"] = data.get("conf_threshold_high", thresholds.get("high", 101))
                 thresholds["medium"] = data.get("conf_threshold_medium", thresholds.get("medium", 55))
                 thresholds["low"] = data.get("conf_threshold_low", thresholds.get("low", 101))
                 current["ai_thresholds"] = thresholds
                 
            elif section == "notifications":
                # Patch notifications
                current["notifications"] = data

            # Save
            try:
                # Ensure all required fields exist with defaults if missing
                if "auto_start_trading" not in current: current["auto_start_trading"] = False
                if "notifications" not in current: current["notifications"] = {}
                
                # Critical Fix: Ensure ai_thresholds exists
                if "ai_thresholds" not in current:
                    current["ai_thresholds"] = {
                        "high": 101, "medium": 55, "low": 101
                    }
                
                # Clean up legacy keys that might confuse Pydantic
                keys_to_remove = [k for k in current.keys() if k not in GlobalSettingsModel.model_fields]
                for k in keys_to_remove:
                    del current[k]
                
                model = GlobalSettingsModel(**current)
                return update_global_settings(model, bot)
            except Exception as validation_error:
                logger.error(f"Validation Error creating GlobalSettingsModel: {validation_error}")
                # Log the actual data causing the issue for debugging
                logger.error(f"Current data payload: {current}")
                raise HTTPException(status_code=422, detail=f"Validation Error: {str(validation_error)}")
            
        else:
             return {"status": "ignored", "message": f"Section {section} not editable via API"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Legacy update failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
