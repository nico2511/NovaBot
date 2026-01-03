"""
Quick Backtest for BTC and DOGE
Tests enabled strategies using current architecture
"""
import sys
import pandas as pd
import json
from datetime import datetime, timedelta

# Import services
from app.services.hyperliquid_service import hyperliquid_service
from strategies.engine import StrategyEngine
from app.core.risk_manager import RiskManager

def simple_backtest(symbol: str, days: int = 30):
    """Run a simple backtest on a symbol"""
    print(f"\n{'='*60}")
    print(f"🧪 BACKTESTING: {symbol} (Last {days} days)")
    print(f"{'='*60}\n")
    
    # Load strategies
    with open("strategies.json", "r") as f:
        config = json.load(f)
    
    # Initialize
    strategy_engine = StrategyEngine(config)
    risk_manager = RiskManager(max_positions=1, daily_stop_loss=50.0)
    
    # Fetch historical data
    print(f"📊 Fetching {days} days of 15m data for {symbol}...")
    df = hyperliquid_service.get_candles(symbol, "15m", limit=days*96)  # 96 candles per day
    
    if df is None or df.empty:
        print(f"❌ Failed to fetch data for {symbol}")
        return None
    
    print(f"✅ Loaded {len(df)} candles")
    print(f"📅 Period: {df.index[0]} → {df.index[-1]}")
    
    # Simple simulation
    balance = 1000.0
    trades = []
    position = None
    
    for i in range(50, len(df)):  # Start after warmup
        current_candle = df.iloc[i]
        df_slice = df.iloc[:i+1]
        
        # Check if we have a position
        if position:
            # Check SL/TP
            current_price = current_candle['close']
            
            if position['side'] == 'BUY':
                if current_price <= position['sl']:
                    # Stop Loss hit
                    pnl = (position['sl'] - position['entry']) * position['size']
                    balance += pnl
                    trades.append({'pnl': pnl, 'exit': 'SL'})
                    position = None
                elif current_price >= position['tp']:
                    # Take Profit hit
                    pnl = (position['tp'] - position['entry']) * position['size']
                    balance += pnl
                    trades.append({'pnl': pnl, 'exit': 'TP'})
                    position = None
            else:  # SELL
                if current_price >= position['sl']:
                    pnl = (position['entry'] - position['sl']) * position['size']
                    balance += pnl
                    trades.append({'pnl': pnl, 'exit': 'SL'})
                    position = None
                elif current_price <= position['tp']:
                    pnl = (position['entry'] - position['tp']) * position['size']
                    balance += pnl
                    trades.append({'pnl': pnl, 'exit': 'TP'})
                    position = None
        
        # Generate signals if no position
        if not position:
            try:
                result = strategy_engine.analyze(df_slice)  # FIX: Don't pass symbol
                print(f"[DEBUG] Strategy result: {result}")  # DEBUG
                
                # FIX: strategy_engine returns {'signals': [...]} not {'signal': '...'}
                signals_list = result.get('signals', []) if result else []
                
                if signals_list:
                    # Take the first signal
                    signal_data = signals_list[0]
                    signal = signal_data.get('signal')
                    
                    if signal and signal != 'HOLD':
                        entry_price = current_candle['close']
                        
                        # Simple position sizing
                        size = (balance * 0.1) / entry_price  # 10% of balance
                        
                        # Use SL/TP from signal if available, otherwise default
                        sl = signal_data.get('sl', entry_price * 0.95 if signal == 'BUY' else entry_price * 1.05)
                        tp = signal_data.get('tp', entry_price * 1.10 if signal == 'BUY' else entry_price * 0.90)
                        
                        position = {
                            'side': signal,
                            'entry': entry_price,
                            'sl': sl,
                            'tp': tp,
                            'size': size
                        }
                        print(f"[{df.index[i]}] 🚀 {signal} @ ${entry_price:.2f} (Strategy: {signal_data.get('strategy', 'Unknown')})")
            except Exception as e:
                print(f"⚠️ Strategy error at candle {i}: {e}")
                import traceback
                traceback.print_exc()
    
    # Close final position if any
    if position:
        final_price = df.iloc[-1]['close']
        if position['side'] == 'BUY':
            pnl = (final_price - position['entry']) * position['size']
        else:
            pnl = (position['entry'] - final_price) * position['size']
        balance += pnl
        trades.append({'pnl': pnl, 'exit': 'EOD'})
    
    # Calculate stats
    total_pnl = balance - 1000.0
    roi = (total_pnl / 1000.0) * 100
    winning_trades = len([t for t in trades if t['pnl'] > 0])
    losing_trades = len([t for t in trades if t['pnl'] < 0])
    win_rate = (winning_trades / len(trades) * 100) if trades else 0
    
    results = {
        'symbol': symbol,
        'initial_balance': 1000.0,
        'final_balance': balance,
        'total_pnl': total_pnl,
        'roi': roi,
        'total_trades': len(trades),
        'winning_trades': winning_trades,
        'losing_trades': losing_trades,
        'win_rate': win_rate
    }
    
    # Display
    print(f"\n{'='*60}")
    print(f"📈 RESULTS: {symbol}")
    print(f"{'='*60}")
    print(f"Initial Balance: ${results['initial_balance']:.2f}")
    print(f"Final Balance:   ${results['final_balance']:.2f}")
    print(f"Total PnL:       ${results['total_pnl']:.2f}")
    print(f"ROI:             {results['roi']:.2f}%")
    print(f"Total Trades:    {results['total_trades']}")
    print(f"Winning Trades:  {results['winning_trades']}")
    print(f"Losing Trades:   {results['losing_trades']}")
    print(f"Win Rate:        {results['win_rate']:.2f}%")
    print(f"{'='*60}\n")
    
    return results

def main():
    symbols = ["BTC", "DOGE"]
    all_results = {}
    
    for symbol in symbols:
        try:
            results = simple_backtest(symbol, days=30)
            if results:
                all_results[symbol] = results
        except Exception as e:
            print(f"❌ Error backtesting {symbol}: {e}")
            import traceback
            traceback.print_exc()
    
    # Summary
    print(f"\n{'='*60}")
    print("📊 BACKTEST SUMMARY")
    print(f"{'='*60}")
    for symbol, results in all_results.items():
        roi = results.get('roi', 0)
        trades = results.get('total_trades', 0)
        win_rate = results.get('win_rate', 0)
        emoji = "✅" if roi > 0 else "❌" if roi < 0 else "➖"
        print(f"{emoji} {symbol:8s} | ROI: {roi:+7.2f}% | Trades: {trades:3d} | Win Rate: {win_rate:5.1f}%")
    print(f"{'='*60}\n")
    
    # Save
    with open("backtest_results_multi.json", "w") as f:
        json.dump(all_results, f, indent=2)
    print("💾 Results saved to: backtest_results_multi.json")

if __name__ == "__main__":
    main()
