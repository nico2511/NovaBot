#!/usr/bin/env python3
"""
Backtest for Last 7 Days
Tests all active strategies on the past week of market data
"""
import pandas as pd
from app.services.hyperliquid_service import hyperliquid_service
from strategies.engine import StrategyEngine
from app.core.risk_manager import RiskManager
from datetime import datetime, timedelta

def run_7day_backtest(symbol="BTC"):
    print(f"🔄 Fetching last 7 days of data for {symbol}...")
    print(f"📅 Period: {(datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')} to {datetime.now().strftime('%Y-%m-%d')}")
    
    # Fetch data: 7 days = 7 * 96 = 672 x 15m candles
    df_15m = hyperliquid_service.get_candles(symbol, interval="15m", limit=800)
    df_1m = hyperliquid_service.get_candles(symbol, interval="1m", limit=10000)
    
    if df_15m.empty or df_1m.empty:
        print("❌ No data found.")
        return
    
    # Filter to last 7 days
    cutoff = datetime.now() - timedelta(days=7)
    df_15m = df_15m[df_15m.index >= cutoff]
    df_1m = df_1m[df_1m.index >= cutoff]
    
    print(f"✅ Loaded {len(df_15m)} x 15m candles and {len(df_1m)} x 1m candles")
    print(f"   Time range: {df_15m.index[0]} to {df_15m.index[-1]}")
    
    # Setup
    rm = RiskManager()
    engine = StrategyEngine(rm)
    
    # Simulation
    balance = 1000
    position = None
    trades = []
    daily_balances = {}  # Track balance by day
    
    print("🚀 Starting 7-Day Backtest...")
    print("-" * 60)
    
    min_window = 50
    
    for i in range(min_window, len(df_15m)):
        window_15m = df_15m.iloc[:i+1]
        current_candle = window_15m.iloc[-1]
        current_time = window_15m.index[-1]
        current_price = current_candle['close']
        current_date = current_time.date()
        
        # Track daily balance
        if current_date not in daily_balances:
            daily_balances[current_date] = balance
        
        # Get 1m data
        window_1m = df_1m[df_1m.index <= current_time].tail(100)
        
        # Exit logic
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
                daily_balances[current_date] = balance
                
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
                outcome = '✅' if pnl_percent > 0 else '❌'
                print(f"{outcome} {current_time.strftime('%m/%d %H:%M')} | {p['strategy'][:15]:15} | {p['side']:4} | PnL: {pnl_percent*100:6.2f}% | Balance: ${balance:.2f}")
                continue
        
        # Entry logic
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
                print(f"🎯 {current_time.strftime('%m/%d %H:%M')} | {position['strategy'][:15]:15} | {sig['signal']:4} @ ${entry:.0f}")
    
    # Report
    print("\n" + "="*70)
    print(f"📊 7-DAY BACKTEST REPORT - {symbol}")
    print("="*70)
    
    wins = [t for t in trades if t['pnl_usd'] > 0]
    losses = [t for t in trades if t['pnl_usd'] <= 0]
    
    total_trades = len(trades)
    win_rate = (len(wins) / total_trades * 100) if total_trades > 0 else 0
    final_pnl = balance - 1000
    
    avg_win = sum(t['pnl_usd'] for t in wins) / len(wins) if wins else 0
    avg_loss = sum(t['pnl_usd'] for t in losses) / len(losses) if losses else 0
    
    print(f"Period: {df_15m.index[0].strftime('%Y-%m-%d')} to {df_15m.index[-1].strftime('%Y-%m-%d')}")
    print(f"Total Trades: {total_trades}")
    print(f"Wins: {len(wins)} ({win_rate:.1f}%) | Losses: {len(losses)}")
    print(f"Average Win: ${avg_win:.2f} | Average Loss: ${avg_loss:.2f}")
    if avg_loss != 0:
        print(f"Win/Loss Ratio: {abs(avg_win/avg_loss):.2f}")
    print(f"\nInitial Balance: $1,000.00")
    print(f"Final Balance:   ${balance:.2f}")
    print(f"Net PnL:         ${final_pnl:.2f} ({(final_pnl/1000)*100:.2f}%)")
    print(f"Status: {'✅ PROFITABLE' if final_pnl > 0 else '❌ UNPROFITABLE'}")
    print("-" * 70)
    
    # Strategy breakdown
    if trades:
        print("\n📈 Strategy Performance:")
        strategy_stats = {}
        for t in trades:
            strat = t['strategy']
            if strat not in strategy_stats:
                strategy_stats[strat] = {'wins': 0, 'losses': 0, 'pnl': 0, 'trades': []}
            if t['outcome'] == 'WIN':
                strategy_stats[strat]['wins'] += 1
            else:
                strategy_stats[strat]['losses'] += 1
            strategy_stats[strat]['pnl'] += t['pnl_usd']
            strategy_stats[strat]['trades'].append(t)
        
        for strat, stats in sorted(strategy_stats.items(), key=lambda x: x[1]['pnl'], reverse=True):
            total = stats['wins'] + stats['losses']
            wr = (stats['wins'] / total * 100) if total > 0 else 0
            status = '✅' if stats['pnl'] > 0 else '❌'
            print(f"{status} {strat[:25]:25} | Trades: {total:2} | WR: {wr:5.1f}% | PnL: ${stats['pnl']:8.2f}")
    
    # Daily breakdown
    if daily_balances:
        print("\n📅 Daily Balance Evolution:")
        sorted_days = sorted(daily_balances.items())
        for date, bal in sorted_days:
            daily_pnl = bal - 1000
            print(f"   {date.strftime('%Y-%m-%d')} | Balance: ${bal:8.2f} | PnL: ${daily_pnl:7.2f}")
    
    # Best/Worst trades
    if trades:
        print("\n🏆 Best Trade:")
        best = max(trades, key=lambda x: x['pnl_usd'])
        print(f"   {best['entry_time'].strftime('%m/%d %H:%M')} | {best['strategy']} | {best['side']} | PnL: {best['pnl_pct']:.2f}% (${best['pnl_usd']:.2f})")
        
        print("\n💔 Worst Trade:")
        worst = min(trades, key=lambda x: x['pnl_usd'])
        print(f"   {worst['entry_time'].strftime('%m/%d %H:%M')} | {worst['strategy']} | {worst['side']} | PnL: {worst['pnl_pct']:.2f}% (${worst['pnl_usd']:.2f})")

if __name__ == "__main__":
    run_7day_backtest()
