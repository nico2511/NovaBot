#!/usr/bin/env python3
"""
Test en temps réel de la logique du bot
Simule exactement ce qui se passe dans main_nextjs.py
"""
import sys
import os
import time
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.services.hyperliquid_service import hyperliquid_service
from strategies.engine import StrategyEngine
from app.core.risk_manager import RiskManager

print("=" * 80)
print("🧪 TEST EN TEMPS RÉEL - SIMULATION DU BOT")
print("=" * 80)

# Simuler l'état du bot
last_candle_time = None
iteration = 0

print("\n⏱️  Je vais faire 3 itérations espacées de 3 secondes")
print("    (comme le bot qui tourne toutes les 5s)")
print("\n" + "=" * 80)

for i in range(3):
    iteration += 1
    print(f"\n🔄 ITÉRATION #{iteration}")
    print("-" * 80)
    
    # 1. Fetch candles (comme dans le bot)
    print("📡 Fetching candles...")
    df = hyperliquid_service.get_candles("BTC", interval="15m", limit=200)
    
    if df.empty:
        print("⚠️ No data received")
        time.sleep(3)
        continue
    
    print(f"✅ Received {len(df)} candles")
    
    # 2. Get current candle time
    current_candle_time = df.index[-1]
    current_price = df['close'].iloc[-1]
    
    print(f"⏰ Current candle time: {current_candle_time}")
    print(f"💰 Current price: ${current_price:.2f}")
    print(f"📊 Last candle time stored: {last_candle_time}")
    
    # 3. Check if new candle (LOGIQUE CRITIQUE DU BOT)
    if last_candle_time != current_candle_time:
        print(f"\n🆕 NOUVELLE BOUGIE DÉTECTÉE!")
        print(f"   Ancienne: {last_candle_time}")
        print(f"   Nouvelle: {current_candle_time}")
        
        last_candle_time = current_candle_time
        
        # 4. Analyze strategies
        print("\n🔍 Analyzing strategies...")
        rm = RiskManager()
        engine = StrategyEngine(rm)
        
        result = engine.analyze(df)
        
        print(f"📊 Analysis complete:")
        print(f"   Regime: {result.get('regime')}")
        print(f"   ADX: {result.get('adx', 0):.2f}")
        print(f"   Active strategies: {len(result.get('strategies', []))}")
        print(f"   Signals found: {len(result.get('signals', []))}")
        
        if result.get('signals'):
            print("\n🚨 SIGNAUX DÉTECTÉS:")
            for sig in result['signals']:
                print(f"   Strategy: {sig.get('strategy')}")
                print(f"   Action: {sig.get('signal')} @ ${sig.get('price', 0):.2f}")
                print(f"   SL: ${sig.get('sl', 0):.2f}")
                print(f"   TP: ${sig.get('tp', 0):.2f}")
                print(f"   Comment: {sig.get('comment')}")
        else:
            print("   ℹ️ No signals for this candle")
    else:
        print(f"\n⏸️  MÊME BOUGIE - Pas d'analyse")
        print(f"   On attend la prochaine bougie 15m...")
    
    if i < 2:
        print(f"\n⏳ Attente 3 secondes avant prochaine itération...")
        time.sleep(3)

print("\n" + "=" * 80)
print("📊 RÉSUMÉ DU TEST")
print("=" * 80)
print(f"Total itérations: {iteration}")
print(f"Dernière bougie: {last_candle_time}")
print("\n💡 CONCLUSION:")
print("   - Le bot vérifie toutes les 5 secondes")
print("   - Mais n'analyse QUE quand une nouvelle bougie 15m apparaît")
print("   - Les bougies 15m changent toutes les 15 minutes")
print("   - Donc le bot analyse ~4 fois par heure maximum")
print("\n⚠️  PROBLÈME IDENTIFIÉ:")
print("   Sur le serveur, les logs montrent que le bot:")
print("   1. ✅ Récupère les données")
print("   2. ❌ Mais ne montre JAMAIS les logs d'analyse")
print("   3. → Soit last_candle_time n'est pas initialisé")
print("   4. → Soit il y a un bug dans la détection de nouvelle bougie")
print("\n🔧 SOLUTION:")
print("   Vérifier l'initialisation de last_candle_time dans BotContext.__init__()")
print("=" * 80)
