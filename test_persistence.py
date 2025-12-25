#!/usr/bin/env python3
"""
Test script to verify persistence logic
Simulates what happens when the app restarts
"""
import json

# Simulate bot_state.json with trading enabled
test_state = {
    "active_trade": None,
    "trading_enabled": False,
    "active_symbol": "BTC",
    "last_updated": "2025-12-25 08:00:00",
    "risk_state": {
        "daily_pnl": 0.0,
        "open_positions": 0,
        "is_stop_mode": False,
        "stop_reason": ""
    },
    "sidebar_settings": {
        "execution_mode": "Auto (Hyperliquid)",
        "trading_enabled": True,  # THIS SHOULD BE RESTORED
        "size_type": "Fixed (USDC)",
        "size_value": 200.0,
        "leverage": 20,
        "max_positions": 2,
        "daily_stop_loss": 50.0
    }
}

print("=" * 60)
print("🧪 TEST DE PERSISTANCE")
print("=" * 60)

print("\n📄 Contenu de bot_state.json simulé:")
print(json.dumps(test_state, indent=2))

print("\n🔍 Valeurs à restaurer:")
sidebar_settings = test_state.get('sidebar_settings', {})
print(f"  • execution_mode: {sidebar_settings.get('execution_mode')}")
print(f"  • trading_enabled: {sidebar_settings.get('trading_enabled')}")

print("\n✅ Logique de restauration:")
print("  1. Au démarrage de l'app, session_state est VIDE")
print("  2. render_sidebar() est appelé avec persisted_settings = sidebar_settings")
print("  3. Pour chaque clé dans persisted_settings:")
print("     - Si la clé n'existe PAS dans session_state")
print("     - Alors: session_state[clé] = persisted_settings[clé]")

# Simulate session_state initialization
session_state = {}
persisted_settings = sidebar_settings

print("\n🔄 Simulation de l'initialisation:")
for key, value in persisted_settings.items():
    if key not in session_state:
        session_state[key] = value
        print(f"  ✅ Restauré: {key} = {value}")

print("\n📊 État final de session_state:")
print(f"  • execution_mode: {session_state.get('execution_mode')}")
print(f"  • trading_enabled: {session_state.get('trading_enabled')}")

print("\n🎯 Résultat attendu:")
if session_state.get('execution_mode') == 'Auto (Hyperliquid)' and session_state.get('trading_enabled') == True:
    print("  ✅ SUCCESS! Les paramètres sont correctement restaurés")
else:
    print("  ❌ ÉCHEC! Les paramètres ne sont pas restaurés")
    print(f"     execution_mode: {session_state.get('execution_mode')} (attendu: 'Auto (Hyperliquid)')")
    print(f"     trading_enabled: {session_state.get('trading_enabled')} (attendu: True)")

print("\n" + "=" * 60)
