"""
Cross-Sectional Momentum Scanner
Hedge fund-style ranking system for token selection
"""
import pandas as pd
import numpy as np
from typing import Dict, List, Tuple
from datetime import datetime

class MomentumScanner:
    """
    Implements Cross-Sectional Momentum strategy:
    1. Calculate momentum score for each asset
    2. Rank assets by score
    3. Select Top N
    4. Filter by MA200 (absolute trend)
    """
    
    def __init__(self, momentum_window: int = 30, regression_window: int = 60):
        """
        Args:
            momentum_window: Days for ROC calculation
            regression_window: Days for linear regression slope
        """
        self.momentum_window = momentum_window
        self.regression_window = regression_window
        
    def calculate_momentum_score(self, df: pd.DataFrame) -> float:
        """
        Calculate composite momentum score.
        
        Formula:
        - 60% ROC (Rate of Change over momentum_window)
        - 40% Linear Regression Slope (over regression_window)
        
        Args:
            df: DataFrame with 'close' column
            
        Returns:
            Momentum score (higher = stronger)
        """
        if df is None or df.empty or len(df) < self.regression_window:
            return -999.0  # Invalid score
            
        try:
            close = df['close'].values
            
            # ROC Component (60%)
            if len(close) >= self.momentum_window:
                roc = (close[-1] - close[-self.momentum_window]) / close[-self.momentum_window]
            else:
                roc = 0.0
            
            # Linear Regression Slope Component (40%)
            x = np.arange(self.regression_window)
            y = close[-self.regression_window:]
            
            # Normalize slope by mean price to make it comparable across assets
            slope = np.polyfit(x, y, 1)[0]
            normalized_slope = slope / np.mean(y) if np.mean(y) > 0 else 0
            
            # Combined Score
            score = 0.6 * roc + 0.4 * normalized_slope
            
            return float(score)
            
        except Exception as e:
            print(f"Error calculating momentum score: {e}")
            return -999.0
    
    def check_ma200_filter(self, df: pd.DataFrame) -> bool:
        """
        Check if asset passes MA200 trend filter.
        
        Conditions:
        - Current price > MA200
        - MA200 slope > 0 (uptrend)
        
        Args:
            df: DataFrame with 'close' column
            
        Returns:
            True if passes filter, False otherwise
        """
        if df is None or df.empty or len(df) < 200:
            return False
            
        try:
            close = df['close'].values
            current_price = close[-1]
            
            # Calculate MA200
            ma_200 = np.mean(close[-200:])
            
            # Calculate MA200 slope (compare last 20 days avg vs previous 20)
            ma_200_recent = np.mean(close[-20:])
            ma_200_prev = np.mean(close[-40:-20])
            ma_200_slope = (ma_200_recent - ma_200_prev) / ma_200_prev if ma_200_prev > 0 else 0
            
            # Both conditions must be true
            passes = current_price > ma_200 and ma_200_slope > 0
            
            return passes
            
        except Exception as e:
            print(f"Error checking MA200 filter: {e}")
            return False
    
    def select_top_momentum(
        self, 
        data_dict: Dict[str, pd.DataFrame], 
        top_n: int = 3,
        require_ma200: bool = True
    ) -> Dict:
        """
        Main function: Rank assets and select Top N.
        
        Args:
            data_dict: {symbol: DataFrame} with OHLCV data
            top_n: Number of top assets to select
            require_ma200: If True, only select assets passing MA200 filter
            
        Returns:
            {
                "selected": ["BTC", "SOL", ...],
                "scores": {"BTC": 0.85, ...},
                "weights": {"BTC": 0.33, ...},
                "timestamp": "2026-01-03 14:35:00"
            }
        """
        if not data_dict:
            return {
                "selected": [],
                "scores": {},
                "weights": {},
                "timestamp": datetime.now().isoformat()
            }
        
        # Step 1: Calculate scores for all assets
        scores = {}
        for symbol, df in data_dict.items():
            score = self.calculate_momentum_score(df)
            
            # Apply MA200 filter if required
            if require_ma200:
                if not self.check_ma200_filter(df):
                    score = -999.0  # Disqualify
            
            scores[symbol] = score
        
        # Step 2: Rank by score (descending)
        ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        
        # Step 3: Select Top N (exclude invalid scores)
        valid_ranked = [(sym, score) for sym, score in ranked if score > -999.0]
        top_assets = valid_ranked[:top_n]
        
        if not top_assets:
            return {
                "selected": [],
                "scores": {},
                "weights": {},
                "timestamp": datetime.now().isoformat()
            }
        
        # Step 4: Calculate equal weights
        selected_symbols = [sym for sym, _ in top_assets]
        weight = 1.0 / len(selected_symbols)
        weights = {sym: weight for sym in selected_symbols}
        
        # Step 5: Build result
        result = {
            "selected": selected_symbols,
            "scores": {sym: score for sym, score in top_assets},
            "weights": weights,
            "timestamp": datetime.now().isoformat(),
            "total_candidates": len(data_dict),
            "valid_candidates": len(valid_ranked)
        }
        
        return result


# Singleton instance
momentum_scanner = MomentumScanner()
