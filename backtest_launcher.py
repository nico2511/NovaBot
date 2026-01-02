#!/usr/bin/env python3
"""
Backtest Launcher - Simulation Isolée des Stratégies
Usage: python backtest_launcher.py
"""

import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from backtest.backtest_engine import BacktestEngine
from strategies.engine import StrategyEngine
from app.core.risk_manager import RiskManager

def strategy_wrapper(df_slice, exchange, symbol):
    """
    Wrapper qui utilise le vrai StrategyEngine du bot.
    
    Args:
        df_slice: DataFrame historique jusqu'à t
        exchange: MockExchange
        symbol: Symbole du token
    
    Returns:
        Signal dict ou None
    """
    # Créer le StrategyEngine (utilise le VRAI code du bot)
    risk_manager = RiskManager()
    engine = StrategyEngine(risk_manager)
    
    # Analyser avec les vraies stratégies
    result = engine.analyze(df_slice)
    
    # Si signal détecté
    if result.get('signals'):
        signal = result['signals'][0]
        
        # Calculer taille de position
        balance = exchange.get_account_balance()
        equity = balance['equity']
        
        # Utiliser le vrai RiskManager
        raw_size = risk_manager.calculate_position_size(
            price=signal['price'],
            sl_price=signal['sl'],
            equity=equity,
            method="risk_pct",
            risk_per_trade_pct=0.01  # Risque 1% par trade
        )
        
        # 🔧 OPTIMIZATION: Cap position to 50% of equity (prevent margin errors)
        max_position_value = equity * 0.5  # 50% of balance
        max_size = max_position_value / signal['price']
        size = min(raw_size, max_size)
        
        # Retourner signal formaté pour MockExchange
        return {
            "symbol": symbol,
            "side": signal['signal'],
            "size": size,
            "sl": signal['sl'],
            "tp": signal['tp']
        }
    
    return None


if __name__ == "__main__":
    print("="*60)
    print("🧪 BACKTEST LAUNCHER - Strategy Validation")
    print("="*60)
    
    # Configuration
    INITIAL_BALANCE = 1000.0  # $1000 initial
    DATA_FILE = "data/historical/BTC_15m.csv"  # Données historiques
    SYMBOL = "BTC"
    
    # Vérifier si le fichier existe
    if not os.path.exists(DATA_FILE):
        print(f"❌ Error: Data file not found: {DATA_FILE}")
        print("\n📥 Please download historical data first:")
        print("   1. Go to https://www.cryptodatadownload.com/data/hyperliquid/")
        print("   2. Download BTC 15m data (last 3 months)")
        print(f"   3. Save as: {DATA_FILE}")
        print("\nOr use the data download script:")
        print("   python scripts/download_historical_data.py")
        sys.exit(1)
    
    # Créer le moteur de backtest
    engine = BacktestEngine(initial_balance=INITIAL_BALANCE)
    
    # Lancer le backtest
    print(f"\n🚀 Starting backtest on {SYMBOL}...")
    print(f"📊 Strategy: StrategyEngine (Real Bot Logic)")
    print(f"💰 Risk per trade: 1% of equity")
    print()
    
    try:
        stats = engine.run(
            data_csv_path=DATA_FILE,
            strategy_func=strategy_wrapper,
            symbol=SYMBOL,
            warmup_candles=50  # 50 bougies pour les indicateurs
        )
        
        # Sauvegarder les résultats
        import json
        with open("backtest_results.json", "w") as f:
            json.dump(stats, f, indent=2)
        
        print(f"\n💾 Results saved to: backtest_results.json")
        
    except Exception as e:
        print(f"\n❌ Backtest failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
