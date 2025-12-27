#!/usr/bin/env python3
"""
Script de test pour le système de commentaires IA
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.services.gemini_service import gemini_service
import json

print("=" * 60)
print("🧪 Test du Système de Commentaires IA")
print("=" * 60)

# Test 1: Analyse de signal
print("\n1️⃣ Test: Analyse de Signal")
print("-" * 60)

signal_data = {
    "signal": "BUY",
    "price": 87000,
    "sl": 86500,
    "tp": 88500,
    "strategy": "ScalpEmaRsi",
    "comment": "EMA Bullish + Trend + RSI"
}

market_context = {
    "symbol": "BTC",
    "regime": "TREND",
    "price": 87000
}

print(f"Signal: {signal_data}")
print(f"Context: {market_context}")
print("\nAppel de l'IA...")

try:
    result = gemini_service.analyze_trade_signal(signal_data, market_context)
    print(f"\n✅ Réponse reçue:")
    print(f"Model: {result.get('model', 'N/A')}")
    
    if result.get('raw_output'):
        try:
            parsed = json.loads(result['raw_output'])
            print(f"\n📊 Analyse:")
            print(f"  - Explication: {parsed.get('explanation', 'N/A')}")
            print(f"  - Confiance: {parsed.get('confidence', 'N/A')}")
            print(f"  - Recommandation: {parsed.get('recommendation', 'N/A')}")
            if parsed.get('risks'):
                print(f"  - Risques: {', '.join(parsed['risks'])}")
        except json.JSONDecodeError:
            print(f"Raw output: {result['raw_output'][:200]}...")
    else:
        print(f"⚠️ Pas de sortie: {result}")
        
except Exception as e:
    print(f"❌ Erreur: {e}")

# Test 2: Analyse d'évolution du marché
print("\n\n2️⃣ Test: Analyse d'Évolution du Marché")
print("-" * 60)

current_data = {
    "symbol": "BTC",
    "price": 87500,
    "regime": "TREND",
    "timestamp": "2025-12-27T17:00:00"
}

previous_data = {
    "symbol": "BTC",
    "price": 87000,
    "regime": "TREND",
    "timestamp": "2025-12-27T16:45:00"
}

print(f"État actuel: {current_data}")
print(f"État précédent: {previous_data}")
print("\nAppel de l'IA...")

try:
    result = gemini_service.analyze_market_evolution(current_data, previous_data)
    print(f"\n✅ Réponse reçue:")
    
    if result.get('raw_output'):
        try:
            parsed = json.loads(result['raw_output'])
            print(f"\n📊 Analyse:")
            print(f"  - Résumé: {parsed.get('summary', 'N/A')}")
            print(f"  - Niveau d'alerte: {parsed.get('alert_level', 'N/A')}")
            if parsed.get('changes'):
                print(f"  - Changements:")
                for change in parsed['changes']:
                    print(f"    • {change}")
        except json.JSONDecodeError:
            print(f"Raw output: {result['raw_output'][:200]}...")
    else:
        print(f"⚠️ Pas de sortie: {result}")
        
except Exception as e:
    print(f"❌ Erreur: {e}")

print("\n" + "=" * 60)
print("✅ Tests terminés!")
print("=" * 60)
print("\n💡 Note: Si vous voyez des erreurs de quota, c'est normal.")
print("   Le système utilise la version gratuite de Gemini.")
print("\n🚀 Pour tester en conditions réelles, démarrez le bot:")
print("   ./start_integrated.sh")
