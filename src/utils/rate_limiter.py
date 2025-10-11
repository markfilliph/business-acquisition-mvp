"""
Token bucket rate limiting for API quota management.
PRIORITY: P0 - Required to prevent unexpected API bills and quota exhaustion.

Task 5: Production-grade rate limiting with registry pattern and thread safety.
"""

import asyncio
import threading
import time
from typing import Dict, Optional
from collections import defaultdict
import structlog

logger = structlog.get_logger(__name__)


class TokenBucketLimiter:
    """
    Thread-safe token bucket rate limiter.

    Allows bursts up to bucket capacity while maintaining steady-state rate.

    Args:
        rate_per_second: Number of requests allowed per second
        burst_size: Maximum burst capacity (default: rate_per_second)

    Example:
        >>> limiter = TokenBucketLimiter(rate_per_second=10, burst_size=20)
        >>> if limiter.acquire():
        >>>     make_api_call()
    """

    def __init__(self, rate_per_second: float, burst_size: Optional[int] = None):
        self.rate_per_second = rate_per_second
        self.burst_size = burst_size or int(rate_per_second)

        self._tokens = float(self.burst_size)
        self._last_refill = time.monotonic()
        self._lock = threading.Lock()

        logger.info("rate_limiter_created",
                   rate_per_second=rate_per_second,
                   burst_size=self.burst_size)

    def acquire(self, tokens: int = 1) -> bool:
        """
        Try to acquire tokens without blocking.

        Args:
            tokens: Number of tokens to acquire (default: 1)

        Returns:
            True if tokens acquired, False if not enough tokens available
        """
        with self._lock:
            self._refill()

            if self._tokens >= tokens:
                self._tokens -= tokens
                logger.debug("rate_limit_acquired",
                           tokens_acquired=tokens,
                           tokens_remaining=round(self._tokens, 2))
                return True

            logger.warning("rate_limit_exceeded",
                         tokens_requested=tokens,
                         tokens_available=round(self._tokens, 2))
            return False

    async def wait(self, tokens: int = 1):
        """
        Wait until tokens are available (blocking).

        Args:
            tokens: Number of tokens to acquire (default: 1)
        """
        while True:
            with self._lock:
                self._refill()

                if self._tokens >= tokens:
                    self._tokens -= tokens
                    logger.debug("rate_limit_acquired_after_wait",
                               tokens_acquired=tokens,
                               tokens_remaining=round(self._tokens, 2))
                    return

                # Calculate wait time
                tokens_needed = tokens - self._tokens
                wait_time = tokens_needed / self.rate_per_second

            logger.debug("rate_limit_waiting",
                        tokens_needed=tokens_needed,
                        wait_seconds=round(wait_time, 2))

            # Wait outside the lock
            await asyncio.sleep(wait_time)

    def _refill(self):
        """Refill tokens based on time elapsed (must be called with lock held)."""
        now = time.monotonic()
        time_passed = now - self._last_refill

        # Add tokens based on time passed
        tokens_to_add = time_passed * self.rate_per_second
        self._tokens = min(self._tokens + tokens_to_add, self.burst_size)
        self._last_refill = now

    def get_available_tokens(self) -> float:
        """Get current number of available tokens."""
        with self._lock:
            self._refill()
            return self._tokens

    def reset(self):
        """Reset limiter to full capacity."""
        with self._lock:
            self._tokens = float(self.burst_size)
            self._last_refill = time.monotonic()
            logger.info("rate_limiter_reset")


class RateLimitRegistry:
    """
    Singleton registry for managing multiple rate limiters.

    Usage:
        >>> registry = RateLimitRegistry.get_instance()
        >>> limiter = registry.get_limiter("google_places")
        >>> if limiter.acquire():
        >>>     make_api_call()
    """

    _instance = None
    _lock = threading.Lock()

    def __init__(self):
        self._limiters: Dict[str, TokenBucketLimiter] = {}
        self._config: Dict[str, Dict] = {}
        self._stats = defaultdict(lambda: {"acquired": 0, "rejected": 0})

    @classmethod
    def get_instance(cls) -> "RateLimitRegistry":
        """Get singleton instance (thread-safe)."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    def register(
        self,
        name: str,
        rate_per_second: float,
        burst_size: Optional[int] = None
    ):
        """
        Register a new rate limiter.

        Args:
            name: Unique identifier for this limiter
            rate_per_second: Rate limit in requests/second
            burst_size: Maximum burst capacity
        """
        if name in self._limiters:
            logger.warning("rate_limiter_already_registered",
                         name=name,
                         message="Overwriting existing limiter")

        self._limiters[name] = TokenBucketLimiter(
            rate_per_second=rate_per_second,
            burst_size=burst_size
        )

        self._config[name] = {
            "rate_per_second": rate_per_second,
            "burst_size": burst_size or int(rate_per_second)
        }

        logger.info("rate_limiter_registered",
                   name=name,
                   rate_per_second=rate_per_second,
                   burst_size=burst_size or int(rate_per_second))

    def get_limiter(self, name: str) -> TokenBucketLimiter:
        """
        Get rate limiter by name.

        Args:
            name: Limiter identifier

        Returns:
            TokenBucketLimiter instance

        Raises:
            KeyError: If limiter not registered
        """
        if name not in self._limiters:
            raise KeyError(
                f"Rate limiter '{name}' not registered. "
                f"Available limiters: {list(self._limiters.keys())}"
            )

        return self._limiters[name]

    def track_acquire(self, name: str, acquired: bool):
        """Track acquisition attempt for metrics."""
        if acquired:
            self._stats[name]["acquired"] += 1
        else:
            self._stats[name]["rejected"] += 1

    def get_stats(self, name: Optional[str] = None) -> Dict:
        """
        Get rate limiting statistics.

        Args:
            name: Optional limiter name (if None, returns all stats)

        Returns:
            Dictionary with statistics
        """
        if name:
            stats = dict(self._stats[name])
            total = stats["acquired"] + stats["rejected"]
            stats["rejection_rate"] = (
                stats["rejected"] / total if total > 0 else 0.0
            )

            if name in self._limiters:
                limiter = self._limiters[name]
                stats["available_tokens"] = limiter.get_available_tokens()
                stats["config"] = self._config[name]

            return stats

        # Return all stats
        all_stats = {}
        for limiter_name in self._limiters.keys():
            all_stats[limiter_name] = self.get_stats(limiter_name)

        return all_stats

    def reset_stats(self, name: Optional[str] = None):
        """Reset statistics for limiter(s)."""
        if name:
            self._stats[name] = {"acquired": 0, "rejected": 0}
        else:
            self._stats.clear()

    def list_limiters(self) -> list:
        """Get list of registered limiter names."""
        return list(self._limiters.keys())


# Convenience functions
def get_limiter(name: str) -> TokenBucketLimiter:
    """
    Get rate limiter from global registry.

    Args:
        name: Limiter identifier

    Returns:
        TokenBucketLimiter instance
    """
    registry = RateLimitRegistry.get_instance()
    return registry.get_limiter(name)


def register_limiter(
    name: str,
    rate_per_second: float,
    burst_size: Optional[int] = None
):
    """
    Register a rate limiter in global registry.

    Args:
        name: Unique identifier
        rate_per_second: Rate limit
        burst_size: Burst capacity
    """
    registry = RateLimitRegistry.get_instance()
    registry.register(name, rate_per_second, burst_size)


# Initialize default limiters
def initialize_default_limiters():
    """Initialize rate limiters for common APIs."""
    registry = RateLimitRegistry.get_instance()

    # Google Places API: 10 requests/second
    registry.register("google_places", rate_per_second=10, burst_size=20)

    # OpenAI API: 50 requests/minute = 0.83/second
    registry.register("openai", rate_per_second=0.83, burst_size=10)

    # Yelp API: 5 requests/second
    registry.register("yelp", rate_per_second=5, burst_size=10)

    # Wayback Machine: 1 request/second (be nice to Archive.org)
    registry.register("wayback", rate_per_second=1, burst_size=2)

    logger.info("default_rate_limiters_initialized",
               limiters=registry.list_limiters())


# Initialize on import
initialize_default_limiters()
