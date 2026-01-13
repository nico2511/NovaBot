"""
Usage Examples: Hyperliquid Rate Limit Fix & WebSocket Integration

This file demonstrates how to use the new retry decorators and WebSocket
price manager in your trading strategies.

Author: NovaBot Team
Date: 2026-01-01
"""

from app.services.hyperliquid_service import hyperliquid_service
from app.utils.retry_decorator import critical_operation, standard_operation
import time


# ============================================
# EXAMPLE 1: Safe Position Close with Retry
# ============================================

def example_close_position_with_retry():
    """
    Demonstrates closing a position with automatic retry on 429 errors.
    
    The @critical_operation decorator provides:
    - 5 retry attempts
    - Exponential backoff (2s → 4s → 8s → 16s → 32s)
    - Doubled delay on 429 errors
    """
    print("=" * 60)
    print("EXAMPLE 1: Close Position with Retry")
    print("=" * 60)
    
    symbol = "BTC"
    
    try:
        # This will automatically retry up to 5 times if 429 error occurs
        result = hyperliquid_service.close_position(symbol)
        
        if result["status"] == "success":
            print(f"✅ Position closed successfully")
            print(f"   Closed size: {result['closed_size']}")
        else:
            print(f"❌ Failed to close position: {result['message']}")
            
    except Exception as e:
        print(f"❌ Critical error after all retries: {e}")


# ============================================
# EXAMPLE 2: Set SL/TP with Percentages
# ============================================

def example_set_sl_tp():
    """
    Demonstrates setting Stop Loss and Take Profit using percentages.
    
    This is much simpler than calculating prices manually.
    """
    print("\n" + "=" * 60)
    print("EXAMPLE 2: Set SL/TP with Percentages")
    print("=" * 60)
    
    # Assume we just opened a LONG position on ETH at $3,000
    symbol = "ETH"
    entry_price = 3000.0
    position_size = 1.0  # 1 ETH
    is_long = True
    
    # Set 2% Stop Loss and 5% Take Profit
    sl_percent = 2.0  # 2% below entry
    tp_percent = 5.0  # 5% above entry
    
    try:
        result = hyperliquid_service.set_sl_tp(
            symbol=symbol,
            entry_price=entry_price,
            sl_percent=sl_percent,
            tp_percent=tp_percent,
            is_long=is_long,
            quantity=position_size
        )
        
        if result["status"] == "success":
            print(f"✅ SL/TP set successfully")
            print(f"   Entry: ${entry_price}")
            print(f"   SL: ${result['sl_price']:.2f} ({sl_percent}% below)")
            print(f"   TP: ${result['tp_price']:.2f} ({tp_percent}% above)")
        else:
            print(f"❌ Failed to set SL/TP: {result.get('message', 'Unknown error')}")
            
    except Exception as e:
        print(f"❌ Error: {e}")


# ============================================
# EXAMPLE 3: Get Real-Time Price (WebSocket)
# ============================================

def example_get_realtime_price():
    """
    Demonstrates getting real-time prices from WebSocket cache.
    
    This is MUCH faster than REST API calls:
    - WebSocket: <1ms latency
    - REST API: 200-500ms latency
    """
    print("\n" + "=" * 60)
    print("EXAMPLE 3: Get Real-Time Price (WebSocket)")
    print("=" * 60)
    
    symbol = "BTC"
    
    # Get price (instant, no API call)
    start_time = time.time()
    price = hyperliquid_service.get_current_price(symbol)
    latency = (time.time() - start_time) * 1000  # Convert to ms
    
    print(f"Symbol: {symbol}")
    print(f"Price: ${price:,.2f}")
    print(f"Latency: {latency:.2f}ms")
    
    # Check WebSocket health
    if hyperliquid_service.ws_manager:
        status = hyperliquid_service.ws_manager.get_status()
        print(f"\nWebSocket Status:")
        print(f"  Running: {status['running']}")
        print(f"  Healthy: {status['healthy']}")
        
        if symbol in status['symbols']:
            symbol_status = status['symbols'][symbol]
            print(f"  Last Update: {symbol_status['last_update']}")
            print(f"  Age: {symbol_status['age_seconds']:.1f}s")
            print(f"  Stale: {symbol_status['is_stale']}")
    else:
        print("\n⚠️ WebSocket not initialized (using REST API fallback)")


# ============================================
# EXAMPLE 4: Full Trade Lifecycle
# ============================================

def example_full_trade_lifecycle():
    """
    Demonstrates a complete trade lifecycle:
    1. Open position
    2. Set SL/TP
    3. Monitor price
    4. Close position
    
    All with automatic retry logic and WebSocket price feeds.
    """
    print("\n" + "=" * 60)
    print("EXAMPLE 4: Full Trade Lifecycle")
    print("=" * 60)
    
    symbol = "BTC"
    
    # Step 1: Open position
    print("\n📈 Step 1: Opening LONG position...")
    try:
        result = hyperliquid_service.execute_order(
            symbol=symbol,
            is_buy=True,
            quantity=0.01,  # 0.01 BTC
            price=None,  # Market order
            sl_price=None,  # Will set separately
            tp_price=None
        )
        
        if result["status"] != "success":
            print(f"❌ Failed to open position: {result['message']}")
            return
        
        print(f"✅ Position opened")
        
        # Get entry price from WebSocket (instant)
        entry_price = hyperliquid_service.get_current_price(symbol)
        print(f"   Entry: ${entry_price:,.2f}")
        
    except Exception as e:
        print(f"❌ Error opening position: {e}")
        return
    
    # Step 2: Set SL/TP
    print("\n🛡️ Step 2: Setting SL/TP...")
    try:
        sl_tp_result = hyperliquid_service.set_sl_tp(
            symbol=symbol,
            entry_price=entry_price,
            sl_percent=2.0,  # 2% SL
            tp_percent=5.0,  # 5% TP
            is_long=True,
            quantity=0.01
        )
        
        if sl_tp_result["status"] == "success":
            print(f"✅ SL/TP set")
            print(f"   SL: ${sl_tp_result['sl_price']:,.2f}")
            print(f"   TP: ${sl_tp_result['tp_price']:,.2f}")
        
    except Exception as e:
        print(f"⚠️ Failed to set SL/TP: {e}")
    
    # Step 3: Monitor price (simulated)
    print("\n👀 Step 3: Monitoring price...")
    for i in range(3):
        current_price = hyperliquid_service.get_current_price(symbol)
        pnl_percent = ((current_price - entry_price) / entry_price) * 100
        print(f"   Price: ${current_price:,.2f} | PnL: {pnl_percent:+.2f}%")
        time.sleep(1)
    
    # Step 4: Close position
    print("\n🔴 Step 4: Closing position...")
    try:
        close_result = hyperliquid_service.close_position(symbol)
        
        if close_result["status"] == "success":
            print(f"✅ Position closed")
            print(f"   Size: {close_result['closed_size']}")
        else:
            print(f"❌ Failed to close: {close_result['message']}")
            
    except Exception as e:
        print(f"❌ Error closing position: {e}")


# ============================================
# EXAMPLE 5: Custom Retry Decorator
# ============================================

def example_custom_retry_decorator():
    """
    Demonstrates creating a custom retry decorator for specific needs.
    """
    from app.utils.retry_decorator import exponential_backoff
    
    print("\n" + "=" * 60)
    print("EXAMPLE 5: Custom Retry Decorator")
    print("=" * 60)
    
    # Create a custom decorator with aggressive retry
    @exponential_backoff(
        max_retries=10,      # More retries
        base_delay=0.5,      # Faster initial retry
        max_delay=60.0,      # Higher max delay
        jitter=True          # Add randomness
    )
    def risky_operation():
        """Simulated risky operation that might fail"""
        import random
        if random.random() < 0.7:  # 70% failure rate
            raise Exception("Simulated failure")
        return "Success!"
    
    try:
        result = risky_operation()
        print(f"✅ Operation succeeded: {result}")
    except Exception as e:
        print(f"❌ Operation failed after all retries: {e}")


# ============================================
# MAIN EXECUTION
# ============================================

if __name__ == "__main__":
    print("\n🚀 Hyperliquid Rate Limit Fix - Usage Examples\n")
    
    # NOTE: These examples are for demonstration only
    # Uncomment the ones you want to run
    
    # example_close_position_with_retry()
    # example_set_sl_tp()
    example_get_realtime_price()
    # example_full_trade_lifecycle()
    # example_custom_retry_decorator()
    
    print("\n✅ Examples completed\n")
