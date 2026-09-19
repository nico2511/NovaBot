import eth_account
from hyperliquid.info import Info
from hyperliquid.exchange import Exchange
from hyperliquid.utils import types
from app.core.config import config
import pandas as pd
import time
import uuid

from hyperliquid.utils.constants import MAINNET_API_URL, TESTNET_API_URL

# Import retry decorators and WebSocket manager
from app.utils.retry_decorator import (
    critical_operation,
    standard_operation,
    lightweight_operation,
    _is_rate_limit_error,
)
from app.utils.websocket_manager import WebSocketPriceManager
from app.utils.rate_limiter import rate_limiter

class HyperliquidService:
    # Fallback IOC offset when symbol-specific slip cannot be resolved (alts).
    MARKET_SLIPPAGE = 0.015

    @staticmethod
    def _execution_mode() -> str:
        return str(getattr(config, "EXECUTION_MODE", None) or "Live").strip().lower()

    @staticmethod
    def _api_base_url() -> str:
        """REST/WS signing base. Paper/testnet mode never signs mainnet."""
        raw = (getattr(config, "HYPERLIQUID_API_URL", None) or "").strip()
        mode = HyperliquidService._execution_mode()
        if mode in ("paper", "testnet"):
            if "testnet" not in (raw or TESTNET_API_URL).lower():
                return TESTNET_API_URL
            return raw or TESTNET_API_URL
        return raw or MAINNET_API_URL

    @staticmethod
    def _assert_not_master_wallet(key_address: str, account_address: str, allow: bool) -> str | None:
        """Refuse a master-wallet private key unless HL_ALLOW_MASTER_KEY is set.

        Returns a warning string when the override is on; raises RuntimeError otherwise.
        """
        master = (account_address or "").strip()
        key_addr = (key_address or "").strip()
        if not master or not key_addr:
            return None
        if key_addr.lower() != master.lower():
            return None
        msg = (
            "HL_PRIVATE_KEY is the MASTER wallet key (same address as "
            "HL_ACCOUNT_ADDRESS). Use a Hyperliquid API Agent key without "
            "withdraw permissions."
        )
        if not allow:
            raise RuntimeError(
                msg + " Set HL_ALLOW_MASTER_KEY=true to override (not recommended)."
            )
        return msg

    @staticmethod
    def _ws_url_from_rest(rest_url: str) -> str:
        """Map REST origin to Hyperliquid WS path (mainnet or testnet)."""
        u = (rest_url or "").strip().rstrip("/")
        if u.startswith("https://"):
            return "wss://" + u[len("https://") :] + "/ws"
        if u.startswith("http://"):
            return "ws://" + u[len("http://") :] + "/ws"
        return "wss://api.hyperliquid.xyz/ws"

    @staticmethod
    def _sanitize_spot_meta(spot_meta: dict) -> dict:
        """Drop spot pairs whose token indices are missing from the tokens map.

        Hyperliquid spot token indices are sparse (not list positions). Older
        SDKs crash with IndexError; even fixed SDKs KeyError if an index is
        absent. Filtering keeps Info/Exchange init resilient.
        """
        tokens = spot_meta.get("tokens") or []
        token_by_index = {
            int(t["index"]): t for t in tokens if isinstance(t, dict) and "index" in t
        }
        universe = []
        for spot_info in spot_meta.get("universe") or []:
            pair = spot_info.get("tokens") or []
            if len(pair) < 2:
                continue
            base, quote = int(pair[0]), int(pair[1])
            if base in token_by_index and quote in token_by_index:
                universe.append(spot_info)
        return {"tokens": tokens, "universe": universe}

    def _build_info_client(self) -> Info:
        """Create Info with a sanitized spot_meta fallback for sparse indices."""
        base_url = self._api_base_url()
        try:
            return Info(base_url=base_url, skip_ws=True)
        except (IndexError, KeyError) as e:
            print(
                f"⚠️ [HyperliquidService] Info init hit spot meta index issue ({e}). "
                "Retrying with sanitized spot_meta..."
            )
            from hyperliquid.api import API

            raw_spot = API(base_url).post("/info", {"type": "spotMeta"})
            clean_spot = self._sanitize_spot_meta(raw_spot)
            dropped = len(raw_spot.get("universe") or []) - len(clean_spot["universe"])
            if dropped:
                print(f"⚠️ [HyperliquidService] Dropped {dropped} malformed spot pairs from meta")
            return Info(base_url=base_url, skip_ws=True, spot_meta=clean_spot)
    
    def __init__(self):
        # Initialize Info API (WebSocket will be managed separately)
        # Initialize Info API with robust retry mechanism for 429s (Startup Protection)
        max_retries = 5
        base_wait = 2
        
        for attempt in range(max_retries):
            try:
                self.info = self._build_info_client()
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
        self.log_callback = None
        
        # Initialize WebSocket Price Manager (will be started externally)
        self.ws_manager: WebSocketPriceManager = None
        
        if config.HL_PRIVATE_KEY and config.HL_ACCOUNT_ADDRESS:
            try:
                # Sanitize key: ensure no whitespace, handle 0x prefix if needed (eth_account usually handles 0x, but whitespace is fatal)
                sanitized_key = config.HL_PRIVATE_KEY.strip()
                if sanitized_key.startswith("0x"):
                    sanitized_key = sanitized_key[2:]
                    
                account = eth_account.Account.from_key(sanitized_key)
                warn = self._assert_not_master_wallet(
                    account.address,
                    config.HL_ACCOUNT_ADDRESS,
                    bool(getattr(config, "HL_ALLOW_MASTER_KEY", False)),
                )
                if warn:
                    self.log("🚨 " + warn + " Override HL_ALLOW_MASTER_KEY=true is set.", "ERROR")
                base_url = self._api_base_url()
                if self._execution_mode() in ("paper", "testnet"):
                    self.log(
                        f"🧪 EXECUTION_MODE={self._execution_mode()} — Exchange URL {base_url}",
                        "WARNING",
                    )
                self.exchange = Exchange(
                    account,
                    base_url=base_url,
                    account_address=config.HL_ACCOUNT_ADDRESS,
                )
            except RuntimeError as e:
                if "MASTER wallet" in str(e):
                    raise
                self.log(f"⚠️ [WARNING] Failed to initialize Hyperliquid Exchange: {e}")
                self.exchange = None
            except Exception as e:
                self.log(f"⚠️ [WARNING] Failed to initialize Hyperliquid Exchange: {e}")
                self.exchange = None
        
        # Initialize metadata cache
        self._meta_cache = None
        
        # Balance cache to prevent 429s from frontend polling
        self._balance_cache = {"time": 0, "data": None}
        self._cache_ttl = 10 # 10 seconds TTL
        
        # Positions cache to keep bot state coherent under rate limiting.
        # If get_positions() is rate-limited, returning [] can make the bot think
        # positions vanished (or that none exist) and cause "ghost" state issues.
        # data=None until the first successful user_state fetch (empty list = flat book)
        self._positions_cache = {"time": 0, "data": None}
        self._positions_cache_ttl = 10  # seconds TTL for cached positions
        # True when last positions read failed (rate-limit/error) with no usable cache.
        # Callers MUST NOT treat an empty list as "flat book" while this is set.
        self._positions_fetch_failed = False
        # True when the returned list is a stale cache (API failed). Never size a
        # market open/close from this snapshot — it can flip a flat book into a reverse.
        self._positions_stale = False
        self._open_orders_cache = {"time": 0, "data": None}
        self._open_orders_fetch_failed = False
    
        self._ws_fallback_last_log: dict[str, float] = {}
    
    def _normalize_ws_symbols(self, symbols: list[str]) -> list[str]:
        out: list[str] = []
        seen: set[str] = set()
        for raw in symbols or []:
            sym = self.get_canonical_symbol(str(raw or "").strip())
            if sym and sym not in seen:
                seen.add(sym)
                out.append(sym)
        return out

    def _fetch_rest_mid(self, symbol: str) -> float:
        """REST mid price (allMids). Returns 0.0 on failure."""
        symbol = self.get_canonical_symbol(symbol)
        try:
            mids = self.info.all_mids()
            mid = mids.get(symbol) if isinstance(mids, dict) else None
            if mid is not None:
                px = float(mid)
                return px if px > 0 else 0.0
        except Exception as e:
            self.log(f"allMids price failed for {symbol}: {e}", "DEBUG")
        return 0.0

    def _seed_ws_prices(self, symbols: list[str]) -> None:
        if not self.ws_manager:
            return
        for sym in self._normalize_ws_symbols(symbols):
            px = self._fetch_rest_mid(sym)
            if px > 0:
                self.ws_manager.seed_price(sym, px)

    def _log_ws_cache_miss_once(self, symbol: str) -> None:
        now = time.time()
        if now - self._ws_fallback_last_log.get(symbol, 0) < 300:
            return
        self._ws_fallback_last_log[symbol] = now
        self.log(
            f"WS price cache miss for {symbol}; seeded from REST until WS tick",
            "DEBUG",
        )
    
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
        """
        tracked = self._normalize_ws_symbols(symbols)
        if not tracked:
            return

        if self.ws_manager is not None:
            if self.ws_manager.is_alive():
                self.ws_manager.sync_symbols(tracked)
                self._seed_ws_prices(tracked)
                self.log(f"WebSocket symbols synced: {', '.join(tracked)}")
                return
            self.log("WebSocket thread dead; restarting price feed")
            self.stop_websocket()

        try:
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
            
            self.ws_manager = WebSocketPriceManager(
                tracked,
                logger=LogBridge(self),
                ws_url=self._ws_url_from_rest(self._api_base_url()),
                user_address=getattr(config, "HL_ACCOUNT_ADDRESS", None),
            )
            self.ws_manager.start()
            self._seed_ws_prices(tracked)
            self.log(f"WebSocket price feeds started for: {', '.join(tracked)}")
        except Exception as e:
            self.log(f"Failed to start WebSocket manager: {e}", "ERROR")
            self.log("Falling back to REST API for price feeds", "INFO")
            self.ws_manager = None
    
    def stop_websocket(self) -> None:
        """
        Stop WebSocket price manager gracefully.
        
        Should be called on bot shutdown.
        """
        if self.ws_manager:
            self.ws_manager.stop()
            self.ws_manager = None

    def ensure_ws_symbol(self, symbol: str) -> None:
        """Track symbol on WS feed and seed REST mid until first WS tick."""
        sym = self.get_canonical_symbol(str(symbol or "").strip())
        if not sym:
            return
        if self.ws_manager is None:
            self.start_websocket([sym])
            return
        self.ws_manager.sync_symbols([sym])
        self._seed_ws_prices([sym])
    
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
        
        - Canonicalizes aliases (PEPE → kPEPE)
        - Retries empty snapshots and 429s with backoff
        - Widens the time window on later attempts
        - Explicit chronological sorting / UTC / OHLCV coercion
        
        Args:
            symbol: Trading pair (e.g., "BTC")
            interval: Candle interval ("1m", "15m", "1h", "1d")
            limit: Number of candles to fetch
            
        Returns:
            DataFrame with OHLCV data, chronologically sorted
        """
        symbol = self.get_canonical_symbol(symbol)
        try:
            interval_seconds = self._parse_interval_to_seconds(interval)
            time_range = limit * interval_seconds * 1000
            max_retries = 3
            retry_delay = 1
            raw_candles = None
            
            for attempt in range(max_retries):
                end_time = int(pd.Timestamp.now(tz='UTC').timestamp() * 1000)
                # Widen window on retries (1.5x → 2.5x → 3.5x) for sparse/gap responses
                buffer = 1.5 + attempt
                start_time = end_time - int(time_range * buffer)

                try:
                    raw_candles = self.info.candles_snapshot(symbol, interval, start_time, end_time)
                except Exception as e:
                    if _is_rate_limit_error(e) and attempt < max_retries - 1:
                        wait_time = retry_delay * (2 ** attempt)
                        self.log(
                            f"Rate limit (429) on candles {symbol} {interval}; "
                            f"retry in {wait_time}s ({attempt + 1}/{max_retries})"
                        )
                        time.sleep(wait_time)
                        continue
                    raise

                if raw_candles:
                    break

                if attempt < max_retries - 1:
                    wait_time = retry_delay * (2 ** attempt)
                    self.log(
                        f"Empty candles for {symbol} {interval}; "
                        f"retry in {wait_time}s ({attempt + 1}/{max_retries}, window×{buffer})"
                    )
                    time.sleep(wait_time)
            
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

    @staticmethod
    def _round_price(price: float, sz_decimals: int, max_decimals: int = 6) -> float:
        """Round price to Hyperliquid tick rules (perps by default).

        Rules (https://hyperliquid.gitbook.io/hyperliquid-docs/for-developers/api/tick-and-lot-size):
        - At most 5 significant figures
        - At most ``max_decimals - szDecimals`` decimal places (6 for perps, 8 for spot)
        - Integer prices are always valid regardless of significant figures
        """
        if price is None or price <= 0:
            return 0.0
        px = float(price)
        if px > 100_000:
            return float(round(px))
        return float(round(float(f"{px:.5g}"), max(0, max_decimals - int(sz_decimals))))

    def _get_precision(self, symbol: str):
        """Get (sz_decimals, max_price_decimals) from Hyperliquid metadata.

        ``max_price_decimals`` is ``6 - szDecimals`` for perps. Actual order
        prices must still go through ``_round_price`` (5 sig figs + this cap).
        """
        meta = self._fetch_metadata()
        
        # 1. Try to find in Universe for szDecimals
        if meta and "universe" in meta:
            for asset in meta["universe"]:
                if asset["name"] == symbol:
                    sz_decimals = int(asset["szDecimals"])
                    price_decimals = max(0, 6 - sz_decimals)
                    return sz_decimals, price_decimals
        
        # 2. Fallback Map for Size Decimals (if metadata lookup fails)
        FALLBACK_SZ = {"BTC": 5, "ETH": 4, "SOL": 2, "DOGE": 0, "PEPE": 0, "WIF": 0, "HYPE": 1, "FARTCOIN": 1, "BCH": 2}
        self.log(f"⚠️ Metadata lookup failed for {symbol}. Using fallback precision.")
        sz_decimals = FALLBACK_SZ.get(symbol, 2)
        return sz_decimals, max(0, 6 - sz_decimals)

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

    def get_open_orders(self, symbol: str = None) -> list:
        """Get open orders (including Triggers), optionally filtered by symbol.

        On rate-limit / API errors, returns the last successful snapshot and sets
        ``_open_orders_fetch_failed``. Callers MUST NOT treat an empty list as
        "no protection orders" while that flag is set — placing SL/TP on a
        false empty book creates duplicates.
        """
        self._open_orders_fetch_failed = False
        if not config.HL_ACCOUNT_ADDRESS:
            return []

        if not rate_limiter.can_call("open_orders"):
            self.log("⚠️ Rate limit protection: skipping get_open_orders", "WARNING")
            return self._stale_open_orders_fallback("rate limit", symbol)

        rate_limiter.record_call("open_orders")

        try:
            # Use frontend_open_orders to get everything (triggers, SL/TP)
            # Standard open_orders only returns book orders
            orders = self.info.frontend_open_orders(config.HL_ACCOUNT_ADDRESS) or []
            self._open_orders_cache = {"time": time.time(), "data": list(orders)}
            self._open_orders_fetch_failed = False
            return self._filter_open_orders(orders, symbol)
        except Exception as e:
            self.log(f"⚠️ Failed to fetch open orders: {e}")
            return self._stale_open_orders_fallback(f"error: {e}", symbol)

    def _filter_open_orders(self, orders: list, symbol: str = None) -> list:
        if not symbol:
            return list(orders)
        want = str(symbol).strip()
        want_upper = want.upper()
        matched = []
        for o in orders:
            coin = str(o.get("coin") or "")
            if coin == want or coin.upper() == want_upper:
                matched.append(o)
        if matched:
            return matched
        try:
            canon = self.get_canonical_symbol(symbol)
            return [o for o in orders if o.get("coin") == canon]
        except Exception:
            return matched

    def _stale_open_orders_fallback(self, reason: str, symbol: str = None) -> list:
        """Return last-known open orders on API failure — never invent an empty book."""
        cache_time = float(self._open_orders_cache.get("time", 0) or 0)
        cached = self._open_orders_cache.get("data")
        self._open_orders_fetch_failed = True
        if cache_time > 0 and cached is not None:
            age = time.time() - cache_time
            self.log(
                f"⚠️ Returning stale open orders ({age:.0f}s old) due to {reason}",
                "WARNING",
            )
            return self._filter_open_orders(list(cached), symbol)
        self.log(
            f"⚠️ Open orders unavailable ({reason}) and no cache — skip SL/TP placement",
            "WARNING",
        )
        return []

    @standard_operation
    def _place_protection_orders(self, symbol: str, is_buy: bool, quantity: float, sl_price: float = None, tp_price: float = None):
        """Place Stop Loss and Take Profit orders on exchange (Hard Stops)"""
        try:
            sz_decimals, _ = self._get_precision(symbol)
            
            # SL/TP logic: 
            # If opened LONG (is_buy=True) -> SL/TP are SELL orders (is_buy=False)
            # If opened SHORT (is_buy=False) -> SL/TP are BUY orders (is_buy=True)
            close_is_buy = not is_buy

            # Round quantity carefully to avoid precision errors rejection
            quantity = float(f"{quantity:.{sz_decimals}f}")
            
            orders = []
            
            if sl_price:
                sl_price = self._round_price(sl_price, sz_decimals)
                # For Market Trigger, limit_px must be aggressive to ensure fill
                sl_limit_px = self._round_price(
                    sl_price * 1.05 if close_is_buy else sl_price * 0.95,
                    sz_decimals,
                )
                
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
                tp_price = self._round_price(tp_price, sz_decimals)
                # For TP, logic is same (Market Trigger needs fill)
                tp_limit_px = self._round_price(
                    tp_price * 1.05 if close_is_buy else tp_price * 0.95,
                    sz_decimals,
                )
                
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

    @staticmethod
    def _classify_order_statuses(result) -> dict:
        """Parse a Hyperliquid order/bulk_orders payload.

        Returns counts used to decide retry vs success vs failure. A fill must
        never be retried (would double the position). An IOC cancel is a miss,
        not success.
        """
        filled = []
        errors = []
        canceled = []
        resting = []
        waiting = []
        if not isinstance(result, dict):
            return {
                "ok_envelope": False,
                "filled": filled,
                "errors": [f"non-dict result: {result}"],
                "canceled": canceled,
                "resting": resting,
                "waiting": waiting,
            }
        if result.get("status") != "ok":
            return {
                "ok_envelope": False,
                "filled": filled,
                "errors": [str(result.get("response") or result.get("status") or result)],
                "canceled": canceled,
                "resting": resting,
                "waiting": waiting,
            }
        statuses = (
            result.get("response", {}).get("data", {}).get("statuses", []) or []
        )
        for status in statuses:
            if isinstance(status, str):
                if "waiting" in status.lower():
                    waiting.append(status)
                elif "cancel" in status.lower():
                    canceled.append(status)
                else:
                    waiting.append(status)
                continue
            if not isinstance(status, dict):
                continue
            if status.get("error"):
                errors.append(str(status["error"]))
            if status.get("filled"):
                filled.append(status["filled"])
            if status.get("canceled") or status.get("cancelled"):
                canceled.append(status.get("canceled") or status.get("cancelled"))
            if status.get("resting"):
                resting.append(status["resting"])
        return {
            "ok_envelope": True,
            "filled": filled,
            "errors": errors,
            "canceled": canceled,
            "resting": resting,
            "waiting": waiting,
        }

    def _position_open_on_exchange(self, symbol: str) -> bool | None:
        """True/False if book is known; None if positions cannot be trusted."""
        symbol = self.get_canonical_symbol(symbol)
        positions = self.get_positions()
        if self._positions_fetch_failed:
            return None
        for p in positions or []:
            if p.get("symbol") == symbol and abs(float(p.get("size") or 0)) > 0:
                return True
        if getattr(self, "_positions_stale", False):
            return None
        return False

    @staticmethod
    def _new_cloid():
        """16-byte client order id — reuse on retry of the *same* unsent intent only."""
        try:
            from hyperliquid.utils.types import Cloid

            return Cloid.from_str("0x" + uuid.uuid4().hex)
        except Exception:
            return None

    @staticmethod
    def _parse_cloid_order_state(resp) -> str:
        """Map Hyperliquid orderStatus payload → filled|open|canceled|rejected|unknown."""
        if not isinstance(resp, dict):
            return "unknown"
        top = str(resp.get("status") or "").lower()
        if top == "unknown":
            return "unknown"
        order_wrap = resp.get("order") if isinstance(resp.get("order"), dict) else resp
        status = str(
            (order_wrap or {}).get("status")
            or resp.get("orderStatus")
            or top
            or ""
        ).lower()
        if "fill" in status:
            return "filled"
        if status in ("open", "triggered", "resting") or "open" in status:
            return "open"
        if "cancel" in status:
            return "canceled"
        if "reject" in status or "margin" in status:
            return "rejected"
        if top in ("ok", "order") and not status:
            return "open"
        return "unknown"

    def _cloid_order_state(self, cloid) -> str | None:
        """Query orderStatus by cloid. None = query failed (do not guess)."""
        if not cloid:
            return "unknown"
        info = getattr(self, "info", None)
        addr = getattr(config, "HL_ACCOUNT_ADDRESS", None)
        if info is None or not addr or not hasattr(info, "query_order_by_cloid"):
            return None
        try:
            from hyperliquid.utils.types import Cloid

            raw = cloid
            if not isinstance(raw, Cloid):
                text = str(raw)
                raw = Cloid.from_str(text if text.startswith("0x") else "0x" + text)
            resp = info.query_order_by_cloid(addr, raw)
            state = self._parse_cloid_order_state(resp)
            self.log(f"🔎 cloid {raw} orderStatus={state}")
            return state
        except Exception as e:
            self.log(f"⚠️ query_order_by_cloid failed: {e}", "WARNING")
            return None

    @staticmethod
    def _entry_slippage(symbol: str) -> float:
        from app.core.live_guards import entry_slippage_for_symbol

        return entry_slippage_for_symbol(symbol)

    @staticmethod
    def _avg_px_from_fills(filled: list) -> float:
        if not filled:
            return 0.0
        first = filled[0]
        if isinstance(first, dict):
            try:
                return float(first.get("avgPx") or 0)
            except (TypeError, ValueError):
                return 0.0
        return 0.0

    @staticmethod
    def _sz_from_fills(filled: list, fallback: float) -> float:
        if not filled:
            return float(fallback or 0)
        first = filled[0]
        if isinstance(first, dict):
            try:
                sz = float(first.get("totalSz") or first.get("sz") or 0)
                if sz > 0:
                    return sz
            except (TypeError, ValueError):
                pass
        return float(fallback or 0)

    def _trigger_order_fields(
        self, symbol: str, close_is_buy: bool, quantity: float, trigger_px: float, tpsl: str
    ) -> dict:
        sz_decimals, _ = self._get_precision(symbol)
        trigger_px = self._round_price(trigger_px, sz_decimals)
        limit_px = self._round_price(
            trigger_px * 1.05 if close_is_buy else trigger_px * 0.95,
            sz_decimals,
        )
        quantity = float(f"{quantity:.{sz_decimals}f}")
        return {
            "coin": symbol,
            "is_buy": close_is_buy,
            "sz": quantity,
            "limit_px": limit_px,
            "order_type": {"trigger": {"triggerPx": trigger_px, "isMarket": True, "tpsl": tpsl}},
            "reduce_only": True,
        }

    def _order_tpsl_kind(self, order: dict, side: str, entry: float) -> str | None:
        """Return 'sl', 'tp', or None for a reduce-only order."""
        if not order.get("reduceOnly") and not order.get("reduce_only"):
            return None
        raw_type = str(
            order.get("orderType")
            or (order.get("order_type") or {}).get("trigger", {}).get("tpsl")
            or ""
        ).lower()
        if "stop" in raw_type or raw_type == "sl":
            return "sl"
        if "take" in raw_type or raw_type == "tp":
            return "tp"
        trigger_px = float(order.get("triggerPx") or order.get("limitPx") or 0)
        if trigger_px <= 0 or entry <= 0:
            return None
        is_buy = str(side or "BUY").upper() in ("BUY", "LONG")
        if is_buy:
            return "sl" if trigger_px < entry else "tp"
        return "sl" if trigger_px > entry else "tp"

    def find_protection_orders(self, symbol: str, side: str, entry: float) -> dict:
        """Locate exchange SL/TP. fetch_failed=True means the book must not be trusted."""
        orders = self.get_open_orders(symbol)
        failed = getattr(self, "_open_orders_fetch_failed", False) is True
        sl_o = tp_o = None
        for o in orders or []:
            kind = self._order_tpsl_kind(o, side, entry)
            if kind == "sl" and sl_o is None:
                sl_o = o
            elif kind == "tp" and tp_o is None:
                tp_o = o
        return {"sl": sl_o, "tp": tp_o, "fetch_failed": failed, "orders": orders or []}

    def confirm_or_place_sl(
        self,
        symbol: str,
        is_buy: bool,
        quantity: float,
        sl_price: float,
        tp_price: float = None,
        entry: float = 0.0,
    ) -> bool | None:
        """Ensure an SL trigger exists for this position.

        True = SL present (placed or already there).
        False = confirmed missing after a successful book read + place attempt.
        None = book unreadable — caller must NOT panic-close.
        """
        side = "BUY" if is_buy else "SELL"
        found = self.find_protection_orders(symbol, side, entry or 0.0)
        if found["fetch_failed"]:
            self.log(
                f"⚠️ Cannot confirm SL for {symbol}: open-orders fetch failed — leaving position",
                "WARNING",
            )
            return None
        sl_order = found["sl"]
        if sl_order:
            try:
                existing_sz = float(sl_order.get("sz") or sl_order.get("origSz") or 0)
            except (TypeError, ValueError):
                existing_sz = 0.0
            if quantity and existing_sz > 0 and abs(existing_sz - float(quantity)) / max(quantity, 1e-12) > 0.05:
                self.log(
                    f"🔄 SL size {existing_sz} ≠ position {quantity} on {symbol} — modifying in place"
                )
                self._modify_protection_order(sl_order, is_buy, quantity, sl_price, "sl")
            return True

        self.log(f"🛡️ SL missing on {symbol} after fill — placing now (sz={quantity})", "ERROR")
        self._place_protection_orders(symbol, is_buy, quantity, sl_price, tp_price if not found["tp"] else None)
        found2 = self.find_protection_orders(symbol, side, entry or 0.0)
        if found2["fetch_failed"]:
            return None
        return found2["sl"] is not None

    def _modify_protection_order(
        self, existing: dict, is_buy: bool, quantity: float, trigger_px: float, tpsl: str
    ) -> bool:
        if not self.exchange or not hasattr(self.exchange, "modify_order"):
            return False
        oid = existing.get("oid")
        if oid is None:
            return False
        symbol = existing.get("coin") or existing.get("symbol")
        close_is_buy = not is_buy
        fields = self._trigger_order_fields(symbol, close_is_buy, quantity, trigger_px, tpsl)
        try:
            resp = self.exchange.modify_order(
                oid,
                fields["coin"],
                fields["is_buy"],
                fields["sz"],
                fields["limit_px"],
                fields["order_type"],
                True,
            )
            parsed = self._classify_order_statuses(resp)
            if parsed["errors"] and not parsed["ok_envelope"]:
                self.log(f"❌ modify {tpsl.upper()} failed: {parsed['errors']}", "ERROR")
                return False
            self.log(f"✅ Modified {tpsl.upper()} oid={oid} → {trigger_px} sz={fields['sz']}")
            return True
        except Exception as e:
            self.log(f"❌ modify {tpsl.upper()} exception: {e}", "ERROR")
            return False

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
        
        # PRECISION & ROUNDING (Use dynamic metadata + HL tick rules)
        sz_decimals, _ = self._get_precision(symbol)
        
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
        # One cloid per *intent*. Reuse after timeout (HL rejects duplicates).
        # Mint a new one only after a confirmed cancel/reject with no fill.
        entry_cloid = self._new_cloid()
        
        for attempt in range(max_retries):
            try:
                # CASE 1: ATOMIC ENTRY + SL/TP (Recommended)
                if sl_price or tp_price:
                    self.log(f"🚀 SUBMITTING ATOMIC ORDER (Entry + SL/TP) for {symbol} (Attempt {attempt + 1})")
                    
                    orders = []
                    
                    # 1. ENTRY ORDER
                    # Hyperliquid bulk_orders does not support a native "market" entry;
                    # we simulate market behavior with an aggressive crossing limit + IOC,
                    # so we don't miss fast moves while still keeping SL/TP atomic grouping.
                    current_px = self.get_current_price(symbol)
                    if current_px <= 0:
                        return {"status": "error", "message": f"No valid market price for {symbol}"}
                    slip = self._entry_slippage(symbol)
                    simulated_limit_px = current_px * (1 + slip) if is_buy else current_px * (1 - slip)
                    entry_limit_px = self._round_price(simulated_limit_px, sz_decimals)
                    signal_px = float(price) if price else None
                    self.log(
                        f"🎯 Atomic entry pricing: signal_px={signal_px}, current_px={current_px}, "
                        f"limit_px={entry_limit_px}, slippage={slip:.1%}"
                    )

                    entry_order = {
                        "coin": symbol,
                        "is_buy": is_buy,
                        "sz": quantity,
                        "limit_px": entry_limit_px,
                        "order_type": {"limit": {"tif": "Ioc"}},
                        "reduce_only": False,
                    }
                    if entry_cloid is not None:
                        entry_order["cloid"] = entry_cloid

                    orders.append(entry_order)

                    # 2. SL/TP ORDERS
                    close_is_buy = not is_buy
                    
                    if sl_price:
                        sl_px_fmt = self._round_price(sl_price, sz_decimals)
                        # For Market Trigger, limit_px should be aggressive to ensure fill when triggered.
                        sl_limit_px = self._round_price(
                            sl_px_fmt * 1.05 if close_is_buy else sl_px_fmt * 0.95,
                            sz_decimals,
                        )
                        orders.append({
                            "coin": symbol,
                            "is_buy": close_is_buy,
                            "sz": quantity,
                            "limit_px": sl_limit_px,
                            "order_type": {"trigger": {"triggerPx": sl_px_fmt, "isMarket": True, "tpsl": "sl"}},
                            "reduce_only": True
                        })
                        
                    if tp_price:
                        tp_px_fmt = self._round_price(tp_price, sz_decimals)
                        # Same aggressive limit behavior for market-trigger TP.
                        tp_limit_px = self._round_price(
                            tp_px_fmt * 1.05 if close_is_buy else tp_px_fmt * 0.95,
                            sz_decimals,
                        )
                        orders.append({
                            "coin": symbol,
                            "is_buy": close_is_buy,
                            "sz": quantity,
                            "limit_px": tp_limit_px,
                            "order_type": {"trigger": {"triggerPx": tp_px_fmt, "isMarket": True, "tpsl": "tp"}},
                            "reduce_only": True
                        })
                    
                    # EXECUTE BULK
                    result = self.exchange.bulk_orders(orders, grouping="normalTpsl")
                    
                # CASE 2: SIMPLE ENTRY (No SL/TP provided)
                else:
                    if price:
                         # LIMIT
                         limit_px = self._round_price(price, sz_decimals)
                         self.log(f"🚀 SUBMITTING LIMIT {'BUY' if is_buy else 'SELL'} {quantity} {symbol} @ {limit_px}")
                         result = self.exchange.order(symbol, is_buy, quantity, limit_px, {"limit": {"tif": "Gtc"}})
                    else:
                         slip = self._entry_slippage(symbol)
                         self.log(
                             f"🚀 SUBMITTING MARKET {'BUY' if is_buy else 'SELL'} "
                             f"{quantity} {symbol} (slippage={slip:.1%})"
                         )
                         mo_kwargs = {"slippage": slip}
                         if entry_cloid is not None:
                             mo_kwargs["cloid"] = entry_cloid
                         result = self.exchange.market_open(
                             symbol, is_buy, quantity, **mo_kwargs
                         )

                # VERIFICATION LOGIC (Shared)
                self.log(f"✅ Exec Result: {result}")
                parsed = self._classify_order_statuses(result)
                filled_orders = parsed["filled"]
                errors = parsed["errors"]

                if filled_orders:
                    self.log(f"✅ Order Filled: {filled_orders[0]}")
                    if errors:
                        self.log(
                            f"⚠️ Entry filled but protection/other legs rejected: {errors}. "
                            "NOT retrying (would double the position). Reconciler must attach SL/TP.",
                            "ERROR",
                        )
                    avg_px = self._avg_px_from_fills(filled_orders)
                    filled_sz = self._sz_from_fills(filled_orders, quantity)
                    return {
                        "status": "success",
                        "result": result,
                        "avg_px": avg_px,
                        "filled_sz": filled_sz,
                        "cloid": str(entry_cloid) if entry_cloid else None,
                    }

                if parsed["resting"]:
                    self.log(f"ℹ️ Entry resting on book (not yet filled): {parsed['resting']}")
                    return {"status": "success", "result": result}

                if errors:
                    self.log(f"❌ Order Rejected: {errors}")
                    existing = self._position_open_on_exchange(symbol)
                    if existing is True:
                        self.log(
                            "⚠️ Rejection after submit but position is open — treating as filled, not retrying",
                            "ERROR",
                        )
                        return {"status": "success", "result": result}
                    if existing is None:
                        self.log(
                            "⛔ Ambiguous fill state (positions API down). NOT retrying entry.",
                            "ERROR",
                        )
                        return {
                            "status": "error",
                            "message": f"Rejected (ambiguous, no retry): {errors}",
                        }
                    if attempt < max_retries - 1:
                        # Confirmed reject, no fill — this cloid is spent.
                        entry_cloid = self._new_cloid()
                        time.sleep(retry_delay)
                        continue
                    return {"status": "error", "message": f"Rejected: {errors}"}

                if parsed["canceled"] and not filled_orders:
                    self.log(f"❌ IOC/entry canceled without fill: {parsed['canceled']}")
                    if attempt < max_retries - 1:
                        # IOC miss consumed the cloid; mint a new intent id.
                        entry_cloid = self._new_cloid()
                        time.sleep(retry_delay)
                        continue
                    return {"status": "error", "message": "Entry IOC canceled without fill"}

                if not parsed["ok_envelope"]:
                    self.log(f"❌ API Error: {result}")
                    existing = self._position_open_on_exchange(symbol)
                    if existing is True:
                        return {"status": "success", "result": result}
                    if existing is None:
                        return {
                            "status": "error",
                            "message": "Ambiguous fill state after non-ok response — not retrying",
                        }
                    if attempt < max_retries - 1:
                        time.sleep(retry_delay)
                        continue

            except Exception as e:
                error_msg = str(e)
                self.log(f"❌ Exception in execute_order (Attempt {attempt+1}): {error_msg}")

                cloid_state = self._cloid_order_state(entry_cloid)
                if cloid_state in ("filled", "open"):
                    self.log(
                        f"⚠️ Exception after submit but cloid is {cloid_state} — not retrying entry",
                        "ERROR",
                    )
                    return {
                        "status": "success",
                        "message": f"cloid {cloid_state} after exception",
                        "cloid": str(entry_cloid) if entry_cloid else None,
                    }

                existing = self._position_open_on_exchange(symbol)
                if existing is True:
                    self.log(
                        "⚠️ Exception after submit but position is open — not retrying entry",
                        "ERROR",
                    )
                    return {"status": "success", "message": "position exists after exception"}
                if existing is None and cloid_state is None:
                    self.log(
                        "⛔ Ambiguous fill state after exception (positions + cloid unreadable). NOT retrying.",
                        "ERROR",
                    )
                    return {
                        "status": "error",
                        "message": f"Ambiguous after exception: {error_msg}",
                    }
                if existing is None:
                    self.log(
                        "⛔ Positions API down after exception. NOT retrying.",
                        "ERROR",
                    )
                    return {
                        "status": "error",
                        "message": f"Ambiguous after exception: {error_msg}",
                    }

                if cloid_state in ("canceled", "rejected"):
                    entry_cloid = self._new_cloid()

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
    def sync_sl_tp(self, symbol: str, is_buy: bool, quantity: float, sl_price: float, tp_price: float, entry_price: float = 0.0):
        """
        Move SL/TP for an existing position by modifying reduce-only triggers
        in place. Never cancel-all first (naked window).
        """
        if not self.exchange:
            return {"status": "error", "message": "No private key configured"}
            
        self.log(f"🔄 SYNCING SL/TP for {symbol} (SL: {sl_price}, TP: {tp_price})...")
        try:
            side = "BUY" if is_buy else "SELL"
            found = self.find_protection_orders(symbol, side, float(entry_price or 0))
            if found["fetch_failed"]:
                self.log(
                    f"⛔ Refusing SL/TP sync for {symbol}: open-orders fetch failed "
                    "(will not cancel protection on a guessed book)",
                    "ERROR",
                )
                return {"status": "error", "message": "open orders unavailable"}

            # Modify existing reduce-only SL/TP in place — never cancel-all first
            # (that leaves a naked window). Non-reduce-only orders are left untouched.
            sl_ok = True
            tp_ok = True
            if sl_price:
                if found["sl"]:
                    sl_ok = self._modify_protection_order(
                        found["sl"], is_buy, quantity, sl_price, "sl"
                    )
                    if not sl_ok:
                        self.log(
                            f"⚠️ SL modify failed for {symbol} — keeping existing SL (not naked)",
                            "ERROR",
                        )
                else:
                    self._place_protection_orders(symbol, is_buy, quantity, sl_price, None)
            if tp_price:
                if found["tp"]:
                    tp_ok = self._modify_protection_order(
                        found["tp"], is_buy, quantity, tp_price, "tp"
                    )
                    if not tp_ok:
                        self.log(
                            f"⚠️ TP modify failed for {symbol} — keeping existing TP",
                            "ERROR",
                        )
                else:
                    self._place_protection_orders(symbol, is_buy, quantity, None, tp_price)

            return {"status": "success" if sl_ok else "partial"}
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

    def _get_account_abstraction_mode(self, address: str) -> str:
        """Hyperliquid account mode: unifiedAccount, portfolioMargin, default, etc."""
        try:
            mode = self.info.post("/info", {"type": "userAbstraction", "user": address})
            if isinstance(mode, str):
                return mode.strip().strip('"')
            return str(mode) if mode is not None else "unknown"
        except Exception as e:
            self.log(f"⚠️ userAbstraction query failed: {e}")
            return "unknown"

    @staticmethod
    def _usdc_balance_from_spot(spot_state: dict) -> tuple[float, float]:
        """Return (total_usdc, available_usdc) from spotClearinghouseState."""
        for bal in (spot_state or {}).get("balances", []):
            if bal.get("coin") == "USDC":
                total = float(bal.get("total", 0) or 0)
                hold = float(bal.get("hold", 0) or 0)
                return total, max(0.0, total - hold)
        return 0.0, 0.0

    @standard_operation
    def get_account_balance(self, force_refresh=False):
        """Fetch account balance and margin information from Hyperliquid (Cached)"""
        if not config.HL_ACCOUNT_ADDRESS:
            err = {
                "status": "error",
                "message": "No account address configured (set HL_ACCOUNT_ADDRESS in .env)",
                "total_equity": 0,
                "available_balance": 0,
                "margin_used": 0,
            }
            self.log(f"⚠️ {err['message']}")
            return err
            
        # Check Cache
        now = time.time()
        if not force_refresh and self._balance_cache["data"] and (now - self._balance_cache["time"] < self._cache_ttl):
            return self._balance_cache["data"]
        
        try:
            address = config.HL_ACCOUNT_ADDRESS
            user_state = self.info.user_state(address)
            spot_state = self.info.spot_user_state(address)
            abstraction_mode = self._get_account_abstraction_mode(address)

            margin_summary = user_state.get("marginSummary", {}) or {}
            perp_account_value = float(margin_summary.get("accountValue", 0) or 0)
            total_margin_used = float(margin_summary.get("totalMarginUsed", 0) or 0)
            withdrawable = float(user_state.get("withdrawable", 0) or 0)

            spot_total, spot_available = self._usdc_balance_from_spot(spot_state)

            # Unified / portfolio margin: spot USDC is source of truth (perp-only state can be 0).
            use_spot = abstraction_mode in ("unifiedAccount", "portfolioMargin") or (
                perp_account_value <= 0 and spot_total > 0
            )

            if use_spot and spot_total > 0:
                account_value = spot_total
                available_balance = spot_available
                if abstraction_mode in ("unifiedAccount", "portfolioMargin"):
                    self.log(
                        f"💰 Balance from spot (mode={abstraction_mode}): "
                        f"equity=${account_value:.2f}, available=${available_balance:.2f}"
                    )
                else:
                    self.log(
                        f"💰 Perp equity $0 — using spot USDC: "
                        f"equity=${account_value:.2f}, available=${available_balance:.2f}"
                    )
            else:
                account_value = perp_account_value
                available_balance = withdrawable if withdrawable > 0 else (account_value - total_margin_used)

            result = {
                "status": "success",
                "total_equity": account_value,
                "available_balance": available_balance,
                "margin_used": total_margin_used,
                "account_abstraction_mode": abstraction_mode,
                "perp_account_value": perp_account_value,
                "spot_usdc_total": spot_total,
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
        """Get total account value in USDC."""
        balance = self.get_account_balance()
        return balance.get("total_equity", 0)

    def _stale_positions_fallback(self, reason: str):
        """Return last-known positions on API failure — never invent a flat book."""
        cache_time = float(self._positions_cache.get("time", 0) or 0)
        cached = self._positions_cache.get("data")
        # time==0 means never successfully fetched (initial state is data=None)
        if cache_time > 0 and cached is not None:
            age = time.time() - cache_time
            self._positions_fetch_failed = False  # stale list is still usable for sync
            self._positions_stale = True
            self.log(
                f"⚠️ Returning stale positions ({age:.0f}s old) due to {reason}",
                "WARNING",
            )
            return list(cached)
        self._positions_fetch_failed = True
        self._positions_stale = False
        self.log(
            f"⚠️ Positions unavailable ({reason}) and no cache — sync must skip closures",
            "WARNING",
        )
        return []

    def get_positions(self):
        """Fetch open positions from Hyperliquid.

        On rate-limit / API errors, returns the last successful snapshot (even if
        older than TTL) instead of ``[]``. An empty list after a *successful*
        fetch means the book is truly flat. If there is no cache at all,
        ``_positions_fetch_failed`` is set so callers skip ghost-close logic.
        """
        if not config.HL_ACCOUNT_ADDRESS:
            self._positions_fetch_failed = False
            return []
        
        # Rate limiting protection
        if not rate_limiter.can_call("user_state"):
            self.log("⚠️ Rate limit protection: skipping get_positions", "WARNING")
            return self._stale_positions_fallback("rate limit")
        rate_limiter.record_call("user_state")
        
        try:
            user_state = self.info.user_state(config.HL_ACCOUNT_ADDRESS)
            if not user_state:
                return self._stale_positions_fallback("empty user_state")
            
            # assetPositions contains list of { position: {...}, type: 'oneWay' }
            raw_positions = user_state.get("assetPositions", [])
            positions = []
            
            for item in raw_positions:
                pos = item.get("position", {})
                if not pos: continue
                
                # Check for open interest (szi > 0 or < 0)
                size = float(pos.get("szi", 0.0))
                if size == 0: continue
                
                symbol = pos.get("coin", "UNKNOWN")
                is_long = size > 0
                
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
                    "liquidation_price": float(pos.get("liquidationPx", 0.0)) if pos.get("liquidationPx") else None,
                    # entry_time comes from bot state / history — do not call user_fills
                    # here (extra CloudFront load caused 504s and false sync closes).
                    "entry_time": None,
                })
            
            # Update cache (even if empty, it reflects truth at this time)
            self._positions_cache = {"time": time.time(), "data": positions}
            self._positions_fetch_failed = False
            self._positions_stale = False
            return positions
        except Exception as e:
            self.log(f"Error fetching positions: {e}")
            return self._stale_positions_fallback(f"error: {e}")

    @lightweight_operation
    def cancel_all_orders(self, symbol: str):
        """Cancel all open orders for a symbol (including SL/TP triggers)."""
        if not self.exchange or not config.HL_ACCOUNT_ADDRESS:
            return
            
        try:
            # frontend_open_orders via get_open_orders — standard open_orders omits triggers
            orders_to_cancel = self.get_open_orders(symbol)
            
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

        Uses reduce-only so a retry / stale snapshot cannot open a reverse
        position. Protection orders are cancelled AFTER a confirmed close so a
        failed close does not leave the trade naked.
        """
        if not self.exchange:
            raise Exception("No private key configured")

        symbol = self.get_canonical_symbol(symbol)

        positions = self.get_positions()
        if self._positions_fetch_failed or getattr(self, "_positions_stale", False):
            msg = (
                f"Positions snapshot untrusted for {symbol} "
                f"(failed={self._positions_fetch_failed}, "
                f"stale={getattr(self, '_positions_stale', False)}) — "
                "refusing market close (exchange SL/TP stay in place)"
            )
            self.log(f"⛔ {msg}", "ERROR")
            return {"status": "error", "message": msg}

        position = next((p for p in positions if p["symbol"] == symbol), None)
        if not position or abs(float(position.get("size") or 0)) <= 0:
            self.log(f"ℹ️ No position found for {symbol} (already flat)")
            try:
                self.cancel_all_orders(symbol)
            except Exception as e:
                self.log(f"⚠️ Failed to cancel leftover orders for {symbol}: {e}")
            return {"status": "success", "closed_size": 0, "message": "already flat"}

        size = float(position["size"])
        side = position["side"]
        is_buy = (side == "SELL")  # Close SHORT with BUY

        sz_decimals, _ = self._get_precision(symbol)
        quantity = float(f"{size:.{sz_decimals}f}")
        if quantity <= 0:
            raise Exception("Position size too small to close")

        self.log(f"🔴 CLOSING {side} position: {quantity} {symbol} (reduce-only)")

        result = None
        if hasattr(self.exchange, "market_close"):
            result = self.exchange.market_close(symbol, sz=quantity)
        else:
            current_px = self.get_current_price(symbol)
            if current_px <= 0:
                raise Exception(f"No valid market price to close {symbol}")
            limit_px = self._round_price(
                current_px * (1 + self.MARKET_SLIPPAGE) if is_buy else current_px * (1 - self.MARKET_SLIPPAGE),
                sz_decimals,
            )
            result = self.exchange.order(
                symbol,
                is_buy,
                quantity,
                limit_px,
                {"limit": {"tif": "Ioc"}},
                True,  # reduce_only — never flip a flat book into a reverse
            )

        parsed = self._classify_order_statuses(result)
        if parsed["errors"] and not parsed["filled"]:
            raise Exception(f"Close rejected: {parsed['errors']}")

        self.log(f"✅ Close order submitted: {symbol} {quantity}")

        time.sleep(2)
        new_positions = self.get_positions()
        if self._positions_fetch_failed:
            # Close may have filled; do not retry a second market order.
            self.log(
                "⚠️ Close submitted but positions API down — not retrying (reduce-only already sent)",
                "WARNING",
            )
            return {"status": "success", "closed_size": size, "result": result, "unverified": True}

        remaining = next((p for p in new_positions if p["symbol"] == symbol), None)
        if remaining and remaining["size"] > quantity * 0.1:
            raise Exception(f"Position not fully closed, {remaining['size']} remaining")
        elif remaining:
            self.log(f"ℹ️ Close incomplete: Dust remaining ({remaining['size']})")

        try:
            self.cancel_all_orders(symbol)
        except Exception as e:
            self.log(f"⚠️ Failed to cancel leftover orders after close: {e}")

        self.log(f"✅ Position closed successfully: {symbol}")
        return {"status": "success", "closed_size": size, "result": result}

    def get_current_price(self, symbol: str) -> float:
        """
        Get current market price from WebSocket cache.
        
        Priority: WebSocket cache → REST allMids → 1m candle close.
        Returns 0.0 only when every source fails (callers must treat that as
        "no price" and skip manage/exit logic).
        
        Args:
            symbol: Trading pair symbol (e.g., "BTC")
        
        Returns:
            Current price or 0.0 if unavailable
        
        Example:
            >>> price = service.get_current_price("BTC")
            >>> if price > 0:
            ...     self.log(f"BTC: ${price}")
        """
        symbol = self.get_canonical_symbol(symbol)

        if self.ws_manager is not None:
            price = self.ws_manager.get_price(symbol)
            if price is not None and price > 0:
                return float(price)

        px = self._fetch_rest_mid(symbol)
        if px > 0:
            if self.ws_manager is not None:
                self.ws_manager.seed_price(symbol, px)
                self._log_ws_cache_miss_once(symbol)
            return px

        try:
            df = self.get_candles(symbol, "1m", 1)
            if not df.empty:
                px = float(df['close'].iloc[-1])
                if px > 0:
                    if self.ws_manager is not None:
                        self.ws_manager.seed_price(symbol, px)
                    return px
        except Exception as e:
            self.log(f"Error getting price via candles: {e}", "ERROR")
        
        return 0.0

    def get_trade_history(self, limit: int = 100):
        """
        Récupère l'historique des trades depuis Hyperliquid.
        
        Returns:
            List of trades on success (possibly empty).
            ``None`` when the API fails after retries (504/5xx/network) so callers
            can distinguish "no fills" from "history unavailable".
        """
        if not config.HL_ACCOUNT_ADDRESS:
            return []

        max_retries = 3
        retry_delay = 1.0
        user_fills = None
        last_err = None

        for attempt in range(max_retries):
            try:
                user_fills = self.info.user_fills(config.HL_ACCOUNT_ADDRESS)
                last_err = None
                break
            except Exception as e:
                last_err = e
                err_str = str(e).lower()
                retriable = (
                    _is_rate_limit_error(e)
                    or "504" in err_str
                    or "502" in err_str
                    or "503" in err_str
                    or "timeout" in err_str
                    or "gateway" in err_str
                )
                if retriable and attempt < max_retries - 1:
                    wait_time = retry_delay * (2 ** attempt)
                    self.log(
                        f"Trade history fetch failed ({e}); retry in {wait_time:.0f}s "
                        f"({attempt + 1}/{max_retries})"
                    )
                    time.sleep(wait_time)
                    continue
                break

        if last_err is not None:
            self.log(f"Error fetching trade history from Hyperliquid: {last_err}")
            ws_raw = self._ws_user_fills_raw(limit)
            if not ws_raw:
                return None
            return self._fills_to_trade_rows(ws_raw, limit)

        merged = list(self._ws_user_fills_raw(limit)) + list(user_fills or [])
        if not merged:
            return []
        return self._fills_to_trade_rows(merged, limit)

    def _ws_user_fills_raw(self, limit: int) -> list:
        mgr = getattr(self, "ws_manager", None)
        if mgr is None or not hasattr(mgr, "recent_user_fills"):
            return []
        try:
            raw = mgr.recent_user_fills(limit=max(int(limit or 50), 50))
            if not isinstance(raw, list):
                return []
            return list(raw)
        except Exception:
            return []

    @staticmethod
    def _fills_to_trade_rows(fills: list, limit: int) -> list:
        trades = []
        seen = set()
        for fill in fills or []:
            if not isinstance(fill, dict):
                continue
            try:
                coin = fill.get("coin") or fill.get("symbol") or ""
                raw_side = str(fill.get("side") or "")
                if raw_side in ("B", "A"):
                    side = "BUY" if raw_side == "B" else "SELL"
                else:
                    side = "BUY" if raw_side.upper() in ("BUY", "LONG", "B") else "SELL"
                price = float(fill.get("px") or fill.get("entry_price") or fill.get("exit_price") or 0)
                size = float(fill.get("sz") or fill.get("size") or 0)
                timestamp = fill.get("time") or fill.get("timestamp") or 0
                if isinstance(timestamp, str):
                    timestamp = 0
                oid = str(fill.get("oid", ""))
                closed_pnl = fill.get("closedPnl", fill.get("pnl"))
                closed_pnl = 0.0 if closed_pnl is None else float(closed_pnl)
                if timestamp:
                    timestamp_str = pd.Timestamp(timestamp, unit="ms").isoformat()
                else:
                    timestamp_str = fill.get("entry_time") or pd.Timestamp.now().isoformat()
                key = (oid, str(timestamp), str(coin))
                if key in seen:
                    continue
                seen.add(key)
                trades.append({
                    "id": f"{coin}_{timestamp}_{oid}",
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
                    "fee": float(fill.get("fee", 0) or 0),
                    "strategy": "Unknown",
                    "exit_reason": "Hyperliquid",
                    "source": "hyperliquid",
                    "dir": fill.get("dir", ""),
                    "leverage": 1,
                })
                if len(trades) >= int(limit or 50):
                    break
            except Exception:
                continue
        return trades

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
    def get_daily_pnl(self, quiet: bool = False):
        """
        Daily PnL = today's realized fills + current unrealized.

        Returns None when the snapshot cannot be trusted (no address / API error)
        so callers do not overwrite risk-manager PnL with a fake 0.
        """
        from datetime import datetime, timezone

        if not config.HL_ACCOUNT_ADDRESS:
            return None

        try:
            now_utc = datetime.now(timezone.utc)
            start_of_day = now_utc.replace(hour=0, minute=0, second=0, microsecond=0)
            start_ts_ms = int(start_of_day.timestamp() * 1000)

            realized_pnl = 0.0
            fills = None
            try:
                fills = self.info.user_fills_by_time(config.HL_ACCOUNT_ADDRESS, start_ts_ms)
            except Exception as by_time_err:
                self.log(f"⚠️ user_fills_by_time failed ({by_time_err}); falling back to user_fills")
                fills = self.info.user_fills(config.HL_ACCOUNT_ADDRESS)
            for fill in fills or []:
                try:
                    ts = int(fill.get("time") or 0)
                except (TypeError, ValueError):
                    ts = 0
                if ts >= start_ts_ms:
                    realized_pnl += float(fill.get("closedPnl") or 0.0)

            unrealized_pnl = sum([p.get("pnl", 0) for p in self.get_positions()])
            total = realized_pnl + unrealized_pnl
            if not quiet:
                self.log(
                    f"💰 Daily PnL: ${total:.2f} "
                    f"(Realized: ${realized_pnl:.2f}, Unrealized: ${unrealized_pnl:.2f})"
                )
            return total

        except Exception as e:
            if not quiet:
                self.log(f"❌ Error calculating daily PnL: {e}")
            return None


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
