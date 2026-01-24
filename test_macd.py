
import pandas as pd
import numpy as np
from app.services.indicators import ta

# Mock data
data = pd.DataFrame({'close': np.random.randn(100) + 100})

# Test MACD
macd = ta.macd(data['close'])
print("MACD Result Columns:", macd.columns)
print(macd.tail())
if not macd.empty and 'MACD' in macd.columns:
    print("MACD Test PASSED")
else:
    print("MACD Test FAILED")
