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
"""Rate limiting service using token bucket algorithm.

This module provides configurable rate limiting per API key or client IP.
It uses an in-memory token bucket algorithm that is compatible with
StoreSingleton for shared state across the application.

The limiter supports:
- Per-API-key rate limiting with optional per-key overrides
- Per-IP rate limiting as a fallback for anonymous access
- Configurable refill rate and bucket capacity
- Logging and metrics for observability
- Graceful handling of clock skew and server restarts
"""

import logging
import threading
import time
from typing import Optional

from app.core.config import settings

logger = logging.getLogger(__name__)


class TokenBucket:
    """Token bucket for rate limiting a single identifier (key or IP).

    This class implements the token bucket algorithm where:
    - Tokens refill at a constant rate (tokens per second)
    - The bucket has a maximum capacity
    - Each request consumes one token
    - Requests are denied if insufficient tokens are available

    The implementation is thread-safe and handles clock skew gracefully.
    """

    def __init__(self, capacity: int, refill_rate: float):
        """Initialize a token bucket.

        Args:
            capacity: Maximum number of tokens in the bucket.
            refill_rate: Number of tokens to add per second.
        """
        self.capacity = capacity
        self.refill_rate = refill_rate
        self.tokens = float(capacity)  # Start with full bucket
        self.last_refill_time = time.time()
        self.lock = threading.Lock()

    def _refill(self, current_time: float) -> None:
        """Refill tokens based on elapsed time.

        Args:
            current_time: Current timestamp in seconds.
        """
        time_elapsed = current_time - self.last_refill_time

        # Handle clock skew or time going backwards
        if time_elapsed < 0:
            logger.warning(
                "Clock skew detected: time went backwards",
                extra={
                    "time_elapsed": time_elapsed,
                    "last_refill_time": self.last_refill_time,
                    "current_time": current_time,
                },
            )
            # Reset to current time to handle clock adjustment
            self.last_refill_time = current_time
            return

        # Add tokens based on elapsed time
        tokens_to_add = time_elapsed * self.refill_rate
        self.tokens = min(self.capacity, self.tokens + tokens_to_add)
        self.last_refill_time = current_time

    def consume(self, tokens: int = 1, current_time: Optional[float] = None) -> bool:
        """Attempt to consume tokens from the bucket.

        Args:
            tokens: Number of tokens to consume (default: 1).
            current_time: Optional current time for testing (default: time.time()).

        Returns:
            True if tokens were available and consumed, False otherwise.
        """
        if current_time is None:
            current_time = time.time()

        with self.lock:
            # Refill bucket based on elapsed time
            self._refill(current_time)

            # Check if enough tokens are available
            if self.tokens >= tokens:
                self.tokens -= tokens
                return True
            else:
                return False

    def get_retry_after(self, tokens: int = 1, current_time: Optional[float] = None) -> float:
        """Calculate seconds until enough tokens will be available.

        Args:
            tokens: Number of tokens needed (default: 1).
            current_time: Optional current time for testing (default: time.time()).

        Returns:
            Seconds to wait before retrying, rounded up to next second.
        """
        if current_time is None:
            current_time = time.time()

        with self.lock:
            self._refill(current_time)

            if self.tokens >= tokens:
                return 0.0

            # Calculate time needed to accumulate enough tokens
            tokens_needed = tokens - self.tokens
            seconds_needed = tokens_needed / self.refill_rate

            # Round up to next second
            import math

            return math.ceil(seconds_needed)


class RateLimiter:
    """Rate limiter supporting per-API-key and per-IP limits.

    This class provides rate limiting using token bucket algorithm with:
    - Per-API-key rate limiting with optional overrides
    - Per-IP rate limiting as fallback
    - Configurable global defaults
    - Thread-safe operation
    - Logging and metrics emission

    The limiter uses in-memory storage and does not persist state across
    restarts. For multi-instance deployments, consider using a distributed
    rate limiting solution.
    """

    def __init__(
        self,
        window_seconds: int,
        max_requests: int,
        enabled: bool = True,
        per_key_overrides: Optional[dict[str, int]] = None,
    ):
        """Initialize the rate limiter.

        Args:
            window_seconds: Time window in seconds for rate limiting.
            max_requests: Maximum requests allowed per window (default limit).
            enabled: Whether rate limiting is enabled (default: True).
            per_key_overrides: Optional dict mapping API keys to custom limits.
                              Keys should be the original (unhashed) API keys.
        """
        self.window_seconds = window_seconds
        self.max_requests = max_requests
        self.enabled = enabled
        # Store per-key overrides with hashed keys for lookup
        self.per_key_overrides = {}
        if per_key_overrides:
            import hashlib

            for key, limit in per_key_overrides.items():
                hashed = f"key:{hashlib.sha256(key.encode()).hexdigest()[:16]}"
                self.per_key_overrides[hashed] = limit

        # Storage for token buckets (keyed by API key or IP address)
        self.buckets: dict[str, TokenBucket] = {}
        self.buckets_lock = threading.Lock()

        # Counters for metrics
        self.allow_count = 0
        self.deny_count = 0
        self.metrics_lock = threading.Lock()

        logger.info(
            "Rate limiter initialized",
            extra={
                "enabled": enabled,
                "window_seconds": window_seconds,
                "max_requests": max_requests,
                "has_overrides": bool(per_key_overrides),
            },
        )

    def _get_limit_for_identifier(self, identifier: str) -> int:
        """Get the rate limit for a specific identifier (key or IP).

        Args:
            identifier: API key or IP address.

        Returns:
            Maximum requests allowed for this identifier.
        """
        # Check for per-key override (only for API keys, not IPs)
        if identifier in self.per_key_overrides:
            return self.per_key_overrides[identifier]

        # Use default limit
        return self.max_requests

    def _get_or_create_bucket(self, identifier: str) -> TokenBucket:
        """Get or create a token bucket for an identifier.

        This method is thread-safe. The bucket is created and stored within
        the lock, and we return a reference to the bucket. Since TokenBucket
        operations use their own internal lock, the bucket can be safely
        used after this method returns.

        Args:
            identifier: API key or IP address.

        Returns:
            TokenBucket instance for this identifier.
        """
        with self.buckets_lock:
            if identifier not in self.buckets:
                limit = self._get_limit_for_identifier(identifier)
                # Calculate refill rate: tokens per second
                refill_rate = limit / self.window_seconds
                self.buckets[identifier] = TokenBucket(capacity=limit, refill_rate=refill_rate)
            # Return reference to bucket - safe because TokenBucket has its own lock
            bucket = self.buckets[identifier]
        return bucket

    def check_rate_limit(
        self,
        api_key: Optional[str] = None,
        client_ip: Optional[str] = None,
        request_id: Optional[str] = None,
    ) -> tuple[bool, Optional[int]]:
        """Check if a request should be allowed or rate limited.

        Args:
            api_key: Optional API key for per-key rate limiting.
            client_ip: Optional client IP for per-IP rate limiting.
            request_id: Optional request ID for logging.

        Returns:
            Tuple of (allowed: bool, retry_after_seconds: Optional[int]).
            If allowed is False, retry_after_seconds indicates when to retry.

        Note:
            If rate limiting is disabled, always returns (True, None).
            Prioritizes API key over IP address when both are provided.
            API keys are hashed before storage to avoid logging plaintext.
        """
        if not self.enabled:
            return True, None

        # Determine identifier: prioritize API key over IP
        if api_key:
            # Hash the API key to avoid storing/logging plaintext
            import hashlib

            identifier = f"key:{hashlib.sha256(api_key.encode()).hexdigest()[:16]}"
            identifier_type = "api_key"
        elif client_ip:
            identifier = f"ip:{client_ip}"
            identifier_type = "client_ip"
        else:
            # No identifier available - deny by default
            logger.warning("Rate limit check with no identifier", extra={"request_id": request_id})
            return False, self.window_seconds

        # Get or create bucket for this identifier
        bucket = self._get_or_create_bucket(identifier)

        # Attempt to consume a token
        allowed = bucket.consume()

        # Update metrics
        with self.metrics_lock:
            if allowed:
                self.allow_count += 1
            else:
                self.deny_count += 1

        # Log the decision
        log_extra = {
            "request_id": request_id,
            "identifier_type": identifier_type,
            "allowed": allowed,
        }

        if allowed:
            logger.debug("Rate limit check: allowed", extra=log_extra)
        else:
            retry_after = bucket.get_retry_after()
            log_extra["retry_after_seconds"] = retry_after
            logger.info("Rate limit check: denied", extra=log_extra)
            return False, retry_after

        return True, None

    def get_metrics(self) -> dict[str, int]:
        """Get current rate limiting metrics.

        Returns:
            Dict with 'allow_count' and 'deny_count'.
        """
        with self.metrics_lock:
            return {"allow_count": self.allow_count, "deny_count": self.deny_count}


# Global rate limiter instance (lazily initialized)
_rate_limiter: Optional[RateLimiter] = None
_rate_limiter_lock = threading.Lock()


def get_rate_limiter() -> RateLimiter:
    """Get the global rate limiter instance.

    This function provides a singleton rate limiter configured from
    application settings. Uses thread-safe lazy initialization.

    Returns:
        RateLimiter: The global rate limiter instance.
    """
    global _rate_limiter

    # Fast path: return existing limiter without acquiring lock
    if _rate_limiter is not None:
        return _rate_limiter

    # Slow path: acquire lock and initialize limiter
    with _rate_limiter_lock:
        # Check again after acquiring lock (double-checked locking)
        if _rate_limiter is not None:
            return _rate_limiter

        logger.info("Initializing rate limiter from settings")

        # Get configuration from settings
        config = settings.get_rate_limit_config()

        # Per-key overrides could be loaded from environment variables or configuration
        # For now, use empty dict (can be extended in future to load from
        # PLANNER_RATE_LIMIT_OVERRIDES environment variable as JSON)
        per_key_overrides = {}

        _rate_limiter = RateLimiter(
            window_seconds=config["window_seconds"],
            max_requests=config["max_requests"],
            enabled=True,  # Enable by default
            per_key_overrides=per_key_overrides,
        )

        logger.info(
            "Rate limiter initialized successfully",
            extra={
                "window_seconds": config["window_seconds"],
                "max_requests": config["max_requests"],
            },
        )

        return _rate_limiter
