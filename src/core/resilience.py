"""
Network resilience patterns: retry, backoff, circuit breaker.
PRIORITY: P0 - Required for all network calls to prevent cascade failures.

Task 4: Enhanced with HALF_OPEN state, jitter, and non-retryable error handling.
"""

from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    retry_if_not_exception_type,
    RetryError
)
import aiohttp
import requests
from collections import defaultdict
from datetime import datetime, timedelta
from enum import Enum
import random
import structlog

logger = structlog.get_logger(__name__)


class CircuitState(Enum):
    """Circuit breaker states."""
    CLOSED = "closed"      # Normal operation
    OPEN = "open"          # Circuit tripped, rejecting calls
    HALF_OPEN = "half_open"  # Testing if service recovered


# Non-retryable HTTP error codes
NON_RETRYABLE_CODES = {400, 401, 403, 404, 422}


class NonRetryableError(Exception):
    """Exception for errors that should not be retried."""
    pass


class CircuitBreakerOpenError(Exception):
    """Exception when circuit breaker is open."""
    pass


class CircuitBreaker:
    """
    Circuit breaker with HALF_OPEN state for gradual recovery.

    States:
    - CLOSED: Normal operation, requests pass through
    - OPEN: Too many failures, blocking all requests
    - HALF_OPEN: Testing recovery with single request

    Args:
        failure_threshold: Number of consecutive failures before opening (default: 5)
        recovery_timeout: Seconds to wait before trying HALF_OPEN (default: 60)
        success_threshold: Successes in HALF_OPEN to close circuit (default: 1)
    """

    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: int = 60,
        success_threshold: int = 1
    ):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.success_threshold = success_threshold

        self.state = defaultdict(lambda: CircuitState.CLOSED)
        self.failures = defaultdict(int)
        self.successes = defaultdict(int)
        self.opened_at = {}

    def is_open(self, service: str) -> bool:
        """Check if circuit is open (blocking requests)."""
        current_state = self.state[service]

        if current_state == CircuitState.OPEN:
            # Check if recovery timeout passed
            if datetime.now() > self.opened_at[service] + timedelta(seconds=self.recovery_timeout):
                # Transition to HALF_OPEN for testing
                self.state[service] = CircuitState.HALF_OPEN
                logger.info("circuit_breaker_half_open",
                           service=service,
                           message="Testing service recovery")
                return False

            return True

        return False

    def record_success(self, service: str):
        """Record successful call."""
        current_state = self.state[service]

        if current_state == CircuitState.HALF_OPEN:
            self.successes[service] += 1

            if self.successes[service] >= self.success_threshold:
                # Recovered! Close circuit
                self.state[service] = CircuitState.CLOSED
                self.failures[service] = 0
                self.successes[service] = 0
                if service in self.opened_at:
                    del self.opened_at[service]
                logger.info("circuit_breaker_closed",
                           service=service,
                           message="Service recovered")

        elif current_state == CircuitState.CLOSED:
            # Reset failure count on success
            self.failures[service] = 0

    def record_failure(self, service: str):
        """Record failed call."""
        current_state = self.state[service]

        if current_state == CircuitState.HALF_OPEN:
            # Failed during recovery test - reopen circuit
            self.state[service] = CircuitState.OPEN
            self.opened_at[service] = datetime.now()
            self.successes[service] = 0
            logger.warning("circuit_breaker_reopened",
                          service=service,
                          message="Recovery test failed")

        elif current_state == CircuitState.CLOSED:
            self.failures[service] += 1

            if self.failures[service] >= self.failure_threshold:
                # Trip circuit
                self.state[service] = CircuitState.OPEN
                self.opened_at[service] = datetime.now()
                logger.error("circuit_breaker_opened",
                            service=service,
                            failures=self.failures[service],
                            threshold=self.failure_threshold)

    def get_state(self, service: str) -> CircuitState:
        """Get current circuit state."""
        return self.state[service]


# Global circuit breaker instance
circuit_breaker = CircuitBreaker()


def _should_retry_error(exception) -> bool:
    """
    Determine if an exception should be retried.

    Non-retryable errors (return False):
    - 400 Bad Request (client error, won't fix on retry)
    - 401 Unauthorized (auth issue, won't fix on retry)
    - 403 Forbidden (permission issue)
    - 404 Not Found (resource doesn't exist)
    - 422 Unprocessable Entity (validation error)
    - NonRetryableError (explicitly marked)

    Retryable errors (return True):
    - 429 Rate Limit (will fix after waiting)
    - 500+ Server errors (might be temporary)
    - Timeout errors
    - Connection errors
    """
    # Explicitly non-retryable
    if isinstance(exception, NonRetryableError):
        return False

    # Check HTTP status codes
    if isinstance(exception, (aiohttp.ClientResponseError, requests.HTTPError)):
        # Try to get status code from different attributes
        status_code = None

        if hasattr(exception, 'status'):
            status_code = exception.status
        elif hasattr(exception, 'response') and exception.response:
            if hasattr(exception.response, 'status_code'):
                status_code = exception.response.status_code
            elif hasattr(exception.response, 'status'):
                status_code = exception.response.status

        if status_code:
            return status_code not in NON_RETRYABLE_CODES

    # Retryable network errors
    retryable_types = (
        aiohttp.ClientError,
        requests.RequestException,
        TimeoutError,
        ConnectionError,
    )

    return isinstance(exception, retryable_types)


def _add_jitter(wait_time: float, jitter_factor: float = 0.1) -> float:
    """
    Add jitter to wait time to prevent thundering herd.

    Args:
        wait_time: Base wait time in seconds
        jitter_factor: Fraction of wait_time to randomize (default 0.1 = 10%)

    Returns:
        Wait time with jitter added

    Example:
        >>> _add_jitter(10.0, 0.1)
        10.534  # Random value between 9.0 and 11.0
    """
    jitter = wait_time * jitter_factor
    return wait_time + random.uniform(-jitter, jitter)


def retry_with_backoff(
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    jitter: bool = True
):
    """
    Decorator for retry with exponential backoff and jitter.

    Args:
        max_retries: Maximum number of retry attempts
        base_delay: Initial delay between retries in seconds
        max_delay: Maximum delay between retries
        jitter: Whether to add randomness to backoff (prevents thundering herd)

    Usage:
        @retry_with_backoff(max_retries=3, base_delay=1.0)
        async def fetch_data(url):
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as response:
                    return await response.json()

    Notes:
        - Automatically skips retry for 400, 401, 403, 404, 422 errors
        - Logs each retry attempt with backoff duration
        - Uses exponential backoff: delay = base_delay * (2 ** attempt)
        - Adds jitter by default to prevent synchronized retries
    """
    def decorator(func):
        async def wrapper(*args, **kwargs):
            last_exception = None

            for attempt in range(max_retries):
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    last_exception = e

                    # Check if should retry
                    if not _should_retry_error(e):
                        logger.warning("non_retryable_error",
                                     function=func.__name__,
                                     error=str(e))
                        raise

                    # Check if this was the last attempt
                    if attempt == max_retries - 1:
                        logger.error("max_retries_exhausted",
                                   function=func.__name__,
                                   attempts=max_retries,
                                   error=str(e))
                        raise

                    # Calculate backoff delay
                    delay = min(base_delay * (2 ** attempt), max_delay)

                    # Add jitter if enabled
                    if jitter:
                        delay = _add_jitter(delay)

                    logger.warning("retry_attempt",
                                 function=func.__name__,
                                 attempt=attempt + 1,
                                 max_retries=max_retries,
                                 delay_seconds=round(delay, 2),
                                 error=str(e))

                    # Wait before retry
                    await asyncio.sleep(delay)

            # Should never reach here, but just in case
            if last_exception:
                raise last_exception

        return wrapper
    return decorator


async def call_with_retry(func, *args, service_name='unknown', **kwargs):
    """
    Wrap async function with retry logic and circuit breaker.

    DEPRECATED: Use @retry_with_backoff decorator instead.
    Kept for backward compatibility.

    Usage:
        result = await call_with_retry(
            places.get_google_data,
            business_name, address,
            service_name='google_places'
        )
    """
    if circuit_breaker.is_open(service_name):
        raise CircuitBreakerOpenError(f"Circuit breaker open for {service_name}")

    try:
        result = await func(*args, **kwargs)
        circuit_breaker.record_success(service_name)
        return result
    except Exception as e:
        circuit_breaker.record_failure(service_name)
        logger.error("network_call_failed", service=service_name, error=str(e))
        raise


class RateLimiter:
    """Token bucket rate limiter."""

    def __init__(self, rate: int, per: float):
        """
        Args:
            rate: Number of calls allowed
            per: Time period in seconds
        """
        self.rate = rate
        self.per = per
        self.allowance = defaultdict(lambda: rate)
        self.last_check = defaultdict(lambda: datetime.now().timestamp())

    async def acquire(self, key: str = 'default'):
        """Acquire permission to make a call."""
        import asyncio

        current = datetime.now().timestamp()
        time_passed = current - self.last_check[key]
        self.last_check[key] = current

        self.allowance[key] += time_passed * (self.rate / self.per)
        if self.allowance[key] > self.rate:
            self.allowance[key] = self.rate

        if self.allowance[key] < 1.0:
            sleep_time = (1.0 - self.allowance[key]) * (self.per / self.rate)
            logger.debug("rate_limit_throttle", key=key, sleep_seconds=sleep_time)
            await asyncio.sleep(sleep_time)
            self.allowance[key] = 0.0
        else:
            self.allowance[key] -= 1.0


# Global rate limiters
google_places_limiter = RateLimiter(rate=100, per=86400)  # 100/day
yelp_limiter = RateLimiter(rate=5000, per=86400)  # 5000/day
openai_limiter = RateLimiter(rate=10000, per=86400)  # 10k/day
