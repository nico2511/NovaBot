#!/usr/bin/env python3
"""
Script pour activer le trading automatique dans bot_state.json
Cela simule ce qui se passerait si vous activiez les options dans l'interface
"""
import json
import os
from datetime import datetime

STATE_FILE = "bot_state.json"

def enable_auto_trading():
    """Active le trading automatique dans bot_state.json"""
    
    if not os.path.exists(STATE_FILE):
        print(f"❌ {STATE_FILE} n'existe pas")
        return
    
    # Charger l'état actuel
    with open(STATE_FILE, "r") as f:
        state = json.load(f)
    
    print("=" * 60)
    print("🔧 ACTIVATION DU TRADING AUTOMATIQUE")
    print("=" * 60)
    
    print(f"\n📄 État actuel de {STATE_FILE}:")
    print(f"  • trading_enabled: {state.get('trading_enabled')}")
    sidebar = state.get('sidebar_settings', {})
    print(f"  • execution_mode: {sidebar.get('execution_mode', 'N/A')}")
    print(f"  • trading_enabled (sidebar): {sidebar.get('trading_enabled', 'N/A')}")
    
    # Mettre à jour les paramètres
    state['trading_enabled'] = True
    
    if 'sidebar_settings' not in state:
        state['sidebar_settings'] = {}
    
    state['sidebar_settings']['execution_mode'] = 'Auto (Hyperliquid)'
    state['sidebar_settings']['trading_enabled'] = True
    state['last_updated'] = str(datetime.now())
    
    # Sauvegarder
    backup_file = f"{STATE_FILE}.backup"
    with open(backup_file, "w") as f:
        json.dump(state, f, indent=4)
    print(f"\n💾 Backup créé: {backup_file}")
    
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=4)
    
    print(f"\n✅ {STATE_FILE} mis à jour:")
    print(f"  • trading_enabled: {state.get('trading_enabled')}")
    print(f"  • execution_mode: {state['sidebar_settings'].get('execution_mode')}")
    print(f"  • trading_enabled (sidebar): {state['sidebar_settings'].get('trading_enabled')}")
    
    print("\n🎯 Prochaines étapes:")
    print("  1. Redémarrez l'application Streamlit")
    print("  2. Vérifiez que 'Auto (Hyperliquid)' est sélectionné")
    print("  3. Vérifiez que '✅ ALLOW LIVE TRADING' est coché")
    print("\n" + "=" * 60)

if __name__ == "__main__":
    enable_auto_trading()
