#!/usr/bin/env python3
"""
Backtest for Yesterday (December 25, 2025)
Tests all active strategies on yesterday's market data
"""
import pandas as pd
from app.services.hyperliquid_service import hyperliquid_service
from strategies.engine import StrategyEngine
from app.core.risk_manager import RiskManager
from datetime import datetime, timedelta

def run_yesterday_backtest(symbol="BTC"):
    yesterday = (datetime.now() - timedelta(days=1)).date()
    print(f"🔄 Fetching yesterday's data for {symbol}...")
    print(f"📅 Date: {yesterday.strftime('%Y-%m-%d')}")
    
    # Fetch 15m and 1m data
    df_15m = hyperliquid_service.get_candles(symbol, interval="15m", limit=300)
    df_1m = hyperliquid_service.get_candles(symbol, interval="1m", limit=2000)
    
    if df_15m.empty or df_1m.empty:
        print("❌ No data found.")
        return
    
    # Filter to yesterday only
    df_15m = df_15m[df_15m.index.date == yesterday]
    df_1m = df_1m[df_1m.index.date == yesterday]
    
    print(f"✅ Loaded {len(df_15m)} x 15m candles and {len(df_1m)} x 1m candles for yesterday")
    print(f"   Time range: {df_15m.index[0]} to {df_15m.index[-1]}")
    
    # Setup Engine
    rm = RiskManager()
    engine = StrategyEngine(rm)
    
    # Simulation
    balance = 1000
    position = None
    trades = []
    
    print("🚀 Starting Backtest...")
    
    min_window = 50
    
    for i in range(min_window, len(df_15m)):
        window_15m = df_15m.iloc[:i+1]
        current_candle = window_15m.iloc[-1]
        current_time = window_15m.index[-1]
        current_price = current_candle['close']
        
        # Get corresponding 1m data
        window_1m = df_1m[df_1m.index <= current_time].tail(100)
        
        # Trade Management (Exit)
        if position:
            p = position
            sl_hit = (p['side'] == 'BUY' and current_candle['low'] <= p['sl']) or \
                     (p['side'] == 'SELL' and current_candle['high'] >= p['sl'])
            tp_hit = (p['side'] == 'BUY' and current_candle['high'] >= p['tp']) or \
                     (p['side'] == 'SELL' and current_candle['low'] <= p['tp'])
            
            if sl_hit or tp_hit:
                exit_price = p['sl'] if sl_hit else p['tp']
                pnl_percent = (exit_price - p['entry']) / p['entry'] if p['side'] == 'BUY' else (p['entry'] - exit_price) / p['entry']
                pnl_usd = pnl_percent * balance
                
                balance += pnl_usd
                
                trades.append({
                    'entry_time': p['time'],
                    'exit_time': current_time,
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
                print(f"   {'✅' if pnl_percent > 0 else '❌'} {p['strategy']}: {p['side']} closed at {exit_price:.2f} | PnL: {pnl_percent*100:.2f}%")
                continue
        
        # Signal Finder (Entry)
        if not position:
            result = engine.analyze(window_15m, extra_data={"1m": window_1m})
            
            if result.get("signals"):
                sig = result["signals"][0]
                entry = sig['price']
                sl = sig.get('sl', entry * 0.98)
                tp = sig.get('tp', entry * 1.02)
                
                position = {
                    'time': current_time,
                    'side': sig['signal'],
                    'entry': entry,
                    'sl': sl,
                    'tp': tp,
                    'strategy': sig.get('strategy', 'Unknown')
                }
                print(f"   🎯 {position['strategy']}: {sig['signal']} @ {entry:.2f} (SL: {sl:.2f}, TP: {tp:.2f})")
    
    # Report
    print("\n" + "="*60)
    print(f"📊 BACKTEST REPORT - {symbol} - {yesterday.strftime('%Y-%m-%d')}")
    print("="*60)
    
    wins = [t for t in trades if t['pnl_usd'] > 0]
    losses = [t for t in trades if t['pnl_usd'] <= 0]
    
    total_trades = len(trades)
    win_rate = (len(wins) / total_trades * 100) if total_trades > 0 else 0
    final_pnl = balance - 1000
    
    print(f"Period: Yesterday ({yesterday.strftime('%Y-%m-%d')})")
    print(f"Total Trades: {total_trades}")
    print(f"Wins: {len(wins)} | Losses: {len(losses)}")
    print(f"Win Rate: {win_rate:.2f}%")
    print(f"Initial Balance: $1000.00")
    print(f"Final Balance:   ${balance:.2f}")
    print(f"Net PnL:         ${final_pnl:.2f} ({(final_pnl/1000)*100:.2f}%)")
    print(f"Status: {'PROFITABLE ✅' if final_pnl > 0 else 'UNPROFITABLE ❌'}")
    print("-" * 60)
    
    if trades:
        print("\n📋 All Trades:")
        for i, t in enumerate(trades, 1):
            outcome_icon = '✅' if t['outcome'] == 'WIN' else '❌'
            print(f"{i}. {outcome_icon} {t['entry_time'].strftime('%H:%M')} | {t['strategy'][:20]:20} | "
                  f"{t['side']:4} @ {t['entry']:8.2f} → {t['exit']:8.2f} | "
                  f"PnL: {t['pnl_pct']:6.2f}% (${t['pnl_usd']:7.2f})")
    else:
        print("\n⚠️ No trades executed yesterday")
    
    # Strategy breakdown
    if trades:
        print("\n📈 Strategy Performance:")
        strategy_stats = {}
        for t in trades:
            strat = t['strategy']
            if strat not in strategy_stats:
                strategy_stats[strat] = {'wins': 0, 'losses': 0, 'pnl': 0}
            if t['outcome'] == 'WIN':
                strategy_stats[strat]['wins'] += 1
            else:
                strategy_stats[strat]['losses'] += 1
            strategy_stats[strat]['pnl'] += t['pnl_usd']
        
        for strat, stats in strategy_stats.items():
            total = stats['wins'] + stats['losses']
            wr = (stats['wins'] / total * 100) if total > 0 else 0
            print(f"   {strat[:30]:30} | Trades: {total:2} | WR: {wr:5.1f}% | PnL: ${stats['pnl']:7.2f}")

if __name__ == "__main__":
    run_yesterday_backtest()
