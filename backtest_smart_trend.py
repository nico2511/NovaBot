"""
Backtest Script for Smart Trend (MTF)
Handles 15m/1m data synchronization for correct verification.
"""
import pandas as pd
import json
import sys
from datetime import timedelta
import time

sys.path.append('.')

from backtest.backtest_engine import BacktestEngine
from backtest.mock_exchange import MockExchange
from strategies.engine import StrategyEngine

class MTFBacktestEngine(BacktestEngine):
    def run_mtf(self, df_15m, df_1m, symbol, config, verbose=True):
        strategy_engine = StrategyEngine(config)
        self.exchange = MockExchange(self.initial_balance, self.fee_rate)
        
        print(f"\n{'='*60}")
        print(f"🧪 MTF BACKTESTING: {symbol}")
        print(f"{'='*60}")
        print(f"📊 15m Data: {len(df_15m)} candles")
        print(f"📊 1m Data:  {len(df_1m)} candles")
        
        # Ensure 1m index is sorted
        df_1m = df_1m.sort_index()
        
        # Main loop
        for i in range(self.warmup_candles, len(df_15m)):
            current_candle = df_15m.iloc[i]
            current_time = current_candle.name
            
            # SLICE 15m
            df_slice_15m = df_15m.iloc[:i+1].copy()
            
            # SLICE 1m: Get data up to current_time
            # IMPORTANT: For real-time simulation, if we are at the CLOSE of 15m candle (e.g. 10:15:00),
            # we should have 1m data up to 10:15:00.
            # Using binary search (asof) or simple slicing if indexed.
            # df_1m[:current_time] includes the row exactly AT current_time if present.
            df_slice_1m = df_1m[:current_time].copy()
            
            # Only proceed if we have enough 1m data
            if len(df_slice_1m) < 10:
                continue
                
            # Set current candle (15m) for Exchange (price source)
            self.exchange.set_current_candle({
                'open': current_candle['open'],
                'high': current_candle['high'],
                'low': current_candle['low'],
                'close': current_candle['close'],
                'volume': current_candle['volume'],
                'timestamp': current_candle.name
            })
            
            # Check Stops
            self.exchange.check_stops()
            
            # Analysis
            if not self.exchange.positions:
                try:
                    # PASS EXTRA DATA
                    result = strategy_engine.analyze(df_slice_15m, extra_data={"1m": df_slice_1m})
                    
                    if result and result.get('signals'):
                        signal_data = result['signals'][0]
                        signal = signal_data.get('signal')
                        
                        if signal and signal != 'HOLD':
                            is_buy = (signal == 'BUY')
                            entry_price = current_candle['close'] 
                            # Note: In reality, entry might be on 1m close, but for simplicity we take 15m close
                            # Or we could take df_slice_1m.iloc[-1]['close'] if trigger is from 1m.
                            # Smart Trend returns 'price' in signal_data (1m close). Use that if available.
                            if 'price' in signal_data:
                                entry_price = signal_data['price']
                            
                            size = (self.exchange.balance * 0.1) / entry_price
                            
                            sl = signal_data.get('sl')
                            tp = signal_data.get('tp')
                            
                            # Execute
                            res = self.exchange.execute_order(
                                symbol, is_buy, size, entry_price, sl, tp
                            )
                            
                            if verbose and res['status'] == 'success':
                                print(f"[{current_time}] 🚀 {signal} @ ${entry_price:.2f} | 1m Close: {df_slice_1m.iloc[-1]['close']:.2f}")

                except Exception as e:
                    if verbose: print(f"Error: {e}")
        
        # Close all
        if self.exchange.positions:
            for s in list(self.exchange.positions.keys()):
                self.exchange.close_position(s, reason="EOD")
                
        return self.exchange.get_stats()

# MAIN EXECUTION
if __name__ == "__main__":
    # Load Data
    try:
        print("Loading Data...")
        df_btc_15m = pd.read_csv('data/historical/BTC_15m.csv')
        df_btc_15m['timestamp'] = pd.to_datetime(df_btc_15m['timestamp'])
        df_btc_15m.set_index('timestamp', inplace=True)
        
        df_btc_1m = pd.read_csv('data/historical/BTC_1m.csv')
        # Fix column name if needed
        if 'time' in df_btc_1m.columns:
            df_btc_1m.rename(columns={'time': 'timestamp'}, inplace=True)
            
        df_btc_1m['timestamp'] = pd.to_datetime(df_btc_1m['timestamp'])
        df_btc_1m.set_index('timestamp', inplace=True)
        print("✅ Data Loaded")
    except FileNotFoundError:
        print("❌ Data missing. Run download_1m_data.py first.")
        sys.exit(1)

    # Config
    config = {
        "market_regime": {"adx_threshold": 25, "timeframe": "15m"},
        "strategies": {
            "smart_trend": {
                "enabled": True,
                "type": "trend",
                "params": {}
            }
        }
    }
    
    # Run
    engine = MTFBacktestEngine(initial_balance=1000.0)
    stats = engine.run_mtf(df_btc_15m, df_btc_1m, "BTC", config, verbose=True)
    
    print("\n" + "="*60)
    print("📊 SMART TREND RESULTS (BTC)")
    print(f"Total PnL: ${stats['total_pnl']:.2f}")
    print(f"ROI:       {stats['roi_pct']:.2f}%")
    print(f"Trades:    {stats['total_trades']}")
    print(f"Win Rate:  {stats['win_rate']:.2f}%")
