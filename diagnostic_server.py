#!/usr/bin/env python3
"""
Script de diagnostic pour identifier pourquoi le bot ne génère pas de signaux
À exécuter sur le serveur : python diagnostic_server.py
"""
import json
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.services.hyperliquid_service import hyperliquid_service
from strategies.engine import StrategyEngine
from app.core.risk_manager import RiskManager

print("=" * 80)
print("🔍 DIAGNOSTIC DU BOT - SERVEUR")
print("=" * 80)

# 1. Vérifier bot_state.json
print("\n1️⃣ État du bot (bot_state.json):")
print("-" * 80)
try:
    with open('bot_state.json', 'r') as f:
        state = json.load(f)
    print(f"   is_running: {state.get('is_running')}")
    print(f"   trading_enabled: {state.get('trading_enabled')}")
    print(f"   active_symbol: {state.get('active_symbol')}")
    print(f"   last_updated: {state.get('last_updated')}")
    print(f"   execution_mode: {state.get('execution_mode')}")
    print(f"   active_trade: {state.get('active_trade')}")
except Exception as e:
    print(f"   ❌ Erreur: {e}")

# 2. Vérifier strategies.json
print("\n2️⃣ Configuration des stratégies:")
print("-" * 80)
try:
    with open('strategies.json', 'r') as f:
        config = json.load(f)
    
    enabled = [name for name, cfg in config['strategies'].items() if cfg.get('enabled')]
    disabled = [name for name, cfg in config['strategies'].items() if not cfg.get('enabled')]
    
    print(f"   Stratégies activées ({len(enabled)}):")
    for s in enabled:
        print(f"      ✅ {s}")
    
    if disabled:
        print(f"   Stratégies désactivées ({len(disabled)}):")
        for s in disabled:
            print(f"      ❌ {s}")
except Exception as e:
    print(f"   ❌ Erreur: {e}")

# 3. Test de connexion API
print("\n3️⃣ Test de connexion Hyperliquid:")
print("-" * 80)
try:
    df = hyperliquid_service.get_candles("BTC", interval="15m", limit=10)
    if not df.empty:
        print(f"   ✅ Connexion OK - {len(df)} bougies reçues")
        print(f"   Dernière bougie: {df.index[-1]}")
        print(f"   Prix actuel: ${df['close'].iloc[-1]:.2f}")
    else:
        print("   ❌ Aucune donnée reçue")
except Exception as e:
    print(f"   ❌ Erreur: {e}")

# 4. Test du moteur de stratégies
print("\n4️⃣ Test du moteur de stratégies:")
print("-" * 80)
try:
    df = hyperliquid_service.get_candles("BTC", interval="15m", limit=200)
    rm = RiskManager()
    engine = StrategyEngine(rm)
    
    result = engine.analyze(df)
    
    print(f"   Régime de marché: {result.get('regime')}")
    print(f"   ADX: {result.get('adx', 0):.2f}")
    print(f"   Stratégies actives: {result.get('strategies', [])}")
    print(f"   Nombre de signaux: {len(result.get('signals', []))}")
    
    if result.get('signals'):
        print("\n   🚨 SIGNAUX DÉTECTÉS:")
        for sig in result['signals']:
            print(f"      - {sig.get('strategy')}: {sig.get('signal')} @ ${sig.get('price', 0):.2f}")
    else:
        print("   ℹ️ Aucun signal détecté pour cette bougie")
        
except Exception as e:
    print(f"   ❌ Erreur: {e}")
    import traceback
    traceback.print_exc()

# 5. Recommandations
print("\n" + "=" * 80)
print("📋 RECOMMANDATIONS")
print("=" * 80)

if state.get('trading_enabled') == False:
    print("⚠️  PROBLÈME: trading_enabled est à False")
    print("   → Le bot ne prendra aucune position même s'il détecte des signaux")
    print("   → Solution: Activer le trading via l'interface Next.js")

print("\n💡 Pour activer le trading:")
print("   1. Ouvrir l'interface: http://votre-serveur:3000")
print("   2. Activer le toggle 'Trading Enabled'")
print("   3. Vérifier que le bot analyse les bougies dans les logs")

print("\n" + "=" * 80)
