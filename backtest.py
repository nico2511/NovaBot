import pandas as pd
from app.services.hyperliquid_service import hyperliquid_service
from strategies.engine import StrategyEngine
import time

from app.core.risk_manager import RiskManager

def run_backtest(symbol="BTC", days=30):
    print(f"🔄 Fetching {days} days of data for {symbol}...")
    
    # 1. Fetch Data
    # 15m candles. 1 day = 96 candles. 30 days = 2880 candles.
    limit = days * 96 + 100 # +buffer
    df = hyperliquid_service.get_candles(symbol, limit=limit)
    
    if df.empty:
        print("❌ No data found.")
        return

    print(f"✅ Loaded {len(df)} candles. Time range: {df.index[0]} to {df.index[-1]}")
    
    # 2. Setup Engine
    rm = RiskManager()
    engine = StrategyEngine(rm)
    
    # 3. Simulation Loop
    balance = 1000 # Starting mock balance (USD)
    position = None # { 'entry': float, 'size': float, 'sl': float, 'tp': float, 'side': 'BUY'/'SELL' }
    trades = []
    
    print("🚀 Starting Simulation...")
    
    # We need a rolling window for indicators. 
    # The engine needs at least ~50-100 candles to compute indicators (EMA200 etc).
    min_window = 200
    
    for i in range(min_window, len(df)):
        # Current slice of data available at this moment in time
        # We index using .iloc to simulate "live" data arriving
        current_idx = df.index[i]
        
        # Optimization: We don't strictly need to pass the whole DF every time if functions utilize pandas_ta correctly,
        # but for safety and simplicity we pass the growing window or a sufficient tail.
        # Passing the full DF up to i is safer for accurate indicator calc.
        # However, engine.analyze takes "df" and calculates on the last row.
        # So we pass df.iloc[:i+1]
        
        window = df.iloc[:i+1]
        current_candle = window.iloc[-1]
        current_price = current_candle['close']
        
        # --- Trade Management (Exit) ---
        if position:
            p = position
            # Check SL/TP
            sl_hit = (p['side'] == 'BUY' and current_price <= p['sl']) or \
                     (p['side'] == 'SELL' and current_price >= p['sl'])
                     
            tp_hit = (p['side'] == 'BUY' and current_price >= p['tp']) or \
                     (p['side'] == 'SELL' and current_price <= p['tp'])
            
            if sl_hit or tp_hit:
                exit_price = p['sl'] if sl_hit else p['tp'] # Assume fill at limit
                # Refine: if High/Low broke it, assume fill at level. 
                # Ideally check High/Low of current candle.
                
                # Check specifics with High/Low for realism
                if p['side'] == 'BUY':
                    if current_candle['low'] <= p['sl']: exit_price = p['sl']; sl_hit = True; tp_hit = False
                    elif current_candle['high'] >= p['tp']: exit_price = p['tp']; tp_hit = True; sl_hit = False
                else: # SELL
                    if current_candle['high'] >= p['sl']: exit_price = p['sl']; sl_hit = True; tp_hit = False
                    elif current_candle['low'] <= p['tp']: exit_price = p['tp']; tp_hit = True; sl_hit = False
                
                if sl_hit or tp_hit:
                    pnl_percent = (exit_price - p['entry']) / p['entry'] if p['side'] == 'BUY' else (p['entry'] - exit_price) / p['entry']
                    pnl_usd = pnl_percent * balance # Compounding? Or fixed size? Let's use 100% equity for simplicity
                    
                    balance += pnl_usd
                    
                    trades.append({
                        'entry_time': p['time'],
                        'exit_time': current_idx,
                        'symbol': symbol,
                        'side': p['side'],
                        'entry': p['entry'],
                        'exit': exit_price,
                        'pnl_pct': pnl_percent * 100,
                        'pnl_usd': pnl_usd,
                        'outcome': 'WIN' if pnl_percent > 0 else 'LOSS',
                        'strategy': p['strategy']
                    })
                    position = None
                    continue # Trade closed, wait for next candle for new signals
        
        # --- Signal Finder (Entry) ---
        if not position:
             result = engine.analyze(window)
             if result.get("signals"):
                 sig = result["signals"][0]
                 
                 # Calc SL/TP if not present (fallback)
                 entry = sig['price']
                 sl = sig.get('sl', entry * 0.95)
                 tp = sig.get('tp', entry * 1.05)
                 
                 position = {
                     'time': current_idx,
                     'side': sig['signal'],
                     'entry': entry,
                     'sl': sl,
                     'tp': tp,
                     'strategy': sig.get('strategy', 'Unknown')
                 }

    # End of Simulation
    print("\n" + "="*40)
    print(f"📊 BACKTEST REPORT: {symbol}")
    print("="*40)
    
    wins = [t for t in trades if t['pnl_usd'] > 0]
    losses = [t for t in trades if t['pnl_usd'] <= 0]
    
    total_trades = len(trades)
    win_rate = (len(wins) / total_trades * 100) if total_trades > 0 else 0
    final_pnl = balance - 1000
    
    print(f"Period: {days} Days")
    print(f"Total Trades: {total_trades}")
    print(f"Win Rate: {win_rate:.2f}%")
    print(f"Status: {'PROFITABLE ✅' if final_pnl > 0 else 'UNPROFITABLE ❌'}")
    print(f"Initial Balance: $1000")
    print(f"Final Balance:   ${balance:.2f}")
    print(f"Net PnL:         ${final_pnl:.2f} ({(final_pnl/1000)*100:.2f}%)")
    print("-" * 40)
    
    if trades:
        print("\nLast 5 Trades:")
        for t in trades[-5:]:
            print(f"{t['entry_time']} | {t['side']} | PnL: {t['pnl_pct']:.2f}% ({t['outcome']}) | {t['strategy']}")

if __name__ == "__main__":
    run_backtest()
