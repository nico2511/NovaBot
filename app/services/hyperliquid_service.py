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
    # Market order slippage simulation (5%)
    MARKET_SLIPPAGE = 0.05
    
    def __init__(self):
        # Initialize Info API (WebSocket will be managed separately)
        # Initialize Info API with robust retry mechanism for 429s (Startup Protection)
        max_retries = 5
        base_wait = 2
        
        for attempt in range(max_retries):
            try:
                self.info = Info(base_url=MAINNET_API_URL, skip_ws=True)
                break
            except Exception as e:
                # Check for Rate Limit (429)
                error_msg = str(e)
                if "429" in error_msg or "Too Many Requests" in error_msg:
                    wait_time = base_wait * (2 ** attempt) # Exponential backoff: 2s, 4s, 8s, 16s, 32s
                    print(f"⚠️ [HyperliquidService] Rate Limit (429) during init. Retrying in {wait_time}s (Attempt {attempt+1}/{max_retries})...")
                    time.sleep(wait_time)
                else:
                    # Non-retriable error
                    print(f"❌ [HyperliquidService] Critical Init Error: {e}")
                    raise e
        else:
             print("❌ [HyperliquidService] Failed to initialize Info API after max retries due to Rate Limits.")
             # Raise to crash process but hopefully PM2 restart delay helps if we waited long enough
             raise Exception("Rate Limit Exceeded during Startup")
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
                self.log(f"⚠️ [WARNING] Failed to initialize Hyperliquid Exchange: {e}")
                self.exchange = None
        
        # Initialize metadata cache
        self._meta_cache = None
        
        # Balance cache to prevent 429s from frontend polling
        self._balance_cache = {"time": 0, "data": None}
        self._cache_ttl = 10 # 10 seconds TTL
    
        # Log callback for UI integration
        self.log_callback = None
    
    def set_log_callback(self, callback_func):
        """
        Set callback function for logging.
        
        Args:
            callback_func: Function that takes (message: str, level: str = "INFO")
        
        Example:
            >>> def bot_log(msg, level="INFO"):
            ...     self.log(f"[{level}] {msg}")
            >>> service.set_log_callback(bot_log)
        """
        self.log_callback = callback_func
    
    def log(self, message: str, level: str = "INFO"):
        """
        Internal logging method.
        
        Routes to callback if set, otherwise prints to console.
        """
        if self.log_callback:
            self.log_callback(message, level)
        else:
            print(f"[{level}] {message}")
    
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
            self.log("⚠️ WebSocket manager already initialized")
            return
        
        try:
            # Create a logger bridge that routes WebSocket logs to our log() method
            class LogBridge:
                """Simple logger bridge for WebSocket integration"""
                def __init__(self, service):
                    self.service = service
                
                def info(self, msg, *args):
                    self.service.log(msg, "INFO")
                
                def error(self, msg, *args):
                    self.service.log(msg, "ERROR")
                
                def warning(self, msg, *args):
                    self.service.log(msg, "WARNING")
                
                def debug(self, msg, *args):
                    self.service.log(msg, "DEBUG")
            
            # Pass LogBridge instance directly to WebSocket
            self.ws_manager = WebSocketPriceManager(symbols, logger=LogBridge(self))
            self.ws_manager.start()
            self.log(f"✅ WebSocket price feeds started for: {', '.join(symbols)}")
        except Exception as e:
            self.log(f"❌ Failed to start WebSocket manager: {e}")
            self.log("⚠️ Falling back to REST API for price feeds")
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


    def get_candles(self, symbol: str, interval: str = "15m", limit: int = 200) -> pd.DataFrame:
        """
        Fetch OHLCV candles from Hyperliquid with robust data handling.
        
        Improvements:
        - 1.5x time buffer to handle gaps (maintenance/low liquidity)
        - Explicit chronological sorting
        - Type coercion for OHLCV columns
        - Duplicate removal
        - UTC timezone enforcement
        
        Args:
            symbol: Trading pair (e.g., "BTC")
            interval: Candle interval ("1m", "15m", "1h", "1d")
            limit: Number of candles to fetch
            
        Returns:
            DataFrame with OHLCV data, chronologically sorted
        """
        try:
            # Calculate end time (UTC)
            end_time = int(pd.Timestamp.now(tz='UTC').timestamp() * 1000)
            
            # Parse interval and calculate start time with 1.5x buffer
            interval_seconds = self._parse_interval_to_seconds(interval)
            time_range = limit * interval_seconds * 1000
            start_time = end_time - int(time_range * 1.5)  # 1.5x buffer for gaps
            
            # RETRY LOGIC for Rate Limits (429)
            max_retries = 3
            retry_delay = 1  # Start with 1 second
            raw_candles = None
            
            for attempt in range(max_retries):
                try:
                    # Fetch candles from Hyperliquid
                    raw_candles = self.info.candles_snapshot(symbol, interval, start_time, end_time)
                    break  # Success, exit retry loop
                    
                except Exception as e:
                    # Check if it's a rate limit error (429)
                    error_code = None
                    if hasattr(e, 'args') and len(e.args) > 0:
                        error_code = e.args[0]
                    
                    if error_code == 429:
                        if attempt < max_retries - 1:
                            wait_time = retry_delay * (2 ** attempt)  # Exponential backoff: 1s, 2s, 4s
                            self.log(f"⚠️ Rate limit hit (429), retrying in {wait_time}s (attempt {attempt + 1}/{max_retries})")
                            time.sleep(wait_time)
                            continue
                        else:
                            self.log(f"❌ Rate limit exceeded after {max_retries} attempts")
                            raise
                    else:
                        # Not a rate limit error, re-raise immediately
                        raise
            
            if not raw_candles:
                self.log(f"⚠️ No candles returned for {symbol} {interval}")
                return pd.DataFrame()
            
            # Convert to DataFrame
            df = pd.DataFrame(raw_candles)
            
            if df.empty:
                return df
            
            # Convert timestamp to datetime with UTC timezone
            df['time'] = pd.to_datetime(df['t'], unit='ms', utc=True)
            df.set_index('time', inplace=True)
            
            # Type coercion for OHLCV columns (handle invalid data gracefully)
            for col in ['o', 'h', 'l', 'c', 'v']:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce')
            
            # Remove rows with NaN in critical columns
            df.dropna(subset=['o', 'h', 'l', 'c'], inplace=True)
            
            # Remove duplicate timestamps (keep last)
            df = df[~df.index.duplicated(keep='last')]
            
            # Sort chronologically (CRITICAL for indicator calculations)
            df.sort_index(inplace=True)
            
            # Standardize column names
            df.rename(columns={
                'o': 'open',
                'h': 'high',
                'l': 'low',
                'c': 'close',
                'v': 'volume'
            }, inplace=True)
            
            # Trim to requested limit (after buffer)
            if len(df) > limit:
                df = df.tail(limit)
            
            return df
            
        except Exception as e:
            self.log(f"Error fetching candles for {symbol} {interval}: {e}")
            import traceback
            traceback.print_exc()
            return pd.DataFrame()


    
    def _fetch_metadata(self):
        """Fetch and cache exchange metadata for precision (Persistent Cache)"""
        import json
        import os
        CACHE_FILE = "data/cache/token_meta_cache.json"

        # 1. Check in-memory cache
        if hasattr(self, "_meta_cache") and self._meta_cache:
            return self._meta_cache
        
        # 2. Try to load from disk IF FRESH (< 24h)
        if os.path.exists(CACHE_FILE):
            try:
                # Check age (24h TTL)
                last_modified = os.path.getmtime(CACHE_FILE)
                if time.time() - last_modified < 86400: # 86400s = 24h
                    with open(CACHE_FILE, "r") as f:
                        self._meta_cache = json.load(f)
                        self.log("✅ Metadata loaded from disk cache (Fresh).")
                else:
                    self.log("⚠️ Metadata cache expired (>24h). Will refresh from API.")
            except Exception as e:
                self.log(f"⚠️ Failed to load metadata cache from disk: {e}")

        # 3. If still needed, fetch from API (and save)
        if not self._meta_cache:
            try:
                self.log("🌐 Fetching metadata from Hyperliquid API...")
                self._meta_cache = self.info.meta()
                
                # Save to disk
                try:
                    with open(CACHE_FILE, "w") as f:
                        json.dump(self._meta_cache, f)
                except Exception as e:
                    self.log(f"⚠️ Warning: Could not save metadata cache: {e}")
                    
            except Exception as e:
                self.log(f"⚠️ Failed to fetch metadata from API: {e}")
                # Fallback to defaults will happen in _get_precision
                return None
        
        return self._meta_cache

    def _infer_price_decimals(self, current_price: float) -> int:
        """
        Intelligently infer price decimals based on current price magnitude.
        Maintains ~4-5 significant figures for precision across all price ranges.
        
        Examples:
            BTC (95000) -> 0 decimals (95000)
            ETH (3500) -> 1 decimal (3500.5)
            SOL (150) -> 2 decimals (150.25)
            HYPE (25) -> 3 decimals (25.123)
            WIF (0.5) -> 4 decimals (0.5123)
            FARTCOIN (0.30) -> 5 decimals (0.30591)
        """
        if current_price >= 1000:
            return 0
        elif current_price >= 100:
            return 1
        elif current_price >= 10:
            return 2
        elif current_price >= 1:
            return 3
        elif current_price >= 0.1:
            return 4
        elif current_price >= 0.01:
            return 5
        else:
            return 6  # Micro-caps

    def _get_precision(self, symbol: str):
        """Get precision for size and price from metadata + dynamic inference"""
        meta = self._fetch_metadata()
        
        # 1. Try to find in Universe for szDecimals
        if meta and "universe" in meta:
            for asset in meta["universe"]:
                if asset["name"] == symbol:
                    sz_decimals = asset["szDecimals"]
                    
                    # Get current price for dynamic precision inference
                    try:
                        current_price = self.get_current_price(symbol)
                        if current_price > 0:
                            price_decimals = self._infer_price_decimals(current_price)
                        else:
                            price_decimals = 4  # Safe fallback
                    except:
                        price_decimals = 4  # Safe fallback if price fetch fails
                    
                    return sz_decimals, price_decimals
        
        # 2. Fallback Map for Size Decimals (if metadata lookup fails)
        FALLBACK_SZ = {"BTC": 5, "ETH": 4, "SOL": 2, "DOGE": 0, "PEPE": 0, "WIF": 0, "HYPE": 1, "FARTCOIN": 1}
        self.log(f"⚠️ Metadata lookup failed for {symbol}. Using fallback precision.")
        return FALLBACK_SZ.get(symbol, 2), 4  # Conservative default 

    @standard_operation
    def _update_market_context_cache(self):
        """
        Fetch and cache BOTH Funding and OI for all symbols in one hit.
        Uses the efficient 'meta_and_asset_ctxs' endpoint.
        """
        now = time.time()
        
        # Initialize cache if needed
        if not hasattr(self, "_market_context_cache"):
            self._market_context_cache = {"time": 0, "funding": {}, "oi": {}}
            
        # 30s TTL
        if now - self._market_context_cache["time"] < 30:
            return
            
        try:
            # Atomic fetch for ALL perpetual symbols
            meta, asset_ctxs = self.info.meta_and_asset_ctxs()
            universe = meta.get("universe", [])
            
            new_funding = {}
            new_oi = {}
            
            for idx, asset in enumerate(universe):
                symbol = asset["name"]
                if idx < len(asset_ctxs):
                    ctx = asset_ctxs[idx]
                    
                    # 1. Funding (Hourly)
                    new_funding[symbol] = float(ctx.get("funding", 0.0))
                    
                    # 2. Open Interest (USD)
                    # OI = openInterest (contracts) * oraclePx (price)
                    oi_contracts = float(ctx.get("openInterest", 0))
                    oracle_px = float(ctx.get("oraclePx", 0))
                    new_oi[symbol] = oi_contracts * oracle_px
                    
            # Atomic Update
            self._market_context_cache["funding"] = new_funding
            self._market_context_cache["oi"] = new_oi
            self._market_context_cache["time"] = now
            # self.log(f"✅ Market Context Cache Updated ({len(universe)} assets)")
            
        except Exception as e:
            self.log(f"⚠️ Failed to update market context cache: {e}")

    @standard_operation
    def get_open_interest(self, symbol: str) -> float:
        """Fetch Open Interest (OI) in USD for a symbol (cached 60s)."""
        symbol = self.get_canonical_symbol(symbol)
        self._update_market_context_cache()
        return self._market_context_cache.get("oi", {}).get(symbol, 0.0)

    @lightweight_operation
    def get_funding_rate(self, symbol: str) -> float:
        """
        Get current funding rate for a symbol (cached 60s).
        Returns funding rate as raw value (e.g. 0.0001 = 0.01%).
        """
        symbol = self.get_canonical_symbol(symbol)
        self._update_market_context_cache()
        return self._market_context_cache.get("funding", {}).get(symbol, 0.0)

    @standard_operation
    def get_open_orders(self, symbol: str = None) -> list:
        """Get open orders (including Triggers), optionally filtered by symbol"""
        try:
            # Use frontend_open_orders to get everything (triggers, SL/TP)
            # Standard open_orders only returns book orders
            orders = self.info.frontend_open_orders(config.HL_ACCOUNT_ADDRESS)
            
            if symbol:
                # Canonicalize symbol
                symbol = self.get_canonical_symbol(symbol)
                return [o for o in orders if o["coin"] == symbol]
            return orders
        except Exception as e:
            self.log(f"⚠️ Failed to fetch open orders: {e}")
            return []

    @standard_operation
    def _place_protection_orders(self, symbol: str, is_buy: bool, quantity: float, sl_price: float = None, tp_price: float = None):
        """Place Stop Loss and Take Profit orders on exchange (Hard Stops)"""
        try:
            sz_decimals, price_decimals = self._get_precision(symbol)
            
            # SL/TP logic: 
            # If opened LONG (is_buy=True) -> SL/TP are SELL orders (is_buy=False)
            # If opened SHORT (is_buy=False) -> SL/TP are BUY orders (is_buy=True)
            close_is_buy = not is_buy

            # Round quantity carefully to avoid precision errors rejection
            quantity = float(f"{quantity:.{sz_decimals}f}")
            
            orders = []
            
            if sl_price:
                sl_price = float(f"{sl_price:.{price_decimals}f}")
                # For Market Trigger, limit_px must be aggressive to ensure fill
                sl_limit_px = sl_price * 1.05 if close_is_buy else sl_price * 0.95
                sl_limit_px = float(f"{sl_limit_px:.{price_decimals}f}")
                
                self.log(f"🛡️ PLACING HARD STOP LOSS for {symbol} @ {sl_price} (sz={quantity}, lim={sl_limit_px})")
                orders.append({
                    "coin": symbol,
                    "is_buy": close_is_buy,
                    "sz": quantity,
                    "limit_px": sl_limit_px,
                    "order_type": {"trigger": {"triggerPx": sl_price, "isMarket": True, "tpsl": "sl"}},
                    "reduce_only": True
                })
                
            if tp_price:
                tp_price = float(f"{tp_price:.{price_decimals}f}")
                # For TP, logic is same (Market Trigger needs fill)
                tp_limit_px = tp_price * 1.05 if close_is_buy else tp_price * 0.95
                tp_limit_px = float(f"{tp_limit_px:.{price_decimals}f}")
                
                self.log(f"🎯 PLACING HARD TAKE PROFIT for {symbol} @ {tp_price} (sz={quantity}, lim={tp_limit_px})")
                orders.append({
                    "coin": symbol,
                    "is_buy": close_is_buy,
                    "sz": quantity,
                    "limit_px": tp_limit_px,
                    "order_type": {"trigger": {"triggerPx": tp_price, "isMarket": True, "tpsl": "tp"}},
                    "reduce_only": True
                })
            
            if orders:
                # Place orders sequentially to ensure robust error handling per order
                self.log(f"🚀 Placing {len(orders)} protection orders sequentially...")
                total_success = 0
                for o in orders:
                     try:
                        tpsl_type = o['order_type']['trigger']['tpsl'].upper()
                        self.log(f"   👉 Sending {tpsl_type} Trigger Order for {symbol} @ {o['order_type']['trigger']['triggerPx']}...")
                        resp = self.exchange.order(o["coin"], o["is_buy"], o["sz"], o["limit_px"], o["order_type"], o["reduce_only"])
                        
                        # DEEP RESPONSE VALIDATION (Ported from execute_order)
                        success = False
                        error_reason = "Unknown Error"
                        
                        if isinstance(resp, dict) and resp.get("status") == "ok":
                            response_data = resp.get("response", {})
                            data_inner = response_data.get("data", {})
                            statuses = data_inner.get("statuses", [])
                            
                            if not statuses:
                                # Sometimes response might be empty list if nothing happened? But usually contains status.
                                success = True 
                            else:
                                # Check the first status (since we send 1 by 1 here)
                                status = statuses[0]
                                if isinstance(status, dict) and status.get("error"):
                                    error_reason = status["error"]
                                    success = False
                                else:
                                    success = True
                        else:
                            error_reason = f"API Status: {resp.get('status') if isinstance(resp, dict) else resp}"
                            
                        if success:
                            self.log(f"   ✅ {tpsl_type} Order CONFIRMED by Exchange.")
                            total_success += 1
                        else:
                            self.log(f"   ❌ {tpsl_type} Order REJECTED: {error_reason}", "ERROR")
                            
                     except Exception as e_ord:
                        self.log(f"   ❌ {tpsl_type} Order Failed Exception: {e_ord}", "ERROR")

                return {"status": "success" if total_success > 0 else "error", "message": f"Placed {total_success}/{len(orders)} orders"}
                
        except Exception as e:
            self.log(f"⚠️ Failed to place protection orders: {e}", "ERROR")
            return {"status": "error", "message": str(e)}

    def get_canonical_symbol(self, symbol: str) -> str:
        """
        Resolve symbol to its canonical Hyperliquid name.
        Handles aliases like PEPE -> kPEPE, BONK -> kBONK.
        """
        meta = self._fetch_metadata()
        if not meta:
            return symbol
            
        universe = [a["name"] for a in meta.get("universe", [])]
        
        # 1. Exact Match (Prioritize user input case: e.g. "kPEPE")
        if symbol in universe:
            return symbol
            
        # 2. Uppercase Match (e.g. "pepe" -> "PEPE")
        upper_symbol = symbol.upper()
        if upper_symbol in universe:
            return upper_symbol
            
        # 3. Try adding 'k' prefix to Uppercase (e.g. "PEPE" -> "kPEPE", "pepe" -> "kPEPE")
        k_symbol = f"k{upper_symbol}"
        if k_symbol in universe:
            self.log(f"ℹ️ Auto-resolving {symbol} -> {k_symbol}")
            return k_symbol
            
        return symbol

    def execute_order(self, symbol: str, is_buy: bool, quantity: float, price: float = None, sl_price: float = None, tp_price: float = None):
        """
        Execute an order on Hyperliquid.
        If SL/TP are provided, uses `bulk_orders` with 'normalTpsl' grouping for atomic execution.
        """
        if not self.exchange:
            return {"status": "error", "message": "No private key configured"}
        
        import time
        
        # NORMALIZATION
        symbol = self.get_canonical_symbol(symbol)
        
        # PRECISION & ROUNDING (Use dynamic metadata)
        sz_decimals, price_decimals = self._get_precision(symbol)
        
        # Round quantity strictly
        if sz_decimals == 0:
            quantity = int(quantity) # Force int if decimals is 0
        else:
            quantity = round(quantity, sz_decimals)
        
        # Check for zero quantity after rounding
        if quantity <= 0:
            return {"status": "error", "message": "Quantity rounded to zero"}
            
        self.log(f"📏 Rounded Order Size: {quantity} {symbol} (sz_decimals={sz_decimals})")
        
        # RETRY CONFIG
        max_retries = 3
        retry_delay = 1
        
        for attempt in range(max_retries):
            try:
                # CASE 1: ATOMIC ENTRY + SL/TP (Recommended)
                if sl_price or tp_price:
                    self.log(f"🚀 SUBMITTING ATOMIC ORDER (Entry + SL/TP) for {symbol} (Attempt {attempt + 1})")
                    
                    orders = []
                    
                    # 1. ENTRY ORDER
                    entry_order = {
                        "coin": symbol,
                        "is_buy": is_buy,
                        "sz": quantity,
                        "limit_px": price if price else float(f"{self.get_current_price(symbol):.{price_decimals}f}"), # Limit px required even for market?
                        # For Market, usually we pass a safe limit offset, but 'limit' type means Limit. 
                        # To do Market Entry, we use "limit": {"tif": "Ioc"} or similar? 
                        # Wait, basic_tpsl.py uses "limit": {"tif": "Gtc"} for entry. It doesn't show Market Entry with SL/TP.
                        # SDK `market_open` enables market. 
                        # For bulk, we need explicit type.
                        # If price is None, we want MARKET.
                        # Using a very aggressive limit price simulates Market.
                        "order_type": {"limit": {"tif": "Gtc"}}, 
                        "reduce_only": False
                    }
                    
                    # Adjust Entry Price for Market simulation if needed
                    current_px = self.get_current_price(symbol)
                    if not price:
                        # Aggressive crossing: Buy @ +5%, Sell @ -5%
                        simulated_limit_px = current_px * (1 + self.MARKET_SLIPPAGE) if is_buy else current_px * (1 - self.MARKET_SLIPPAGE)
                        entry_order["limit_px"] = float(f"{simulated_limit_px:.{price_decimals}f}")
                    else:
                        entry_order["limit_px"] = float(f"{price:.{price_decimals}f}")

                    orders.append(entry_order)

                    # 2. SL/TP ORDERS
                    close_is_buy = not is_buy
                    
                    if sl_price:
                        sl_px_fmt = float(f"{sl_price:.{price_decimals}f}")
                        orders.append({
                            "coin": symbol,
                            "is_buy": close_is_buy,
                            "sz": quantity,
                            "limit_px": sl_px_fmt,
                            "order_type": {"trigger": {"triggerPx": sl_px_fmt, "isMarket": True, "tpsl": "sl"}},
                            "reduce_only": True
                        })
                        
                    if tp_price:
                        tp_px_fmt = float(f"{tp_price:.{price_decimals}f}")
                        orders.append({
                            "coin": symbol,
                            "is_buy": close_is_buy,
                            "sz": quantity,
                            "limit_px": tp_px_fmt,
                            "order_type": {"trigger": {"triggerPx": tp_px_fmt, "isMarket": True, "tpsl": "tp"}},
                            "reduce_only": True
                        })
                    
                    # EXECUTE BULK
                    result = self.exchange.bulk_orders(orders, grouping="normalTpsl")
                    
                # CASE 2: SIMPLE ENTRY (No SL/TP provided)
                else:
                    if price:
                         # LIMIT
                         limit_px = float(f"{price:.{price_decimals}f}")
                         self.log(f"🚀 SUBMITTING LIMIT {'BUY' if is_buy else 'SELL'} {quantity} {symbol} @ {limit_px}")
                         result = self.exchange.order(symbol, is_buy, quantity, limit_px, {"limit": {"tif": "Gtc"}})
                    else:
                         # MARKET
                         self.log(f"🚀 SUBMITTING MARKET {'BUY' if is_buy else 'SELL'} {quantity} {symbol}")
                         result = self.exchange.market_open(symbol, is_buy, quantity)

                # VERIFICATION LOGIC (Shared)
                self.log(f"✅ Exec Result: {result}")
                
                # CRITICAL FIX: Handle case where SDK returns a string (error message) instead of dict
                if not isinstance(result, dict):
                    self.log(f"❌ API returned non-dict result: {result}")
                    if attempt < max_retries - 1:
                        time.sleep(retry_delay)
                        continue
                    return {"status": "error", "message": f"API Error: {str(result)}"}

                if result.get("status") == "ok":
                    response = result.get("response", {})
                    data = response.get("data", {})
                    statuses = data.get("statuses", [])
                    
                    # CRITICAL FIX: Parse statuses safely (can be dict or string)
                    # Hyperliquid returns strings like 'waitingForTrigger' for SL/TP
                    errors = []
                    filled_orders = []
                    
                    for status in statuses:
                        if isinstance(status, dict):
                            # Dict status (filled, error, etc.)
                            if status.get("error"):
                                errors.append(status["error"])
                            elif status.get("filled"):
                                filled_orders.append(status["filled"])
                        elif isinstance(status, str):
                            # String status ('waitingForTrigger', etc.) - this is OK
                            pass
                        else:
                            self.log(f"⚠️ Unknown status type: {type(status)} = {status}")
                    
                    # Check for errors
                    if errors:
                        self.log(f"❌ Order Rejected: {errors}")
                        if attempt < max_retries - 1:
                            time.sleep(retry_delay)
                            continue
                        return {"status": "error", "message": f"Rejected: {errors}"}
                    
                    # Check if entry was filled
                    if filled_orders:
                        self.log(f"✅ Order Filled: {filled_orders[0]}")
                        
                    # Success
                    return {"status": "success", "result": result}
                    
                else:
                     self.log(f"❌ API Error: {result}")
                     if attempt < max_retries - 1:
                         time.sleep(retry_delay)
                         continue
            
            except Exception as e:
                error_msg = str(e)
                self.log(f"❌ Exception in execute_order (Attempt {attempt+1}): {error_msg}")
                
                # Smart Backoff for Rate Limits
                wait_time = retry_delay
                if "429" in error_msg or "Too Many Requests" in error_msg:
                    self.log("🚫 Rate Limit Hit (429). Cooling down for 10s...")
                    wait_time = 10
                
                if attempt < max_retries - 1:
                     time.sleep(wait_time)
                     continue
                return {"status": "error", "message": error_msg}

        return {"status": "error", "message": "Max retries exceeded"}
    
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
        
        self.log(f"🛡️ Setting SL/TP for {symbol}: SL={sl_price:.2f}, TP={tp_price:.2f}")
        
        # Use existing method (which also has retry logic via decorator)
        self._place_protection_orders(symbol, is_long, quantity, sl_price, tp_price)
        
        return {
            "status": "success",
            "sl_price": sl_price,
            "tp_price": tp_price
        }

    @standard_operation
    def sync_sl_tp(self, symbol: str, is_buy: bool, quantity: float, sl_price: float, tp_price: float):
        """
        Sync SL/TP orders for an existing position.
        First cancels ALL open orders for the symbol, then places new SL/TP.
        """
        if not self.exchange:
            return {"status": "error", "message": "No private key configured"}
            
        self.log(f"🔄 SYNCING SL/TP for {symbol} (SL: {sl_price}, TP: {tp_price})...")
        try:
            # 1. Cancel existing orders to avoid duplicates/conflicts
            self.cancel_all_orders(symbol)
            
            # 2. Place new protection orders
            if sl_price or tp_price:
                self._place_protection_orders(symbol, is_buy, quantity, sl_price, tp_price)
                
            return {"status": "success"}
        except Exception as e:
            self.log(f"❌ Failed to sync SL/TP: {e}")
            return {"status": "error", "message": str(e)}

    def update_leverage(self, symbol: str, leverage: int, is_cross: bool = True):
        """Update leverage and margin type (Cross/Isolated) for a symbol"""
        if not self.exchange:
            return {"status": "error", "message": "No private key configured"}
            
        try:
            self.log(f"⚙️ Updating leverage for {symbol}: {leverage}x (Cross: {is_cross})")
            # Set leverage
            self.exchange.update_leverage(leverage, symbol, is_cross)
            return {"status": "success", "leverage": leverage, "is_cross": is_cross}
        except Exception as e:
            self.log(f"❌ Failed to update leverage: {e}")
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
            self.log(f"Error fetching account balance: {e}")
            # If API fails, try to return stale cache if available
            if self._balance_cache["data"]:
                self.log("⚠️ Returning stale balance cache due to API error")
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
            
            # Get user fills to find entry times
            try:
                user_fills = self.info.user_fills(config.HL_ACCOUNT_ADDRESS)
            except:
                user_fills = []
            
            for item in raw_positions:
                pos = item.get("position", {})
                if not pos: continue
                
                # Check for open interest (szi > 0 or < 0)
                size = float(pos.get("szi", 0.0))
                if size == 0: continue
                
                symbol = pos.get("coin", "UNKNOWN")
                is_long = size > 0
                
                # Find entry time from fills (most recent fill that OPENED this position)
                entry_time = None
                if user_fills:
                    # Look for the opening fill that matches current position direction
                    target_dir = "Open Long" if is_long else "Open Short"
                    for fill in user_fills:
                        if fill.get("coin") == symbol and fill.get("dir") == target_dir:
                            # Found the opening fill for this position
                            timestamp_ms = fill.get("time", 0)
                            if timestamp_ms:
                                import pandas as pd
                                entry_time = pd.Timestamp(timestamp_ms, unit='ms').isoformat()
                                break  # Use the most recent opening fill
                
                # Robust leverage parsing
                lev_data = pos.get("leverage", {})
                if isinstance(lev_data, dict):
                    leverage = float(lev_data.get("value", 1.0))
                else:
                    leverage = float(lev_data or 1.0)
                
                positions.append({
                    "symbol": symbol,
                    "side": "BUY" if is_long else "SELL",
                    "size": abs(size),
                    "entry_price": float(pos.get("entryPx", 0.0)),
                    "pnl": float(pos.get("unrealizedPnl", 0.0)),
                    "leverage": leverage,
                    "entry_time": entry_time
                })
                
            return positions
        except Exception as e:
            self.log(f"Error fetching positions: {e}")
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
                
            self.log(f"🧹 Cancelling {len(orders_to_cancel)} open orders for {symbol}...")
            for order in orders_to_cancel:
                self.exchange.cancel(symbol, order["oid"])
                
        except Exception as e:
            self.log(f"⚠️ Error cancelling orders: {e}")

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
        self.log(f"🧹 Cancelling pending orders for {symbol}...")
        try:
            self.cancel_all_orders(symbol)
        except Exception as e:
            self.log(f"⚠️ Failed to cancel orders (continuing anyway): {e}")
        
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
        
        self.log(f"🔴 CLOSING {side} position: {quantity} {symbol}")
        
        # Step 4: Execute market close order
        # This will raise exception if it fails, triggering decorator retry
        result = self.exchange.market_open(symbol, is_buy, quantity)
        self.log(f"✅ Close order submitted: {symbol} {quantity}")
        
        # Step 5: Verify closure
        time.sleep(2)  # Wait for fill
        new_positions = self.get_positions()
        remaining = next((p for p in new_positions if p["symbol"] == symbol), None)
        
        if remaining and remaining["size"] > quantity * 0.1:
            # Significant position remains - this is an error
            raise Exception(f"Position not fully closed, {remaining['size']} remaining")
        elif remaining:
            # Just dust remaining - acceptable
            self.log(f"ℹ️ Close incomplete: Dust remaining ({remaining['size']})")
        
        self.log(f"✅ Position closed successfully: {symbol}")
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
            ...     self.log(f"BTC: ${price}")
        """
        # Try WebSocket cache first (preferred method)
        if self.ws_manager is not None:
            price = self.ws_manager.get_price(symbol)
            if price is not None:
                return price
            else:
                self.log(f"⚠️ WebSocket price unavailable for {symbol}, falling back to REST")
        
        # Fallback to REST API (with warning)
        try:
            df = self.get_candles(symbol, "1m", 1)
            if not df.empty:
                return float(df['close'].iloc[-1])
        except Exception as e:
            self.log(f"❌ Error getting price via REST: {e}")
        
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
            
            # DEBUG: See raw data in console
            print(f"🔎 [HyperliquidService] Raw Fills (first 2): {user_fills[:2]}")
            
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
                    oid = str(fill.get("oid", ""))
                    
                    # Robust PnL Mapping
                    # Hyperliquid sometimes returns 'closedPnl', sometimes it's implied in other structures
                    closed_pnl = fill.get("closedPnl")
                    if closed_pnl is None:
                        closed_pnl = 0.0
                    else:
                        closed_pnl = float(closed_pnl)
                    
                    # Formater timestamp
                    if timestamp:
                        timestamp_str = pd.Timestamp(timestamp, unit='ms').isoformat()
                    else:
                        timestamp_str = pd.Timestamp.now().isoformat()
                    
                    # Unique ID generation: Symbol + Timestamp + OID (to be sure)
                    unique_id = f"{coin}_{timestamp}_{oid}"
                    
                    trade_data = {
                        "id": unique_id,
                        "oid": oid,
                        "symbol": coin,
                        "side": side,
                        "entry_price": price,
                        "exit_price": price,
                        "size": size,
                        "pnl": closed_pnl,
                        "pnl_percent": (closed_pnl / (price * size) * 100) if (price * size) > 0 else 0,
                        "entry_time": timestamp_str,
                        "exit_time": timestamp_str,
                        "timestamp": timestamp_str,
                        "fee": float(fill.get("fee", 0)),
                        "strategy": "Unknown",
                        "exit_reason": "Hyperliquid",
                        "source": "hyperliquid",
                        "leverage": 1
                    }
                    
                    trades.append(trade_data)
                    
                except Exception as e:
                    self.log(f"Error parsing fill: {e}")
                    continue
            
            return trades
            
        except Exception as e:
            self.log(f"Error fetching trade history from Hyperliquid: {e}")
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
            self.log(f"Error fetching market data for {symbol}: {e}")
            return {}

    @standard_operation
    def get_daily_pnl(self):
        """
        Calculate daily PnL using account value snapshot method.
        
        Method:
        1. Save account value at 00:00 UTC (start of day)
        2. Calculate PnL = Current Account Value - Start of Day Value
        
        This captures both realized and unrealized PnL automatically.
        
        Returns:
            float: Total daily PnL in USDC
        """
        import json
        import os
        from datetime import datetime, timezone
        
        if not config.HL_ACCOUNT_ADDRESS:
            return 0.0
            
        try:
            # 1. Start of Day (UTC)
            now_utc = datetime.now(timezone.utc)
            start_of_day = now_utc.replace(hour=0, minute=0, second=0, microsecond=0)
            start_ts_ms = int(start_of_day.timestamp() * 1000)
            
            # 2. Realized PnL (Today's Fills)
            realized_pnl = 0.0
            trades_count = 0
            user_fills = self.info.user_fills(config.HL_ACCOUNT_ADDRESS)
            if user_fills:
                for fill in user_fills:
                    if fill.get("time", 0) >= start_ts_ms:
                        realized_pnl += float(fill.get("closedPnl") or 0.0)
                        trades_count += 1
                    else:
                        break
                        
            # 3. Unrealized PnL
            unrealized_pnl = sum([p.get("pnl", 0) for p in self.get_positions()])
            
            total = realized_pnl + unrealized_pnl
            self.log(f"💰 Daily PnL: ${total:.2f} (Realized: ${realized_pnl:.2f}, Unrealized: ${unrealized_pnl:.2f})")
            return total

            # LEGACY CODE BELOW (Unreachable)
            balance_data = self.get_account_balance()
            current_value = balance_data.get("total_equity", 0.0)
            
            # Get today's date (UTC)
            now_utc = datetime.now(timezone.utc)
            today_str = now_utc.strftime("%Y-%m-%d")
            
            # Load or create snapshot
            snapshot_data = {}
            if os.path.exists(SNAPSHOT_FILE):
                try:
                    with open(SNAPSHOT_FILE, "r") as f:
                        snapshot_data = json.load(f)
                except Exception as e:
                    self.log(f"⚠️ Could not load snapshot file: {e}")
            
            # Check if we need to create today's snapshot
            if today_str not in snapshot_data:
                # New day! Save current value as start of day
                snapshot_data[today_str] = {
                    "start_value": current_value,
                    "timestamp": now_utc.isoformat()
                }
                
                # Clean up old snapshots (keep last 7 days)
                dates = sorted(snapshot_data.keys())
                if len(dates) > 7:
                    for old_date in dates[:-7]:
                        del snapshot_data[old_date]
                
                # Save snapshot
                try:
                    with open(SNAPSHOT_FILE, "w") as f:
                        json.dump(snapshot_data, f, indent=2)
                    self.log(f"📸 Created new daily snapshot: ${current_value:.2f}")
                except Exception as e:
                    self.log(f"⚠️ Could not save snapshot: {e}")
            
            # Calculate daily PnL
            start_value = snapshot_data.get(today_str, {}).get("start_value", current_value)
            daily_pnl = current_value - start_value
            
            self.log(f"💰 Daily PnL: ${daily_pnl:.2f} (Start: ${start_value:.2f}, Current: ${current_value:.2f})")
            return daily_pnl
            
        except Exception as e:
            self.log(f"❌ Error calculating daily PnL: {e}")
            import traceback
            traceback.print_exc()
            return 0.0


# Lazy initialization to prevent blocking during import
_hyperliquid_service_instance = None

def get_hyperliquid_service():
    """Get or create the HyperliquidService singleton instance"""
    global _hyperliquid_service_instance
    if _hyperliquid_service_instance is None:
        _hyperliquid_service_instance = HyperliquidService()
    return _hyperliquid_service_instance

# Backward compatibility: create a property-like object
class _HyperliquidServiceProxy:
    def __getattr__(self, name):
        return getattr(get_hyperliquid_service(), name)

hyperliquid_service = _HyperliquidServiceProxy()
