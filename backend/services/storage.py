"""
Atomic Storage Service for NovaBot
Provides atomic file writes for JSON data to prevent corruption
All data files are organized in the data/ directory
"""
import os
import json
import tempfile
import shutil
from typing import Any, Dict
from pathlib import Path
import logging

logger = logging.getLogger("StorageService")


class StorageService:
    """Service for atomic file operations with organized data structure"""
    
    def __init__(self, base_dir: str):
        """
        Initialize storage service with organized data structure
        
        Directory structure:
        - data/config/     - Configuration files (user_settings.json, strategies.json, theme.json)
        - data/cache/      - Cache files (token_meta_cache.json)
        - data/state/      - State files (daily_pnl_snapshot.json)
        - data/analysis/   - Analysis files (signal_analysis.json, sentiment_history.json)
        
        Args:
            base_dir: Base directory for all storage operations
        """
        # Robust pathing: Ensure we are at the project root even if launched from backend/
        path_obj = Path(base_dir).absolute()
        if path_obj.name == "backend":
            self.base_dir = path_obj.parent
        else:
            self.base_dir = path_obj
            
        self.data_dir = self.base_dir / "data"
        
        # Create organized subdirectories
        self.config_dir = self.data_dir / "config"
        self.cache_dir = self.data_dir / "cache"
        self.state_dir = self.data_dir / "state"
        self.analysis_dir = self.data_dir / "analysis"
        
        # Create all directories
        for directory in [self.config_dir, self.cache_dir, self.state_dir, self.analysis_dir]:
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
            "operations": {},
            "risk_defaults": {},
            "ai_config": {},
            "scanner": {},
            "notifications": {}
        })
    
    def save_strategies(self, strategies: Dict[str, Any]) -> bool:
        """Save strategies configuration atomically to data/config/strategies.json"""
        return self.atomic_write_json(self.config_dir / "strategies.json", strategies, indent=2)
    
    def load_strategies(self) -> Dict[str, Any]:
        """Load strategies configuration from data/config/strategies.json"""
        return self.read_json(self.config_dir / "strategies.json", default={"strategies": []})
    
    def save_theme(self, theme: Dict[str, Any]) -> bool:
        """Save theme configuration atomically to data/config/theme.json"""
        return self.atomic_write_json(self.config_dir / "theme.json", theme, indent=2)
    
    def load_theme(self) -> Dict[str, Any]:
        """Load theme configuration from data/config/theme.json"""
        return self.read_json(self.config_dir / "theme.json", default={})
    
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
    
    # Analysis files (data/analysis/)
    
    def save_signal_analysis(self, analysis: Dict[str, Any]) -> bool:
        """Save signal analysis atomically to data/analysis/signal_analysis.json"""
        return self.atomic_write_json(self.analysis_dir / "signal_analysis.json", analysis, indent=2)
    
    def load_signal_analysis(self) -> Any:
        """Load signal analysis from data/analysis/signal_analysis.json"""
        return self.read_json(self.analysis_dir / "signal_analysis.json", default=[])
    
    def save_sentiment_history(self, history: Dict[str, Any]) -> bool:
        """Save sentiment history atomically to data/analysis/sentiment_history.json"""
        return self.atomic_write_json(self.analysis_dir / "sentiment_history.json", history, indent=2)
    
    def load_sentiment_history(self) -> Any:
        """Load sentiment history from data/analysis/sentiment_history.json"""
        return self.read_json(self.analysis_dir / "sentiment_history.json", default=[])


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
    logger.info(f"   - Analysis: {storage_service.analysis_dir}")
    return storage_service
