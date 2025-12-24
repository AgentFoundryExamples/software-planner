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


class TestRateLimiterRapidRequests:
    """Test cases for rapid repeated requests and fingerprint handling."""
    
    def test_rapid_repeated_requests_from_same_fingerprint(self):
        """Test that rapid requests from same fingerprint are properly limited."""
        limiter = RateLimiter(
            window_seconds=60,
            max_requests=3,
            enabled=True
        )
        
        # Make rapid requests (no sleep between)
        results = []
        for i in range(5):  # More than the limit
            allowed, retry_after = limiter.check_rate_limit(
                api_key="rapid-key",
                request_id=f"rapid-{i}"
            )
            results.append(allowed)
        
        # Exactly 3 should be allowed, rest denied
        assert results == [True, True, True, False, False]
        
        # Wait for the bucket to replenish one token (20 seconds for 1 token in a 60s/3req window)
        time.sleep(21)
        
        # This request should now be allowed
        allowed, _ = limiter.check_rate_limit(api_key="rapid-key", request_id="after-wait")
        assert allowed is True
    
    def test_fingerprint_isolation_api_key_vs_ip(self):
        """Test that API key and IP fingerprints are isolated."""
        limiter = RateLimiter(
            window_seconds=60,
            max_requests=2,
            enabled=True
        )
        
        # Exhaust quota for API key
        for i in range(2):
            allowed, _ = limiter.check_rate_limit(
                api_key="test-key",
                client_ip="192.168.1.100",
                request_id=f"key-{i}"
            )
            assert allowed is True
        
        # API key quota exhausted
        allowed, _ = limiter.check_rate_limit(
            api_key="test-key",
            client_ip="192.168.1.100",
            request_id="key-fail"
        )
        assert allowed is False
        
        # Same IP but no API key should have independent quota
        allowed, _ = limiter.check_rate_limit(
            api_key=None,
            client_ip="192.168.1.100",
            request_id="ip-1"
        )
        assert allowed is True
    
    def test_state_isolation_between_different_fingerprints(self):
        """Test that state is properly isolated between different clients."""
        limiter = RateLimiter(
            window_seconds=60,
            max_requests=2,
            enabled=True
        )
        
        # Client 1 exhausts quota
        for i in range(2):
            allowed, _ = limiter.check_rate_limit(
                api_key="client1-key",
                request_id=f"c1-{i}"
            )
            assert allowed is True
        
        allowed, _ = limiter.check_rate_limit(
            api_key="client1-key",
            request_id="c1-fail"
        )
        assert allowed is False
        
        # Client 2 should have full quota
        for i in range(2):
            allowed, _ = limiter.check_rate_limit(
                api_key="client2-key",
                request_id=f"c2-{i}"
            )
            assert allowed is True
        
        # Client 3 with different IP should have full quota
        for i in range(2):
            allowed, _ = limiter.check_rate_limit(
                client_ip="10.0.0.1",
                request_id=f"c3-{i}"
            )
            assert allowed is True


class TestRateLimiterStateLeakage:
    """Test cases to verify no state leakage between tests."""
    
    def test_limiter_state_does_not_leak_between_instances(self):
        """Test that creating new limiter instances have independent state."""
        limiter1 = RateLimiter(
            window_seconds=60,
            max_requests=2,
            enabled=True
        )
        
        # Exhaust limiter1 quota
        for i in range(2):
            limiter1.check_rate_limit(api_key="test-key", request_id=f"req-{i}")
        
        allowed, _ = limiter1.check_rate_limit(api_key="test-key", request_id="fail")
        assert allowed is False
        
        # Create new limiter - should have fresh state
        limiter2 = RateLimiter(
            window_seconds=60,
            max_requests=2,
            enabled=True
        )
        
        # limiter2 should allow requests even though limiter1 is exhausted
        allowed, _ = limiter2.check_rate_limit(api_key="test-key", request_id="new")
        assert allowed is True
    
    def test_metrics_isolated_per_limiter_instance(self):
        """Test that metrics are isolated per limiter instance."""
        limiter1 = RateLimiter(
            window_seconds=60,
            max_requests=2,
            enabled=True
        )
        
        limiter2 = RateLimiter(
            window_seconds=60,
            max_requests=2,
            enabled=True
        )
        
        # Make requests to limiter1
        limiter1.check_rate_limit(api_key="key1", request_id="req1")
        limiter1.check_rate_limit(api_key="key1", request_id="req2")
        limiter1.check_rate_limit(api_key="key1", request_id="req3")  # Denied
        
        metrics1 = limiter1.get_metrics()
        assert metrics1["allow_count"] == 2
        assert metrics1["deny_count"] == 1
        
        # Limiter2 should have clean metrics
        metrics2 = limiter2.get_metrics()
        assert metrics2["allow_count"] == 0
        assert metrics2["deny_count"] == 0
    
    def test_bucket_cleanup_does_not_affect_other_keys(self):
        """Test that modifying buckets for one key doesn't affect others."""
        limiter = RateLimiter(
            window_seconds=60,
            max_requests=5,
            enabled=True
        )
        
        # Create buckets for multiple keys
        limiter.check_rate_limit(api_key="key1", request_id="k1-1")
        limiter.check_rate_limit(api_key="key2", request_id="k2-1")
        limiter.check_rate_limit(api_key="key3", request_id="k3-1")
        
        # Exhaust key1
        for i in range(5):
            limiter.check_rate_limit(api_key="key1", request_id=f"k1-exhaust-{i}")
        
        # key1 should be denied
        allowed, _ = limiter.check_rate_limit(api_key="key1", request_id="k1-fail")
        assert allowed is False
        
        # key2 and key3 should still work
        allowed, _ = limiter.check_rate_limit(api_key="key2", request_id="k2-2")
        assert allowed is True
        
        allowed, _ = limiter.check_rate_limit(api_key="key3", request_id="k3-2")
        assert allowed is True


class TestRateLimiterConcurrentSafety:
    """Test cases for thread safety with concurrent access."""
    
    def test_concurrent_access_no_race_conditions(self):
        """Test that concurrent access doesn't cause race conditions."""
        limiter = RateLimiter(
            window_seconds=60,
            max_requests=20,  # Higher limit for this test
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
        
        # Create 25 threads (5 should be denied)
        threads = []
        for i in range(25):
            thread = threading.Thread(
                target=make_request,
                args=(f"concurrent-req-{i}",)
            )
            threads.append(thread)
            thread.start()
        
        for thread in threads:
            thread.join()
        
        # Should have exactly 20 allowed and 5 denied
        assert sum(results) == 20
        assert len([r for r in results if not r]) == 5
    
    def test_concurrent_different_keys_no_interference(self):
        """Test that concurrent requests with different keys don't interfere."""
        limiter = RateLimiter(
            window_seconds=60,
            max_requests=3,
            enabled=True
        )
        
        results = {"key1": [], "key2": [], "key3": []}
        lock = threading.Lock()
        
        def make_requests_for_key(key_name, count):
            for i in range(count):
                allowed, _ = limiter.check_rate_limit(
                    api_key=key_name,
                    request_id=f"{key_name}-{i}"
                )
                with lock:
                    results[key_name].append(allowed)
        
        # Create threads for 3 different keys
        threads = [
            threading.Thread(target=make_requests_for_key, args=("key1", 5)),
            threading.Thread(target=make_requests_for_key, args=("key2", 5)),
            threading.Thread(target=make_requests_for_key, args=("key3", 5)),
        ]
        
        for thread in threads:
            thread.start()
        
        for thread in threads:
            thread.join()
        
        # Each key should have 3 allowed, 2 denied
        for key_name in ["key1", "key2", "key3"]:
            assert sum(results[key_name]) == 3, f"{key_name} should have 3 allowed"
            assert len([r for r in results[key_name] if not r]) == 2, f"{key_name} should have 2 denied"
