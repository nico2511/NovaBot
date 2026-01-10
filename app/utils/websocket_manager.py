"""
WebSocket Price Manager for Hyperliquid Real-Time Price Feeds

This module provides a thread-safe WebSocket manager that subscribes to
real-time price updates from Hyperliquid, eliminating the need for REST
API calls for price checks and reducing rate limit exposure by ~80%.

Author: NovaBot Team
Date: 2026-01-01
"""

import asyncio
import threading
import time
import json
import logging
import websockets
from typing import Dict, Optional, List, Callable
from datetime import datetime


class WebSocketPriceManager:
    """
    Manages WebSocket connections for real-time price feeds from Hyperliquid.
    
    This manager runs in a background thread to avoid blocking the main trading
    loop. It maintains a thread-safe cache of current prices that can be accessed
    instantly without making REST API calls.
    
    Features:
    - Thread-safe price cache with lock-based synchronization
    - Automatic reconnection on disconnect
    - Staleness detection (alerts if price hasn't updated in 30s)
    - Graceful shutdown
    - Callback support for price updates
    - Integrated logging system
    
    Architecture:
        Main Thread (Trading Bot)
            ↓ (read only)
        Price Cache (Dict with Lock)
            ↑ (write only)
        Background Thread → Asyncio Event Loop → WebSocket Connection → Hyperliquid
    
    Example:
        >>> manager = WebSocketPriceManager(["BTC", "ETH"])
        >>> manager.start()
        >>> 
        >>> # In trading loop
        >>> btc_price = manager.get_price("BTC")
        >>> if btc_price:
        ...     print(f"BTC: ${btc_price}")
        >>> 
        >>> # Cleanup on shutdown
        >>> manager.stop()
    """
    
    def __init__(
        self,
        symbols: List[str],
        on_price_update: Optional[Callable[[str, float], None]] = None,
        staleness_threshold: int = 30,
        logger: Optional[logging.Logger] = None
    ):
        """
        Initialize WebSocket Price Manager.
        
        Args:
            symbols: List of symbols to subscribe to (e.g., ["BTC", "ETH", "HYPE"])
            on_price_update: Optional callback function(symbol, price) called on each update
            staleness_threshold: Seconds before price is considered stale (default: 30)
            logger: Optional logger instance. If None, uses print() as fallback
        """
        self.symbols = symbols
        self.on_price_update = on_price_update
        self.staleness_threshold = staleness_threshold
        
        # Logging setup
        if logger:
            self.logger = logger
        else:
            # Fallback: Create a basic logger
            self.logger = logging.getLogger(__name__)
            if not self.logger.handlers:
                handler = logging.StreamHandler()
                handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
                self.logger.addHandler(handler)
                self.logger.setLevel(logging.INFO)
        
        # Thread-safe price cache
        self.prices: Dict[str, float] = {}
        self.last_update: Dict[str, float] = {}  # Timestamp of last update
        self._lock = threading.Lock()
        
        # WebSocket connection state
        self._ws_thread: Optional[threading.Thread] = None
        self._running = False
        self._reconnect_delay = 1.0  # Start with 1s, exponential backoff
        self._max_reconnect_delay = 60.0
        
        # Hyperliquid WebSocket endpoint
        self._ws_url = "wss://api.hyperliquid.xyz/ws"
        
        self.logger.info(f"📡 WebSocket Price Manager initialized for symbols: {', '.join(symbols)}")
    
    def start(self) -> None:
        """
        Start the WebSocket manager in a background thread.
        
        This method is non-blocking and returns immediately. The WebSocket
        connection is established in the background thread.
        """
        if self._running:
            self.logger.warning("⚠️ WebSocket manager already running")
            return
        
        self._running = True
        self._ws_thread = threading.Thread(
            target=self._run_ws_loop,
            daemon=True,
            name="HyperliquidWSManager"
        )
        self._ws_thread.start()
        self.logger.info(f"✅ WebSocket Price Manager started for {len(self.symbols)} symbols")
    
    def stop(self) -> None:
        """
        Stop the WebSocket manager gracefully.
        
        This will close the WebSocket connection and join the background thread.
        Blocks until the thread terminates (max 5 seconds).
        """
        if not self._running:
            return
        
        self.logger.info("🛑 Stopping WebSocket Price Manager...")
        self._running = False
        
        if self._ws_thread:
            self._ws_thread.join(timeout=5.0)
            if self._ws_thread.is_alive():
                self.logger.warning("⚠️ WebSocket thread did not terminate gracefully")
            else:
                self.logger.info("✅ WebSocket manager stopped")
    
    def get_price(self, symbol: str) -> Optional[float]:
        """
        Get the current cached price for a symbol (thread-safe).
        
        Args:
            symbol: Trading pair symbol (e.g., "BTC")
        
        Returns:
            Current price or None if unavailable/stale
        
        Example:
            >>> price = manager.get_price("BTC")
            >>> if price:
            ...     print(f"BTC: ${price}")
            ... else:
            ...     print("Price unavailable")
        """
        with self._lock:
            # Check if price exists
            if symbol not in self.prices:
                return None
            
            # Check staleness
            last_update_time = self.last_update.get(symbol, 0)
            age = time.time() - last_update_time
            
            if age > self.staleness_threshold:
                self.logger.warning(f"⚠️ Price for {symbol} is stale ({age:.1f}s old)")
                return None
            
            return self.prices[symbol]
    
    def get_all_prices(self) -> Dict[str, float]:
        """
        Get all cached prices (thread-safe).
        
        Returns:
            Dictionary of {symbol: price} for all subscribed symbols
        """
        with self._lock:
            return self.prices.copy()
    
    def add_symbol(self, symbol: str) -> None:
        """
        Add a new symbol to the subscription list.
        
        Note: Hyperliquid's 'allMids' channel sends prices for ALL assets.
        This method only updates the local whitelist for filtering - no reconnection needed.
        
        Args:
            symbol: Symbol to add (e.g., "SOL")
        """
        self.logger.info(f"➕ Adding symbol {symbol} to local filter (no reconnection needed)")
        with self._lock:
            if symbol not in self.symbols:
                self.symbols.append(symbol)
    
    def remove_symbol(self, symbol: str) -> None:
        """
        Remove a symbol from the subscription list.
        
        Args:
            symbol: Symbol to remove
        """
        self.logger.info(f"➖ Removing symbol {symbol} from WebSocket subscription")
        with self._lock:
            if symbol in self.symbols:
                self.symbols.remove(symbol)
        
        with self._lock:
            self.prices.pop(symbol, None)
            self.last_update.pop(symbol, None)
    
    def _run_ws_loop(self) -> None:
        """
        Background thread entry point that runs the asyncio event loop.
        
        This method creates a new event loop and runs the WebSocket
        subscription coroutine. It handles reconnection with exponential backoff.
        """
        # Create new event loop for this thread
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        while self._running:
            try:
                self.logger.info("🔌 Connecting to Hyperliquid WebSocket...")
                loop.run_until_complete(self._subscribe_prices())
                
                # If we exit cleanly, reset reconnect delay
                self._reconnect_delay = 1.0
                
            except Exception as e:
                if not self._running:
                    break
                
                self.logger.error(f"❌ WebSocket error: {e}")
                self.logger.info(f"🔄 Reconnecting in {self._reconnect_delay:.1f}s...")
                
                time.sleep(self._reconnect_delay)
                
                # Exponential backoff for reconnection
                self._reconnect_delay = min(
                    self._reconnect_delay * 2.0,
                    self._max_reconnect_delay
                )
        
        loop.close()
        self.logger.info("🔌 WebSocket event loop closed")
    
    async def _subscribe_prices(self) -> None:
        """
        Async coroutine that maintains the WebSocket connection and processes messages.
        
        This method:
        1. Connects to Hyperliquid WebSocket
        2. Sends subscription message for allMids (all symbols)
        3. Processes incoming price updates
        4. Updates the thread-safe price cache
        
        Raises:
            Exception: On connection failure or protocol error
        """
        async with websockets.connect(self._ws_url) as websocket:
            self.logger.info(f"✅ Connected to Hyperliquid WebSocket")
            
            # Subscribe to all mid prices
            # Hyperliquid WebSocket subscription format:
            # {"method": "subscribe", "subscription": {"type": "allMids"}}
            subscription_msg = {
                "method": "subscribe",
                "subscription": {
                    "type": "allMids"  # Subscribe to all mid prices
                }
            }
            
            await websocket.send(json.dumps(subscription_msg))
            self.logger.info(f"📡 Subscribed to allMids channel (filtering {len(self.symbols)} symbols locally)")
            
            # Process incoming messages
            while self._running:
                try:
                    # Wait for message with timeout
                    message = await asyncio.wait_for(
                        websocket.recv(),
                        timeout=30.0  # 30s timeout
                    )
                    
                    # Parse and process message
                    self._process_message(message)
                    
                except asyncio.TimeoutError:
                    # Send ping to keep connection alive
                    await websocket.ping()
                    
                except Exception as e:
                    self.logger.error(f"⚠️ Error processing WebSocket message: {e}")
                    break
    
    def _process_message(self, message: str) -> None:
        """
        Process incoming WebSocket message and update price cache.
        
        Wrapped in try/except to prevent silent crashes from malformed JSON.
        
        Args:
            message: JSON string from WebSocket
        """
        try:
            data = json.loads(message)
            
            # Hyperliquid sends price updates in format:
            # {"channel": "allMids", "data": {"BTC": "50000.5", "ETH": "3000.2", ...}}
            if data.get("channel") == "allMids":
                mids_data = data.get("data", {})
                # Hyperliquid wraps prices in a "mids" key
                mids = mids_data.get("mids", mids_data)
                
                # Update prices for subscribed symbols
                current_time = time.time()
                
                with self._lock:
                    for symbol in self.symbols:
                        if symbol in mids:
                            price = float(mids[symbol])
                            self.prices[symbol] = price
                            self.last_update[symbol] = current_time
                            
                            # Call callback if provided
                            if self.on_price_update:
                                try:
                                    self.on_price_update(symbol, price)
                                except Exception as e:
                                    self.logger.error(f"⚠️ Error in price update callback: {e}")
        
        except json.JSONDecodeError as e:
            self.logger.error(f"⚠️ Invalid JSON from WebSocket: {message[:100]} | Error: {e}")
        except Exception as e:
            self.logger.error(f"⚠️ Error processing message: {e}")
    
    def is_healthy(self) -> bool:
        """
        Check if the WebSocket manager is healthy.
        
        Returns:
            True if running and receiving updates, False otherwise
        """
        if not self._running:
            return False
        
        # Check if we have recent price updates
        with self._lock:
            if not self.last_update:
                return False
            
            current_time = time.time()
            recent_updates = [
                current_time - ts < self.staleness_threshold
                for ts in self.last_update.values()
            ]
            
            # Healthy if at least 50% of symbols have recent updates
            return sum(recent_updates) >= len(self.symbols) * 0.5
    
    def get_status(self) -> Dict:
        """
        Get detailed status information about the WebSocket manager.
        
        Returns:
            Dictionary with status information
        """
        with self._lock:
            current_time = time.time()
            
            symbol_status = {}
            for symbol in self.symbols:
                price = self.prices.get(symbol)
                last_update = self.last_update.get(symbol, 0)
                age = current_time - last_update if last_update > 0 else None
                
                symbol_status[symbol] = {
                    "price": price,
                    "last_update": datetime.fromtimestamp(last_update).isoformat() if last_update > 0 else None,
                    "age_seconds": age,
                    "is_stale": age > self.staleness_threshold if age else True
                }
            
            return {
                "running": self._running,
                "healthy": self.is_healthy(),
                "symbols": symbol_status,
                "reconnect_delay": self._reconnect_delay
            }
