
import requests
import sys
import json

BASE_URL = "http://localhost:8001"

def check_endpoint(method, endpoint):
    try:
        url = f"{BASE_URL}{endpoint}"
        if method == "GET":
            response = requests.get(url, timeout=2)
        else:
            response = requests.post(url, timeout=2)
        
        if response.status_code == 200:
            print(f"✅ {endpoint}: OK")
            return response.json()
        else:
            print(f"❌ {endpoint}: Failed ({response.status_code})")
            return None
    except Exception as e:
        print(f"❌ {endpoint}: Error ({e})")
        return None

def verify_system():
    print("🔍 Starting System Verification...")
    
    # 1. Check Status
    status = check_endpoint("GET", "/api/status")
    if status:
        print(f"   => Bot Running: {status.get('is_running')}")
        print(f"   => Active Symbol: {status.get('active_symbol')}")
    
    # 2. Check Strategies
    strategies = check_endpoint("GET", "/api/config/strategy-list")
    if strategies:
        print(f"   => Loaded Strategies: {len(strategies)}")

    # 3. Check Settings (Critical for User Config Split)
    settings = check_endpoint("GET", "/api/settings/all")
    if settings:
        notifs = settings.get("notifications", {})
        alert_webhook = notifs.get("discord_webhook_alerts", "")
        print(f"   => Settings Loaded Correctly: {True if settings else False}")
        print(f"   => Discord Webhook Present: {'Yes' if alert_webhook and 'discord' in alert_webhook else 'NO ⚠️'}")
        
    print("\n🏁 Use Browser to check UI if all checks passed.")

if __name__ == "__main__":
    verify_system()
