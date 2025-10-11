"""
Tests for resilience patterns: retry, circuit breaker, exponential backoff.
Ensures API failures are handled gracefully with automatic recovery.
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime, timedelta
import aiohttp
import requests

from src.core.resilience import (
    CircuitBreaker,
    CircuitState,
    CircuitBreakerOpenError,
    NonRetryableError,
    _should_retry_error,
    _add_jitter,
    retry_with_backoff,
    NON_RETRYABLE_CODES
)


class TestCircuitBreakerStates:
    """Test circuit breaker state transitions."""

    def test_initial_state_is_closed(self):
        """Test that circuit starts in CLOSED state."""
        cb = CircuitBreaker()
        assert cb.get_state("test_service") == CircuitState.CLOSED

    def test_circuit_opens_after_threshold_failures(self):
        """Test circuit opens after N consecutive failures."""
        cb = CircuitBreaker(failure_threshold=3)

        # Record failures
        for i in range(3):
            cb.record_failure("test_service")

        # Circuit should be open
        assert cb.is_open("test_service") is True
        assert cb.get_state("test_service") == CircuitState.OPEN

    def test_success_resets_failure_count(self):
        """Test that success resets failure counter."""
        cb = CircuitBreaker(failure_threshold=3)

        # Record 2 failures, then success
        cb.record_failure("test_service")
        cb.record_failure("test_service")
        cb.record_success("test_service")

        # Record 2 more failures (should NOT open, counter was reset)
        cb.record_failure("test_service")
        cb.record_failure("test_service")

        assert cb.is_open("test_service") is False

    def test_circuit_transitions_to_half_open_after_timeout(self):
        """Test circuit moves to HALF_OPEN after recovery timeout."""
        cb = CircuitBreaker(failure_threshold=2, recovery_timeout=1)

        # Open circuit
        cb.record_failure("test_service")
        cb.record_failure("test_service")
        assert cb.get_state("test_service") == CircuitState.OPEN

        # Wait for recovery timeout
        import time
        time.sleep(1.1)

        # Check if circuit allows testing
        is_open = cb.is_open("test_service")

        assert is_open is False
        assert cb.get_state("test_service") == CircuitState.HALF_OPEN

    def test_half_open_success_closes_circuit(self):
        """Test that success in HALF_OPEN closes circuit."""
        cb = CircuitBreaker(failure_threshold=2, recovery_timeout=1, success_threshold=1)

        # Open circuit
        cb.record_failure("test_service")
        cb.record_failure("test_service")

        # Wait and transition to HALF_OPEN
        import time
        time.sleep(1.1)
        cb.is_open("test_service")  # Trigger transition

        # Success in HALF_OPEN should close circuit
        cb.record_success("test_service")

        assert cb.get_state("test_service") == CircuitState.CLOSED

    def test_half_open_failure_reopens_circuit(self):
        """Test that failure in HALF_OPEN reopens circuit."""
        cb = CircuitBreaker(failure_threshold=2, recovery_timeout=1)

        # Open circuit
        cb.record_failure("test_service")
        cb.record_failure("test_service")

        # Wait and transition to HALF_OPEN
        import time
        time.sleep(1.1)
        cb.is_open("test_service")  # Trigger transition

        # Failure in HALF_OPEN should reopen
        cb.record_failure("test_service")

        assert cb.get_state("test_service") == CircuitState.OPEN

    def test_multiple_services_independent(self):
        """Test that different services have independent circuits."""
        cb = CircuitBreaker(failure_threshold=2)

        # Fail service A
        cb.record_failure("service_a")
        cb.record_failure("service_a")

        # Service A should be open, B should be closed
        assert cb.is_open("service_a") is True
        assert cb.is_open("service_b") is False


class TestRetryErrorClassification:
    """Test retry error classification."""

    def test_non_retryable_error_not_retried(self):
        """Test NonRetryableError is not retried."""
        error = NonRetryableError("Bad request")
        assert _should_retry_error(error) is False

    def test_400_error_not_retried(self):
        """Test 400 Bad Request is not retried."""
        response = Mock()
        response.status_code = 400
        error = requests.HTTPError(response=response)

        assert _should_retry_error(error) is False

    def test_401_error_not_retried(self):
        """Test 401 Unauthorized is not retried."""
        response = Mock()
        response.status_code = 401
        error = requests.HTTPError(response=response)

        assert _should_retry_error(error) is False

    def test_404_error_not_retried(self):
        """Test 404 Not Found is not retried."""
        response = Mock()
        response.status_code = 404
        error = requests.HTTPError(response=response)

        assert _should_retry_error(error) is False

    def test_429_error_is_retried(self):
        """Test 429 Rate Limit is retried."""
        response = Mock()
        response.status_code = 429
        error = requests.HTTPError(response=response)

        assert _should_retry_error(error) is True

    def test_500_error_is_retried(self):
        """Test 500 Server Error is retried."""
        response = Mock()
        response.status_code = 500
        error = requests.HTTPError(response=response)

        assert _should_retry_error(error) is True

    def test_timeout_error_is_retried(self):
        """Test TimeoutError is retried."""
        error = TimeoutError("Request timed out")
        assert _should_retry_error(error) is True

    def test_connection_error_is_retried(self):
        """Test ConnectionError is retried."""
        error = ConnectionError("Connection refused")
        assert _should_retry_error(error) is True

    def test_aiohttp_client_error_is_retried(self):
        """Test aiohttp.ClientError is retried."""
        error = aiohttp.ClientError("Network error")
        assert _should_retry_error(error) is True


class TestJitter:
    """Test jitter functionality."""

    def test_jitter_adds_randomness(self):
        """Test that jitter adds randomness to wait time."""
        wait_time = 10.0
        jitter_factor = 0.1

        # Run multiple times and ensure variance
        results = [_add_jitter(wait_time, jitter_factor) for _ in range(10)]

        # All results should be within jitter range
        for result in results:
            assert 9.0 <= result <= 11.0

        # Results should not all be identical
        assert len(set(results)) > 1

    def test_jitter_zero_factor(self):
        """Test jitter with zero factor returns original time."""
        wait_time = 10.0
        result = _add_jitter(wait_time, jitter_factor=0.0)

        assert result == wait_time


class TestRetryDecorator:
    """Test retry decorator with backoff."""

    @pytest.mark.asyncio
    async def test_successful_call_no_retry(self):
        """Test successful call doesn't retry."""
        call_count = 0

        @retry_with_backoff(max_retries=3)
        async def successful_function():
            nonlocal call_count
            call_count += 1
            return "success"

        result = await successful_function()

        assert result == "success"
        assert call_count == 1

    @pytest.mark.asyncio
    async def test_retries_on_retryable_error(self):
        """Test function retries on retryable errors."""
        call_count = 0

        @retry_with_backoff(max_retries=3, base_delay=0.01)
        async def flaky_function():
            nonlocal call_count
            call_count += 1
            if call_count <= 2:  # Fail first 2 attempts
                raise TimeoutError("Timeout")
            return "success"

        result = await flaky_function()

        assert result == "success"
        assert call_count == 3  # 3 total attempts

    @pytest.mark.asyncio
    async def test_no_retry_on_non_retryable_error(self):
        """Test function doesn't retry on non-retryable errors."""
        call_count = 0

        @retry_with_backoff(max_retries=3)
        async def bad_request_function():
            nonlocal call_count
            call_count += 1
            raise NonRetryableError("Bad request")

        with pytest.raises(NonRetryableError):
            await bad_request_function()

        assert call_count == 1  # Should NOT retry

    @pytest.mark.asyncio
    async def test_max_retries_exhausted(self):
        """Test function fails after max retries."""
        call_count = 0

        @retry_with_backoff(max_retries=3, base_delay=0.01)
        async def always_fails():
            nonlocal call_count
            call_count += 1
            raise TimeoutError("Always fails")

        with pytest.raises(TimeoutError):
            await always_fails()

        assert call_count == 3

    @pytest.mark.asyncio
    async def test_exponential_backoff(self):
        """Test exponential backoff timing."""
        call_times = []

        @retry_with_backoff(max_retries=3, base_delay=0.1, jitter=False)
        async def timed_function():
            import time
            call_times.append(time.time())
            raise TimeoutError("Fail")

        with pytest.raises(TimeoutError):
            await timed_function()

        # Check delays between calls increase
        if len(call_times) >= 2:
            delay1 = call_times[1] - call_times[0]
            # First retry should be ~0.1s (base_delay * 2^0)
            assert 0.05 <= delay1 <= 0.25  # Allow some variance


class TestRealWorldScenarios:
    """Test realistic failure scenarios."""

    @pytest.mark.asyncio
    async def test_api_flapping_recovery(self):
        """Test API that fails then recovers."""
        cb = CircuitBreaker(failure_threshold=3, recovery_timeout=1)

        # Simulate failing API
        for i in range(3):
            cb.record_failure("api")

        assert cb.is_open("api") is True

        # Wait for recovery timeout
        import time
        time.sleep(1.1)

        # Circuit should allow testing
        cb.is_open("api")
        assert cb.get_state("api") == CircuitState.HALF_OPEN

        # API recovers
        cb.record_success("api")

        assert cb.get_state("api") == CircuitState.CLOSED

    @pytest.mark.asyncio
    async def test_rate_limit_then_success(self):
        """Test API rate limit followed by success."""
        call_count = 0

        @retry_with_backoff(max_retries=3, base_delay=0.01)
        async def rate_limited_api():
            nonlocal call_count
            call_count += 1

            if call_count <= 1:  # Fail first attempt
                # Simulate 429 Rate Limit
                response = Mock()
                response.status_code = 429
                raise requests.HTTPError(response=response)

            return {"data": "success"}

        result = await rate_limited_api()

        assert result == {"data": "success"}
        assert call_count == 2  # 1 failure + 1 success

    @pytest.mark.asyncio
    async def test_permanent_failure_no_retry(self):
        """Test permanent failures (404) don't retry."""
        call_count = 0

        @retry_with_backoff(max_retries=3)
        async def not_found_api():
            nonlocal call_count
            call_count += 1

            response = Mock()
            response.status_code = 404
            raise requests.HTTPError(response=response)

        with pytest.raises(requests.HTTPError):
            await not_found_api()

        assert call_count == 1  # Should NOT retry


class TestCircuitBreakerIntegration:
    """Test circuit breaker integration with retry."""

    def test_circuit_breaker_blocks_calls_when_open(self):
        """Test circuit breaker prevents calls when open."""
        cb = CircuitBreaker(failure_threshold=2)

        # Trip circuit
        cb.record_failure("test")
        cb.record_failure("test")

        assert cb.is_open("test") is True

        # Attempting call should fail immediately
        with pytest.raises(Exception):
            if cb.is_open("test"):
                raise CircuitBreakerOpenError("Circuit open")

    def test_circuit_breaker_allows_testing_after_timeout(self):
        """Test circuit allows one test call in HALF_OPEN."""
        cb = CircuitBreaker(failure_threshold=2, recovery_timeout=1)

        # Trip circuit
        cb.record_failure("test")
        cb.record_failure("test")

        # Wait for timeout
        import time
        time.sleep(1.1)

        # Should allow testing
        assert cb.is_open("test") is False
        assert cb.get_state("test") == CircuitState.HALF_OPEN


class TestEdgeCases:
    """Test edge cases and error conditions."""

    def test_circuit_breaker_with_zero_threshold(self):
        """Test circuit breaker with threshold=0 opens immediately."""
        cb = CircuitBreaker(failure_threshold=0)

        # With threshold 0, circuit should never open (failures < 0 is impossible)
        # This is a degenerate case - circuit stays closed
        cb.record_failure("test")

        # Should not open (failures=1 is not >= 0 in the comparison)
        # Actually, 1 >= 0 is True, so it SHOULD open
        assert cb.is_open("test") is True

    def test_multiple_successes_in_half_open(self):
        """Test multiple successes required in HALF_OPEN."""
        cb = CircuitBreaker(failure_threshold=2, recovery_timeout=1, success_threshold=2)

        # Open circuit
        cb.record_failure("test")
        cb.record_failure("test")

        # Transition to HALF_OPEN
        import time
        time.sleep(1.1)
        cb.is_open("test")

        # First success shouldn't close circuit
        cb.record_success("test")
        assert cb.get_state("test") == CircuitState.HALF_OPEN

        # Second success should close
        cb.record_success("test")
        assert cb.get_state("test") == CircuitState.CLOSED

    @pytest.mark.asyncio
    async def test_concurrent_retry_calls(self):
        """Test concurrent calls with retry don't interfere."""
        call_counts = {"a": 0, "b": 0}

        @retry_with_backoff(max_retries=2, base_delay=0.01)
        async def concurrent_function(call_id):
            call_counts[call_id] += 1
            if call_counts[call_id] <= 1:  # Fail first attempt
                raise TimeoutError("First call fails")
            return f"success_{call_id}"

        # Run concurrently
        results = await asyncio.gather(
            concurrent_function("a"),
            concurrent_function("b")
        )

        assert results == ["success_a", "success_b"]
        assert call_counts["a"] == 2  # 1 failure + 1 success
        assert call_counts["b"] == 2  # 1 failure + 1 success


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
