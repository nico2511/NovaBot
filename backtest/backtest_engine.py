"""
Professional Backtest Engine
Simulates trading strategies on historical data with zero lookahead bias
"""
import pandas as pd
import json
from typing import Dict, List, Optional
from datetime import datetime
import sys
sys.path.append('.')

from backtest.mock_exchange import MockExchange
from strategies.engine import StrategyEngine
from app.core.risk_manager import RiskManager

class BacktestEngine:
    """
    Professional backtest engine following industry best practices
    """
    
    def __init__(
        self,
        initial_balance: float = 1000.0,
        fee_rate: float = 0.0005,
        warmup_candles: int = 50
    ):
        """
        Initialize backtest engine
        
        Args:
            initial_balance: Starting capital
            fee_rate: Trading fee (0.0005 = 0.05%)
            warmup_candles: Minimum candles before trading starts
        """
        self.initial_balance = initial_balance
        self.fee_rate = fee_rate
        self.warmup_candles = warmup_candles
        self.exchange = MockExchange(initial_balance, fee_rate)
        
    def run(
        self,
        df: pd.DataFrame,
        symbol: str,
        strategy_config: Dict,
        verbose: bool = False
    ) -> Dict:
        """
        Run backtest on historical data
        
        Args:
            df: Historical OHLCV data with DatetimeIndex
            symbol: Trading symbol
            strategy_config: Strategy configuration dict
            verbose: Print trade execution logs
            
        Returns:
            Backtest results with statistics
        """
        # Initialize strategy engine with config
        strategy_engine = StrategyEngine(config=strategy_config)
        
        # Reset exchange
        self.exchange = MockExchange(self.initial_balance, self.fee_rate)
        
        print(f"\n{'='*60}")
        print(f"🧪 BACKTESTING: {symbol}")
        print(f"{'='*60}")
        print(f"📊 Data: {len(df)} candles ({df.index[0]} → {df.index[-1]})")
        print(f"💰 Initial Balance: ${self.initial_balance:.2f}")
        print(f"📈 Fee Rate: {self.fee_rate*100:.3f}%")
        print(f"{'='*60}\n")
        
        # Main backtest loop
        for i in range(self.warmup_candles, len(df)):
            current_candle = df.iloc[i]
            
            # ANTI-LOOKAHEAD: Only use data up to current index
            df_slice = df.iloc[:i+1].copy()
            
            # Set current candle for exchange
            self.exchange.set_current_candle({
                'open': current_candle['open'],
                'high': current_candle['high'],
                'low': current_candle['low'],
                'close': current_candle['close'],
                'volume': current_candle['volume'],
                'timestamp': current_candle.name
            })
            
            # Check SL/TP first
            self.exchange.check_stops()
            
            # Generate signals if no position
            if not self.exchange.positions:
                try:
                    result = strategy_engine.analyze(df_slice)
                    
                    if result and result.get('signals'):
                        signal_data = result['signals'][0]  # Take first signal
                        signal = signal_data.get('signal')
                        
                        if signal and signal != 'HOLD':
                            # Execute trade
                            is_buy = (signal == 'BUY')
                            entry_price = current_candle['close']
                            
                            # Position sizing (10% of balance)
                            size = (self.exchange.balance * 0.1) / entry_price
                            
                            # Get SL/TP from signal or use defaults
                            if is_buy:
                                sl = signal_data.get('sl', entry_price * 0.95)
                                tp = signal_data.get('tp', entry_price * 1.10)
                            else:
                                sl = signal_data.get('sl', entry_price * 1.05)
                                tp = signal_data.get('tp', entry_price * 0.90)
                            
                            # Execute order
                            order_result = self.exchange.execute_order(
                                symbol=symbol,
                                is_buy=is_buy,
                                size=size,
                                price=entry_price,
                                sl_price=sl,
                                tp_price=tp
                            )
                            
                            if verbose and order_result['status'] == 'success':
                                strategy_name = signal_data.get('strategy', 'Unknown')
                                print(f"[{current_candle.name}] 🚀 {signal} @ ${entry_price:.2f} ({strategy_name})")
                
                except Exception as e:
                    if verbose:
                        print(f"⚠️ Error at candle {i}: {e}")
        
        # Close any remaining positions
        if self.exchange.positions:
            for symbol in list(self.exchange.positions.keys()):
                self.exchange.close_position(symbol, reason="EOD")
        
        # Generate report
        stats = self.exchange.get_stats()
        
        # Display results
        self._display_results(symbol, stats)
        
        return {
            'symbol': symbol,
            'stats': stats,
            'trades': self.exchange.history
        }
    
    def _display_results(self, symbol: str, stats: Dict):
        """Display backtest results"""
        print(f"\n{'='*60}")
        print(f"📈 RESULTS: {symbol}")
        print(f"{'='*60}")
        print(f"Initial Balance: ${self.initial_balance:.2f}")
        print(f"Final Balance:   ${stats['final_balance']:.2f}")
        print(f"Total PnL:       ${stats['total_pnl']:.2f}")
        print(f"ROI:             {stats['roi_pct']:.2f}%")
        print(f"Total Trades:    {stats['total_trades']}")
        print(f"Winning Trades:  {stats['winning_trades']}")
        print(f"Losing Trades:   {stats['losing_trades']}")
        print(f"Win Rate:        {stats['win_rate']:.2f}%")
        print(f"Avg Win:         ${stats['avg_win']:.2f}")
        print(f"Avg Loss:        ${stats['avg_loss']:.2f}")
        print(f"Total Fees:      ${stats['total_fees']:.2f}")
        print(f"{'='*60}\n")


if __name__ == "__main__":
    # Test the engine
    from app.services.hyperliquid_service import hyperliquid_service
    
    # Load config
    with open("strategies.json", "r") as f:
        config = json.load(f)
    
    # Fetch data
    print("Fetching BTC data...")
    df = hyperliquid_service.get_candles("BTC", "15m", limit=2880)  # 30 days
    
    if df is not None and not df.empty:
        # Run backtest
        engine = BacktestEngine(initial_balance=1000.0)
        results = engine.run(df, "BTC", config, verbose=True)
        
        # Save results
        with open("backtest_results_professional.json", "w") as f:
            # Convert trades to serializable format
            serializable_results = {
                'symbol': results['symbol'],
                'stats': results['stats'],
                'trades': [
                    {k: str(v) if isinstance(v, (datetime, pd.Timestamp)) else v 
                     for k, v in trade.items()}
                    for trade in results['trades']
                ]
            }
            json.dump(serializable_results, f, indent=2)
        
        print("💾 Results saved to: backtest_results_professional.json")
    else:
        print("❌ Failed to fetch data")
