"""Tests for Cache, CircuitBreaker, and RateLimiter."""

import time
import pytest
from crypto_mcp.governance.cache import MemoryCache
from crypto_mcp.governance.circuit_breaker import (
    CircuitBreaker,
    CircuitState,
    SlidingWindowRateLimiter,
)


def test_memory_cache_fresh_and_expiration():
    cache = MemoryCache(default_fresh_ttl=0.1, default_stale_ttl=0.3)
    cache.set("key1", "val1")

    # Immediately fresh
    val, is_stale, age = cache.get("key1", allow_stale=False)
    assert val == "val1"
    assert not is_stale
    assert age is not None

    # Wait for fresh TTL to expire but within stale TTL
    time.sleep(0.12)
    val_fresh, _, _ = cache.get("key1", allow_stale=False)
    assert val_fresh is None

    # With allow_stale=True, returns stale value
    val_stale, is_stale, age_stale = cache.get("key1", allow_stale=True)
    assert val_stale == "val1"
    assert is_stale is True

    # Wait until stale expires
    time.sleep(0.2)
    val_expired, _, _ = cache.get("key1", allow_stale=True)
    assert val_expired is None


def test_circuit_breaker_tripping_and_recovery():
    cb = CircuitBreaker("test_provider", failure_threshold=2, recovery_timeout=0.15)
    assert cb.is_available() is True
    assert cb.state == CircuitState.CLOSED

    # Failure 1
    cb.record_failure()
    assert cb.is_available() is True
    assert cb.state == CircuitState.CLOSED

    # Failure 2 -> Trips to OPEN
    cb.record_failure()
    assert cb.state == CircuitState.OPEN
    assert cb.is_available() is False

    # Wait for recovery timeout -> transitions to HALF_OPEN on next check
    time.sleep(0.18)
    assert cb.is_available() is True
    assert cb.state == CircuitState.HALF_OPEN

    # Recovery success -> returns to CLOSED
    cb.record_success()
    assert cb.state == CircuitState.CLOSED
    assert cb.is_available() is True


def test_sliding_window_rate_limiter():
    limiter = SlidingWindowRateLimiter(max_requests=2, window_seconds=0.2)
    assert limiter.acquire() is True
    assert limiter.acquire() is True
    # 3rd request should be throttled
    assert limiter.acquire() is False

    # Wait for window to expire
    time.sleep(0.22)
    assert limiter.acquire() is True
