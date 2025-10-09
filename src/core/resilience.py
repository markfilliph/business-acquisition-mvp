"""
Network resilience patterns: retry, backoff, circuit breaker.
PRIORITY: P1 - Required for all network calls.
"""

from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
import aiohttp
from collections import defaultdict
from datetime import datetime, timedelta
import structlog

logger = structlog.get_logger(__name__)


class CircuitBreaker:
    """Simple circuit breaker for API calls."""

    def __init__(self, failure_threshold=3, recovery_timeout=300):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout  # seconds
        self.failures = defaultdict(int)
        self.opened_at = {}

    def is_open(self, service: str) -> bool:
        """Check if circuit is open (service unavailable)."""
        if service not in self.opened_at:
            return False

        # Check if recovery timeout passed
        if datetime.now() > self.opened_at[service] + timedelta(seconds=self.recovery_timeout):
            # Try half-open state
            self.failures[service] = 0
            del self.opened_at[service]
            return False

        return True

    def record_success(self, service: str):
        """Record successful call."""
        self.failures[service] = 0
        if service in self.opened_at:
            del self.opened_at[service]
            logger.info("circuit_breaker_closed", service=service)

    def record_failure(self, service: str):
        """Record failed call."""
        self.failures[service] += 1

        if self.failures[service] >= self.failure_threshold:
            self.opened_at[service] = datetime.now()
            logger.warning("circuit_breaker_opened", service=service, failures=self.failures[service])


# Global circuit breaker instance
circuit_breaker = CircuitBreaker()


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=10),
    retry=retry_if_exception_type((aiohttp.ClientError, TimeoutError))
)
async def call_with_retry(func, *args, service_name='unknown', **kwargs):
    """
    Wrap async function with retry logic and circuit breaker.

    Usage:
        result = await call_with_retry(
            places.get_google_data,
            business_name, address,
            service_name='google_places'
        )
    """
    if circuit_breaker.is_open(service_name):
        raise Exception(f"Circuit breaker open for {service_name}")

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
