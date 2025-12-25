#!/usr/bin/env python3
"""
Diagnostic script for PyBot
Checks the current state and configuration
"""
import json
import os
from datetime import datetime

def check_bot_state():
    """Check the bot_state.json file"""
    print("=" * 60)
    print("🔍 DIAGNOSTIC PYBOT - État du Bot")
    print("=" * 60)
    print(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    
    # Check bot_state.json
    if os.path.exists("bot_state.json"):
        print("✅ bot_state.json trouvé")
        with open("bot_state.json", "r") as f:
            state = json.load(f)
        
        print("\n📊 État actuel du bot:")
        print(f"  • Trading activé: {state.get('trading_enabled', 'N/A')}")
        print(f"  • Symbole actif: {state.get('active_symbol', 'N/A')}")
        print(f"  • Trade actif: {state.get('active_trade', 'N/A')}")
        print(f"  • Dernière mise à jour: {state.get('last_updated', 'N/A')}")
        
        print("\n🛡️ État du Risk Manager:")
        risk = state.get('risk_state', {})
        print(f"  • PnL journalier: ${risk.get('daily_pnl', 0):.2f}")
        print(f"  • Positions ouvertes: {risk.get('open_positions', 0)}")
        print(f"  • Mode stop: {risk.get('is_stop_mode', False)}")
        if risk.get('stop_reason'):
            print(f"  • Raison du stop: {risk.get('stop_reason')}")
        
        print("\n⚙️ Paramètres de la sidebar:")
        sidebar = state.get('sidebar_settings', {})
        if sidebar:
            print(f"  • Mode d'exécution: {sidebar.get('execution_mode', 'N/A')}")
            print(f"  • Trading en direct: {sidebar.get('trading_enabled', 'N/A')}")
            print(f"  • Type de taille: {sidebar.get('size_type', 'N/A')}")
            print(f"  • Valeur de taille: {sidebar.get('size_value', 'N/A')}")
            print(f"  • Levier: {sidebar.get('leverage', 'N/A')}")
            print(f"  • Max positions: {sidebar.get('max_positions', 'N/A')}")
            print(f"  • Stop loss journalier: ${sidebar.get('daily_stop_loss', 'N/A')}")
        else:
            print("  ⚠️ Aucun paramètre de sidebar trouvé")
    else:
        print("❌ bot_state.json non trouvé")
    
    # Check strategies.json
    print("\n" + "=" * 60)
    if os.path.exists("strategies.json"):
        print("✅ strategies.json trouvé")
        with open("strategies.json", "r") as f:
            strategies = json.load(f)
        
        print("\n📈 Stratégies configurées:")
        strats = strategies.get('strategies', {})
        enabled_count = 0
        for name, config in strats.items():
            status = "✅" if config.get('enabled') else "❌"
            enabled_count += 1 if config.get('enabled') else 0
            print(f"  {status} {name} ({config.get('type', 'N/A')})")
        
        print(f"\n  Total: {len(strats)} stratégies, {enabled_count} activées")
        
        regime = strategies.get('market_regime', {})
        print(f"\n🌊 Régime de marché:")
        print(f"  • Seuil ADX: {regime.get('adx_threshold', 'N/A')}")
        print(f"  • Timeframe: {regime.get('timeframe', 'N/A')}")
    else:
        print("❌ strategies.json non trouvé")
    
    # Check .env
    print("\n" + "=" * 60)
    if os.path.exists(".env"):
        print("✅ .env trouvé")
        with open(".env", "r") as f:
            lines = f.readlines()
        
        print("\n🔑 Variables d'environnement:")
        has_hl_key = False
        has_hl_address = False
        
        for line in lines:
            line = line.strip()
            if line.startswith("HL_PRIVATE_KEY=") and len(line) > 15:
                has_hl_key = True
                print("  ✅ HL_PRIVATE_KEY configuré")
            elif line.startswith("HL_ACCOUNT_ADDRESS=") and len(line) > 19:
                has_hl_address = True
                print("  ✅ HL_ACCOUNT_ADDRESS configuré")
        
        if not has_hl_key:
            print("  ⚠️ HL_PRIVATE_KEY manquant ou vide")
        if not has_hl_address:
            print("  ⚠️ HL_ACCOUNT_ADDRESS manquant ou vide")
    else:
        print("❌ .env non trouvé")
    
    # Recommendations
    print("\n" + "=" * 60)
    print("💡 RECOMMANDATIONS:")
    print("=" * 60)
    
    if os.path.exists("bot_state.json"):
        with open("bot_state.json", "r") as f:
            state = json.load(f)
        
        sidebar = state.get('sidebar_settings', {})
        
        if not state.get('trading_enabled'):
            print("⚠️  Le trading n'est PAS activé dans l'état du bot")
            print("   → Activez 'ALLOW LIVE TRADING' dans l'interface")
        
        if sidebar.get('execution_mode') != 'Auto (Hyperliquid)':
            print("⚠️  Le mode d'exécution n'est pas sur 'Auto (Hyperliquid)'")
            print(f"   → Mode actuel: {sidebar.get('execution_mode', 'N/A')}")
            print("   → Changez le mode dans l'interface")
        
        if not sidebar.get('trading_enabled'):
            print("⚠️  Le trading n'est PAS activé dans les paramètres de la sidebar")
            print("   → Activez 'ALLOW LIVE TRADING' dans l'interface")
        
        if state.get('trading_enabled') and sidebar.get('execution_mode') == 'Auto (Hyperliquid)' and sidebar.get('trading_enabled'):
            print("✅ Configuration correcte pour le trading automatique!")
    
    print("\n" + "=" * 60)

if __name__ == "__main__":
    check_bot_state()
