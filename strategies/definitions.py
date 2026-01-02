from abc import ABC, abstractmethod
from app.services.indicators import ta
import pandas as pd
from strategies.base import BaseStrategy

# Strategies that have not yet been extracted to their own files
# TODO: Refactor these into individual files

class TestTriggerStrategy(BaseStrategy):
    """
    Strategy for TESTING purposes only.
    Triggers a signal almost constantly to verify engine/execution.
    """
    def add_indicators(self, df):
        return df

    def generate_signal(self, df, extra_data=None):
        if df.empty:
            return None
            
        close = df['close'].iloc[-1]
        
        # User asked for "strategy de test hyper light en trigger"
        # Let's signal regularly.
        return {
            "signal": "BUY",
            "sl": close * 0.99,
            "tp": close * 1.02,
            "comment": "TEST TRIGGER"
        }

    def calculate_progress(self, df, extra_data=None):
        return 100
