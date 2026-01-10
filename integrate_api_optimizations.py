#!/usr/bin/env python3
"""
Script d'intégration automatique des optimisations API
Version: 2.0.0
ATTENTION: Fait un backup avant toute modification
"""

import shutil
import re
from pathlib import Path

def backup_file(filepath):
    """Create backup of file"""
    backup_path = f"{filepath}.backup"
    shutil.copy(filepath, backup_path)
    print(f"✅ Backup créé: {backup_path}")
    return backup_path

def integrate_optimizations():
    """Integrate all API optimizations"""
    
    api_file = Path("backend/api.py")
    
    if not api_file.exists():
        print("❌ Fichier backend/api.py introuvable")
        return False
    
    # 1. Backup
    print("\n📦 Création du backup...")
    backup_file(api_file)
    
    # 2. Lire le fichier
    print("\n📖 Lecture du fichier...")
    with open(api_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 3. Modifications
    print("\n🔧 Application des optimisations...")
    
    # 3.1 Ajouter imports
    if "from backend.api_optimizations import" not in content:
        import_section = """
# Optimizations imports
import time
import logging
from backend.api_optimizations import (
    logger,
    verify_api_key,
    ai_cooldown_check,
    ai_cache_update,
    execute_bot_action,
    log_requests_middleware
)
"""
        # Insérer après les imports existants (après ligne ~15)
        content = content.replace(
            "import pandas as pd",
            f"import pandas as pd{import_section}"
        )
        print("  ✅ Imports ajoutés")
    
    # 3.2 Ajouter middleware logging (après création de app)
    if "@app.middleware" not in content or "log_middleware" not in content:
        middleware_code = """
# Logging middleware
@app.middleware("http")
async def log_middleware(request: Request, call_next):
    return await log_requests_middleware(request, call_next)
"""
        # Insérer après app = FastAPI(...)
        content = content.replace(
            'app = FastAPI(title="HyperLiquid Trading Bot API")',
            f'app = FastAPI(title="HyperLiquid Trading Bot API"){middleware_code}'
        )
        print("  ✅ Middleware logging ajouté")
    
    # 3.3 Ajouter bridge status endpoint
    if "/api/bridge/status" not in content:
        bridge_endpoint = '''
@app.get("/api/bridge/status")
async def get_bridge_status():
    """Get bot bridge connection status"""
    try:
        if not bot_bridge:
            return {
                "connected": False,
                "status": "not_initialized",
                "message": "Bot bridge not initialized"
            }
        
        is_connected = bot_bridge.is_connected()
        
        if is_connected:
            bot = bot_bridge.get_bot_context()
            return {
                "connected": True,
                "status": "connected",
                "bot_running": getattr(bot, 'is_running', False),
                "active_symbol": getattr(bot, 'active_symbol', None),
                "uptime": time.time() - getattr(bot, 'start_time', time.time())
            }
        else:
            return {
                "connected": False,
                "status": "disconnected",
                "message": "Bot bridge disconnected - using fallback mode"
            }
            
    except Exception as e:
        logger.error(f"Bridge status check error: {e}")
        return {
            "connected": False,
            "status": "error",
            "error": str(e)
        }
'''
        # Insérer avant la dernière route
        content = content.replace(
            '@app.get("/api/logs")',
            f'{bridge_endpoint}\n\n@app.get("/api/logs")'
        )
        print("  ✅ Bridge status endpoint ajouté")
    
    # 3.4 Protéger endpoints critiques
    endpoints_to_protect = [
        ("/close_trade", "async def close_trade("),
        ("/execute_manual_trade", "async def execute_manual_trade("),
        ("/force_breakeven", "async def force_breakeven("),
        ("/recalibrate_stops", "async def recalibrate_stops("),
        ("/toggle_gamification", "async def toggle_gamification("),
        ("/dev/git_pull", "async def dev_git_pull("),
        ("/dev/restart_all", "async def dev_restart_all("),
        ("/dev/rebuild_frontend", "async def dev_rebuild_frontend(")
    ]
    
    for route, func_def in endpoints_to_protect:
        if route in content and "_: bool = Depends(verify_api_key)" not in content[content.find(route):content.find(route)+500]:
            # Ajouter Depends(verify_api_key)
            pattern = f"({re.escape(func_def)})"
            replacement = f"{func_def}_: bool = Depends(verify_api_key), "
            content = re.sub(pattern, replacement, content, count=1)
            print(f"  ✅ Protection ajoutée: {route}")
    
    # 3.5 Ajouter AI cooldown
    ai_endpoints = [
        "ai_signal_analysis",
        "ai_market_commentary",
        "ai_position_analysis"
    ]
    
    for endpoint in ai_endpoints:
        if endpoint in content and "ai_cooldown_check" not in content[content.find(endpoint):content.find(endpoint)+1000]:
            # Trouver le début de la fonction
            func_start = content.find(f"async def {endpoint}")
            if func_start != -1:
                # Trouver le premier try:
                try_pos = content.find("try:", func_start)
                if try_pos != -1:
                    cooldown_code = f'''
        # Check AI cooldown
        cached = ai_cooldown_check("{endpoint.replace("ai_", "")}")
        if cached:
            return cached
        
'''
                    content = content[:try_pos+4] + cooldown_code + content[try_pos+4:]
                    print(f"  ✅ AI cooldown ajouté: {endpoint}")
    
    # 3.6 Remplacer print par logger (sélectif)
    content = re.sub(r'print\(f"Error:', 'logger.error(f"', content)
    content = re.sub(r'print\(f"⚠️', 'logger.warning(f"⚠️', content)
    content = re.sub(r'print\(f"❌', 'logger.error(f"❌', content)
    print("  ✅ Logs améliorés (print → logger)")
    
    # 4. Écrire le fichier modifié
    print("\n💾 Sauvegarde des modifications...")
    with open(api_file, 'w', encoding='utf-8') as f:
        f.write(content)
    
    print("\n✅ Intégration terminée !")
    print(f"\n📝 Backup disponible: {api_file}.backup")
    print("\n🧪 Testez maintenant avec: python -m uvicorn backend.api:app --reload")
    print("\n⚠️ Si problème, restaurez: cp backend/api.py.backup backend/api.py")
    
    return True

if __name__ == "__main__":
    print("=" * 60)
    print("  API Optimizations Integration Script v2.0.0")
    print("=" * 60)
    
    success = integrate_optimizations()
    
    if success:
        print("\n🎉 Intégration réussie !")
    else:
        print("\n❌ Intégration échouée")
