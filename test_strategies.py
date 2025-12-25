#!/usr/bin/env python3
"""
Simplified diagnostic script to test strategies
Tests all strategies with sample data to verify they work
"""
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def create_sample_data(num_candles=200, base_price=100000, volatility=0.02):
    """
    Create sample OHLCV data for testing
    """
    dates = pd.date_range(end=datetime.now(), periods=num_candles, freq='15min')
    
    # Generate random walk
    returns = np.random.normal(0, volatility, num_candles)
    prices = base_price * np.exp(np.cumsum(returns))
    
    # Create OHLCV
    data = []
    for i, price in enumerate(prices):
        high = price * (1 + abs(np.random.normal(0, volatility/2)))
        low = price * (1 - abs(np.random.normal(0, volatility/2)))
        open_price = prices[i-1] if i > 0 else price
        close_price = price
        volume = np.random.uniform(1000, 10000)
        
        data.append({
            'open': open_price,
            'high': high,
            'low': low,
            'close': close_price,
            'volume': volume
        })
    
    df = pd.DataFrame(data, index=dates)
    return df

def test_strategies():
    """
    Test all strategies with sample data
    """
    print("=" * 80)
    print("🧪 TEST DES STRATÉGIES")
    print("=" * 80)
    print(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    
    # Import strategies
    try:
        from strategies.definitions import (
            ScalpEmaRsi, InstitutionalScalp, SwingTrendPullback,
            DayTradingORB, MeanReversion, SMCFVG
        )
        print("✅ Toutes les stratégies importées avec succès\n")
    except Exception as e:
        print(f"❌ Erreur lors de l'import des stratégies: {e}")
        return
    
    # Create sample data
    print("📊 Génération de données de test...")
    df = create_sample_data(num_candles=200, base_price=95000, volatility=0.015)
    print(f"✅ {len(df)} bougies générées")
    print(f"   Prix: ${df['close'].iloc[0]:,.2f} → ${df['close'].iloc[-1]:,.2f}\n")
    
    # Test each strategy
    strategies = {
        "ScalpEmaRsi": ScalpEmaRsi({"params": {"ema_fast": 9, "ema_slow": 21, "rsi_period": 14}}),
        "InstitutionalScalp": InstitutionalScalp({"params": {"liq_grab_lookback": 20}}),
        "SwingTrendPullback": SwingTrendPullback({"params": {"ema_trend": 200, "ema_pullback_fast": 20, "ema_pullback_slow": 50}}),
        "DayTradingORB": DayTradingORB({"params": {}}),
        "MeanReversion": MeanReversion({"params": {"bb_length": 20, "bb_std": 2.0, "rsi_period": 14}}),
        "SMCFVG": SMCFVG({"params": {"fvg_threshold": 0.005}})
    }
    
    print("🔬 Test de chaque stratégie...\n")
    print("-" * 80)
    
    results = {}
    
    for name, strategy in strategies.items():
        print(f"\n🎯 Test: {name}")
        try:
            # Test with fresh copy of data
            df_test = df.copy()
            signal = strategy.generate_signal(df_test)
            
            if signal:
                print(f"   ✅ SIGNAL GÉNÉRÉ!")
                print(f"      Type: {signal.get('signal', 'N/A')}")
                print(f"      SL: ${signal.get('sl', 0):,.2f}")
                print(f"      TP: ${signal.get('tp', 0):,.2f}")
                print(f"      Commentaire: {signal.get('comment', 'N/A')}")
                results[name] = "✅ Fonctionne - Signal généré"
            else:
                print(f"   ⚪ Pas de signal (conditions non remplies)")
                results[name] = "⚪ Fonctionne - Pas de signal"
                
        except Exception as e:
            print(f"   ❌ ERREUR: {e}")
            results[name] = f"❌ Erreur: {str(e)[:50]}"
    
    # Summary
    print("\n" + "=" * 80)
    print("📊 RÉSUMÉ DES TESTS")
    print("=" * 80)
    
    for name, result in results.items():
        print(f"   {name}: {result}")
    
    # Count working strategies
    working = sum(1 for r in results.values() if "✅" in r or "⚪" in r)
    total = len(results)
    
    print(f"\n🎯 Stratégies fonctionnelles: {working}/{total}")
    
    if working == total:
        print("\n✅ TOUTES LES STRATÉGIES SONT OPÉRATIONNELLES!")
    else:
        print("\n⚠️  Certaines stratégies ont des erreurs")
    
    print("\n" + "=" * 80)
    print("\n💡 NOTES:")
    print("   • Les stratégies peuvent ne pas générer de signal si les conditions")
    print("     de marché ne correspondent pas à leurs critères")
    print("   • C'est NORMAL - les stratégies sont sélectives")
    print("   • L'important est qu'elles ne génèrent PAS d'erreurs")
    print("\n" + "=" * 80)

if __name__ == "__main__":
    try:
        test_strategies()
    except Exception as e:
        print(f"\n❌ Erreur fatale: {e}")
        import traceback
        traceback.print_exc()
