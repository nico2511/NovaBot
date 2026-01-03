"""
Test Momentum Ranking (Local)
Quick test to validate the momentum scanner works
"""
import sys
sys.path.insert(0, '.')

from app.services.token_scanner import HyperliquidScanner

def test_momentum_ranking():
    print("🧪 Testing Momentum Ranking...")
    print("=" * 60)
    
    scanner = HyperliquidScanner()
    
    print("\n📊 Running momentum ranking (Top 3)...")
    try:
        result = scanner.scan_momentum_ranking(top_n=3)
        
        print("\n✅ SUCCESS!")
        print("=" * 60)
        print(f"Selected Tokens: {result['selected']}")
        print(f"Valid Candidates: {result.get('valid_candidates', 'N/A')}/{result.get('total_candidates', 'N/A')}")
        
        if result['selected']:
            print("\n📈 Rankings:")
            for i, symbol in enumerate(result['selected'], 1):
                score = result['scores'].get(symbol, 0)
                weight = result['weights'].get(symbol, 0)
                print(f"  {i}. {symbol:6s} | Score: {score:+.4f} | Weight: {weight:.2%}")
        else:
            print("\n⚠️ No tokens passed the MA200 filter")
            
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_momentum_ranking()
