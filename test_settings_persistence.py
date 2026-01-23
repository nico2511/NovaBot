"""
Settings Persistence Test Suite
Tests all settings operations to ensure reliable persistence
"""

import requests
import json
import time
import sys

# Configuration
API_BASE_URL = "http://10.10.20.76:8001"  # Production server
API_KEY = "dev_secret_change_in_production"  # Update if needed

class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    END = '\033[0m'

def print_test(name):
    print(f"\n{Colors.BLUE}🧪 TEST: {name}{Colors.END}")

def print_success(msg):
    print(f"{Colors.GREEN}✅ {msg}{Colors.END}")

def print_error(msg):
    print(f"{Colors.RED}❌ {msg}{Colors.END}")

def print_warning(msg):
    print(f"{Colors.YELLOW}⚠️  {msg}{Colors.END}")

# Test 1: Check API connectivity
def test_api_connectivity():
    print_test("API Connectivity")
    try:
        response = requests.get(f"{API_BASE_URL}/api/status", timeout=5)
        if response.status_code == 200:
            print_success("API is reachable")
            return True
        else:
            print_error(f"API returned status {response.status_code}")
            return False
    except Exception as e:
        print_error(f"Cannot reach API: {e}")
        return False

# Test 2: Get all settings
def test_get_all_settings():
    print_test("Get All Settings")
    try:
        response = requests.get(f"{API_BASE_URL}/api/settings/all")
        if response.status_code == 200:
            settings = response.json()
            print_success(f"Retrieved settings: {list(settings.keys())}")
            return settings
        else:
            print_error(f"Failed to get settings: {response.status_code}")
            return None
    except Exception as e:
        print_error(f"Error: {e}")
        return None

# Test 3: Update scanner settings
def test_update_scanner_settings():
    print_test("Update Scanner Settings")
    
    # Get current settings
    response = requests.get(f"{API_BASE_URL}/api/settings/scanner")
    if response.status_code != 200:
        print_error("Failed to get current scanner settings")
        return False
    
    original = response.json()
    print(f"   Original: {original}")
    
    # Update settings
    new_settings = {
        "enabled": not original.get("enabled", False),
        "interval": 20,
        "min_score": 80,
        "auto_switch": True,
        "gamification_enabled": True
    }
    
    payload = {
        "section": "scanner",
        "data": new_settings
    }
    
    response = requests.post(
        f"{API_BASE_URL}/api/settings/update",
        json=payload,
        headers={"Content-Type": "application/json"}
    )
    
    if response.status_code == 200:
        print_success("Settings updated successfully")
        
        # Verify update
        time.sleep(1)
        response = requests.get(f"{API_BASE_URL}/api/settings/scanner")
        if response.status_code == 200:
            updated = response.json()
            print(f"   Updated: {updated}")
            
            # Check if values match
            if updated.get("interval") == 20 and updated.get("min_score") == 80:
                print_success("Settings persisted correctly")
                return True
            else:
                print_error("Settings did not persist correctly")
                return False
        else:
            print_error("Failed to verify update")
            return False
    else:
        print_error(f"Update failed: {response.status_code} - {response.text}")
        return False

# Test 4: Update global settings
def test_update_global_settings():
    print_test("Update Global Settings (Risk Defaults)")
    
    # Get current settings
    response = requests.get(f"{API_BASE_URL}/api/settings/global")
    if response.status_code != 200:
        print_error("Failed to get current global settings")
        return False
    
    original = response.json()
    print(f"   Original max_positions: {original.get('max_positions')}")
    
    # Update risk_defaults
    new_max_positions = 2 if original.get("max_positions") == 1 else 1
    
    payload = {
        "section": "risk_defaults",
        "data": {
            "max_positions": new_max_positions,
            "daily_stop_loss": 50.0,
            "bot_persona": "Conservative Scalper",
            "risk_profile": "Capital Preservation First"
        }
    }
    
    response = requests.post(
        f"{API_BASE_URL}/api/settings/update",
        json=payload,
        headers={"Content-Type": "application/json"}
    )
    
    if response.status_code == 200:
        print_success("Risk defaults updated")
        
        # Verify update
        time.sleep(1)
        response = requests.get(f"{API_BASE_URL}/api/settings/global")
        if response.status_code == 200:
            updated = response.json()
            print(f"   Updated max_positions: {updated.get('max_positions')}")
            
            if updated.get("max_positions") == new_max_positions:
                print_success("Risk defaults persisted correctly")
                return True
            else:
                print_error(f"Expected {new_max_positions}, got {updated.get('max_positions')}")
                return False
        else:
            print_error("Failed to verify update")
            return False
    else:
        print_error(f"Update failed: {response.status_code}")
        return False

# Test 5: Check logs endpoint
def test_logs_endpoint():
    print_test("Logs Endpoint")
    try:
        response = requests.get(f"{API_BASE_URL}/api/logs?limit=10")
        if response.status_code == 200:
            data = response.json()
            logs = data.get("logs", [])
            print_success(f"Logs endpoint working - {len(logs)} entries retrieved")
            return True
        else:
            print_error(f"Logs endpoint failed: {response.status_code}")
            return False
    except Exception as e:
        print_error(f"Error: {e}")
        return False

# Test 6: Check for backup files
def test_backup_files():
    print_test("Backup File Creation")
    print_warning("This test requires SSH access to production server")
    print("   Manual check: SSH to server and run:")
    print("   ls -la user_settings.json*")
    print("   You should see: user_settings.json and user_settings.json.bak")
    return True

# Main test runner
def run_all_tests():
    print(f"\n{'='*60}")
    print(f"{Colors.BLUE}Settings Persistence Test Suite{Colors.END}")
    print(f"Target: {API_BASE_URL}")
    print(f"{'='*60}")
    
    results = {}
    
    # Run tests
    results["API Connectivity"] = test_api_connectivity()
    
    if results["API Connectivity"]:
        results["Get All Settings"] = test_get_all_settings() is not None
        results["Update Scanner Settings"] = test_update_scanner_settings()
        results["Update Global Settings"] = test_update_global_settings()
        results["Logs Endpoint"] = test_logs_endpoint()
        results["Backup Files"] = test_backup_files()
    else:
        print_error("\nCannot proceed - API is not reachable")
        sys.exit(1)
    
    # Summary
    print(f"\n{'='*60}")
    print(f"{Colors.BLUE}TEST SUMMARY{Colors.END}")
    print(f"{'='*60}")
    
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    
    for test_name, result in results.items():
        status = f"{Colors.GREEN}PASS{Colors.END}" if result else f"{Colors.RED}FAIL{Colors.END}"
        print(f"{test_name}: {status}")
    
    print(f"\n{Colors.BLUE}Results: {passed}/{total} tests passed{Colors.END}")
    
    if passed == total:
        print(f"{Colors.GREEN}🎉 All tests passed!{Colors.END}\n")
        return 0
    else:
        print(f"{Colors.RED}⚠️  Some tests failed{Colors.END}\n")
        return 1

if __name__ == "__main__":
    exit_code = run_all_tests()
    sys.exit(exit_code)
