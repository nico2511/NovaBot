#!/usr/bin/env python3
"""
Diagnostic script to analyze why no trades were taken
Simulates the bot's behavior with historical data
"""
import pandas as pd
import sys
from datetime import datetime, timedelta
from app.services.hyperliquid_service import hyperliquid_service
from app.core.risk_manager import RiskManager
from strategies.engine import StrategyEngine
from app.core.config import config

def analyze_night_trading(symbol="BTC", hours_back=12):
    """
    Analyze what happened during the night
    """
    print("=" * 80)
    print(f"🔍 ANALYSE DE LA NUIT - {symbol}")
    print("=" * 80)
    print(f"Période analysée: Dernières {hours_back} heures")
    print(f"Heure actuelle: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    
    # 1. Fetch historical data
    print("📊 Récupération des données...")
    df = hyperliquid_service.get_candles(symbol, interval="15m", limit=100)
    
    if df.empty:
        print("❌ Impossible de récupérer les données!")
        return
    
    print(f"✅ {len(df)} bougies récupérées")
    print(f"   Période: {df.index[0]} → {df.index[-1]}")
    print(f"   Prix actuel: ${df['close'].iloc[-1]:,.2f}\n")
    
    # 2. Initialize components
    risk_manager = RiskManager(
        max_positions=config.DEFAULT_MAX_POSITIONS,
        daily_stop_loss=config.DEFAULT_DAILY_STOP_LOSS
    )
    strategy_engine = StrategyEngine(risk_manager)
    
    # 3. Analyze each candle
    print("🔎 Analyse des signaux générés...\n")
    print("-" * 80)
    
    signals_found = []
    total_candles = len(df)
    
    # Analyze last N candles (simulate the night)
    candles_to_check = min(hours_back * 4, total_candles)  # 4 candles per hour (15m)
    
    for i in range(total_candles - candles_to_check, total_candles):
        # Get data up to this point
        df_slice = df.iloc[:i+1].copy()
        
        if len(df_slice) < 50:
            continue
        
        # Analyze
        result = strategy_engine.analyze(df_slice)
        
        timestamp = df_slice.index[-1]
        price = df_slice['close'].iloc[-1]
        
        # Check if signals were generated
        if result.get("signals"):
            for sig in result["signals"]:
                signals_found.append({
                    "time": timestamp,
                    "price": price,
                    "strategy": sig.get("strategy"),
                    "signal": sig.get("signal"),
                    "sl": sig.get("sl"),
                    "tp": sig.get("tp"),
                    "comment": sig.get("comment", ""),
                    "regime": result.get("regime"),
                    "adx": result.get("adx")
                })
                
                print(f"🚨 SIGNAL DÉTECTÉ!")
                print(f"   Temps: {timestamp}")
                print(f"   Stratégie: {sig.get('strategy')}")
                print(f"   Type: {sig.get('signal')}")
                print(f"   Prix: ${price:,.2f}")
                print(f"   SL: ${sig.get('sl', 0):,.2f} | TP: ${sig.get('tp', 0):,.2f}")
                print(f"   Régime: {result.get('regime')} (ADX: {result.get('adx', 0):.1f})")
                print(f"   Commentaire: {sig.get('comment', '')}")
                print("-" * 80)
    
    # 4. Summary
    print("\n" + "=" * 80)
    print("📈 RÉSUMÉ DE L'ANALYSE")
    print("=" * 80)
    
    print(f"\n🕐 Période analysée: {candles_to_check} bougies ({candles_to_check/4:.1f} heures)")
    print(f"🎯 Signaux trouvés: {len(signals_found)}")
    
    if signals_found:
        print("\n📊 Répartition par stratégie:")
        strategies = {}
        for sig in signals_found:
            strat = sig["strategy"]
            strategies[strat] = strategies.get(strat, 0) + 1
        
        for strat, count in strategies.items():
            print(f"   • {strat}: {count} signal(s)")
        
        print("\n📋 Détails des signaux:")
        for i, sig in enumerate(signals_found, 1):
            print(f"\n   Signal #{i}:")
            print(f"      Temps: {sig['time']}")
            print(f"      Stratégie: {sig['strategy']}")
            print(f"      Type: {sig['signal']}")
            print(f"      Prix: ${sig['price']:,.2f}")
            print(f"      Régime: {sig['regime']} (ADX: {sig['adx']:.1f})")
    else:
        print("\n⚠️  AUCUN SIGNAL TROUVÉ!")
        print("\n🔍 Raisons possibles:")
        print("   1. Conditions de marché ne correspondent pas aux critères des stratégies")
        print("   2. ADX trop faible (< 25) → Seules stratégies 'range' actives")
        print("   3. Filtres trop stricts (EMA, RSI, volatilité)")
        print("   4. Pas assez de volatilité (ATR trop faible)")
        
        # Analyze current market conditions
        print("\n📊 Conditions actuelles du marché:")
        last_result = strategy_engine.analyze(df)
        print(f"   • Régime: {last_result.get('regime', 'N/A')}")
        print(f"   • ADX: {last_result.get('adx', 0):.1f}")
        print(f"   • Stratégies actives: {', '.join(last_result.get('strategies', []))}")
        
        # Check individual strategy conditions
        print("\n🔬 Vérification des conditions par stratégie:")
        
        # Check if we have enough data
        if len(df) >= 200:
            # Calculate some indicators for analysis
            df.ta.ema(length=9, append=True)
            df.ta.ema(length=21, append=True)
            df.ta.ema(length=200, append=True)
            df.ta.rsi(length=14, append=True)
            df.ta.adx(length=14, append=True)
            df.ta.atr(length=14, append=True)
            
            close = df['close'].iloc[-1]
            
            if 'EMA_9' in df.columns and 'EMA_21' in df.columns:
                ema9 = df['EMA_9'].iloc[-1]
                ema21 = df['EMA_21'].iloc[-1]
                ema200 = df['EMA_200'].iloc[-1] if 'EMA_200' in df.columns else 0
                rsi = df['RSI_14'].iloc[-1] if 'RSI_14' in df.columns else 0
                adx = df['ADX_14'].iloc[-1] if 'ADX_14' in df.columns else 0
                atr = df['ATRr_14'].iloc[-1] if 'ATRr_14' in df.columns else 0
                
                print(f"\n   ScalpEmaRsi:")
                print(f"      • EMA 9: ${ema9:,.2f} | EMA 21: ${ema21:,.2f}")
                print(f"      • Position: {'Au-dessus' if ema9 > ema21 else 'En-dessous'} EMA 21")
                print(f"      • Trend (EMA 200): ${ema200:,.2f} | Prix {'au-dessus' if close > ema200 else 'en-dessous'}")
                print(f"      • RSI: {rsi:.1f} (Besoin: 50-70 pour BUY, 30-50 pour SELL)")
                
                print(f"\n   Conditions générales:")
                print(f"      • ADX: {adx:.1f} (Seuil: 25 pour TREND)")
                print(f"      • ATR: ${atr:,.2f} (Volatilité)")
                print(f"      • Prix: ${close:,.2f}")
    
    print("\n" + "=" * 80)
    print("\n💡 RECOMMANDATIONS:")
    print("=" * 80)
    
    if not signals_found:
        print("\n1. ✅ Les stratégies sont maintenant TOUTES implémentées")
        print("2. 🔧 Vérifier que le trading automatique est activé:")
        print("      • Mode: Auto (Hyperliquid)")
        print("      • Checkbox: ✅ ALLOW LIVE TRADING")
        print("3. 📊 Le marché était peut-être trop calme cette nuit")
        print("4. ⚙️  Considérer d'ajuster les paramètres si trop restrictifs:")
        print("      • Réduire le seuil ADX (ex: 20 au lieu de 25)")
        print("      • Élargir les zones RSI")
        print("      • Réduire le seuil de volatilité")
    else:
        print("\n1. ✅ Des signaux ÉTAIENT disponibles!")
        print("2. ⚠️  Vérifier pourquoi ils n'ont pas été exécutés:")
        print("      • Trading activé? (bot_state.json)")
        print("      • Risk Manager bloqué?")
        print("      • Engine démarré?")
        print("3. 🔍 Vérifier les logs du serveur pour cette période")
    
    print("\n" + "=" * 80)

if __name__ == "__main__":
    # Allow custom symbol and hours
    symbol = sys.argv[1] if len(sys.argv) > 1 else "BTC"
    hours = int(sys.argv[2]) if len(sys.argv) > 2 else 12
    
    try:
        analyze_night_trading(symbol, hours)
    except Exception as e:
        print(f"\n❌ Erreur lors de l'analyse: {e}")
        import traceback
        traceback.print_exc()
