"""
Production HTTP client with rate limiting, circuit breaker, and compliance.
"""
import asyncio
import random
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, List, Optional, Set
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser

import aiohttp
import structlog

from ..core.config import HttpConfig
from ..core.exceptions import HttpClientError, RateLimitError, CircuitBreakerOpenError


class CircuitBreakerState(Enum):
    """Circuit breaker states."""
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitBreaker:
    """Circuit breaker for handling service failures."""
    
    def __init__(self, failure_threshold: int = 5, timeout_seconds: int = 60):
        self.failure_threshold = failure_threshold
        self.timeout_seconds = timeout_seconds
        self.failure_count = 0
        self.last_failure_time: Optional[datetime] = None
        self.state = CircuitBreakerState.CLOSED
        self.logger = structlog.get_logger(__name__)
    
    def can_execute(self) -> bool:
        """Check if request can be executed."""
        now = datetime.utcnow()
        
        if self.state == CircuitBreakerState.CLOSED:
            return True
        
        if self.state == CircuitBreakerState.OPEN:
            if self.last_failure_time and (now - self.last_failure_time).seconds >= self.timeout_seconds:
                self.state = CircuitBreakerState.HALF_OPEN
                self.logger.info("circuit_breaker_half_open", domain=self._domain_name)
                return True
            return False
        
        # HALF_OPEN state
        return True
    
    def record_success(self):
        """Record successful request."""
        self.failure_count = 0
        if self.state != CircuitBreakerState.CLOSED:
            self.state = CircuitBreakerState.CLOSED
            self.logger.info("circuit_breaker_closed", domain=self._domain_name)
    
    def record_failure(self):
        """Record failed request."""
        self.failure_count += 1
        self.last_failure_time = datetime.utcnow()
        
        if self.failure_count >= self.failure_threshold:
            self.state = CircuitBreakerState.OPEN
            self.logger.warning("circuit_breaker_opened", 
                              domain=self._domain_name,
                              failure_count=self.failure_count)
    
    @property
    def _domain_name(self) -> str:
        """Get domain name for logging (if available)."""
        return getattr(self, 'domain', 'unknown')


class RateLimiter:
    """Token bucket rate limiter."""
    
    def __init__(self, requests_per_minute: int, burst_size: int = None):
        self.requests_per_minute = requests_per_minute
        self.burst_size = burst_size or requests_per_minute
        self.tokens = self.burst_size
        self.last_refill = datetime.utcnow()
        self.lock = asyncio.Lock()
    
    async def acquire(self) -> bool:
        """Acquire a token for making a request."""
        async with self.lock:
            now = datetime.utcnow()
            
            # Refill tokens
            time_passed = (now - self.last_refill).total_seconds()
            tokens_to_add = int(time_passed * (self.requests_per_minute / 60))
            
            if tokens_to_add > 0:
                self.tokens = min(self.burst_size, self.tokens + tokens_to_add)
                self.last_refill = now
            
            if self.tokens > 0:
                self.tokens -= 1
                return True
            
            return False
    
    async def wait_for_token(self):
        """Wait until a token is available."""
        while not await self.acquire():
            await asyncio.sleep(0.1)


class HttpClient:
    """Production-grade HTTP client with resilience patterns."""
    
    def __init__(self, config: HttpConfig):
        self.config = config
        self.session: Optional[aiohttp.ClientSession] = None
        self.circuit_breakers: Dict[str, CircuitBreaker] = {}
        self.rate_limiter = RateLimiter(config.requests_per_minute)
        self.robots_cache: Dict[str, bool] = {}
        self.logger = structlog.get_logger(__name__)
        
        # Request statistics
        self.stats = {
            'requests_made': 0,
            'requests_failed': 0,
            'requests_blocked_by_robots': 0,
            'requests_blocked_by_circuit_breaker': 0
        }
    
    async def __aenter__(self):
        """Async context manager entry."""
        await self._create_session()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        if self.session:
            await self.session.close()
    
    async def _create_session(self):
        """Create aiohttp session with proper configuration."""
        timeout = aiohttp.ClientTimeout(
            total=self.config.read_timeout,
            connect=self.config.connection_timeout
        )
        
        connector = aiohttp.TCPConnector(
            limit=self.config.concurrent_requests,
            limit_per_host=2,
            ttl_dns_cache=300,
            use_dns_cache=True,
            keepalive_timeout=30
        )
        
        self.session = aiohttp.ClientSession(
            timeout=timeout,
            connector=connector,
            headers={'User-Agent': self.config.user_agent},
            raise_for_status=False  # Handle status codes manually
        )
    
    def _get_circuit_breaker(self, domain: str) -> CircuitBreaker:
        """Get or create circuit breaker for domain."""
        if domain not in self.circuit_breakers:
            breaker = CircuitBreaker()
            breaker.domain = domain  # For logging
            self.circuit_breakers[domain] = breaker
        
        return self.circuit_breakers[domain]
    
    async def _check_robots_txt(self, url: str) -> bool:
        """Check if URL is allowed by robots.txt."""
        if not self.config.respect_robots_txt:
            return True
        
        parsed = urlparse(url)
        domain = f"{parsed.scheme}://{parsed.netloc}"
        
        # Check cache first
        if domain in self.robots_cache:
            return self.robots_cache[domain]
        
        try:
            robots_url = urljoin(domain, '/robots.txt')
            
            # Use a separate session for robots.txt to avoid infinite recursion
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10)) as session:
                async with session.get(robots_url) as response:
                    if response.status == 200:
                        robots_content = await response.text()
                        
                        # Parse robots.txt
                        allowed = self._parse_robots_txt(robots_content, parsed.path, self.config.user_agent)
                        self.robots_cache[domain] = allowed
                        
                        if not allowed:
                            self.logger.info("robots_txt_disallowed", 
                                           url=url, 
                                           user_agent=self.config.user_agent)
                        
                        return allowed
        
        except Exception as e:
            self.logger.warning("robots_txt_check_failed", domain=domain, error=str(e))
        
        # Default to allowed if robots.txt is unavailable
        self.robots_cache[domain] = True
        return True
    
    def _parse_robots_txt(self, content: str, path: str, user_agent: str) -> bool:
        """Parse robots.txt content to check if path is allowed."""
        try:
            rp = RobotFileParser()
            rp.set_url("http://example.com/robots.txt")  # Dummy URL
            rp.feed(content)
            return rp.can_fetch(user_agent, path)
        except Exception:
            # Fallback to simple parsing
            user_agent_section = False
            
            for line in content.split('\n'):
                line = line.strip().lower()
                
                if line.startswith('user-agent:'):
                    ua = line.split(':', 1)[1].strip()
                    user_agent_section = ua == '*' or user_agent.lower() in ua
                
                elif user_agent_section and line.startswith('disallow:'):
                    disallow_path = line.split(':', 1)[1].strip()
                    if disallow_path == '/' or path.startswith(disallow_path):
                        return False
            
            return True
    
    async def _add_request_jitter(self):
        """Add random jitter to prevent thundering herd."""
        jitter = 0.1 + (random.random() * 0.5)  # 0.1-0.6 seconds
        await asyncio.sleep(jitter)
    
    async def get(self, url: str, **kwargs) -> Optional[aiohttp.ClientResponse]:
        """Make a GET request with full resilience patterns."""
        parsed = urlparse(url)
        domain = parsed.netloc
        
        # Check circuit breaker
        circuit_breaker = self._get_circuit_breaker(domain)
        if not circuit_breaker.can_execute():
            self.stats['requests_blocked_by_circuit_breaker'] += 1
            self.logger.warning("request_blocked_by_circuit_breaker", url=url)
            raise CircuitBreakerOpenError(f"Circuit breaker open for {domain}")
        
        # Check robots.txt
        if not await self._check_robots_txt(url):
            self.stats['requests_blocked_by_robots'] += 1
            self.logger.info("request_blocked_by_robots", url=url)
            return None
        
        # Rate limiting
        await self.rate_limiter.wait_for_token()
        
        # Add jitter
        await self._add_request_jitter()
        
        # Make request with retries
        last_exception = None
        
        for attempt in range(self.config.max_retries + 1):
            try:
                self.stats['requests_made'] += 1
                
                async with self.session.get(url, **kwargs) as response:
                    circuit_breaker.record_success()
                    
                    self.logger.info("http_request_success", 
                                   url=url,
                                   status=response.status,
                                   attempt=attempt + 1)
                    
                    return response
                    
            except Exception as e:
                last_exception = e
                self.stats['requests_failed'] += 1
                
                self.logger.warning("http_request_failed", 
                                  url=url,
                                  attempt=attempt + 1,
                                  error=str(e))
                
                if attempt < self.config.max_retries:
                    # Exponential backoff
                    wait_time = (self.config.backoff_factor ** attempt) + random.uniform(0, 1)
                    await asyncio.sleep(wait_time)
                else:
                    circuit_breaker.record_failure()
        
        # All retries failed
        raise HttpClientError(f"Request failed after {self.config.max_retries + 1} attempts: {last_exception}")
    
    def get_stats(self) -> Dict[str, int]:
        """Get client statistics."""
        return self.stats.copy()