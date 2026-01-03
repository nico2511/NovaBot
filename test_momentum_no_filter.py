"""
Test Momentum Ranking (No MA200 Filter)
Validates scoring logic even if market is bearish
"""
import sys
sys.path.insert(0, '.')

from app.services.token_scanner import HyperliquidScanner

def test_momentum_no_filter():
    print("🧪 Testing Momentum Ranking (NO MA200 Filter)...")
    print("=" * 60)
    
    scanner = HyperliquidScanner()
    
    print("\n📊 Running momentum ranking (Top 5, Filter OFF)...")
    try:
        result = scanner.scan_momentum_ranking(top_n=5)
        
        # Override to disable MA200 filter for testing
        from app.services.momentum_scanner import momentum_scanner
        from app.services.hyperliquid_service import hyperliquid_service
        
        # Get tokens
        tokens = scanner.get_all_tokens()[:15]  # Top 15 by volume
        
        # Fetch data
        data_dict = {}
        print(f"\n📥 Fetching data for {len(tokens)} tokens...")
        for symbol in tokens:
            try:
                df = hyperliquid_service.get_candles(symbol, "1d", 200)
                if not df.empty:
                    data_dict[symbol] = df
                    print(f"  ✅ {symbol}: {len(df)} candles")
            except Exception as e:
                print(f"  ⚠️ {symbol}: {e}")
        
        # Run ranking WITHOUT MA200 filter
        print(f"\n🎯 Ranking {len(data_dict)} tokens...")
        result = momentum_scanner.select_top_momentum(data_dict, top_n=5, require_ma200=False)
        
        print("\n✅ SUCCESS!")
        print("=" * 60)
        print(f"Selected Tokens: {result['selected']}")
        print(f"Valid Candidates: {result.get('valid_candidates', 'N/A')}/{result.get('total_candidates', 'N/A')}")
        
        if result['selected']:
            print("\n📈 Rankings (Top 5):")
            for i, symbol in enumerate(result['selected'], 1):
                score = result['scores'].get(symbol, 0)
                weight = result['weights'].get(symbol, 0)
                print(f"  {i}. {symbol:6s} | Score: {score:+.4f} | Weight: {weight:.2%}")
        else:
            print("\n⚠️ No valid tokens found")
            
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_momentum_no_filter()
