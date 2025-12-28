#!/usr/bin/env python3
"""
Automated Backtesting for All Strategies
Compares performance across all available strategies

Requirements:
pip install backtesting pandas pandas-ta ccxt tabulate
"""

import ccxt
import pandas as pd
from datetime import datetime, timedelta
from backtesting import Backtest, Strategy
from backtesting.lib import crossover
import pandas_ta as ta
from tabulate import tabulate
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


# ============================================
# DATA FETCHING
# ============================================

def fetch_data(symbol='BTC/USDT', timeframe='15m', months=6, exchange_name='binance'):
    """Fetch historical OHLCV data"""
    print(f"📊 Fetching {months} months of {symbol} data ({timeframe})...")
    
    exchange_class = getattr(ccxt, exchange_name)
    exchange = exchange_class({'enableRateLimit': True})
    
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
            print(f"  Fetched {len(candles)} candles (Total: {len(all_candles)})", end='\r')
        except Exception as e:
            print(f"\n  Error: {e}")
            break
    
    df = pd.DataFrame(all_candles, columns=['timestamp', 'Open', 'High', 'Low', 'Close', 'Volume'])
    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
    df.set_index('timestamp', inplace=True)
    df = df[~df.index.duplicated(keep='first')]
    
    print(f"\n✅ Fetched {len(df)} candles from {df.index[0]} to {df.index[-1]}")
    return df


# ============================================
# STRATEGY IMPLEMENTATIONS
# ============================================

class GoldenCrossStrategy(Strategy):
    """Golden Cross: SMA 50/200 crossover"""
    
    def init(self):
        close = pd.Series(self.data.Close, index=self.data.index)
        self.sma_50 = self.I(ta.sma, close, length=50)
        self.sma_200 = self.I(ta.sma, close, length=200)
    
    def next(self):
        if len(self.data) < 201:
            return
        
        if self.position:
            # Exit LONG if price closes below SMA 50
            if self.position.is_long and self.data.Close[-1] < self.sma_50[-1]:
                self.position.close()
            # Exit SHORT if price closes above SMA 50
            elif self.position.is_short and self.data.Close[-1] > self.sma_50[-1]:
                self.position.close()
            return
        
        # Golden Cross: SMA 50 crosses above SMA 200
        if crossover(self.sma_50, self.sma_200):
            sl = self.sma_50[-1] * 0.97
            tp = self.data.Close[-1] * 1.10
            self.buy(sl=sl, tp=tp)
        
        # Death Cross: SMA 50 crosses below SMA 200
        elif crossover(self.sma_200, self.sma_50):
            sl = self.sma_50[-1] * 1.03
            tp = self.data.Close[-1] * 0.90
            self.sell(sl=sl, tp=tp)


class RSIReversalStrategy(Strategy):
    """RSI Reversal: Exit from extreme zones"""
    
    rsi_period = 14
    rsi_oversold = 30
    rsi_overbought = 70
    
    def init(self):
        close = pd.Series(self.data.Close, index=self.data.index)
        self.rsi = self.I(ta.rsi, close, length=self.rsi_period)
    
    def next(self):
        if len(self.data) < self.rsi_period + 1:
            return
        
        if self.position:
            return  # Let SL/TP handle exits
        
        current_rsi = self.rsi[-1]
        previous_rsi = self.rsi[-2]
        price = self.data.Close[-1]
        
        # LONG: RSI crosses above 30
        if previous_rsi < self.rsi_oversold and current_rsi > self.rsi_oversold:
            sl = price * 0.985
            tp = price * 1.030
            self.buy(sl=sl, tp=tp)
        
        # SHORT: RSI crosses below 70
        elif previous_rsi > self.rsi_overbought and current_rsi < self.rsi_overbought:
            sl = price * 1.015
            tp = price * 0.970
            self.sell(sl=sl, tp=tp)


class BollingerBreakoutStrategy(Strategy):
    """Bollinger Breakout: Momentum with impulsive candles"""
    
    bb_length = 20
    bb_std = 2.0
    
    def init(self):
        close = pd.Series(self.data.Close, index=self.data.index)
        
        # Bollinger Bands
        bbands = ta.bbands(close, length=self.bb_length, std=self.bb_std)
        self.bb_upper = self.I(lambda: bbands[f'BBU_{self.bb_length}_{self.bb_std}'].values)
        self.bb_middle = self.I(lambda: bbands[f'BBM_{self.bb_length}_{self.bb_std}'].values)
        self.bb_lower = self.I(lambda: bbands[f'BBL_{self.bb_length}_{self.bb_std}'].values)
        
        # Candle body
        body = abs(self.data.Close - self.data.Open)
        self.avg_body = self.I(lambda: pd.Series(body).rolling(10).mean().values)
    
    def next(self):
        if len(self.data) < 30:
            return
        
        if self.position:
            # Exit at middle band
            if self.position.is_long and self.data.Close[-1] <= self.bb_middle[-1]:
                self.position.close()
            elif self.position.is_short and self.data.Close[-1] >= self.bb_middle[-1]:
                self.position.close()
            return
        
        close = self.data.Close[-1]
        open_price = self.data.Open[-1]
        body = abs(close - open_price)
        
        # Check if impulsive
        if body <= self.avg_body[-1]:
            return
        
        # LONG: Green candle closes above upper band
        if close > open_price and close > self.bb_upper[-1]:
            sl = self.bb_middle[-1]
            tp = close + (close - self.bb_middle[-1]) * 1.5
            self.buy(sl=sl, tp=tp)
        
        # SHORT: Red candle closes below lower band
        elif close < open_price and close < self.bb_lower[-1]:
            sl = self.bb_middle[-1]
            tp = close - (self.bb_middle[-1] - close) * 1.5
            self.sell(sl=sl, tp=tp)


class ScalpEMAStrategy(Strategy):
    """Scalp EMA: Fast EMA crossover with trend filter"""
    
    def init(self):
        close = pd.Series(self.data.Close, index=self.data.index)
        self.ema_9 = self.I(ta.ema, close, length=9)
        self.ema_21 = self.I(ta.ema, close, length=21)
        self.ema_200 = self.I(ta.ema, close, length=200)
        self.rsi = self.I(ta.rsi, close, length=14)
    
    def next(self):
        if len(self.data) < 201:
            return
        
        if self.position:
            return  # Let SL/TP handle
        
        price = self.data.Close[-1]
        
        # LONG: EMA 9 crosses above EMA 21, price above EMA 200, RSI > 50
        if (crossover(self.ema_9, self.ema_21) and 
            price > self.ema_200[-1] and 
            self.rsi[-1] > 50):
            sl = price * 0.98
            tp = price * 1.04
            self.buy(sl=sl, tp=tp)
        
        # SHORT: EMA 9 crosses below EMA 21, price below EMA 200, RSI < 50
        elif (crossover(self.ema_21, self.ema_9) and 
              price < self.ema_200[-1] and 
              self.rsi[-1] < 50):
            sl = price * 1.02
            tp = price * 0.96
            self.sell(sl=sl, tp=tp)


# ============================================
# BACKTESTING ENGINE
# ============================================

def run_backtest(df, strategy_class, strategy_name, initial_cash=10000, commission=0.0006):
    """Run backtest for a single strategy"""
    print(f"\n{'='*60}")
    print(f"🧪 Testing: {strategy_name}")
    print(f"{'='*60}")
    
    try:
        bt = Backtest(
            df,
            strategy_class,
            cash=initial_cash,
            commission=commission,
            exclusive_orders=True
        )
        
        stats = bt.run()
        
        return {
            'Strategy': strategy_name,
            'Return %': f"{stats['Return [%]']:.2f}%",
            'Win Rate %': f"{stats['Win Rate [%]']:.2f}%",
            'Trades': stats['# Trades'],
            'Max DD %': f"{stats['Max. Drawdown [%]']:.2f}%",
            'Sharpe': f"{stats['Sharpe Ratio']:.2f}",
            'Final $': f"${stats['Equity Final [$]']:,.2f}",
            'Avg Trade %': f"{stats['Avg. Trade [%]']:.2f}%",
            'Best Trade %': f"{stats['Best Trade [%]']:.2f}%",
            'Worst Trade %': f"{stats['Worst Trade [%]']:.2f}%",
            '_stats': stats,
            '_bt': bt
        }
    except Exception as e:
        print(f"❌ Error: {e}")
        return {
            'Strategy': strategy_name,
            'Return %': 'ERROR',
            'Win Rate %': '-',
            'Trades': 0,
            'Max DD %': '-',
            'Sharpe': '-',
            'Final $': '-',
            'Avg Trade %': '-',
            'Best Trade %': '-',
            'Worst Trade %': '-',
            '_stats': None,
            '_bt': None
        }


# ============================================
# MAIN EXECUTION
# ============================================

if __name__ == "__main__":
    print("=" * 60)
    print("🚀 AUTOMATED STRATEGY BACKTESTING")
    print("=" * 60)
    
    # Configuration
    SYMBOL = 'BTC/USDT'
    TIMEFRAME = '15m'
    MONTHS = 6
    INITIAL_CASH = 10000
    COMMISSION = 0.0006
    
    # Fetch data once
    df = fetch_data(SYMBOL, TIMEFRAME, MONTHS, 'binance')
    
    # Define strategies to test
    strategies = [
        (GoldenCrossStrategy, "Golden Cross (SMA 50/200)"),
        (RSIReversalStrategy, "RSI Reversal (30/70)"),
        (BollingerBreakoutStrategy, "Bollinger Breakout"),
        (ScalpEMAStrategy, "Scalp EMA (9/21/200)"),
    ]
    
    # Run all backtests
    results = []
    for strategy_class, strategy_name in strategies:
        result = run_backtest(df, strategy_class, strategy_name, INITIAL_CASH, COMMISSION)
        results.append(result)
    
    # Display comparison table
    print("\n" + "=" * 60)
    print("📊 STRATEGY COMPARISON")
    print("=" * 60)
    
    # Summary table
    summary_headers = ['Strategy', 'Return %', 'Win Rate %', 'Trades', 'Sharpe', 'Max DD %']
    summary_data = [[r['Strategy'], r['Return %'], r['Win Rate %'], r['Trades'], r['Sharpe'], r['Max DD %']] 
                    for r in results]
    
    print("\n" + tabulate(summary_data, headers=summary_headers, tablefmt='grid'))
    
    # Detailed table
    print("\n" + "=" * 60)
    print("📈 DETAILED METRICS")
    print("=" * 60)
    
    detailed_headers = ['Strategy', 'Final $', 'Avg Trade %', 'Best Trade %', 'Worst Trade %']
    detailed_data = [[r['Strategy'], r['Final $'], r['Avg Trade %'], r['Best Trade %'], r['Worst Trade %']] 
                     for r in results]
    
    print("\n" + tabulate(detailed_data, headers=detailed_headers, tablefmt='grid'))
    
    # Find best strategy
    valid_results = [r for r in results if r['_stats'] is not None]
    if valid_results:
        best_strategy = max(valid_results, key=lambda x: x['_stats']['Return [%]'])
        
        print("\n" + "=" * 60)
        print("🏆 BEST PERFORMING STRATEGY")
        print("=" * 60)
        print(f"\n✨ {best_strategy['Strategy']}")
        print(f"   Return: {best_strategy['Return %']}")
        print(f"   Win Rate: {best_strategy['Win Rate %']}")
        print(f"   Sharpe Ratio: {best_strategy['Sharpe']}")
        print(f"   Total Trades: {best_strategy['Trades']}")
        
        # Ask if user wants to see the chart
        print("\n" + "=" * 60)
        print("📊 Would you like to see the interactive chart?")
        print("=" * 60)
        response = input("Open chart for best strategy? (y/n): ").lower()
        
        if response == 'y':
            print("\n🎨 Opening interactive chart...")
            best_strategy['_bt'].plot()
    
    print("\n✅ Backtesting complete!")
    print("=" * 60)
