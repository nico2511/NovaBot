from abc import ABC, abstractmethod
import pandas as pd

class BaseStrategy(ABC):
    def __init__(self, config=None):
        self.name = self.__class__.__name__
        self.config = config or {}
        self.params = self.config.get("params", {})
        self.last_rejection_reason = None

    # ==========================
    # DYNAMIC PARAM ACCESS
    # ==========================

    def get_param(self, key, default=None):
        """
        Always read a parameter from the LIVE self.config["params"] dict.

        Rationale:
        - The API endpoint POST /api/engine/config/strategy-params mutates
          strategy.config["params"] at runtime.
        - Subclasses that cache params in __init__ will not see those updates
          until the engine is rebuilt. Using get_param() inside
          generate_signal()/calculate_progress() guarantees hot-edit support.
        """
        try:
            params = self.config.get("params") or {}
            if key in params:
                return params[key]
            return default
        except Exception:
            return default

    def refresh_params(self):
        """
        Best-effort sync of self.params with self.config['params'].
        Called by the API after strategy-params updates to keep the legacy
        'self.params' attribute in sync for any consumer that still reads it.
        """
        try:
            self.params = self.config.get("params", {}) or {}
        except Exception:
            self.params = {}

    @abstractmethod
    def generate_signal(self, df, extra_data=None):
        """
        Generate signal from dataframe.
        
        Args:
            df: Primary dataframe (typically the strategy's main timeframe)
            extra_data: Optional dict with additional dataframes (e.g., {"1m": df_1m, "1h": df_1h})
        """
        pass

    def add_indicators(self, df):
        """Add indicators to the dataframe. Should be overridden by subclasses."""
        pass

    # ==========================
    # DYNAMIC ANALYSIS HELPERS
    # ==========================
    
    def get_adx_slope(self, df, period=14):
        """
        Calculate ADX Slope (Current - Previous).
        Returns: float (Positive = Strengthening, Negative = Weakening)
        """
        if 'ADX_14' not in df.columns:
            # Try to calculate or return 0
            return 0
            
        try:
            current = df['ADX_14'].iloc[-1]
            prev = df['ADX_14'].iloc[-2]
            return current - prev
        except:
            return 0

    def get_rsi_delta(self, df, period=14):
        """
        Calculate RSI Delta (Current - Previous).
        Returns: float (>0 = Momentum increasing)
        """
        col = f"RSI_{period}"
        if col not in df.columns: return 0
        
        try:
            current = df[col].iloc[-1]
            prev = df[col].iloc[-2]
            return current - prev
        except:
            return 0

    def detect_bearish_divergence(self, df, rsi_col="RSI_14", lookback=5):
        """
        Detect Bearish Divergence: Price HH but RSI LH.
        Returns: bool
        """
        if rsi_col not in df.columns or len(df) < lookback: return False
        
        try:
            # Simple check: Price High is max of Lookback and matches Current
            # RSI High is NOT max of Lookback
            
            recent = df.iloc[-lookback:]
            
            price_high_idx = recent['high'].idxmax()
            rsi_high_idx = recent[rsi_col].idxmax()
            
            # If highest price is the current candle (or very recent)
            # But highest RSI was older -> Divergence
            
            current_idx = df.index[-1]
            
            if price_high_idx == current_idx and rsi_high_idx != current_idx:
                 return True
                 
            return False
        except:
            return False

    def manage_trade(self, trade, current_price, df=None, extra_data=None):
        """
        Optional: Override trade management logic (Trailing SL, TP, etc).
        
        Args:
            trade (dict): Active trade data from bot context
            current_price (float): Current market price
            df (pd.DataFrame): Current market data
            
        Returns:
            dict or None: 
                - If None: Use default bot management (fallback)
                - If dict: Updates to apply (e.g., {"sl": 1234.5})
                    - Return empty dict {} to signal "I handled it, do nothing else"
        """
        return None # Default: Fallback to bot logic

    def _reject(self, reason: str):
        """Set a human-readable rejection reason for diagnostics and return None."""
        self.last_rejection_reason = reason
        return None

