# Copyright 2025 John Brosnihan
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""Tests for the rate limiter service."""

import threading
import time
from unittest.mock import patch

import pytest

from app.services.rate_limiter import RateLimiter, TokenBucket


class TestTokenBucket:
    """Test cases for the TokenBucket class."""
    
    def test_token_bucket_initialization(self):
        """Test that token bucket initializes with full capacity."""
        bucket = TokenBucket(capacity=10, refill_rate=2.0)
        
        assert bucket.capacity == 10
        assert bucket.refill_rate == 2.0
        assert bucket.tokens == 10.0
    
    def test_consume_single_token_success(self):
        """Test consuming a single token when available."""
        bucket = TokenBucket(capacity=10, refill_rate=2.0)
        
        result = bucket.consume(tokens=1)
        
        assert result is True
        assert bucket.tokens == 9.0
    
    def test_consume_multiple_tokens_success(self):
        """Test consuming multiple tokens when available."""
        bucket = TokenBucket(capacity=10, refill_rate=2.0)
        
        result = bucket.consume(tokens=5)
        
        assert result is True
        assert bucket.tokens == 5.0
    
    def test_consume_fails_when_insufficient_tokens(self):
        """Test that consume fails when insufficient tokens available."""
        bucket = TokenBucket(capacity=10, refill_rate=2.0)
        
        # Consume all tokens
        bucket.consume(tokens=10)
        
        # Try to consume more
        result = bucket.consume(tokens=1)
        
        assert result is False
        # Use approximate comparison for floating point
        assert bucket.tokens == pytest.approx(0.0, abs=1e-3)
    
    def test_token_refill_over_time(self):
        """Test that tokens refill at the correct rate."""
        bucket = TokenBucket(capacity=10, refill_rate=2.0)
        current_time = 1000.0
        
        # Consume all tokens
        bucket.consume(tokens=10, current_time=current_time)
        assert bucket.tokens == 0.0
        
        # Wait 2 seconds (should refill 4 tokens: 2 tokens/sec * 2 sec)
        current_time += 2.0
        result = bucket.consume(tokens=1, current_time=current_time)
        
        assert result is True
        assert bucket.tokens == pytest.approx(3.0)  # 4 refilled - 1 consumed
    
    def test_token_refill_does_not_exceed_capacity(self):
        """Test that refilling does not exceed bucket capacity."""
        bucket = TokenBucket(capacity=10, refill_rate=2.0)
        current_time = 1000.0
        
        # Consume 5 tokens
        bucket.consume(tokens=5, current_time=current_time)
        assert bucket.tokens == 5.0
        
        # Wait 10 seconds (should refill 20 tokens, but cap at capacity)
        current_time += 10.0
        bucket.consume(tokens=0, current_time=current_time)  # Trigger refill
        
        assert bucket.tokens == 10.0  # Capped at capacity
    
    def test_clock_skew_handling(self):
        """Test that clock skew (time going backwards) is handled gracefully."""
        bucket = TokenBucket(capacity=10, refill_rate=2.0)
        current_time = 1000.0
        
        # First consume with normal time
        bucket.consume(tokens=5, current_time=current_time)
        
        # Time goes backwards (clock skew)
        current_time -= 5.0
        result = bucket.consume(tokens=1, current_time=current_time)
        
        # Should still work, just reset the refill time
        assert result is True
        assert bucket.tokens == 4.0
    
    def test_get_retry_after_when_tokens_available(self):
        """Test retry_after returns 0 when tokens are available."""
        bucket = TokenBucket(capacity=10, refill_rate=2.0)
        
        retry_after = bucket.get_retry_after(tokens=1)
        
        assert retry_after == 0.0
    
    def test_get_retry_after_when_tokens_unavailable(self):
        """Test retry_after calculates correct wait time."""
        bucket = TokenBucket(capacity=10, refill_rate=2.0)
        current_time = 1000.0
        
        # Consume all tokens
        bucket.consume(tokens=10, current_time=current_time)
        
        # Need 1 token: should take 0.5 seconds (1 token / 2 tokens per sec)
        # But rounds up to 1 second
        retry_after = bucket.get_retry_after(tokens=1, current_time=current_time)
        
        assert retry_after == 1  # Rounded up
    
    def test_get_retry_after_multiple_tokens(self):
        """Test retry_after with multiple tokens needed."""
        bucket = TokenBucket(capacity=10, refill_rate=2.0)
        current_time = 1000.0
        
        # Consume all tokens
        bucket.consume(tokens=10, current_time=current_time)
        
        # Need 6 tokens: should take 3 seconds (6 tokens / 2 tokens per sec)
        retry_after = bucket.get_retry_after(tokens=6, current_time=current_time)
        
        assert retry_after == 3


class TestRateLimiter:
    """Test cases for the RateLimiter class."""
    
    def test_rate_limiter_initialization(self):
        """Test rate limiter initializes correctly."""
        limiter = RateLimiter(
            window_seconds=60,
            max_requests=10,
            enabled=True
        )
        
        assert limiter.window_seconds == 60
        assert limiter.max_requests == 10
        assert limiter.enabled is True
        assert len(limiter.buckets) == 0
    
    def test_rate_limiter_allows_request_within_limit(self):
        """Test that requests within limit are allowed."""
        limiter = RateLimiter(
            window_seconds=60,
            max_requests=10,
            enabled=True
        )
        
        allowed, retry_after = limiter.check_rate_limit(
            api_key="test-key-123",
            request_id="req-1"
        )
        
        assert allowed is True
        assert retry_after is None
    
    def test_rate_limiter_denies_request_over_limit(self):
        """Test that requests over limit are denied."""
        limiter = RateLimiter(
            window_seconds=60,
            max_requests=3,
            enabled=True
        )
        
        # Make 3 requests (should all succeed)
        for i in range(3):
            allowed, _ = limiter.check_rate_limit(
                api_key="test-key-123",
                request_id=f"req-{i}"
            )
            assert allowed is True
        
        # 4th request should be denied
        allowed, retry_after = limiter.check_rate_limit(
            api_key="test-key-123",
            request_id="req-4"
        )
        
        assert allowed is False
        assert retry_after is not None
        assert retry_after > 0
    
    def test_rate_limiter_per_key_isolation(self):
        """Test that rate limits are isolated per API key."""
        limiter = RateLimiter(
            window_seconds=60,
            max_requests=2,
            enabled=True
        )
        
        # Key 1 makes 2 requests
        for i in range(2):
            allowed, _ = limiter.check_rate_limit(
                api_key="key-1",
                request_id=f"req-1-{i}"
            )
            assert allowed is True
        
        # Key 1's 3rd request is denied
        allowed, _ = limiter.check_rate_limit(
            api_key="key-1",
            request_id="req-1-3"
        )
        assert allowed is False
        
        # Key 2 can still make requests
        allowed, _ = limiter.check_rate_limit(
            api_key="key-2",
            request_id="req-2-1"
        )
        assert allowed is True
    
    def test_rate_limiter_ip_fallback(self):
        """Test that IP-based limiting works as fallback."""
        limiter = RateLimiter(
            window_seconds=60,
            max_requests=2,
            enabled=True
        )
        
        # Make requests from IP without API key
        allowed, _ = limiter.check_rate_limit(
            client_ip="192.168.1.100",
            request_id="req-1"
        )
        assert allowed is True
        
        allowed, _ = limiter.check_rate_limit(
            client_ip="192.168.1.100",
            request_id="req-2"
        )
        assert allowed is True
        
        # 3rd request from same IP should be denied
        allowed, retry_after = limiter.check_rate_limit(
            client_ip="192.168.1.100",
            request_id="req-3"
        )
        assert allowed is False
        assert retry_after is not None
    
    def test_rate_limiter_prioritizes_api_key_over_ip(self):
        """Test that API key is prioritized over IP for rate limiting."""
        limiter = RateLimiter(
            window_seconds=60,
            max_requests=2,
            enabled=True
        )
        
        # Make requests with both API key and IP
        # Rate limiting should be per API key, not IP
        allowed, _ = limiter.check_rate_limit(
            api_key="test-key",
            client_ip="192.168.1.100",
            request_id="req-1"
        )
        assert allowed is True
        
        allowed, _ = limiter.check_rate_limit(
            api_key="test-key",
            client_ip="192.168.1.200",  # Different IP, same key
            request_id="req-2"
        )
        assert allowed is True
        
        # 3rd request should be denied based on API key, not IP
        allowed, _ = limiter.check_rate_limit(
            api_key="test-key",
            client_ip="192.168.1.300",  # Yet another IP
            request_id="req-3"
        )
        assert allowed is False
    
    def test_rate_limiter_disabled_bypasses_enforcement(self):
        """Test that disabled rate limiter allows all requests."""
        limiter = RateLimiter(
            window_seconds=60,
            max_requests=2,
            enabled=False  # Disabled
        )
        
        # Make many requests (should all succeed)
        for i in range(10):
            allowed, retry_after = limiter.check_rate_limit(
                api_key="test-key",
                request_id=f"req-{i}"
            )
            assert allowed is True
            assert retry_after is None
    
    def test_rate_limiter_per_key_overrides(self):
        """Test that per-key overrides work correctly."""
        limiter = RateLimiter(
            window_seconds=60,
            max_requests=2,  # Default limit
            enabled=True,
            per_key_overrides={
                "premium-key": 5,  # Override: 5 requests
                "basic-key": 1     # Override: 1 request
            }
        )
        
        # Premium key should get 5 requests
        for i in range(5):
            allowed, _ = limiter.check_rate_limit(
                api_key="premium-key",
                request_id=f"req-premium-{i}"
            )
            assert allowed is True
        
        # 6th request denied
        allowed, _ = limiter.check_rate_limit(
            api_key="premium-key",
            request_id="req-premium-6"
        )
        assert allowed is False
        
        # Basic key should get only 1 request
        allowed, _ = limiter.check_rate_limit(
            api_key="basic-key",
            request_id="req-basic-1"
        )
        assert allowed is True
        
        # 2nd request denied
        allowed, _ = limiter.check_rate_limit(
            api_key="basic-key",
            request_id="req-basic-2"
        )
        assert allowed is False
        
        # Unknown key should get default limit (2)
        for i in range(2):
            allowed, _ = limiter.check_rate_limit(
                api_key="unknown-key",
                request_id=f"req-unknown-{i}"
            )
            assert allowed is True
        
        allowed, _ = limiter.check_rate_limit(
            api_key="unknown-key",
            request_id="req-unknown-3"
        )
        assert allowed is False
    
    def test_rate_limiter_no_identifier_denies(self):
        """Test that requests without API key or IP are denied."""
        limiter = RateLimiter(
            window_seconds=60,
            max_requests=10,
            enabled=True
        )
        
        allowed, retry_after = limiter.check_rate_limit(
            api_key=None,
            client_ip=None,
            request_id="req-1"
        )
        
        assert allowed is False
        assert retry_after is not None
    
    def test_rate_limiter_metrics(self):
        """Test that metrics are tracked correctly."""
        limiter = RateLimiter(
            window_seconds=60,
            max_requests=2,
            enabled=True
        )
        
        # Make 3 requests (2 allowed, 1 denied)
        limiter.check_rate_limit(api_key="key-1", request_id="req-1")
        limiter.check_rate_limit(api_key="key-1", request_id="req-2")
        limiter.check_rate_limit(api_key="key-1", request_id="req-3")
        
        metrics = limiter.get_metrics()
        
        assert metrics["allow_count"] == 2
        assert metrics["deny_count"] == 1
    
    def test_rate_limiter_concurrent_requests(self):
        """Test rate limiter with concurrent requests (thread safety)."""
        limiter = RateLimiter(
            window_seconds=60,
            max_requests=10,
            enabled=True
        )
        
        results = []
        lock = threading.Lock()
        
        def make_request(request_id):
            allowed, _ = limiter.check_rate_limit(
                api_key="concurrent-key",
                request_id=request_id
            )
            with lock:
                results.append(allowed)
        
        # Create 15 threads making concurrent requests
        threads = []
        for i in range(15):
            thread = threading.Thread(
                target=make_request,
                args=(f"concurrent-req-{i}",)
            )
            threads.append(thread)
            thread.start()
        
        # Wait for all threads
        for thread in threads:
            thread.join()
        
        # Should have exactly 10 allowed and 5 denied
        assert sum(results) == 10  # Count of True (allowed)
        assert len([r for r in results if not r]) == 5  # Count of False (denied)
    
    def test_rate_limiter_api_key_hashing(self):
        """Test that API keys are hashed before storage."""
        limiter = RateLimiter(
            window_seconds=60,
            max_requests=10,
            enabled=True
        )
        
        # Make a request with an API key
        limiter.check_rate_limit(
            api_key="my-secret-api-key-12345",
            request_id="req-1"
        )
        
        # Check that the raw API key is not in the buckets
        assert "my-secret-api-key-12345" not in limiter.buckets
        
        # Check that a hashed version is in the buckets
        # All bucket keys should start with "key:" or "ip:"
        bucket_keys = list(limiter.buckets.keys())
        assert len(bucket_keys) == 1
        assert bucket_keys[0].startswith("key:")
        assert "my-secret-api-key-12345" not in bucket_keys[0]


class TestRateLimiterIntegration:
    """Integration tests for rate limiter with time-based scenarios."""
    
    def test_burst_then_sustained_load(self):
        """Test handling burst at start of window then sustained load."""
        limiter = RateLimiter(
            window_seconds=10,  # 10 second window
            max_requests=5,     # 5 requests max
            enabled=True
        )
        
        # Burst: make 5 requests immediately (all should succeed)
        for i in range(5):
            allowed, _ = limiter.check_rate_limit(
                api_key="burst-key",
                request_id=f"burst-{i}"
            )
            assert allowed is True
        
        # 6th immediate request should fail
        allowed, retry_after = limiter.check_rate_limit(
            api_key="burst-key",
            request_id="burst-fail"
        )
        assert allowed is False
        assert retry_after is not None
        
        # Wait for retry_after seconds
        time.sleep(retry_after)
        
        # Should be able to make another request after waiting
        allowed, _ = limiter.check_rate_limit(
            api_key="burst-key",
            request_id="post-wait"
        )
        assert allowed is True
