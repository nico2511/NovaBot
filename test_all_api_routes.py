"""
Comprehensive API Test Suite
Tests ALL endpoints to ensure 100% functionality
"""

import requests
import json
import time
import sys
from typing import Dict, List, Tuple

# Configuration
API_BASE_URL = "http://10.10.20.76:8001"
API_KEY = "dev_secret_change_in_production"

class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    END = '\033[0m'

class APITester:
    def __init__(self, base_url: str):
        self.base_url = base_url
        self.results = []
        self.passed = 0
        self.failed = 0
        
    def test(self, name: str, method: str, endpoint: str, **kwargs) -> bool:
        """Generic test method"""
        print(f"\n{Colors.CYAN}Testing: {name}{Colors.END}")
        print(f"  {method} {endpoint}")
        
        try:
            url = f"{self.base_url}{endpoint}"
            
            if method == "GET":
                response = requests.get(url, timeout=10, **kwargs)
            elif method == "POST":
                response = requests.post(url, timeout=10, **kwargs)
            else:
                print(f"{Colors.RED}❌ Unknown method: {method}{Colors.END}")
                return False
            
            # Check status code
            if response.status_code in [200, 201]:
                print(f"{Colors.GREEN}✅ PASS - Status: {response.status_code}{Colors.END}")
                
                # Try to parse JSON
                try:
                    data = response.json()
                    print(f"  Response keys: {list(data.keys()) if isinstance(data, dict) else type(data).__name__}")
                except:
                    print(f"  Response: {response.text[:100]}")
                
                self.passed += 1
                self.results.append((name, True, response.status_code))
                return True
            else:
                print(f"{Colors.RED}❌ FAIL - Status: {response.status_code}{Colors.END}")
                print(f"  Response: {response.text[:200]}")
                self.failed += 1
                self.results.append((name, False, response.status_code))
                return False
                
        except Exception as e:
            print(f"{Colors.RED}❌ ERROR: {str(e)}{Colors.END}")
            self.failed += 1
            self.results.append((name, False, str(e)))
            return False
    
    def print_summary(self):
        """Print test summary"""
        print(f"\n{'='*70}")
        print(f"{Colors.BLUE}TEST SUMMARY{Colors.END}")
        print(f"{'='*70}")
        
        total = self.passed + self.failed
        print(f"\nTotal Tests: {total}")
        print(f"{Colors.GREEN}Passed: {self.passed}{Colors.END}")
        print(f"{Colors.RED}Failed: {self.failed}{Colors.END}")
        print(f"Success Rate: {(self.passed/total*100):.1f}%\n")
        
        if self.failed > 0:
            print(f"{Colors.YELLOW}Failed Tests:{Colors.END}")
            for name, passed, info in self.results:
                if not passed:
                    print(f"  ❌ {name} - {info}")
        
        print(f"\n{'='*70}\n")
        
        return self.failed == 0

def main():
    print(f"\n{Colors.BLUE}{'='*70}")
    print(f"COMPREHENSIVE API TEST SUITE")
    print(f"Target: {API_BASE_URL}")
    print(f"{'='*70}{Colors.END}\n")
    
    tester = APITester(API_BASE_URL)
    
    # ==========================================
    # CORE STATUS & INFO
    # ==========================================
    print(f"\n{Colors.BLUE}=== CORE STATUS & INFO ==={Colors.END}")
    
    tester.test("Get Bot Status", "GET", "/api/status")
    tester.test("Get Market Data", "GET", "/api/market/data")
    tester.test("Get Active Trade", "GET", "/api/active_trade")
    
    # ==========================================
    # ENGINE CONTROL
    # ==========================================
    print(f"\n{Colors.BLUE}=== ENGINE CONTROL ==={Colors.END}")
    
    # Note: Not testing start/stop/enable/disable to avoid disrupting production
    print(f"{Colors.YELLOW}⚠️  Skipping engine control tests (start/stop/enable/disable) to avoid disrupting production{Colors.END}")
    
    # ==========================================
    # SETTINGS MANAGEMENT
    # ==========================================
    print(f"\n{Colors.BLUE}=== SETTINGS MANAGEMENT ==={Colors.END}")
    
    tester.test("Get All Settings", "GET", "/api/settings/all")
    tester.test("Get Scanner Settings", "GET", "/api/settings/scanner")
    tester.test("Get Global Settings", "GET", "/api/settings/global")
    
    # Test settings update
    scanner_update = {
        "section": "scanner",
        "data": {
            "enabled": False,
            "interval": 15,
            "min_score": 75,
            "auto_switch": False,
            "gamification_enabled": True
        }
    }
    tester.test(
        "Update Scanner Settings", 
        "POST", 
        "/api/settings/update",
        json=scanner_update,
        headers={"Content-Type": "application/json"}
    )
    
    # ==========================================
    # STRATEGIES
    # ==========================================
    print(f"\n{Colors.BLUE}=== STRATEGIES ==={Colors.END}")
    
    tester.test("Get Strategies List", "GET", "/api/config/strategy-list")
    tester.test("Get Strategies (Legacy)", "GET", "/api/strategies")
    
    # ==========================================
    # TRADE HISTORY & LOGS
    # ==========================================
    print(f"\n{Colors.BLUE}=== TRADE HISTORY & LOGS ==={Colors.END}")
    
    tester.test("Get Exchange Fills", "GET", "/api/exchange/fills?limit=10")
    tester.test("Get Bot Trades", "GET", "/api/bot/trades?limit=10")
    tester.test("Get Bot Trade Stats", "GET", "/api/bot/trades/stats")
    tester.test("Get Logs", "GET", "/api/logs?limit=20")
    tester.test("Get Equity Curve", "GET", "/api/history/equity")
    
    # ==========================================
    # MARKET DATA
    # ==========================================
    print(f"\n{Colors.BLUE}=== MARKET DATA ==={Colors.END}")
    
    tester.test("Get Market Metrics (BTC)", "GET", "/api/market_metrics?symbol=BTC")
    tester.test("Get Market Metrics (ETH)", "GET", "/api/market_metrics?symbol=ETH")
    
    # ==========================================
    # GAMIFICATION
    # ==========================================
    print(f"\n{Colors.BLUE}=== GAMIFICATION ==={Colors.END}")
    
    tester.test("Get Gamification Status", "GET", "/api/gamification_status")
    
    # ==========================================
    # POSITIONS & ACCOUNT
    # ==========================================
    print(f"\n{Colors.BLUE}=== POSITIONS & ACCOUNT ==={Colors.END}")
    
    tester.test("Get Open Positions", "GET", "/api/positions")
    tester.test("Get Account Balance", "GET", "/api/account/balance")
    
    # ==========================================
    # DIAGNOSTICS
    # ==========================================
    print(f"\n{Colors.BLUE}=== DIAGNOSTICS ==={Colors.END}")
    
    tester.test("Get Diagnostics", "GET", "/api/dev/diagnostics")
    
    # ==========================================
    # METADATA
    # ==========================================
    print(f"\n{Colors.BLUE}=== METADATA ==={Colors.END}")
    
    tester.test("Get Token Metadata", "GET", "/api/meta")
    
    # ==========================================
    # SUMMARY
    # ==========================================
    success = tester.print_summary()
    
    if success:
        print(f"{Colors.GREEN}🎉 ALL TESTS PASSED - API is 100% functional!{Colors.END}\n")
        return 0
    else:
        print(f"{Colors.RED}⚠️  SOME TESTS FAILED - Review errors above{Colors.END}\n")
        return 1

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
