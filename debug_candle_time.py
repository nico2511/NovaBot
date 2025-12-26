#!/usr/bin/env python3
"""
Script pour vérifier EXACTEMENT ce qui se passe avec last_candle_time
À exécuter sur le serveur pour debug
"""
import sys
import os
import time
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.services.hyperliquid_service import hyperliquid_service

print("=" * 80)
print("🔍 DEBUG: Vérification de la détection de nouvelle bougie")
print("=" * 80)

# Simuler exactement ce que fait le bot
last_candle_time = None

for i in range(5):
    print(f"\n--- Itération {i+1} ---")
    
    # Fetch comme le bot
    df = hyperliquid_service.get_candles("BTC", interval="15m", limit=200)
    
    if df.empty:
        print("❌ No data")
        continue
    
    current_candle_time = df.index[-1]
    current_price = df['close'].iloc[-1]
    
    print(f"current_candle_time: {current_candle_time}")
    print(f"current_candle_time type: {type(current_candle_time)}")
    print(f"last_candle_time: {last_candle_time}")
    print(f"last_candle_time type: {type(last_candle_time)}")
    
    # Test de comparaison
    print(f"\nComparaison:")
    print(f"  last_candle_time != current_candle_time: {last_candle_time != current_candle_time}")
    print(f"  last_candle_time == current_candle_time: {last_candle_time == current_candle_time}")
    print(f"  last_candle_time is None: {last_candle_time is None}")
    
    if last_candle_time != current_candle_time:
        print("✅ NOUVELLE BOUGIE DÉTECTÉE!")
        last_candle_time = current_candle_time
    else:
        print("⏸️  Même bougie")
    
    if i < 4:
        time.sleep(2)

print("\n" + "=" * 80)
print("🎯 CONCLUSION:")
print(f"Dernière valeur de last_candle_time: {last_candle_time}")
print(f"Type: {type(last_candle_time)}")
print("=" * 80)
