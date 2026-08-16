"""
Atomic Storage Service for NovaBot
Provides atomic file writes for JSON data to prevent corruption
All data files are organized in the data/ directory
"""
import os
import json
import tempfile
import shutil
from typing import Dict, Any, Optional, List
from pathlib import Path
import logging

logger = logging.getLogger("StorageService")


class StorageService:
    """Service for atomic file operations with organized data structure"""
    
    def __init__(self, base_dir: str):
        """
        Initialize storage service with organized data structure
        
        Directory structure:
        - data/config/     - Configuration files (user_settings.json, strategies.json)
        - data/cache/      - Cache files (token_meta_cache.json)
        - data/state/      - State files (daily_pnl_snapshot.json)
        Args:
            base_dir: Base directory for all storage operations
        """
        # Robust pathing: Ensure we are at the project root
        self.base_dir = Path(base_dir).absolute()
        self.data_dir = self.base_dir / "data"
        self.defaults_dir = self.base_dir / "app" / "core" / "defaults"
        self.default_strategies_path = self.defaults_dir / "strategies.default.json"
        
        # Initialize directories
        self._ensure_dirs()
    
    def _ensure_dirs(self):
        """Ensure all necessary data subdirectories exist."""
        self.config_dir = self.data_dir / "config"
        self.cache_dir = self.data_dir / "cache"
        self.state_dir = self.data_dir / "state"
        
        for directory in [self.config_dir, self.cache_dir, self.state_dir]:
            directory.mkdir(parents=True, exist_ok=True)
    
    def atomic_write_json(self, filepath: Path, data: Dict[str, Any], indent: int = 2) -> bool:
        """
        Atomically write JSON data to a file.
        
        Uses a temporary file + rename strategy to ensure atomicity.
        If the write fails, the original file remains unchanged.
        
        Args:
            filepath: Full path to the file (Path object)
            data: Dictionary to write as JSON
            indent: JSON indentation level
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # Ensure parent directory exists
            filepath.parent.mkdir(parents=True, exist_ok=True)
            
            # Create temp file in the same directory for atomic rename
            temp_fd, temp_path = tempfile.mkstemp(
                dir=filepath.parent,
                prefix=f".{filepath.name}.",
                suffix=".tmp"
            )
            
            try:
                # Write to temp file
                with os.fdopen(temp_fd, 'w') as f:
                    json.dump(data, f, indent=indent)
                    f.flush()
                    os.fsync(f.fileno())  # Force write to disk
                
                # Atomic rename
                shutil.move(temp_path, filepath)
                logger.debug(f"✅ Atomically wrote {filepath.name}")
                return True
                
            except Exception as e:
                # Clean up temp file on error
                try:
                    os.unlink(temp_path)
                except:
                    pass
                raise e
                
        except Exception as e:
            logger.error(f"❌ Failed to write {filepath.name}: {e}")
            return False
    
    def read_json(self, filepath: Path, default: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Read JSON data from a file.
        
        Args:
            filepath: Full path to the file (Path object)
            default: Default value if file doesn't exist or is invalid
            
        Returns:
            Dict containing the JSON data, or default if error
        """
        if not filepath.exists():
            logger.info(f"ℹ️ File not found: {filepath.name}, using default")
            return default if default is not None else {}
        
        try:
            with open(filepath, 'r') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"❌ Failed to read {filepath.name}: {e}")
            return default if default is not None else {}
    
    # Configuration files (data/config/)
    
    def save_settings(self, settings: Dict[str, Any]) -> bool:
        """Save user settings atomically to data/config/user_settings.json"""
        return self.atomic_write_json(self.config_dir / "user_settings.json", settings, indent=4)
    
    def load_settings(self) -> Dict[str, Any]:
        """Load user settings from data/config/user_settings.json"""
        return self.read_json(self.config_dir / "user_settings.json", default={
            "operations": {
                "trading_timeframe": "15m",
                "auto_start_trading": False
            },
            "risk_defaults": {
                "max_positions": 1,
                "allow_same_symbol_concurrent": False,
                "daily_stop_loss": 50.0,
                "bot_persona": "Conservative Scalper",
                "risk_profile": "Capital Preservation First"
            },
            "ai_config": {
                "conf_threshold_high": 75,
                "conf_threshold_medium": 55,
                "conf_threshold_low": 35
            },
            "scanner": {
                "enabled": False,
                "interval": 15,
                "min_score": 60,
                "auto_switch": False,
                "min_volume_24h": 2000000,
                "min_open_interest": 1000000,
                "max_tokens": 40,
                "funding_filter_enabled": False,
                "scan_while_in_trade": False,
                "analyze_top_k": 3,
                "whitelist": [
                    "BTC", "ETH", "SOL", "ARB", "OP", "SUI", "APT", "AVAX",
                    "LINK", "UNI", "AAVE", "ADA", "NEAR", "INJ", "TIA",
                    "DOT", "ATOM", "LTC", "BCH", "XRP"
                ]
            },
            "notifications": {}
        })
    
    def save_strategies(self, strategies: Dict[str, Any]) -> bool:
        """Save strategies configuration atomically to data/config/strategies.json"""
        return self.atomic_write_json(self.config_dir / "strategies.json", strategies, indent=2)
    
    def load_strategies(self) -> Dict[str, Any]:
        """Load strategies configuration from data/config/strategies.json"""
        return self.read_json(self.config_dir / "strategies.json", default={})

    def _merge_missing(self, target: Any, source: Any) -> Any:
        """
        Merge source into target without overwriting existing user/runtime values.
        - Dict: recursively add missing keys
        - List/scalars: keep target as-is if present, else take source
        """
        if isinstance(target, dict) and isinstance(source, dict):
            merged = dict(target)
            for k, v in source.items():
                if k in merged:
                    merged[k] = self._merge_missing(merged[k], v)
                else:
                    merged[k] = v
            return merged
        return target if target is not None else source

    def sync_strategies_from_defaults(self) -> Dict[str, Any]:
        """
        Ensure runtime data/config/strategies.json contains all new default strategies/keys.
        Preserves user-modified existing values.
        """
        result = {"status": "noop", "added_top_level": [], "added_keys_count": 0}
        try:
            if not self.default_strategies_path.exists():
                logger.warning(f"⚠️ Default strategies file not found: {self.default_strategies_path}")
                result["status"] = "missing_default"
                return result

            default_cfg = self.read_json(self.default_strategies_path, default={})
            runtime_path = self.config_dir / "strategies.json"
            runtime_cfg = self.read_json(runtime_path, default={})

            if not isinstance(default_cfg, dict):
                logger.error("❌ Invalid default strategies format (not a dict)")
                result["status"] = "invalid_default"
                return result
            if not isinstance(runtime_cfg, dict):
                runtime_cfg = {}

            old_top = set(runtime_cfg.keys())
            merged_cfg = self._merge_missing(runtime_cfg, default_cfg)

            # Drop obsolete strategy blocks no longer present in defaults
            # (keeps market_regime + currently shipped strategies only).
            allowed_top = set(default_cfg.keys())
            pruned_keys = sorted(k for k in list(merged_cfg.keys()) if k not in allowed_top)
            for k in pruned_keys:
                merged_cfg.pop(k, None)

            new_top = set(merged_cfg.keys())
            added_top_level = sorted(list(new_top - old_top))

            # Count added nested keys roughly by serializing path walk
            def count_missing_added(a, b):
                # a = original runtime, b = merged
                if isinstance(a, dict) and isinstance(b, dict):
                    total = 0
                    for k, bv in b.items():
                        if k not in a:
                            total += 1
                        else:
                            total += count_missing_added(a[k], bv)
                    return total
                return 0

            added_keys_count = count_missing_added(runtime_cfg, merged_cfg)

            changed = (merged_cfg != runtime_cfg)
            if changed:
                ok = self.save_strategies(merged_cfg)
                if not ok:
                    result["status"] = "save_failed"
                    return result

                logger.info("✅ Strategy config synced from defaults (non-destructive merge)")
                if added_top_level:
                    logger.info(f"   + Added strategies: {', '.join(added_top_level)}")
                if pruned_keys:
                    logger.info(f"   - Removed obsolete strategies: {', '.join(pruned_keys)}")
                logger.info(f"   + Added missing keys: {added_keys_count}")
                result["status"] = "updated"
                result["removed_top_level"] = pruned_keys
            else:
                logger.info("ℹ️ Strategy config already up to date with defaults")
                result["status"] = "noop"
                result["removed_top_level"] = pruned_keys

            result["added_top_level"] = added_top_level
            result["added_keys_count"] = added_keys_count
            return result
        except Exception as e:
            logger.error(f"❌ Failed to sync strategies from defaults: {e}")
            result["status"] = "error"
            result["error"] = str(e)
            return result
    

    # Cache files (data/cache/)
    
    def save_token_cache(self, cache: Dict[str, Any]) -> bool:
        """Save token metadata cache atomically to data/cache/token_meta_cache.json"""
        return self.atomic_write_json(self.cache_dir / "token_meta_cache.json", cache, indent=2)
    
    def load_token_cache(self) -> Dict[str, Any]:
        """Load token metadata cache from data/cache/token_meta_cache.json"""
        return self.read_json(self.cache_dir / "token_meta_cache.json", default={})
    
    # State files (data/state/)
    
    def save_pnl_snapshot(self, snapshot: Dict[str, Any]) -> bool:
        """Save daily PnL snapshot atomically to data/state/daily_pnl_snapshot.json"""
        return self.atomic_write_json(self.state_dir / "daily_pnl_snapshot.json", snapshot, indent=2)
    
    def load_pnl_snapshot(self) -> Dict[str, Any]:
        """Load daily PnL snapshot from data/state/daily_pnl_snapshot.json"""
        return self.read_json(self.state_dir / "daily_pnl_snapshot.json", default={})
    

# Global storage service instance
# Will be initialized with BASE_DIR from api.py
storage_service = None


def init_storage(base_dir: str):
    """Initialize global storage service"""
    global storage_service
    storage_service = StorageService(base_dir)
    logger.info(f"✅ Storage service initialized with organized data structure")
    logger.info(f"   - Config: {storage_service.config_dir}")
    logger.info(f"   - Cache: {storage_service.cache_dir}")
    logger.info(f"   - State: {storage_service.state_dir}")
    return storage_service
