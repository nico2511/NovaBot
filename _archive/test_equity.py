from app.core.trade_recorder import TradeRecorder
import pandas as pd
import os

print(f"Current CWD: {os.getcwd()}")


# Mimic _read_csv_safe with engine='python'
headers = [
    "timestamp", "symbol", "side", "entry_price", "exit_price", 
    "size", "pnl", "strategy", "exit_reason", "leverage",
    "entry_regime", "entry_adx", "entry_rsi", "entry_ema20", "entry_ema50",
    "entry_volume_ratio", "ai_confidence", "ai_reasoning"
]

print("Testing read_csv with engine='python'...")
# csv_file = "data/trade_history.csv"
recorder = TradeRecorder()

try:
    df = pd.read_csv(recorder.csv_file, names=headers, header=None, skiprows=1, engine='python')
    print("✅ Success! Rows:", len(df))
    print("Columns:", len(df.columns))
    if not df.empty:
        print("Last row PnL:", df.iloc[-1]['pnl'])
        
    # Original test
    curve = recorder.get_equity_curve() 
    print("✅ Equity Curve Points:", len(curve))
    if curve:
        print("First:", curve[0])
        print("Last:", curve[-1])
except Exception as e:
    print(f"❌ Error: {e}")
