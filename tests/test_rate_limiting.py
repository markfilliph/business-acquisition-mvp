"""
Tests for token bucket rate limiting.
Ensures API calls respect rate limits and prevent quota exhaustion.
"""

import pytest
import asyncio
import time
import threading
from src.utils.rate_limiter import (
    TokenBucketLimiter,
    RateLimitRegistry,
    get_limiter,
    register_limiter
)


class TestTokenBucketBasics:
    """Test basic token bucket functionality."""

    def test_acquire_within_limit(self):
        """Test acquiring tokens within limit succeeds."""
        limiter = TokenBucketLimiter(rate_per_second=10, burst_size=10)

        # Should be able to acquire up to burst_size
        for i in range(10):
            assert limiter.acquire() is True

    def test_acquire_exceeds_limit(self):
        """Test acquiring beyond limit fails."""
        limiter = TokenBucketLimiter(rate_per_second=10, burst_size=10)

        # Exhaust tokens
        for i in range(10):
            limiter.acquire()

        # Next acquire should fail
        assert limiter.acquire() is False

    def test_tokens_refill_over_time(self):
        """Test tokens refill at specified rate."""
        limiter = TokenBucketLimiter(rate_per_second=10, burst_size=10)

        # Exhaust tokens
        for i in range(10):
            limiter.acquire()

        # Wait for refill (0.5 seconds = 5 tokens at 10/sec)
        time.sleep(0.5)

        # Should be able to acquire ~5 tokens
        acquired = 0
        for i in range(10):
            if limiter.acquire():
                acquired += 1

        assert 4 <= acquired <= 6  # Allow some timing variance

    def test_burst_capacity(self):
        """Test burst capacity limits token accumulation."""
        limiter = TokenBucketLimiter(rate_per_second=10, burst_size=5)

        # Wait to ensure full refill
        time.sleep(1.0)

        # Should only be able to acquire burst_size tokens
        acquired = 0
        for i in range(10):
            if limiter.acquire():
                acquired += 1

        assert acquired == 5  # Limited by burst_size

    def test_get_available_tokens(self):
        """Test getting current token count."""
        limiter = TokenBucketLimiter(rate_per_second=10, burst_size=10)

        # Start with full capacity
        assert limiter.get_available_tokens() == 10.0

        # Acquire some tokens
        limiter.acquire()
        limiter.acquire()

        # Allow small variance due to timing
        available = limiter.get_available_tokens()
        assert 7.9 <= available <= 8.1

    def test_reset(self):
        """Test resetting limiter."""
        limiter = TokenBucketLimiter(rate_per_second=10, burst_size=10)

        # Exhaust tokens
        for i in range(10):
            limiter.acquire()

        # Allow small variance due to timing
        available_before = limiter.get_available_tokens()
        assert available_before < 0.5  # Should be nearly exhausted

        # Reset
        limiter.reset()

        assert limiter.get_available_tokens() == 10.0


class TestTokenBucketWait:
    """Test blocking wait functionality."""

    @pytest.mark.asyncio
    async def test_wait_acquires_when_available(self):
        """Test wait returns immediately when tokens available."""
        limiter = TokenBucketLimiter(rate_per_second=10, burst_size=10)

        start = time.time()
        await limiter.wait()
        elapsed = time.time() - start

        # Should return almost immediately
        assert elapsed < 0.1

    @pytest.mark.asyncio
    async def test_wait_blocks_until_refill(self):
        """Test wait blocks until tokens refill."""
        limiter = TokenBucketLimiter(rate_per_second=10, burst_size=10)

        # Exhaust tokens
        for i in range(10):
            limiter.acquire()

        # Wait for 1 token (should take ~0.1 seconds at 10/sec)
        start = time.time()
        await limiter.wait()
        elapsed = time.time() - start

        assert 0.05 <= elapsed <= 0.2  # Allow timing variance

    @pytest.mark.asyncio
    async def test_multiple_waits_sequential(self):
        """Test multiple waits execute sequentially."""
        limiter = TokenBucketLimiter(rate_per_second=10, burst_size=1)

        wait_times = []

        async def timed_wait():
            start = time.time()
            await limiter.wait()
            wait_times.append(time.time() - start)

        # Run 3 waits sequentially
        for i in range(3):
            await timed_wait()

        # Second and third waits should block
        assert wait_times[0] < 0.1  # First immediate
        assert wait_times[1] > 0.05  # Second blocked
        assert wait_times[2] > 0.05  # Third blocked


class TestRateLimitRegistry:
    """Test rate limiter registry."""

    def test_register_and_get_limiter(self):
        """Test registering and retrieving limiters."""
        registry = RateLimitRegistry()

        registry.register("test_api", rate_per_second=5, burst_size=10)

        limiter = registry.get_limiter("test_api")
        assert isinstance(limiter, TokenBucketLimiter)

    def test_get_nonexistent_limiter_raises_error(self):
        """Test getting unregistered limiter raises KeyError."""
        registry = RateLimitRegistry()

        with pytest.raises(KeyError):
            registry.get_limiter("nonexistent")

    def test_list_limiters(self):
        """Test listing registered limiters."""
        registry = RateLimitRegistry()

        registry.register("api1", rate_per_second=10)
        registry.register("api2", rate_per_second=20)

        limiters = registry.list_limiters()

        assert "api1" in limiters
        assert "api2" in limiters

    def test_get_stats(self):
        """Test getting limiter statistics."""
        registry = RateLimitRegistry()
        registry.register("test_api", rate_per_second=10, burst_size=10)

        limiter = registry.get_limiter("test_api")

        # Acquire some tokens
        registry.track_acquire("test_api", limiter.acquire())
        registry.track_acquire("test_api", limiter.acquire())

        stats = registry.get_stats("test_api")

        assert stats["acquired"] == 2
        assert stats["rejected"] == 0
        assert "available_tokens" in stats
        assert "config" in stats

    def test_rejection_tracking(self):
        """Test tracking rejections."""
        registry = RateLimitRegistry()
        registry.register("test_api", rate_per_second=10, burst_size=2)

        limiter = registry.get_limiter("test_api")

        # Exhaust tokens
        registry.track_acquire("test_api", limiter.acquire())
        registry.track_acquire("test_api", limiter.acquire())

        # This should be rejected
        registry.track_acquire("test_api", limiter.acquire())

        stats = registry.get_stats("test_api")

        assert stats["acquired"] == 2
        assert stats["rejected"] == 1
        assert stats["rejection_rate"] == 1/3

    def test_reset_stats(self):
        """Test resetting statistics."""
        registry = RateLimitRegistry()
        registry.register("test_api", rate_per_second=10)

        limiter = registry.get_limiter("test_api")
        registry.track_acquire("test_api", limiter.acquire())

        # Reset stats
        registry.reset_stats("test_api")

        stats = registry.get_stats("test_api")
        assert stats["acquired"] == 0
        assert stats["rejected"] == 0


class TestThreadSafety:
    """Test thread safety of rate limiter."""

    def test_concurrent_acquires(self):
        """Test concurrent acquires from multiple threads."""
        limiter = TokenBucketLimiter(rate_per_second=100, burst_size=50)

        acquired_count = [0]
        lock = threading.Lock()

        def worker():
            for i in range(10):
                if limiter.acquire():
                    with lock:
                        acquired_count[0] += 1

        # Start 10 threads, each trying to acquire 10 tokens
        threads = []
        for i in range(10):
            t = threading.Thread(target=worker)
            t.start()
            threads.append(t)

        for t in threads:
            t.join()

        # Should acquire at most burst_size tokens
        # Allow small variance for timing/refill during test
        assert 45 <= acquired_count[0] <= 55


class TestRealWorldScenarios:
    """Test realistic API usage scenarios."""

    @pytest.mark.asyncio
    async def test_api_rate_limiting(self):
        """Test API rate limiting scenario."""
        # Simulate API with 5 requests/second limit
        limiter = TokenBucketLimiter(rate_per_second=5, burst_size=10)

        successful_calls = 0
        failed_calls = 0

        # Try to make 20 calls immediately
        for i in range(20):
            if limiter.acquire():
                successful_calls += 1
            else:
                failed_calls += 1

        # Should succeed for burst_size, fail for rest
        assert successful_calls == 10
        assert failed_calls == 10

    @pytest.mark.asyncio
    async def test_sustained_rate(self):
        """Test sustained request rate."""
        # Use smaller burst to avoid initial burst dominating the test
        limiter = TokenBucketLimiter(rate_per_second=10, burst_size=2)

        calls_made = 0
        duration = 0.5  # seconds

        start = time.time()
        while time.time() - start < duration:
            await limiter.wait()
            calls_made += 1

        # Should make approximately rate * duration calls
        # With burst=2, initial burst is small, so rate dominates
        # Expected: ~5 calls (10/s * 0.5s), but allow variance
        assert 3 <= calls_made <= 8  # Allow large variance for timing

    def test_quota_exhaustion_prevention(self):
        """Test preventing quota exhaustion."""
        # Simulate daily quota: 100 requests/day
        limiter = TokenBucketLimiter(
            rate_per_second=100/(24*3600),  # ~0.00115/sec
            burst_size=100
        )

        # Make burst of requests
        acquired = 0
        for i in range(200):
            if limiter.acquire():
                acquired += 1

        # Should only get burst_size
        assert acquired == 100

        # Future requests should fail (no time for refill)
        assert limiter.acquire() is False


class TestConvenienceFunctions:
    """Test convenience functions."""

    def test_register_and_get_global(self):
        """Test global register and get functions."""
        register_limiter("test_global", rate_per_second=10)

        limiter = get_limiter("test_global")
        assert isinstance(limiter, TokenBucketLimiter)

    def test_default_limiters_initialized(self):
        """Test default limiters are available."""
        # Should have default limiters from initialization
        try:
            google_limiter = get_limiter("google_places")
            assert isinstance(google_limiter, TokenBucketLimiter)

            openai_limiter = get_limiter("openai")
            assert isinstance(openai_limiter, TokenBucketLimiter)
        except KeyError:
            pytest.fail("Default limiters not initialized")


class TestEdgeCases:
    """Test edge cases."""

    def test_zero_rate(self):
        """Test limiter with zero rate (blocked)."""
        limiter = TokenBucketLimiter(rate_per_second=0, burst_size=10)

        # Initial burst available
        assert limiter.acquire() is True

        # But no refill
        time.sleep(0.5)
        for i in range(15):
            limiter.acquire()

        # Should still be exhausted
        assert limiter.acquire() is False

    def test_very_high_rate(self):
        """Test limiter with very high rate."""
        limiter = TokenBucketLimiter(rate_per_second=10000, burst_size=10000)

        # Should handle high rate
        acquired = 0
        for i in range(10000):
            if limiter.acquire():
                acquired += 1

        assert acquired == 10000

    def test_fractional_tokens(self):
        """Test acquiring fractional tokens."""
        limiter = TokenBucketLimiter(rate_per_second=0.5, burst_size=5)

        # Exhaust initial burst
        for i in range(5):
            limiter.acquire()

        # Wait for 4 seconds = 2 tokens at 0.5/sec
        time.sleep(4.1)  # Slightly longer to account for timing

        # Should be able to acquire 2 tokens
        acquired = 0
        for i in range(4):
            if limiter.acquire():
                acquired += 1

        # Should get approximately 2 tokens (allow 1-3 for timing variance)
        assert 1 <= acquired <= 3


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
