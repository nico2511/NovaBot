#!/usr/bin/env python3
"""
Backtesting Script for RSI Reversal Strategy
Using backtesting.py library

Requirements:
pip install backtesting pandas pandas-ta ccxt
"""

import ccxt
import pandas as pd
from datetime import datetime, timedelta
from backtesting import Backtest, Strategy
from backtesting.lib import crossover
import pandas_ta as ta


# ============================================
# DATA FETCHING
# ============================================

def fetch_data(symbol='BTC/USDT', timeframe='15m', months=6, exchange_name='binance'):
    """
    Fetch historical OHLCV data for the specified period.
    
    Args:
        symbol: Trading pair (e.g., 'BTC/USDT')
        timeframe: Candle timeframe (e.g., '15m', '1h')
        months: Number of months of historical data
        exchange_name: Exchange to use ('binance', 'kucoin', etc.)
    
    Returns:
        pandas.DataFrame with OHLCV data
    """
    print(f"📊 Fetching {months} months of {symbol} data ({timeframe})...")
    
    # Initialize exchange
    exchange_class = getattr(ccxt, exchange_name)
    exchange = exchange_class({
        'enableRateLimit': True,
    })
    
    # Calculate time range
    now = datetime.now()
    start_date = now - timedelta(days=months * 30)
    start_timestamp = int(start_date.timestamp() * 1000)
    
    # Fetch data in chunks (exchanges limit to ~1000 candles per request)
    all_candles = []
    current_timestamp = start_timestamp
    
    while current_timestamp < int(now.timestamp() * 1000):
        try:
            candles = exchange.fetch_ohlcv(
                symbol,
                timeframe=timeframe,
                since=current_timestamp,
                limit=1000
            )
            
            if not candles:
                break
            
            all_candles.extend(candles)
            current_timestamp = candles[-1][0] + 1  # Move to next batch
            
            print(f"  Fetched {len(candles)} candles (Total: {len(all_candles)})")
            
        except Exception as e:
            print(f"  Error fetching data: {e}")
            break
    
    # Convert to DataFrame
    df = pd.DataFrame(all_candles, columns=['timestamp', 'Open', 'High', 'Low', 'Close', 'Volume'])
    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
    df.set_index('timestamp', inplace=True)
    
    # Remove duplicates
    df = df[~df.index.duplicated(keep='first')]
    
    print(f"✅ Fetched {len(df)} candles from {df.index[0]} to {df.index[-1]}")
    
    return df


# ============================================
# STRATEGY IMPLEMENTATION
# ============================================

class RsiReversalStrategy(Strategy):
    """
    RSI Reversal Strategy for Backtesting
    
    Entry:
    - LONG: RSI crosses above 30 (exit from oversold)
    - SHORT: RSI crosses below 70 (exit from overbought)
    
    Risk Management:
    - Stop Loss: 2% fixed
    - Take Profit: 4% fixed (1:2 ratio)
    """
    
    # Strategy parameters
    rsi_period = 14
    rsi_oversold = 30
    rsi_overbought = 70
    stop_loss_pct = 0.02  # 2%
    take_profit_pct = 0.04  # 4%
    
    def init(self):
        """Initialize indicators"""
        # Calculate RSI
        close = pd.Series(self.data.Close, index=self.data.index)
        self.rsi = self.I(ta.rsi, close, length=self.rsi_period)
    
    def next(self):
        """Execute on each candle"""
        # Skip if not enough data
        if len(self.data) < self.rsi_period + 1:
            return
        
        current_rsi = self.rsi[-1]
        previous_rsi = self.rsi[-2]
        price = self.data.Close[-1]
        
        # Close existing positions if conditions are met
        if self.position:
            return  # Let SL/TP handle exits
        
        # LONG Entry: RSI crosses above 30 (exit from oversold)
        if previous_rsi < self.rsi_oversold and current_rsi > self.rsi_oversold:
            sl_price = price * (1 - self.stop_loss_pct)
            tp_price = price * (1 + self.take_profit_pct)
            
            self.buy(
                sl=sl_price,
                tp=tp_price
            )
        
        # SHORT Entry: RSI crosses below 70 (exit from overbought)
        elif previous_rsi > self.rsi_overbought and current_rsi < self.rsi_overbought:
            sl_price = price * (1 + self.stop_loss_pct)
            tp_price = price * (1 - self.take_profit_pct)
            
            self.sell(
                sl=sl_price,
                tp=tp_price
            )


# ============================================
# MAIN EXECUTION
# ============================================

if __name__ == "__main__":
    print("=" * 60)
    print("🚀 RSI Reversal Strategy Backtest")
    print("=" * 60)
    
    # Configuration
    SYMBOL = 'BTC/USDT'
    TIMEFRAME = '15m'
    MONTHS = 6
    INITIAL_CASH = 10000
    COMMISSION = 0.0006  # 0.06% (taker fee)
    
    # Fetch data
    df = fetch_data(
        symbol=SYMBOL,
        timeframe=TIMEFRAME,
        months=MONTHS,
        exchange_name='binance'
    )
    
    # Run backtest
    print("\n" + "=" * 60)
    print("📈 Running Backtest...")
    print("=" * 60)
    
    bt = Backtest(
        df,
        RsiReversalStrategy,
        cash=INITIAL_CASH,
        commission=COMMISSION,
        exclusive_orders=True  # Only one position at a time
    )
    
    # Execute
    stats = bt.run()
    
    # Display results
    print("\n" + "=" * 60)
    print("📊 BACKTEST RESULTS")
    print("=" * 60)
    print(f"\n💰 Performance:")
    print(f"  Initial Capital:    ${INITIAL_CASH:,.2f}")
    print(f"  Final Equity:       ${stats['Equity Final [$]']:,.2f}")
    print(f"  Total Return:       {stats['Return [%]']:.2f}%")
    print(f"  Buy & Hold Return:  {stats['Buy & Hold Return [%]']:.2f}%")
    
    print(f"\n📈 Trading Stats:")
    print(f"  Total Trades:       {stats['# Trades']}")
    print(f"  Win Rate:           {stats['Win Rate [%]']:.2f}%")
    print(f"  Best Trade:         {stats['Best Trade [%]']:.2f}%")
    print(f"  Worst Trade:        {stats['Worst Trade [%]']:.2f}%")
    print(f"  Avg Trade:          {stats['Avg. Trade [%]']:.2f}%")
    
    print(f"\n⚠️  Risk Metrics:")
    print(f"  Max Drawdown:       {stats['Max. Drawdown [%]']:.2f}%")
    print(f"  Sharpe Ratio:       {stats['Sharpe Ratio']:.2f}")
    print(f"  Sortino Ratio:      {stats['Sortino Ratio']:.2f}")
    
    print(f"\n⏱️  Duration:")
    print(f"  Start Date:         {stats['Start']}")
    print(f"  End Date:           {stats['End']}")
    print(f"  Duration:           {stats['Duration']}")
    
    print("\n" + "=" * 60)
    print("🎨 Opening interactive chart...")
    print("=" * 60)
    
    # Open interactive plot in browser
    bt.plot()
    
    print("\n✅ Backtest complete!")
