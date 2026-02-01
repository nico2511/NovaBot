"""
Settings Watcher Service
Monitors user_settings.json for external changes and triggers hot-reload.
Uses polling to avoid external dependencies (watchdog) and ensure cross-platform stability.
"""
import time
import logging
from pathlib import Path
from threading import Thread
from typing import Callable, Dict, Any, Optional
from backend.services.storage import storage_service

logger = logging.getLogger("SettingsWatcher")

class SettingsWatcher:
    def __init__(self, config_path: Path, callback: Callable[[Dict[str, Any]], None], poll_interval: float = 2.0):
        """
        Initialize SettingsWatcher
        
        Args:
            config_path: Path to user_settings.json
            callback: Function to call when settings change (receives new settings dict)
            poll_interval: time in seconds between checks
        """
        self.config_path = config_path
        self._callback = callback
        self._poll_interval = poll_interval
        self._running = False
        self._thread: Optional[Thread] = None
        self._last_mtime = 0.0

    def start(self):
        """Start the polling thread"""
        if self._running:
            logger.warning("⚠️ Watcher already running")
            return

        # Initialize mtime
        if self.config_path.exists():
            self._last_mtime = self.config_path.stat().st_mtime
            logger.info(f"👀 Watcher init: Tracking {self.config_path.name}")
        else:
            logger.warning(f"⚠️ Config file not found at start: {self.config_path}")

        self._running = True
        self._thread = Thread(target=self._poll_loop, daemon=True, name="SettingsWatcherThread")
        self._thread.start()
        logger.info("🚀 Settings Watcher started")

    def stop(self):
        """Stop the polling thread"""
        self._running = False
        if self._thread:
            self._thread.join(timeout=1.0)
        logger.info("🛑 Settings Watcher stopped")

    def _poll_loop(self):
        """Polling loop to detect file changes"""
        while self._running:
            try:
                time.sleep(self._poll_interval)
                
                if not self.config_path.exists():
                    continue

                try:
                    current_mtime = self.config_path.stat().st_mtime
                except FileNotFoundError:
                    continue # File might have been deleted mid-check

                # Detect Change
                if current_mtime > self._last_mtime:
                    # Debounce (wait for write to complete)
                    time.sleep(0.5) 
                    
                    # Verify mtime stable
                    try:
                        new_mtime = self.config_path.stat().st_mtime
                        if new_mtime != current_mtime:
                             continue # Still changing
                    except:
                        continue

                    logger.info("♻️ Detected settings file change - Reloading...")
                    self._last_mtime = current_mtime
                    
                    try:
                        # Load new settings
                        new_settings = storage_service.load_settings()
                        
                        # Trigger Callback
                        if self._callback:
                            self._callback(new_settings)
                            
                    except Exception as e:
                        logger.error(f"❌ Failed to reload settings: {e}")
                        
            except Exception as e:
                logger.error(f"❌ Error in watcher loop: {e}")
                time.sleep(5.0) # Backoff on error
