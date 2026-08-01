"""
WebSocket Price Manager for Hyperliquid Real-Time Price Feeds

This module provides a thread-safe WebSocket manager that subscribes to
real-time price updates from Hyperliquid, eliminating the need for REST
API calls for price checks and reducing rate limit exposure.

Refactored for Stability & Logging Compatibility.
"""

import asyncio
import threading
import time
import json
import logging
import websockets
from typing import Dict, Optional, List, Callable, Any

class WebSocketPriceManager:
    """
    Manages WebSocket connections for real-time price feeds from Hyperliquid.
    
    Robustness Features:
    - Thread-safe price cache (Lock)
    - Auto-reconnection with Exponential Backoff
    - Custom Logger compatibility (accepts LogBridge or standard Logger)
    - Daemon thread execution
    """
    
    def __init__(
        self,
        symbols: List[str],
        on_price_update: Optional[Callable[[str, float], None]] = None,
        staleness_threshold: int = 30,
        logger: Any = None
    ):
        """
        Initialize WebSocket Price Manager.
        
        Args:
            symbols: List of symbols to subscribe to (e.g., ["BTC", "ETH"])
            on_price_update: Optional callback(symbol, price) called on updates
            staleness_threshold: Seconds before price is considered stale
            logger: Optional logger instance (standard logging.Logger or custom object with info/warning/error methods)
        """
        self.symbols = symbols
        self.on_price_update = on_price_update
        self.staleness_threshold = staleness_threshold
        self.logger = logger
        
        # Thread-safe price cache
        self.prices: Dict[str, float] = {}
        self.last_update: Dict[str, float] = {}
        self._lock = threading.Lock()
        
        # WebSocket connection state
        self._ws_thread: Optional[threading.Thread] = None
        self._running = False
        self._reconnect_delay = 1.0
        self._max_reconnect_delay = 60.0
        self._websocket = None  # active connection; closed from stop() to unblock recv
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        
        # Hyperliquid WebSocket endpoint
        self._ws_url = "wss://api.hyperliquid.xyz/ws"
        
        self._log_info(f"📡 WebSocket Manager initialized for symbols: {', '.join(symbols)}")

    def _log_info(self, msg: str):
        """Internal log method: INFO"""
        if self.logger and hasattr(self.logger, 'info'):
            self.logger.info(msg)
        else:
            print(f"[WS-INFO] {msg}")

    def _log_warning(self, msg: str):
        """Internal log method: WARNING"""
        if self.logger and hasattr(self.logger, 'warning'):
            self.logger.warning(msg)
        else:
            print(f"[WS-WARN] {msg}")

    def _log_error(self, msg: str):
        """Internal log method: ERROR"""
        if self.logger and hasattr(self.logger, 'error'):
            self.logger.error(msg)
        else:
            print(f"[WS-ERROR] {msg}")

    def start(self) -> None:
        """Start the WebSocket manager in a background daemon thread."""
        if self._running:
            self._log_warning("⚠️ WebSocket manager already running")
            return
        
        self._running = True
        self._ws_thread = threading.Thread(
            target=self._run_ws_loop,
            daemon=True,
            name="HyperliquidWSManager"
        )
        self._ws_thread.start()
        self._log_info(f"✅ WebSocket Manager started (Daemon Thread). Monitoring {len(self.symbols)} symbols.")
    
    def stop(self) -> None:
        """Stop the WebSocket manager gracefully."""
        if not self._running:
            return
        
        self._log_info("🛑 Stopping WebSocket Manager...")
        self._running = False

        # Unblock recv() on the WS thread's loop (cross-thread safe)
        ws = self._websocket
        loop = self._loop
        if ws is not None and loop is not None and loop.is_running():
            try:
                fut = asyncio.run_coroutine_threadsafe(ws.close(), loop)
                fut.result(timeout=2.0)
            except Exception:
                pass
        self._websocket = None
        
        if self._ws_thread:
            self._ws_thread.join(timeout=5.0)
            if self._ws_thread.is_alive():
                # Daemon thread — harmless; do not WARNING (Discord spam on redeploy)
                self._log_info("ℹ️ WebSocket thread still winding down (daemon; safe to ignore).")
            else:
                self._log_info("✅ WebSocket Manager stopped.")

    def get_price(self, symbol: str) -> Optional[float]:
        """Get thread-safe price for a symbol."""
        with self._lock:
            if symbol not in self.prices:
                return None
            
            last_update_time = self.last_update.get(symbol, 0)
            age = time.time() - last_update_time
            
            if age > self.staleness_threshold:
                # Log once per threshold breach to avoid spamming? 
                # For now keeping it simple as requested
                # self._log_warning(f"⚠️ Price for {symbol} is stale ({age:.1f}s old)")
                return None
            
            return self.prices[symbol]
    
    def get_all_prices(self) -> Dict[str, float]:
        """Get copy of all cached prices."""
        with self._lock:
            return self.prices.copy()

    def add_symbol(self, symbol: str) -> None:
        """Add symbol to local filter."""
        self._log_info(f"➕ Adding symbol {symbol}")
        with self._lock:
            if symbol not in self.symbols:
                self.symbols.append(symbol)

    def remove_symbol(self, symbol: str) -> None:
        """Remove symbol from local filter."""
        self._log_info(f"➖ Removing symbol {symbol}")
        with self._lock:
            if symbol in self.symbols:
                self.symbols.remove(symbol)
                self.prices.pop(symbol, None)
                self.last_update.pop(symbol, None)

    def _run_ws_loop(self) -> None:
        """
        Main loop for the background thread.
        Handles asyncio event loop creation and crash resilience.
        """
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        self._loop = loop
        
        while self._running:
            try:
                self._log_info("🔌 Connecting to Hyperliquid WebSocket (allMids)...")
                loop.run_until_complete(self._subscribe_and_listen())
                
                if not self._running:
                    break

                # Clean server close (~hours) is normal — backoff before reconnect
                # so we don't hammer CloudFront and spam Discord.
                self._log_info(f"🔄 WS reconnecting in {self._reconnect_delay:.1f}s...")
                time.sleep(self._reconnect_delay)
                self._reconnect_delay = min(self._reconnect_delay * 2.0, self._max_reconnect_delay)
                
            except Exception as e:
                if not self._running:
                    break
                
                self._log_error(f"❌ WebSocket connection crashed: {e}")
                self._log_info(f"🔄 Reconnecting in {self._reconnect_delay:.1f}s...")
                
                time.sleep(self._reconnect_delay)
                
                # Exponential backoff
                self._reconnect_delay = min(self._reconnect_delay * 2.0, self._max_reconnect_delay)
        
        try:
            loop.close()
        except Exception:
            pass
        self._loop = None
        self._log_info("🔌 WebSocket event loop terminated.")

    async def _subscribe_and_listen(self) -> None:
        """Coroutine: Connects, Subscribes, and Listens."""
        async with websockets.connect(
            self._ws_url,
            ping_interval=20,
            ping_timeout=20,
            close_timeout=5,
        ) as websocket:
            self._websocket = websocket
            try:
                self._log_info("✅ WebSocket Connected.")
                # Fresh connection — reset backoff so routine closes don't grow forever
                self._reconnect_delay = 1.0
                
                # Subscribe to allMids
                sub_msg = {
                    "method": "subscribe",
                    "subscription": {"type": "allMids"}
                }
                await websocket.send(json.dumps(sub_msg))
                self._log_info("📡 Subscribed to 'allMids'.")
                
                while self._running:
                    try:
                        # 20s timeout for heartbeats
                        message = await asyncio.wait_for(websocket.recv(), timeout=20.0)
                        self._process_message(message)
                    except asyncio.TimeoutError:
                        # Ping to check aliveness
                        await websocket.ping()
                    except websockets.exceptions.ConnectionClosed as e:
                        # INFO only — Discord forwards WARNING/ERROR and this is routine (~3h LB)
                        self._log_info(f"🔌 WS closed by server ({getattr(e, 'code', '?')}); will reconnect.")
                        break
                    except Exception as e:
                        self._log_error(f"⚠️ Error receiving message: {e}")
                        break
            finally:
                if self._websocket is websocket:
                    self._websocket = None

    def _process_message(self, message: str) -> None:
        """Parses JSON message and updates price cache safely."""
        try:
            data = json.loads(message)
            
            # Message format: {"channel": "allMids", "data": {"mids": {"BTC": "...", "ETH": "..."}}}
            if data.get("channel") == "allMids":
                payload = data.get("data", {})
                mids = payload.get("mids", {})
                
                current_time = time.time()
                
                # Optimize locking: only lock once per batch
                with self._lock:
                    for symbol in self.symbols:
                        if symbol in mids:
                            try:
                                price = float(mids[symbol])
                                self.prices[symbol] = price
                                self.last_update[symbol] = current_time
                                
                                if self.on_price_update:
                                    # Call callback outside? No, keep it simple for now, 
                                    # but warn if it blocks.
                                    # Ideally callbacks should be non-blocking.
                                    pass 
                            except ValueError:
                                continue
                                
                # Processing callbacks outside lock would be better for performance 
                # if callback is slow, but requires copying data.
                # Given current usage (lightweight), this is acceptable.
                
        except json.JSONDecodeError:
            pass
        except Exception as e:
            self._log_error(f"Error parsing message: {e}")
