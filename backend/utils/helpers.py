"""
Backend Helper Utilities
Common helper functions for JSON serialization and data processing
"""
import math
import numpy as np
import pandas as pd
from typing import Any, Dict, List, Union

def sanitize_for_json(obj: Any) -> Any:
    """
    Recursively sanitize an object for JSON serialization.
    Handles NaN, Infinity, NumPy types, and DataFrames.
    """
    if obj is None:
        return None
        
    if isinstance(obj, (int, bool, str)):
        return obj
        
    if isinstance(obj, float):
        if math.isnan(obj) or math.isinf(obj):
            return None
        return obj
        
    if isinstance(obj, (np.integer, np.int64, np.int32)):
        return int(obj)
        
    if isinstance(obj, (np.floating, np.float64, np.float32)):
        val = float(obj)
        if math.isnan(val) or math.isinf(val):
            return None
        return val
        
    if isinstance(obj, np.ndarray):
        return sanitize_for_json(obj.tolist())
        
    if isinstance(obj, pd.DataFrame):
        return sanitize_for_json(obj.to_dict(orient="records"))
        
    if isinstance(obj, pd.Series):
        return sanitize_for_json(obj.to_dict())
        
    if isinstance(obj, dict):
        return {str(k): sanitize_for_json(v) for k, v in obj.items()}
        
    if isinstance(obj, list):
        return [sanitize_for_json(item) for item in obj]
        
    # Fallback for unknown objects (try str)
    return str(obj)
