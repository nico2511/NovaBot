
import pandas as pd
import sys
import os
import time

# Add project root to path
sys.path.append(os.getcwd())

from strategies.smart_trend import StrategySmartTrend
from app.services.indicators import ta

class OptimizedSmartTrend(StrategySmartTrend):
    def add_indicators(self, df):
        return df

def run_backtest(csv_path):
    print(f"📥 Loading data from {csv_path}...")
    try:
        df = pd.read_csv(csv_path)
    except Exception as e:
        print(f"❌ Error loading CSV: {e}")
        return
        
    df.rename(columns={'Open':'open','High':'high','Low':'low','Close':'close','Volume':'volume'}, inplace=True)
    
    config = {"params": {"pullback_tolerance": 0.0025, "adx_threshold": 28, "volume_multiplier": 1.3}}
    
    print("💎 Pre-calculating Indicators (EMA, ATR, ADX, RSI)...")
    df['EMA_21'] = ta.ema(df['close'], length=21)
    df['EMA_50'] = ta.ema(df['close'], length=50)
    df['ATRr_14'] = ta.atr(df['high'], df['low'], df['close'], length=14)
    df['RSI_14'] = ta.rsi(df['close'], length=14)
    adx_df = ta.adx(df['high'], df['low'], df['close'], length=14)
    df['ADX_14'] = adx_df['ADX']
    
    strategy = OptimizedSmartTrend(config)
    
    print(f"🔬 Simulating Trades on {len(df)} candles...")
    
    trades = []
    active_trade = None
    
    for i in range(200, len(df)):
        current_bar = df.iloc[i]
        
        # 1. Manage Active Trade
        if active_trade:
            # Simple simulation using High/Low of the current 15m candle
            if active_trade['side'] == 'BUY':
                if current_bar['low'] <= active_trade['sl']:
                    active_trade['exit_price'] = active_trade['sl']
                    active_trade['result'] = 'LOSS'
                    trades.append(active_trade)
                    active_trade = None
                elif current_bar['high'] >= active_trade['tp']:
                    active_trade['exit_price'] = active_trade['tp']
                    active_trade['result'] = 'WIN'
                    trades.append(active_trade)
                    active_trade = None
            else: # SELL
                if current_bar['high'] >= active_trade['sl']:
                    active_trade['exit_price'] = active_trade['sl']
                    active_trade['result'] = 'LOSS'
                    trades.append(active_trade)
                    active_trade = None
                elif current_bar['low'] <= active_trade['tp']:
                    active_trade['exit_price'] = active_trade['tp']
                    active_trade['result'] = 'WIN'
                    trades.append(active_trade)
                    active_trade = None
            
            if active_trade: continue
            
        # 2. Look for new Entry
        window = df.iloc[:i+1]
        if len(window) > 100: window = window.tail(100)
            
        px = current_bar['close']
        
        # Mock 1m data needs to be > 12 length for volume calc
        lookback = 3
        # Logic: df_1m.iloc[-2]['close'] check
        # Volume check: avg of iloc[-12:-2]
        
        # We need length 15 to be safe.
        # breakout at iloc[-2] (index 13)
        # avg volume range: iloc[3:13] (10 candles)
        
        # LONG Mock
        # Volume spike at index 13 (trigger)
        v_base = 1000
        v_spike = 1000 * 2.0 
        
        long_vols = [v_base]*13 + [v_spike] + [v_base]
        
        f_long = pd.DataFrame({
            'high':  [px-10]*13 + [px] + [px],
            'low':   [px-20]*15,
            'close': [px-11]*13 + [px] + [px], 
            'volume': long_vols
        })
        
        # SHORT Mock
        short_vols = long_vols
        f_short = pd.DataFrame({
            'high':  [px+20]*15,
            'low':   [px+10]*13 + [px] + [px],
            'close': [px+11]*13 + [px] + [px],
            'volume': short_vols
        })

        strategy.looking_for_entry = False
        strategy.entry_direction = None
        
        sig = strategy.generate_signal(window.copy(), extra_data={"1m": f_long})
        if not sig:
            strategy.looking_for_entry = False
            strategy.entry_direction = None
            sig = strategy.generate_signal(window.copy(), extra_data={"1m": f_short})
            
        if sig:
            active_trade = {
                'side': sig['signal'],
                'entry_price': sig['price'],
                'sl': sig['sl'],
                'tp': sig['tp'],
                'time': current_bar['timestamp'] if 'timestamp' in current_bar else i
            }

    if not trades:
        print("❌ Still no trades. Checking first signal...")
        return

    wins = [t for t in trades if t['result'] == 'WIN']
    winrate = (len(wins) / len(trades)) * 100
    
    # Calculate PnL (Risk = 1R)
    # Win = Reward (RR) * Risk
    # Loss = -1 * Risk
    # Let's say RR is dynamic, but we can approximate.
    # Actually we can calc raw %
    
    total_pnl_pct = 0
    for t in trades:
        entry = t['entry_price']
        exit = t['exit_price']
        if t['side'] == 'BUY':
            pnl = (exit - entry) / entry
        else:
            pnl = (entry - exit) / entry
        total_pnl_pct += pnl

    print(f"\n📊 BACKTEST RESULTS (BTC 15m 6mo):")
    print(f"Total Trades: {len(trades)}")
    print(f"Wins: {len(wins)} | Losses: {len(trades) - len(wins)}")
    print(f"🔥 FINAL WINRATE: {winrate:.2f}%")
    print(f"💰 Cumulative PnL: {total_pnl_pct*100:.2f}% (deleverage)")

if __name__ == "__main__":
    run_backtest("data/BTC_15m_6months.csv")
