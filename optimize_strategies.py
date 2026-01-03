"""
Strategy Optimization Script
Tests directional filters (LONG/SHORT/BOTH) and parameter combinations
"""
import json
import pandas as pd
from itertools import product
from typing import Dict, List
import sys
sys.path.append('.')

from backtest.backtest_engine import BacktestEngine
from app.services.hyperliquid_service import hyperliquid_service

class StrategyOptimizer:
    """Optimize strategy parameters and directional filters"""
    
    def __init__(self, symbols: List[str] = ["BTC"], days: int = 30):
        """
        Initialize optimizer
        
        Args:
            symbols: List of symbols to test
            days: Number of days of historical data
        """
        self.symbols = symbols
        self.days = days
        self.data_cache = {}
        
        # Load base config
        with open("strategies.json", "r") as f:
            self.base_config = json.load(f)
    
    def fetch_data(self, symbol: str) -> pd.DataFrame:
        """Fetch and cache historical data"""
        if symbol not in self.data_cache:
            print(f"📊 Fetching {self.days} days of data for {symbol}...")
            df = hyperliquid_service.get_candles(symbol, "15m", limit=self.days * 96)
            self.data_cache[symbol] = df
        return self.data_cache[symbol]
    
    def test_config(
        self,
        symbol: str,
        strategy_name: str,
        params: Dict,
        direction: str  # 'LONG_ONLY', 'SHORT_ONLY', 'BOTH'
    ) -> Dict:
        """
        Test a specific configuration
        
        Args:
            symbol: Trading symbol
            strategy_name: Strategy to test
            params: Strategy parameters
            direction: Directional filter
            
        Returns:
            Backtest results
        """
        # Create config with only this strategy enabled
        config = {
            "market_regime": self.base_config["market_regime"],
            "strategies": {}
        }
        
        # Get strategy type from base config
        base_strategy = self.base_config["strategies"].get(strategy_name, {})
        strategy_type = base_strategy.get("type", "trend")
        
        # Set directional filters
        if direction == 'LONG_ONLY':
            params['allow_longs'] = True
            params['allow_shorts'] = False
        elif direction == 'SHORT_ONLY':
            params['allow_longs'] = False
            params['allow_shorts'] = True
        else:  # BOTH
            params['allow_longs'] = True
            params['allow_shorts'] = True
        
        # Add strategy
        config["strategies"][strategy_name] = {
            "enabled": True,
            "type": strategy_type,
            "params": params
        }
        
        # Get data
        df = self.fetch_data(symbol)
        
        if df is None or df.empty:
            return None
        
        # Run backtest
        engine = BacktestEngine(initial_balance=1000.0)
        try:
            results = engine.run(df, symbol, config, verbose=False)
            return results['stats']
        except Exception as e:
            print(f"⚠️ Error testing {strategy_name} ({direction}): {e}")
            return None
    
    def optimize_strategy(
        self,
        strategy_name: str,
        param_grid: Dict[str, List],
        directions: List[str] = ['LONG_ONLY', 'SHORT_ONLY', 'BOTH']
    ) -> Dict:
        """
        Optimize a single strategy
        
        Args:
            strategy_name: Strategy to optimize
            param_grid: Dictionary of parameter names to lists of values
            directions: List of directional filters to test
            
        Returns:
            Best configuration and results
        """
        print(f"\n{'='*60}")
        print(f"🔬 OPTIMIZING: {strategy_name}")
        print(f"{'='*60}\n")
        
        best_config = None
        best_roi = -999
        all_results = []
        
        # Generate all parameter combinations
        param_names = list(param_grid.keys())
        param_values = list(param_grid.values())
        
        total_tests = len(list(product(*param_values))) * len(directions) * len(self.symbols)
        test_count = 0
        
        for param_combo in product(*param_values):
            params = dict(zip(param_names, param_combo))
            
            for direction in directions:
                for symbol in self.symbols:
                    test_count += 1
                    print(f"[{test_count}/{total_tests}] Testing {strategy_name} on {symbol} ({direction}) with {params}...", end='\r')
                    
                    stats = self.test_config(symbol, strategy_name, params.copy(), direction)
                    
                    if stats:
                        result = {
                            'strategy': strategy_name,
                            'symbol': symbol,
                            'params': params,
                            'direction': direction,
                            'roi': stats['roi_pct'],
                            'win_rate': stats['win_rate'],
                            'total_trades': stats['total_trades'],
                            'avg_win': stats['avg_win'],
                            'avg_loss': stats['avg_loss']
                        }
                        
                        all_results.append(result)
                        
                        if stats['roi_pct'] > best_roi:
                            best_roi = stats['roi_pct']
                            best_config = result
        
        print()  # New line after progress
        
        # Display best result
        if best_config:
            print(f"\n✅ BEST CONFIG for {strategy_name}:")
            print(f"   Symbol: {best_config['symbol']}")
            print(f"   Direction: {best_config['direction']}")
            print(f"   Params: {best_config['params']}")
            print(f"   ROI: {best_config['roi']:.2f}%")
            print(f"   Win Rate: {best_config['win_rate']:.2f}%")
            print(f"   Trades: {best_config['total_trades']}")
        
        return {
            'best': best_config,
            'all_results': all_results
        }
    
    def optimize_all(self) -> Dict:
        """Optimize all enabled strategies"""
        
        # Define parameter grids for each strategy
        param_grids = {
            'institutional_scalp': {
                'liq_grab_lookback': [10, 15, 20, 25]
            },
            'elastic_reversion': {
                'oversold_rsi': [20, 25, 30],
                'overbought_rsi': [70, 75, 80],
                'extension_pct': [0.03, 0.04, 0.05]
            },
            'smart_trend': {},  # No params to optimize
            'golden_cross': {
                'sl_pct': [0.01, 0.015, 0.02],
                'tp_pct': [0.02, 0.03, 0.04]
            },
            'test_ema': {}  # Test strategy
        }
        
        results = {}
        
        for strategy_name, param_grid in param_grids.items():
            # Check if strategy is enabled in base config
            if not self.base_config['strategies'].get(strategy_name, {}).get('enabled', False):
                print(f"⏭️  Skipping {strategy_name} (disabled)")
                continue
            
            # If no params to optimize, just test directions
            if not param_grid:
                # Use default params from base config
                default_params = self.base_config['strategies'][strategy_name].get('params', {})
                param_grid = {k: [v] for k, v in default_params.items()}
            
            result = self.optimize_strategy(strategy_name, param_grid)
            results[strategy_name] = result
        
        return results
    
    def generate_report(self, results: Dict, output_file: str = "optimization_report.md"):
        """Generate markdown report"""
        with open(output_file, "w") as f:
            f.write("# 📊 Strategy Optimization Report\n\n")
            f.write(f"**Test Period:** {self.days} days\n")
            f.write(f"**Symbols Tested:** {', '.join(self.symbols)}\n\n")
            f.write("---\n\n")
            
            for strategy_name, result in results.items():
                best = result['best']
                
                if not best:
                    f.write(f"## ❌ {strategy_name}\n\n")
                    f.write("No profitable configuration found.\n\n")
                    continue
                
                emoji = "✅" if best['roi'] > 0 else "⚠️" if best['roi'] > -1 else "❌"
                
                f.write(f"## {emoji} {strategy_name}\n\n")
                f.write(f"**Best Configuration:**\n")
                f.write(f"- **Symbol:** {best['symbol']}\n")
                f.write(f"- **Direction:** `{best['direction']}`\n")
                f.write(f"- **Parameters:**\n")
                for param, value in best['params'].items():
                    f.write(f"  - `{param}`: {value}\n")
                f.write(f"\n**Performance:**\n")
                f.write(f"- **ROI:** {best['roi']:.2f}%\n")
                f.write(f"- **Win Rate:** {best['win_rate']:.2f}%\n")
                f.write(f"- **Total Trades:** {best['total_trades']}\n")
                f.write(f"- **Avg Win:** ${best['avg_win']:.2f}\n")
                f.write(f"- **Avg Loss:** ${best['avg_loss']:.2f}\n")
                f.write(f"\n---\n\n")
        
        print(f"\n💾 Report saved to: {output_file}")
    
    def update_strategies_json(self, results: Dict):
        """Update strategies.json with optimized parameters"""
        for strategy_name, result in results.items():
            best = result['best']
            
            if best and strategy_name in self.base_config['strategies']:
                # Update params
                self.base_config['strategies'][strategy_name]['params'].update(best['params'])
        
        # Save updated config
        with open("strategies_optimized.json", "w") as f:
            json.dump(self.base_config, f, indent=4)
        
        print(f"\n💾 Optimized config saved to: strategies_optimized.json")


if __name__ == "__main__":
    # Run optimization
    optimizer = StrategyOptimizer(symbols=["BTC", "DOGE"], days=30)
    
    print("\n🚀 Starting Strategy Optimization...")
    print("This will test multiple configurations for each strategy.\n")
    
    results = optimizer.optimize_all()
    
    # Generate report
    optimizer.generate_report(results)
    
    # Update config
    optimizer.update_strategies_json(results)
    
    print("\n✅ Optimization complete!")
