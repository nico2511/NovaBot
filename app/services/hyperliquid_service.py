import eth_account
from hyperliquid.info import Info
from hyperliquid.exchange import Exchange
from hyperliquid.utils import types
from app.core.config import config
import pandas as pd

from hyperliquid.utils.constants import MAINNET_API_URL

class HyperliquidService:
    def __init__(self):
        self.info = Info(base_url=MAINNET_API_URL, skip_ws=True)
        self.exchange = None
        
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
        """Fetch and cache exchange metadata for precision"""
        if hasattr(self, "_meta_cache") and self._meta_cache:
            return self._meta_cache
        try:
            self._meta_cache = self.info.meta()
            return self._meta_cache
        except Exception as e:
            print(f"⚠️ Failed to fetch metadata: {e}")
            return None

    def _get_precision(self, symbol: str):
        """Get precision for size and price from metadata"""
        meta = self._fetch_metadata()
        if not meta:
            return 6, 4 # Safe defaults
            
        try:
            universe = meta.get("universe", [])
            for asset in universe:
                if asset["name"] == symbol:
                    return asset["szDecimals"], asset["maxPriceDecimals"]
        except Exception as e:
            print(f"⚠️ Error parsing metadata for {symbol}: {e}")
            
        return 6, 4 # Defaults if not found

    def execute_order(self, symbol: str, is_buy: bool, quantity: float, price: float = None):
        if not self.exchange:
            return {"status": "error", "message": "No private key configured"}
        
        try:
            # Dynamic Precision Rounding
            sz_decimals, price_decimals = self._get_precision(symbol)
            
            # Format Quantity
            quantity = float(f"{quantity:.{sz_decimals}f}")
            
            if price:
                # LIMIT ORDER
                price = float(f"{price:.{price_decimals}f}")
                print(f"🚀 SUBMITTING LIMIT {'BUY' if is_buy else 'SELL'} {quantity} {symbol} @ {price}")
                result = self.exchange.order(symbol, is_buy, quantity, price, {"limit": {"tif": "Gtc"}})
            else:
                # MARKET ORDER
                print(f"🚀 SUBMITTING MARKET {'BUY' if is_buy else 'SELL'} {quantity} {symbol}")
                result = self.exchange.market_open(symbol, is_buy, quantity)
                
            print(f"✅ Order execution result: {result}")
            return {"status": "success", "result": result}
            
        except Exception as e:
            print(f"❌ Order execution failed: {e}")
            return {"status": "error", "message": str(e)}

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

    def get_account_balance(self):
        """Fetch account balance and margin information from Hyperliquid"""
        if not config.HL_ACCOUNT_ADDRESS:
            return {
                "status": "error",
                "message": "No account address configured",
                "equity": 0.0,
                "message": "No Hyperliquid account configured",
                "total_equity": 0,
                "available_balance": 0,
                "margin_used": 0
            }
        
        try:
            info = Info(config.HYPERLIQUID_API_URL, skip_ws=True)
            user_state = info.user_state(config.HL_ACCOUNT_ADDRESS)
            
            # Extract balance info
            margin_summary = user_state.get("marginSummary", {})
            account_value = float(margin_summary.get("accountValue", 0))
            total_margin_used = float(margin_summary.get("totalMarginUsed", 0))
            
            return {
                "status": "success",
                "total_equity": account_value,
                "available_balance": account_value - total_margin_used,
                "margin_used": total_margin_used
            }
        except Exception as e:
            print(f"Error fetching account balance: {e}")
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

    def close_position(self, symbol: str):
        """Close an open position on Hyperliquid"""
        if not self.exchange:
            return {"status": "error", "message": "No private key configured"}
        
        try:
            # Get current position
            positions = self.get_positions()
            position = next((p for p in positions if p["symbol"] == symbol), None)
            
            if not position:
                return {"status": "error", "message": f"No position found for {symbol}"}
            
            size = position["size"]
            side = position["side"]
            
            # Close with opposite order (market order)
            is_buy = (side == "SELL")  # If SHORT, BUY to close
            
            print(f"🔴 CLOSING {side} position: {size} {symbol}")
            result = self.execute_order(symbol, is_buy, size)
            
            return {"status": "success", "result": result, "closed_size": size}
            
        except Exception as e:
            print(f"❌ Failed to close position: {e}")
            return {"status": "error", "message": str(e)}

    def get_current_price(self, symbol: str) -> float:
        """Get current market price for a symbol"""
        try:
            df = self.get_candles(symbol, "1m", 1)
            if not df.empty:
                return float(df['close'].iloc[-1])
            return 0.0
        except Exception as e:
            print(f"Error getting current price: {e}")
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

hyperliquid_service = HyperliquidService()
