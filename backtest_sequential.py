#!/usr/bin/env python3
"""
Sequential Strategy Backtesting with Final Report
Tests each strategy one by one with detailed progress
"""

import ccxt
import pandas as pd
from datetime import datetime, timedelta
from backtesting import Backtest, Strategy
from backtesting.lib import crossover
import pandas_ta as ta
from tabulate import tabulate
import json


# ============================================
# DATA FETCHING
# ============================================

def fetch_data(symbol='BTC/USDT', timeframe='15m', months=6):
    """Fetch historical data"""
    print(f"\n📊 Fetching {months} months of {symbol} ({timeframe})...")
    
    exchange = ccxt.binance({'enableRateLimit': True})
    now = datetime.now()
    start_date = now - timedelta(days=months * 30)
    start_timestamp = int(start_date.timestamp() * 1000)
    
    all_candles = []
    current_timestamp = start_timestamp
    
    while current_timestamp < int(now.timestamp() * 1000):
        try:
            candles = exchange.fetch_ohlcv(symbol, timeframe=timeframe, since=current_timestamp, limit=1000)
            if not candles:
                break
            all_candles.extend(candles)
            current_timestamp = candles[-1][0] + 1
            print(f"  Progress: {len(all_candles)} candles", end='\r')
        except Exception as e:
            print(f"\n  Error: {e}")
            break
    
    df = pd.DataFrame(all_candles, columns=['timestamp', 'Open', 'High', 'Low', 'Close', 'Volume'])
    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
    df.set_index('timestamp', inplace=True)
    df = df[~df.index.duplicated(keep='first')]
    
    print(f"\n✅ Loaded {len(df)} candles ({df.index[0].date()} to {df.index[-1].date()})")
    return df


# ============================================
# STRATEGIES
# ============================================

class GoldenCrossStrategy(Strategy):
    def init(self):
        close = pd.Series(self.data.Close, index=self.data.index)
        self.sma_50 = self.I(ta.sma, close, length=50)
        self.sma_200 = self.I(ta.sma, close, length=200)
    
    def next(self):
        if len(self.data) < 201 or self.position:
            return
        
        # Use size parameter to control position size (10% of equity)
        if crossover(self.sma_50, self.sma_200):
            self.buy(size=0.1)
        elif crossover(self.sma_200, self.sma_50):
            self.sell(size=0.1)


class RSIReversalStrategy(Strategy):
    rsi_period = 14
    
    def init(self):
        close = pd.Series(self.data.Close, index=self.data.index)
        self.rsi = self.I(ta.rsi, close, length=self.rsi_period)
    
    def next(self):
        if len(self.data) < self.rsi_period + 1 or self.position:
            return
        
        current_rsi = self.rsi[-1]
        previous_rsi = self.rsi[-2]
        
        if previous_rsi < 30 and current_rsi > 30:
            self.buy(size=0.1)
        elif previous_rsi > 70 and current_rsi < 70:
            self.sell(size=0.1)


class BollingerBreakoutStrategy(Strategy):
    bb_length = 20
    bb_std = 2.0
    
    def init(self):
        close = pd.Series(self.data.Close, index=self.data.index)
        bbands = ta.bbands(close, length=self.bb_length, std=self.bb_std)
        self.bb_upper = self.I(lambda: bbands[f'BBU_{self.bb_length}_{self.bb_std}'].values)
        self.bb_lower = self.I(lambda: bbands[f'BBL_{self.bb_length}_{self.bb_std}'].values)
    
    def next(self):
        if len(self.data) < 30 or self.position:
            return
        
        close = self.data.Close[-1]
        open_price = self.data.Open[-1]
        
        if close > open_price and close > self.bb_upper[-1]:
            self.buy(size=0.1)
        elif close < open_price and close < self.bb_lower[-1]:
            self.sell(size=0.1)


class ScalpEMAStrategy(Strategy):
    def init(self):
        close = pd.Series(self.data.Close, index=self.data.index)
        self.ema_9 = self.I(ta.ema, close, length=9)
        self.ema_21 = self.I(ta.ema, close, length=21)
        self.ema_200 = self.I(ta.ema, close, length=200)
        self.rsi = self.I(ta.rsi, close, length=14)
    
    def next(self):
        if len(self.data) < 201 or self.position:
            return
        
        price = self.data.Close[-1]
        
        if (crossover(self.ema_9, self.ema_21) and 
            price > self.ema_200[-1] and 
            self.rsi[-1] > 50):
            self.buy(size=0.1)
        elif (crossover(self.ema_21, self.ema_9) and 
              price < self.ema_200[-1] and 
              self.rsi[-1] < 50):
            self.sell(size=0.1)


# ============================================
# BACKTESTING
# ============================================

def run_single_backtest(df, strategy_class, strategy_name, config):
    """Run backtest for one strategy"""
    print(f"\n{'='*70}")
    print(f"🧪 Testing: {strategy_name}")
    print(f"{'='*70}")
    
    try:
        bt = Backtest(
            df,
            strategy_class,
            cash=config['cash'],
            commission=config['commission'],
            exclusive_orders=True
        )
        
        print("   Running backtest...")
        stats = bt.run()
        
        # Extract key metrics
        result = {
            'name': strategy_name,
            'return_pct': stats['Return [%]'],
            'win_rate': stats['Win Rate [%]'],
            'trades': stats['# Trades'],
            'max_dd': stats['Max. Drawdown [%]'],
            'sharpe': stats['Sharpe Ratio'],
            'final_equity': stats['Equity Final [$]'],
            'avg_trade': stats['Avg. Trade [%]'],
            'best_trade': stats['Best Trade [%]'],
            'worst_trade': stats['Worst Trade [%]'],
            'buy_hold': stats['Buy & Hold Return [%]'],
            'duration': str(stats['Duration']),
            'stats': stats,
            'bt': bt
        }
        
        # Display summary
        print(f"\n   ✅ Results:")
        print(f"      Return:        {result['return_pct']:.2f}%")
        print(f"      Win Rate:      {result['win_rate']:.2f}%")
        print(f"      Trades:        {result['trades']}")
        print(f"      Sharpe:        {result['sharpe']:.2f}")
        print(f"      Max Drawdown:  {result['max_dd']:.2f}%")
        
        return result
        
    except Exception as e:
        print(f"\n   ❌ Error: {e}")
        return {
            'name': strategy_name,
            'return_pct': 0,
            'win_rate': 0,
            'trades': 0,
            'max_dd': 0,
            'sharpe': 0,
            'final_equity': config['cash'],
            'avg_trade': 0,
            'best_trade': 0,
            'worst_trade': 0,
            'buy_hold': 0,
            'duration': '-',
            'error': str(e),
            'stats': None,
            'bt': None
        }


# ============================================
# REPORT GENERATION
# ============================================

def generate_final_report(results, config):
    """Generate comprehensive final report"""
    print("\n" + "="*70)
    print("📊 FINAL BACKTEST REPORT")
    print("="*70)
    
    # Configuration
    print(f"\n⚙️  Configuration:")
    print(f"   Symbol:          {config['symbol']}")
    print(f"   Timeframe:       {config['timeframe']}")
    print(f"   Period:          {config['months']} months")
    print(f"   Initial Capital: ${config['cash']:,}")
    print(f"   Commission:      {config['commission']*100:.2f}%")
    
    # Summary Table
    print("\n" + "="*70)
    print("📈 PERFORMANCE SUMMARY")
    print("="*70)
    
    summary_data = []
    for r in results:
        summary_data.append([
            r['name'],
            f"{r['return_pct']:.2f}%",
            f"{r['win_rate']:.2f}%",
            r['trades'],
            f"{r['sharpe']:.2f}",
            f"{r['max_dd']:.2f}%"
        ])
    
    print("\n" + tabulate(
        summary_data,
        headers=['Strategy', 'Return %', 'Win Rate %', 'Trades', 'Sharpe', 'Max DD %'],
        tablefmt='grid'
    ))
    
    # Detailed Metrics
    print("\n" + "="*70)
    print("📊 DETAILED METRICS")
    print("="*70)
    
    detailed_data = []
    for r in results:
        detailed_data.append([
            r['name'],
            f"${r['final_equity']:,.2f}",
            f"{r['avg_trade']:.2f}%",
            f"{r['best_trade']:.2f}%",
            f"{r['worst_trade']:.2f}%"
        ])
    
    print("\n" + tabulate(
        detailed_data,
        headers=['Strategy', 'Final Equity', 'Avg Trade %', 'Best Trade %', 'Worst Trade %'],
        tablefmt='grid'
    ))
    
    # Rankings
    print("\n" + "="*70)
    print("🏆 RANKINGS")
    print("="*70)
    
    # Best Return
    best_return = max(results, key=lambda x: x['return_pct'])
    print(f"\n🥇 Best Return:     {best_return['name']} ({best_return['return_pct']:.2f}%)")
    
    # Best Win Rate
    best_winrate = max(results, key=lambda x: x['win_rate'] if x['trades'] > 0 else 0)
    print(f"🎯 Best Win Rate:   {best_winrate['name']} ({best_winrate['win_rate']:.2f}%)")
    
    # Best Sharpe
    best_sharpe = max(results, key=lambda x: x['sharpe'] if not pd.isna(x['sharpe']) else -999)
    print(f"📊 Best Sharpe:     {best_sharpe['name']} ({best_sharpe['sharpe']:.2f})")
    
    # Most Active
    most_trades = max(results, key=lambda x: x['trades'])
    print(f"🔄 Most Trades:     {most_trades['name']} ({most_trades['trades']} trades)")
    
    # Comparison with Buy & Hold
    print("\n" + "="*70)
    print("📉 VS BUY & HOLD")
    print("="*70)
    
    buy_hold = results[0]['buy_hold'] if results else 0
    print(f"\nBuy & Hold Return: {buy_hold:.2f}%\n")
    
    for r in results:
        diff = r['return_pct'] - buy_hold
        symbol = "✅" if diff > 0 else "❌"
        print(f"{symbol} {r['name']:30} {diff:+.2f}% vs B&H")
    
    # Save to JSON
    report_file = 'backtest_report.json'
    report_data = {
        'config': config,
        'timestamp': datetime.now().isoformat(),
        'results': [{k: v for k, v in r.items() if k not in ['stats', 'bt']} for r in results]
    }
    
    with open(report_file, 'w') as f:
        json.dump(report_data, f, indent=2)
    
    print(f"\n💾 Report saved to: {report_file}")
    print("\n" + "="*70)


# ============================================
# MAIN
# ============================================

if __name__ == "__main__":
    print("="*70)
    print("🚀 SEQUENTIAL STRATEGY BACKTESTING")
    print("="*70)
    
    # Configuration
    config = {
        'symbol': 'BTC/USDT',
        'timeframe': '15m',
        'months': 6,
        'cash': 10000,
        'commission': 0.0006
    }
    
    # Fetch data once
    df = fetch_data(config['symbol'], config['timeframe'], config['months'])
    
    # Define strategies
    strategies = [
        (GoldenCrossStrategy, "Golden Cross (SMA 50/200)"),
        (RSIReversalStrategy, "RSI Reversal (30/70)"),
        (BollingerBreakoutStrategy, "Bollinger Breakout"),
        (ScalpEMAStrategy, "Scalp EMA (9/21/200)"),
    ]
    
    # Run backtests sequentially
    results = []
    for i, (strategy_class, strategy_name) in enumerate(strategies, 1):
        print(f"\n[{i}/{len(strategies)}]", end=" ")
        result = run_single_backtest(df, strategy_class, strategy_name, config)
        results.append(result)
    
    # Generate final report
    generate_final_report(results, config)
    
    print("\n✅ All backtests complete!")
