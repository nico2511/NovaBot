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

    def get_candles(self, symbol: str, interval: str = "15m", limit: int = 100) -> pd.DataFrame:
        try:
            # Current time in ms
            end_time = int(pd.Timestamp.now().timestamp() * 1000)
            # Approx start time (limit * interval * buffer)
            # 15m = 900s. 100 candles = 90000s.
            start_time = end_time - (limit * 15 * 60 * 1000)
            
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

    def execute_order(self, symbol: str, is_buy: bool, quantity: float, price: float = None):
        if not self.exchange:
            return {"status": "error", "message": "No private key configured"}
        
        # This is a placeholder for the actual execution logic
        # Implementation depends on whether we want Market or Limit orders
        # For this prototype, we'll assume Market if price is None
        
        print(f"EXECUTING {'BUY' if is_buy else 'SELL'} {quantity} {symbol} @ {price or 'MARKET'}")
        return {"status": "mock_success", "tx": "0x123..."}

hyperliquid_service = HyperliquidService()
