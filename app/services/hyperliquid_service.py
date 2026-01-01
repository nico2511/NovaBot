import eth_account
from hyperliquid.info import Info
from hyperliquid.exchange import Exchange
from hyperliquid.utils import types
from app.core.config import config
import pandas as pd
import time

from hyperliquid.utils.constants import MAINNET_API_URL

# Import retry decorators and WebSocket manager
from app.utils.retry_decorator import critical_operation, standard_operation, lightweight_operation
from app.utils.websocket_manager import WebSocketPriceManager

class HyperliquidService:
    def __init__(self):
        # Initialize Info API (WebSocket will be managed separately)
        self.info = Info(base_url=MAINNET_API_URL, skip_ws=True)
        self.exchange = None
        
        # Initialize WebSocket Price Manager (will be started externally)
        self.ws_manager: WebSocketPriceManager = None
        
        if config.HL_PRIVATE_KEY and config.HL_ACCOUNT_ADDRESS:
            try:
                # Sanitize key: ensure no whitespace, handle 0x prefix if needed (eth_account usually handles 0x, but whitespace is fatal)
                sanitized_key = config.HL_PRIVATE_KEY.strip()
                if sanitized_key.startswith("0x"):
                    sanitized_key = sanitized_key[2:]
                    
                account = eth_account.Account.from_key(sanitized_key)
                self.exchange = Exchange(account, base_url=MAINNET_API_URL, account_address=config.HL_ACCOUNT_ADDRESS)
            except Exception as e:
                print(f"⚠️ [WARNING] Failed to initialize Hyperliquid Exchange: {e}")
                self.exchange = None
        
        # Initialize metadata cache
        self._meta_cache = None
        
        # Balance cache to prevent 429s from frontend polling
        self._balance_cache = {"time": 0, "data": None}
        self._cache_ttl = 10 # 10 seconds TTL
    
    def start_websocket(self, symbols: list[str]) -> None:
        """
        Start WebSocket price manager for real-time price feeds.
        
        This should be called once at bot startup with the list of symbols
        to monitor. The WebSocket runs in a background thread and continuously
        updates price cache.
        
        Args:
            symbols: List of symbols to subscribe to (e.g., ["BTC", "ETH"])
        
        Example:
            >>> service = HyperliquidService()
            >>> service.start_websocket(["BTC", "HYPE"])
        """
        if self.ws_manager is not None:
            print("⚠️ WebSocket manager already initialized")
            return
        
        try:
            self.ws_manager = WebSocketPriceManager(symbols)
            self.ws_manager.start()
            print(f"✅ WebSocket price feeds started for: {', '.join(symbols)}")
        except Exception as e:
            print(f"❌ Failed to start WebSocket manager: {e}")
            print("⚠️ Falling back to REST API for price feeds")
            self.ws_manager = None
    
    def stop_websocket(self) -> None:
        """
        Stop WebSocket price manager gracefully.
        
        Should be called on bot shutdown.
        """
        if self.ws_manager:
            self.ws_manager.stop()
            self.ws_manager = None
    
    def _parse_interval_to_seconds(self, interval: str) -> int:
        """Parse interval string (e.g., '1m', '15m', '1h') to seconds"""
        interval = interval.lower().strip()
        if interval.endswith('m'):
            return int(interval[:-1]) * 60
        elif interval.endswith('h'):
            return int(interval[:-1]) * 3600
        elif interval.endswith('d'):
            return int(interval[:-1]) * 86400
        else:
            # Default to 15m if unknown
            return 900

    def get_candles(self, symbol: str, interval: str = "15m", limit: int = 100) -> pd.DataFrame:
        try:
            # CRITICAL: Use UTC time for Hyperliquid API (not local time)
            end_time = int(pd.Timestamp.now(tz='UTC').timestamp() * 1000)
            
            # Parse interval to calculate start_time correctly
            interval_seconds = self._parse_interval_to_seconds(interval)
            start_time = end_time - (limit * interval_seconds * 1000)
            
            raw_candles = self.info.candles_snapshot(symbol, interval, start_time, end_time)
            
            if not raw_candles:
                return pd.DataFrame()
                
            df = pd.DataFrame(raw_candles)
            df['time'] = pd.to_datetime(df['t'], unit='ms')
            df.set_index('time', inplace=True)
            # Convert numeric columns
            for col in ['o', 'h', 'l', 'c', 'v']:
                df[col] = df[col].astype(float)
            
            # Standardize column names for pandas_ta and UI
            df.rename(columns={
                'o': 'open', 
                'h': 'high', 
                'l': 'low', 
                'c': 'close', 
                'v': 'volume'
            }, inplace=True)
            
            return df.tail(limit)
        except Exception as e:
            print(f"Error fetching candles: {e}")
            return pd.DataFrame()

    
    def _fetch_metadata(self):
        """Fetch and cache exchange metadata for precision (Persistent Cache)"""
        import json
        import os
        CACHE_FILE = "token_meta_cache.json"

        # 1. Check in-memory cache
        if hasattr(self, "_meta_cache") and self._meta_cache:
            return self._meta_cache
        
        # 2. Try to load from disk
        if os.path.exists(CACHE_FILE):
            try:
                with open(CACHE_FILE, "r") as f:
                    self._meta_cache = json.load(f)
                    print("✅ Metadata loaded from disk cache.")
            except Exception as e:
                print(f"⚠️ Failed to load metadata cache from disk: {e}")

        # 3. If still needed, fetch from API (and save)
        if not self._meta_cache:
            try:
                print("🌐 Fetching metadata from Hyperliquid API...")
                self._meta_cache = self.info.meta()
                
                # Save to disk
                try:
                    with open(CACHE_FILE, "w") as f:
                        json.dump(self._meta_cache, f)
                except Exception as e:
                    print(f"⚠️ Warning: Could not save metadata cache: {e}")
                    
            except Exception as e:
                print(f"⚠️ Failed to fetch metadata from API: {e}")
                # Fallback to defaults will happen in _get_precision
                return None
        
        return self._meta_cache

    def _get_precision(self, symbol: str):
        """Get precision for size and price from metadata"""
        meta = self._fetch_metadata()
        if not meta:
            return 6, 4 # Safe defaults
            
        try:
            universe = meta.get("universe", [])
            for asset in universe:
                if asset["name"] == symbol:
                    # Use .get() to avoid KeyErrors if API keys change/missing
                    return asset.get("szDecimals", 6), asset.get("maxPriceDecimals", 4)
        except Exception as e:
            print(f"⚠️ Error parsing metadata for {symbol}: {e}")
            
        return 6, 4 # Defaults if not found

    @standard_operation
    def _place_protection_orders(self, symbol: str, is_buy: bool, quantity: float, sl_price: float = None, tp_price: float = None):
        """Place Stop Loss and Take Profit orders on exchange (Hard Stops)"""
        try:
            sz_decimals, price_decimals = self._get_precision(symbol)
            
            # SL/TP logic: 
            # If opened LONG (is_buy=True) -> SL/TP are SELL orders (is_buy=False)
            # If opened SHORT (is_buy=False) -> SL/TP are BUY orders (is_buy=True)
            close_is_buy = not is_buy
            
            if sl_price:
                sl_price = float(f"{sl_price:.{price_decimals}f}")
                print(f"🛡️ PLACING HARD STOP LOSS for {symbol} @ {sl_price}")
                # "trigger": {"triggerPx": sl_price, "isMarket": True, "tpsl": "sl"}
                self.exchange.order(
                    symbol, close_is_buy, quantity, sl_price, 
                    {"trigger": {"triggerPx": sl_price, "isMarket": True, "tpsl": "sl"}},
                    reduce_only=True
                )
                
            if tp_price:
                tp_price = float(f"{tp_price:.{price_decimals}f}")
                print(f"🎯 PLACING HARD TAKE PROFIT for {symbol} @ {tp_price}")
                # "trigger": {"triggerPx": tp_price, "isMarket": True, "tpsl": "tp"}
                self.exchange.order(
                    symbol, close_is_buy, quantity, tp_price, 
                    {"trigger": {"triggerPx": tp_price, "isMarket": True, "tpsl": "tp"}},
                    reduce_only=True
                )
                
        except Exception as e:
            print(f"⚠️ Failed to place protection orders: {e}")

    def get_canonical_symbol(self, symbol: str) -> str:
        """
        Resolve symbol to its canonical Hyperliquid name.
        Handles aliases like PEPE -> kPEPE, BONK -> kBONK.
        """
        meta = self._fetch_metadata()
        if not meta:
            return symbol
            
        universe = [a["name"] for a in meta.get("universe", [])]
        
        # 1. Exact match
        if symbol in universe:
            return symbol
            
        # 2. Try adding 'k' prefix (e.g. PEPE -> kPEPE)
        k_symbol = f"k{symbol}"
        if k_symbol in universe:
            print(f"ℹ️ Auto-resolving {symbol} -> {k_symbol}")
            return k_symbol
            
        # 3. Try removing 'k' prefix (e.g. kPEPE -> PEPE - unlikely but safe)
        if symbol.startswith("k") and symbol[1:] in universe:
            return symbol[1:]
            
        return symbol

    def execute_order(self, symbol: str, is_buy: bool, quantity: float, price: float = None, sl_price: float = None, tp_price: float = None):
        if not self.exchange:
            return {"status": "error", "message": "No private key configured"}
        
        import time
        
        # NORMALIZATION: Ensure we use the correct symbol (e.g. kPEPE)
        symbol = self.get_canonical_symbol(symbol)
        
        # Dynamic Precision Rounding
        sz_decimals, price_decimals = self._get_precision(symbol)
        
        # Format Quantity
        quantity = float(f"{quantity:.{sz_decimals}f}")
        
        # Retry configuration
        max_retries = 3
        retry_delay = 1  # seconds
        
        for attempt in range(max_retries):
            try:
                if price:
                    # LIMIT ORDER
                    price = float(f"{price:.{price_decimals}f}")
                    print(f"🚀 SUBMITTING LIMIT {'BUY' if is_buy else 'SELL'} {quantity} {symbol} @ {price} (Attempt {attempt + 1}/{max_retries})")
                    result = self.exchange.order(symbol, is_buy, quantity, price, {"limit": {"tif": "Gtc"}})
                else:
                    # MARKET ORDER
                    print(f"🚀 SUBMITTING MARKET {'BUY' if is_buy else 'SELL'} {quantity} {symbol} (Attempt {attempt + 1}/{max_retries})")
                    result = self.exchange.market_open(symbol, is_buy, quantity)
                
                print(f"✅ Order execution result: {result}")
                
                # Verify order was accepted
                if result.get("status") == "ok":
                    # Check for inner error status (CRITICAL FIX)
                    # Hyperliquid returns "status": "ok" even if execution failed
                    # Structure: {'status': 'ok', 'response': {'type': 'order', 'data': {'statuses': [{'error': 'Order has invalid size.'}]}}}
                    response_data = result.get("response", {}).get("data", {})
                    statuses = response_data.get("statuses", [])
                    
                    if statuses and statuses[0].get("error"):
                         error_msg = statuses[0].get("error")
                         print(f"❌ Order Rejected by Engine: {error_msg}")
                         if attempt < max_retries - 1:
                            time.sleep(retry_delay * (2 ** attempt))
                            continue
                         else:
                            return {"status": "error", "message": f"Order rejected: {error_msg}"}

                    # Wait a moment for order to fill
                    time.sleep(2)
                    
                    # Verify position exists
                    positions = self.get_positions()
                    position_found = any(p["symbol"] == symbol for p in positions)
                    
                    if position_found:
                        print(f"✅ Position verified on exchange for {symbol}")
                        # Place Hard Stops
                        self._place_protection_orders(symbol, is_buy, quantity, sl_price, tp_price)
                        return {"status": "success", "result": result}
                    else:
                        print(f"⚠️ Order accepted but position not found, retrying...")
                        if attempt < max_retries - 1:
                            time.sleep(retry_delay * (2 ** attempt))  # Exponential backoff
                            continue
                        else:
                            return {"status": "error", "message": "Order accepted but position not found after retries"}
                else:
                    # Request failed (HTML error etc)
                    print(f"❌ Order Request Failed: {result}")
                    if attempt < max_retries - 1:
                        time.sleep(retry_delay * (2 ** attempt))
                        continue
                    else:
                        return {"status": "error", "message": f"Order request failed: {result}"}
                        
            except Exception as e:
                print(f"❌ Order execution failed (Attempt {attempt + 1}/{max_retries}): {e}")
                if attempt < max_retries - 1:
                    time.sleep(retry_delay * (2 ** attempt))
                    continue
                else:
                    return {"status": "error", "message": f"Order failed after {max_retries} attempts: {str(e)}"}
        
        return {"status": "error", "message": "Order execution failed"}
    
    @standard_operation
    def set_sl_tp(
        self,
        symbol: str,
        entry_price: float,
        sl_percent: float,
        tp_percent: float,
        is_long: bool,
        quantity: float
    ) -> dict:
        """
        Calculate and place Stop Loss and Take Profit orders.
        
        This is a convenience method that calculates SL/TP prices based on
        percentages and places them as native exchange orders (Trigger Orders).
        
        Args:
            symbol: Trading pair symbol (e.g., "BTC")
            entry_price: Position entry price
            sl_percent: Stop loss percentage (e.g., 2.0 for 2%)
            tp_percent: Take profit percentage (e.g., 5.0 for 5%)
            is_long: True if LONG position, False if SHORT
            quantity: Position size in tokens
        
        Returns:
            dict: {"status": "success"|"error", "sl_price": float, "tp_price": float}
        
        Example:
            >>> # For a LONG position at $50,000 with 2% SL and 5% TP
            >>> service.set_sl_tp("BTC", 50000, 2.0, 5.0, True, 0.1)
            >>> # SL = $49,000 (2% below entry)
            >>> # TP = $52,500 (5% above entry)
            
            >>> # For a SHORT position at $3,000 with 2% SL and 5% TP
            >>> service.set_sl_tp("ETH", 3000, 2.0, 5.0, False, 1.0)
            >>> # SL = $3,060 (2% above entry)
            >>> # TP = $2,850 (5% below entry)
        
        Raises:
            Exception: If exchange not configured or order placement fails
        """
        if not self.exchange:
            raise Exception("No private key configured")
        
        # Calculate SL/TP prices based on position direction
        if is_long:
            # LONG: SL below entry, TP above entry
            sl_price = entry_price * (1 - sl_percent / 100)
            tp_price = entry_price * (1 + tp_percent / 100)
        else:
            # SHORT: SL above entry, TP below entry
            sl_price = entry_price * (1 + sl_percent / 100)
            tp_price = entry_price * (1 - tp_percent / 100)
        
        print(f"🛡️ Setting SL/TP for {symbol}: SL={sl_price:.2f}, TP={tp_price:.2f}")
        
        # Use existing method (which also has retry logic via decorator)
        self._place_protection_orders(symbol, is_long, quantity, sl_price, tp_price)
        
        return {
            "status": "success",
            "sl_price": sl_price,
            "tp_price": tp_price
        }

    def update_leverage(self, symbol: str, leverage: int, is_cross: bool = True):
        """Update leverage and margin type (Cross/Isolated) for a symbol"""
        if not self.exchange:
            return {"status": "error", "message": "No private key configured"}
            
        try:
            print(f"⚙️ Updating leverage for {symbol}: {leverage}x (Cross: {is_cross})")
            # Set leverage
            self.exchange.update_leverage(leverage, symbol, is_cross)
            return {"status": "success", "leverage": leverage, "is_cross": is_cross}
        except Exception as e:
            print(f"❌ Failed to update leverage: {e}")
            return {"status": "error", "message": str(e)}

    @standard_operation
    def get_account_balance(self, force_refresh=False):
        """Fetch account balance and margin information from Hyperliquid (Cached)"""
        if not config.HL_ACCOUNT_ADDRESS:
            return {
                "status": "error",
                "message": "No account address configured",
                "total_equity": 0,
                "available_balance": 0,
                "margin_used": 0
            }
            
        # Check Cache
        now = time.time()
        if not force_refresh and self._balance_cache["data"] and (now - self._balance_cache["time"] < self._cache_ttl):
            return self._balance_cache["data"]
        
        try:
            info = Info(config.HYPERLIQUID_API_URL, skip_ws=True)
            user_state = info.user_state(config.HL_ACCOUNT_ADDRESS)
            
            # Extract balance info
            margin_summary = user_state.get("marginSummary", {})
            account_value = float(margin_summary.get("accountValue", 0))
            total_margin_used = float(margin_summary.get("totalMarginUsed", 0))
            
            result = {
                "status": "success",
                "total_equity": account_value,
                "available_balance": account_value - total_margin_used,
                "margin_used": total_margin_used
            }
            
            # Update Cache
            self._balance_cache = {"time": now, "data": result}
            return result
            
        except Exception as e:
            print(f"Error fetching account balance: {e}")
            # If API fails, try to return stale cache if available
            if self._balance_cache["data"]:
                print("⚠️ Returning stale balance cache due to API error")
                return self._balance_cache["data"]
                
            return {
                "status": "error",
                "message": str(e),
                "total_equity": 0,
                "available_balance": 0,
                "margin_used": 0
            }
    
    def get_account_value(self):
        """Get total account value in USDC for gamification"""
        balance = self.get_account_balance()
        return balance.get("total_equity", 0)

    def get_positions(self):
        """Fetch open positions from Hyperliquid"""
        if not config.HL_ACCOUNT_ADDRESS:
            return []
        
        try:
            user_state = self.info.user_state(config.HL_ACCOUNT_ADDRESS)
            if not user_state:
                return []
            
            # assetPositions contains list of { position: {...}, type: 'oneWay' }
            raw_positions = user_state.get("assetPositions", [])
            positions = []
            
            for item in raw_positions:
                pos = item.get("position", {})
                if not pos: continue
                
                # Check for open interest (szi > 0 or < 0)
                size = float(pos.get("szi", 0.0))
                if size == 0: continue
                
                positions.append({
                    "symbol": pos.get("coin", "UNKNOWN"),
                    "side": "BUY" if size > 0 else "SELL",
                    "size": abs(size),
                    "entry_price": float(pos.get("entryPx", 0.0)),
                    "pnl": float(pos.get("unrealizedPnl", 0.0)),
                    "leverage": float(pos.get("leverage", {}).get("value", 1.0))
                })
                
            return positions
        except Exception as e:
            print(f"Error fetching positions: {e}")
            return []

    @lightweight_operation
    def cancel_all_orders(self, symbol: str):
        """Cancel all open orders for a symbol"""
        if not self.exchange or not config.HL_ACCOUNT_ADDRESS:
            return
            
        try:
            open_orders = self.info.open_orders(config.HL_ACCOUNT_ADDRESS)
            orders_to_cancel = [o for o in open_orders if o["coin"] == symbol]
            
            if not orders_to_cancel:
                return
                
            print(f"🧹 Cancelling {len(orders_to_cancel)} open orders for {symbol}...")
            for order in orders_to_cancel:
                self.exchange.cancel(symbol, order["oid"])
                
        except Exception as e:
            print(f"⚠️ Error cancelling orders: {e}")

    @critical_operation
    def close_position(self, symbol: str):
        """
        Close an open position on Hyperliquid with robust retry logic.
        
        This method has the highest priority for retry logic as failing to close
        a position during volatile markets can result in significant losses.
        
        The @critical_operation decorator provides:
        - 5 retry attempts with exponential backoff
        - Special handling for 429 rate limit errors
        - Automatic delay increase: 2s → 4s → 8s → 16s → 32s
        
        Args:
            symbol: Trading pair symbol (e.g., "BTC")
        
        Returns:
            dict: {"status": "success"|"error", "message": str, "closed_size": float}
        
        Raises:
            Exception: After max retries exhausted (will be caught by decorator)
        """
        if not self.exchange:
            raise Exception("No private key configured")
        
        # Step 1: Cancel all pending orders (TP/SL)
        print(f"🧹 Cancelling pending orders for {symbol}...")
        try:
            self.cancel_all_orders(symbol)
        except Exception as e:
            print(f"⚠️ Failed to cancel orders (continuing anyway): {e}")
        
        # Step 2: Get current position
        positions = self.get_positions()
        position = next((p for p in positions if p["symbol"] == symbol), None)
        
        if not position:
            raise Exception(f"No position found for {symbol}")
        
        size = position["size"]
        side = position["side"]
        is_buy = (side == "SELL")  # Close SHORT with BUY
        
        # Step 3: Calculate precise quantity
        sz_decimals, _ = self._get_precision(symbol)
        quantity = float(f"{size:.{sz_decimals}f}")
        
        if quantity <= 0:
            raise Exception("Position size too small to close")
        
        print(f"🔴 CLOSING {side} position: {quantity} {symbol}")
        
        # Step 4: Execute market close order
        # This will raise exception if it fails, triggering decorator retry
        result = self.exchange.market_open(symbol, is_buy, quantity)
        print(f"✅ Close order submitted: {symbol} {quantity}")
        
        # Step 5: Verify closure
        time.sleep(2)  # Wait for fill
        new_positions = self.get_positions()
        remaining = next((p for p in new_positions if p["symbol"] == symbol), None)
        
        if remaining and remaining["size"] > quantity * 0.1:
            # Significant position remains - this is an error
            raise Exception(f"Position not fully closed, {remaining['size']} remaining")
        elif remaining:
            # Just dust remaining - acceptable
            print(f"ℹ️ Close incomplete: Dust remaining ({remaining['size']})")
        
        print(f"✅ Position closed successfully: {symbol}")
        return {"status": "success", "closed_size": size, "result": result}

    def get_current_price(self, symbol: str) -> float:
        """
        Get current market price from WebSocket cache.
        
        This method prioritizes WebSocket price feeds to minimize REST API calls
        and reduce rate limit exposure. Falls back to REST API if WebSocket is
        unavailable or price is stale.
        
        Args:
            symbol: Trading pair symbol (e.g., "BTC")
        
        Returns:
            Current price or 0.0 if unavailable
        
        Example:
            >>> price = service.get_current_price("BTC")
            >>> if price > 0:
            ...     print(f"BTC: ${price}")
        """
        # Try WebSocket cache first (preferred method)
        if self.ws_manager is not None:
            price = self.ws_manager.get_price(symbol)
            if price is not None:
                return price
            else:
                print(f"⚠️ WebSocket price unavailable for {symbol}, falling back to REST")
        
        # Fallback to REST API (with warning)
        try:
            df = self.get_candles(symbol, "1m", 1)
            if not df.empty:
                return float(df['close'].iloc[-1])
        except Exception as e:
            print(f"❌ Error getting price via REST: {e}")
        
        return 0.0

    def get_trade_history(self, limit: int = 100):
        """
        Récupère l'historique des trades depuis Hyperliquid
        
        Returns:
            List of trades with: symbol, side, entry, exit, pnl, timestamp
        """
        if not config.HL_ACCOUNT_ADDRESS:
            return []
        
        try:
            # Utiliser l'API Hyperliquid pour récupérer les fills (trades exécutés)
            user_fills = self.info.user_fills(config.HL_ACCOUNT_ADDRESS)
            
            if not user_fills:
                return []
            
            # Parser et formater les trades
            trades = []
            
            # Grouper les fills par position (entry + exit)
            # Pour simplifier, on prend chaque fill comme un trade individuel
            for fill in user_fills[:limit]:
                try:
                    coin = fill.get("coin", "")
                    side = "BUY" if fill.get("side") == "B" else "SELL"
                    price = float(fill.get("px", 0))
                    size = float(fill.get("sz", 0))
                    timestamp = fill.get("time", 0)
                    
                    # Calculer PnL si disponible
                    closed_pnl = float(fill.get("closedPnl", 0))
                    
                    # Formater timestamp
                    if timestamp:
                        timestamp_str = pd.Timestamp(timestamp, unit='ms').isoformat()
                    else:
                        timestamp_str = pd.Timestamp.now().isoformat()
                    
                    trade_data = {
                        "id": fill.get("oid", f"{coin}_{timestamp}"),
                        "symbol": coin,
                        "side": side,
                        "entry_price": price,
                        "exit_price": price,  # Pour un fill unique, entry = exit
                        "size": size,
                        "pnl": closed_pnl,
                        "pnl_percent": (closed_pnl / (price * size) * 100) if (price * size) > 0 else 0,
                        "entry_time": timestamp_str,
                        "exit_time": timestamp_str,
                        "timestamp": timestamp_str,
                        "fee": float(fill.get("fee", 0)),
                        "strategy": "Unknown",  # Non disponible depuis Hyperliquid
                        "exit_reason": "Hyperliquid",
                        "source": "hyperliquid",
                        "leverage": 1  # Non disponible, default
                    }
                    
                    trades.append(trade_data)
                    
                except Exception as e:
                    print(f"Error parsing fill: {e}")
                    continue
            
            return trades
            
        except Exception as e:
            print(f"Error fetching trade history from Hyperliquid: {e}")
            import traceback
            traceback.print_exc()
            return []

    def get_market_data(self, symbol: str):
        """
        Get market data for a symbol (price, volume, etc.)
        """
        if not symbol or not self.info:
            return {}
            
        try:
            # Get all meta and context
            meta_and_context = self.info.meta_and_asset_ctxs()
            
            # Find universe index for symbol
            universe = meta_and_context[0]["universe"]
            symbol_index = next((i for i, asset in enumerate(universe) if asset["name"] == symbol), None)
            
            if symbol_index is None:
                return {}
                
            # Get context for this symbol
            ctx = meta_and_context[1][symbol_index]
            
            return {
                "price": float(ctx.get("markPx", 0)),
                "volume_24h": float(ctx.get("dayNtlVlm", 0)),
                "funding_rate": float(ctx.get("funding", 0)),
                "open_interest": float(ctx.get("openInterest", 0)) * float(ctx.get("markPx", 0)), # Convert to USD
                "oracle_price": float(ctx.get("oraclePx", 0)),
                "prev_day_price": float(ctx.get("prevDayPx", 0))
            }
        except Exception as e:
            print(f"Error fetching market data for {symbol}: {e}")
            return {}

hyperliquid_service = HyperliquidService()
