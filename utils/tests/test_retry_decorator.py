"""
Unit Tests for Exponential Backoff Retry Decorator

Tests the retry logic, 429 error detection, and exponential backoff behavior.

Author: NovaBot Team
Date: 2026-01-01
"""

import pytest
import time
from app.utils.retry_decorator import (
    exponential_backoff,
    critical_operation,
    standard_operation,
    lightweight_operation,
    _is_rate_limit_error
)


class TestRateLimitDetection:
    """Test suite for 429 rate limit error detection"""
    
    def test_detect_tuple_format_429(self):
        """Test detection of 429 in tuple format: (429, None, 'null', None)"""
        error = Exception((429, None, 'null', None, {}))
        assert _is_rate_limit_error(error) is True
    
    def test_detect_integer_429(self):
        """Test detection of 429 as direct integer"""
        error = Exception(429)
        assert _is_rate_limit_error(error) is True
    
    def test_detect_string_429(self):
        """Test detection of '429' in error message"""
        error = Exception("HTTP Error 429: Rate limit exceeded")
        assert _is_rate_limit_error(error) is True
    
    def test_detect_rate_limit_string(self):
        """Test detection of 'rate limit' in error message"""
        error = Exception("Rate limit exceeded, please try again later")
        assert _is_rate_limit_error(error) is True
    
    def test_non_rate_limit_error(self):
        """Test that non-429 errors are not detected as rate limits"""
        error = Exception("Connection timeout")
        assert _is_rate_limit_error(error) is False
        
        error = Exception((500, None, 'Internal Server Error', None))
        assert _is_rate_limit_error(error) is False


class TestExponentialBackoff:
    """Test suite for exponential backoff decorator"""
    
    def test_success_on_first_attempt(self):
        """Test that successful calls return immediately"""
        call_count = 0
        
        @exponential_backoff(max_retries=3, base_delay=0.1)
        def successful_call():
            nonlocal call_count
            call_count += 1
            return "success"
        
        result = successful_call()
        assert result == "success"
        assert call_count == 1
    
    def test_retry_on_exception(self):
        """Test that function retries on exception"""
        call_count = 0
        
        @exponential_backoff(max_retries=3, base_delay=0.1)
        def failing_call():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise Exception("Temporary failure")
            return "success"
        
        result = failing_call()
        assert result == "success"
        assert call_count == 3
    
    def test_max_retries_exhausted(self):
        """Test that exception is raised after max retries"""
        call_count = 0
        
        @exponential_backoff(max_retries=2, base_delay=0.1)
        def always_failing():
            nonlocal call_count
            call_count += 1
            raise Exception("Permanent failure")
        
        with pytest.raises(Exception, match="Permanent failure"):
            always_failing()
        
        assert call_count == 3  # Initial + 2 retries
    
    def test_exponential_delay_increase(self):
        """Test that delay increases exponentially"""
        delays = []
        call_count = 0
        
        @exponential_backoff(max_retries=3, base_delay=0.1, jitter=False)
        def track_delays():
            nonlocal call_count
            call_count += 1
            if call_count < 4:
                delays.append(time.time())
                raise Exception("Test")
            return "success"
        
        start_time = time.time()
        track_delays()
        
        # Verify delays are approximately: 0.1s, 0.2s, 0.4s
        # (allowing 50ms tolerance for execution time)
        if len(delays) >= 3:
            delay1 = delays[1] - delays[0]
            delay2 = delays[2] - delays[1]
            
            assert 0.08 < delay1 < 0.15  # ~0.1s
            assert 0.18 < delay2 < 0.25  # ~0.2s
    
    def test_rate_limit_double_delay(self):
        """Test that 429 errors trigger doubled delay"""
        call_count = 0
        delays = []
        
        @exponential_backoff(max_retries=2, base_delay=0.1, jitter=False)
        def rate_limited_call():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                delays.append(time.time())
                raise Exception((429, None, 'Rate limit', None))
            return "success"
        
        rate_limited_call()
        
        # First retry delay should be ~0.2s (0.1 * 2 for 429)
        if len(delays) >= 2:
            delay1 = delays[1] - delays[0]
            assert 0.18 < delay1 < 0.25  # ~0.2s (doubled)


class TestConvenienceDecorators:
    """Test suite for convenience decorator wrappers"""
    
    def test_critical_operation_config(self):
        """Test that critical_operation uses aggressive retry"""
        call_count = 0
        
        @critical_operation
        def critical_call():
            nonlocal call_count
            call_count += 1
            if call_count < 5:
                raise Exception("Test")
            return "success"
        
        result = critical_call()
        assert result == "success"
        assert call_count == 5  # Should retry up to 5 times
    
    def test_standard_operation_config(self):
        """Test that standard_operation uses moderate retry"""
        call_count = 0
        
        @standard_operation
        def standard_call():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise Exception("Test")
            return "success"
        
        result = standard_call()
        assert result == "success"
        assert call_count == 3  # Should retry up to 3 times
    
    def test_lightweight_operation_config(self):
        """Test that lightweight_operation uses minimal retry"""
        call_count = 0
        
        @lightweight_operation
        def lightweight_call():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise Exception("Test")
            return "success"
        
        result = lightweight_call()
        assert result == "success"
        assert call_count == 2  # Should retry up to 2 times


class TestJitter:
    """Test suite for jitter functionality"""
    
    def test_jitter_adds_randomness(self):
        """Test that jitter adds randomness to delays"""
        delays = []
        
        for _ in range(5):
            call_count = 0
            
            @exponential_backoff(max_retries=1, base_delay=1.0, jitter=True)
            def jittered_call():
                nonlocal call_count
                call_count += 1
                if call_count == 1:
                    start = time.time()
                    raise Exception("Test")
                return time.time() - start
            
            try:
                delay = jittered_call()
                delays.append(delay)
            except:
                pass
        
        # Verify delays are not all identical (jitter is working)
        # Delays should be in range [0.75s, 1.25s] with jitter
        assert len(set(delays)) > 1  # Not all the same
        assert all(0.7 < d < 1.3 for d in delays)  # Within jitter range


class TestMaxDelay:
    """Test suite for max delay cap"""
    
    def test_max_delay_cap(self):
        """Test that delay never exceeds max_delay"""
        call_count = 0
        
        @exponential_backoff(
            max_retries=10,
            base_delay=1.0,
            max_delay=5.0,
            exponential_base=2.0,
            jitter=False
        )
        def capped_delay_call():
            nonlocal call_count
            call_count += 1
            if call_count < 11:
                raise Exception("Test")
            return "success"
        
        # This would normally result in delays: 1, 2, 4, 8, 16, 32...
        # But should be capped at 5.0
        start_time = time.time()
        capped_delay_call()
        total_time = time.time() - start_time
        
        # Total time should be less than if uncapped
        # Uncapped: 1+2+4+8+16+32+64+128+256+512 = 1023s
        # Capped: 1+2+4+5+5+5+5+5+5+5 = 42s
        assert total_time < 50  # Should be ~42s, allowing overhead


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
