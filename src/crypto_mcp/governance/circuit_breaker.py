"""Circuit Breaker and Local Rate Limiter for upstream providers."""

import time
from collections import deque
from enum import Enum
from typing import Optional
from crypto_mcp.utils.logging import logger


class CircuitState(str, Enum):
    CLOSED = "CLOSED"      # Normal operation
    OPEN = "OPEN"          # Failing, fast-reject/bypass
    HALF_OPEN = "HALF_OPEN"  # Testing recovery


class CircuitBreaker:
    """Circuit breaker to short-circuit repeated upstream failures."""

    def __init__(
        self,
        name: str,
        failure_threshold: int = 3,
        recovery_timeout: float = 30.0,
    ):
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.failure_count = 0
        self.state = CircuitState.CLOSED
        self.last_state_change = time.time()

    def is_available(self) -> bool:
        """Check if provider is available to take requests."""
        now = time.time()
        if self.state == CircuitState.CLOSED:
            return True

        if self.state == CircuitState.OPEN:
            if now - self.last_state_change >= self.recovery_timeout:
                logger.info(f"Circuit breaker [{self.name}] entering HALF_OPEN probe state.")
                self.state = CircuitState.HALF_OPEN
                self.last_state_change = now
                return True
            return False

        if self.state == CircuitState.HALF_OPEN:
            # Allow limited probe requests
            return True

        return True

    def record_success(self) -> None:
        """Record a successful call."""
        if self.state != CircuitState.CLOSED:
            logger.info(f"Circuit breaker [{self.name}] recovered to CLOSED.")
        self.failure_count = 0
        self.state = CircuitState.CLOSED
        self.last_state_change = time.time()

    def record_failure(self) -> None:
        """Record a failed call."""
        self.failure_count += 1
        now = time.time()

        if self.state == CircuitState.HALF_OPEN:
            logger.warning(f"Circuit breaker [{self.name}] probe failed. Returning to OPEN.")
            self.state = CircuitState.OPEN
            self.last_state_change = now
        elif self.failure_count >= self.failure_threshold and self.state == CircuitState.CLOSED:
            logger.warning(
                f"Circuit breaker [{self.name}] triggered after {self.failure_count} failures. Entering OPEN state for {self.recovery_timeout}s."
            )
            self.state = CircuitState.OPEN
            self.last_state_change = now


class SlidingWindowRateLimiter:
    """Local rate limiter using sliding window log."""

    def __init__(self, max_requests: int, window_seconds: float = 60.0):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.requests: deque[float] = deque()

    def acquire(self) -> bool:
        """Try to acquire a request token. Returns True if permitted, False if throttled."""
        now = time.time()
        # Remove expired timestamps
        cutoff = now - self.window_seconds
        while self.requests and self.requests[0] < cutoff:
            self.requests.popleft()

        if len(self.requests) < self.max_requests:
            self.requests.append(now)
            return True
        return False
