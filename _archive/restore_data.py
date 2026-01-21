from app.core.trade_recorder import TradeRecorder
import random
from datetime import datetime, timedelta

recorder = TradeRecorder()

print(f"Injecting dummy trades into {recorder.csv_file}...")

trades = []
base_time = datetime.now() - timedelta(days=5)
balance = 1000

for i in range(10):
    pnl = random.uniform(-50, 80)
    balance += pnl
    
    trade = {
        "symbol": "BTC",
        "side": "BUY" if random.random() > 0.5 else "SELL",
        "entry_price": 50000 + random.uniform(-1000, 1000),
        "exit_price": 50000 + random.uniform(-1000, 1000),
        "size": 0.1,
        "pnl": pnl,
        "strategy": "smart_trend",
        "exit_reason": "TP_HIT" if pnl > 0 else "SL_HIT",
        "leverage": 1,
        # Indicators
        "regime": "TREND",
        "adx": 25 + i,
        "rsi": 50 + i,
        "ema_20": 49000,
        "ema_50": 48000,
        "volume_ratio": 1.2,
        "ai_confidence": 85,
        "ai_reasoning": "Mock trade for chart testing"
    }
    
    # We cheat and use internal record logic but we need to supply timestamp manually if we want past history
    # Converting internal _record to accept timestamp override would be invasive.
    # Instead, we construct the row manually matching headers.
    
    row = [
        (base_time + timedelta(hours=i*12)).isoformat(),
        trade["symbol"], trade["side"], trade["entry_price"], trade["exit_price"],
        trade["size"], trade["pnl"], trade["strategy"], trade["exit_reason"], trade["leverage"],
        trade["regime"], trade["adx"], trade["rsi"], trade["ema_20"], trade["ema_50"],
        trade["volume_ratio"], trade["ai_confidence"], trade["ai_reasoning"]
    ]
    
    import csv
    with open(recorder.csv_file, 'a', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(row)

print("✅ Injected 10 trades.")
