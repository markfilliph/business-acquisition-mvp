"""
SQLite-based API response caching.
PRIORITY: P1 - Critical for reducing API costs and improving performance.

Task 9: HTTP & API Response Caching
- SQLite-based caching with TTL support
- Automatic expiration cleanup
- Cache statistics tracking
- Decorator for easy function caching
"""

import json
import sqlite3
import time
import hashlib
from pathlib import Path
from typing import Any, Optional, Callable, Dict
from functools import wraps
import structlog

logger = structlog.get_logger(__name__)


class APICache:
    """SQLite-based API response cache with TTL support."""

    def __init__(self, db_path: str = "data/api_cache.db"):
        """
        Initialize API cache.

        Args:
            db_path: Path to SQLite database file

        Schema:
            - key: TEXT PRIMARY KEY (cache key)
            - value: TEXT (JSON-serialized data)
            - expires_at: INTEGER (Unix timestamp)
            - created_at: INTEGER (Unix timestamp)
        """
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        # Statistics
        self.stats = {
            "hits": 0,
            "misses": 0,
            "sets": 0,
            "invalidations": 0,
            "expirations": 0
        }

        # Initialize database
        self._init_db()
        self._cleanup_expired()

        logger.info("cache_initialized", db_path=str(self.db_path))

    def _init_db(self):
        """Initialize database schema."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS cache (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    expires_at INTEGER NOT NULL,
                    created_at INTEGER NOT NULL
                )
            """)

            # Create index on expires_at for faster cleanup
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_expires_at
                ON cache(expires_at)
            """)

            conn.commit()

    def _cleanup_expired(self):
        """Remove expired entries from cache."""
        now = int(time.time())

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "DELETE FROM cache WHERE expires_at < ?",
                (now,)
            )
            expired_count = cursor.rowcount
            conn.commit()

        if expired_count > 0:
            self.stats["expirations"] += expired_count
            logger.info("cache_cleanup", expired_count=expired_count)

    def get(self, key: str) -> Optional[Any]:
        """
        Get value from cache.

        Args:
            key: Cache key

        Returns:
            Cached value if exists and not expired, None otherwise

        Example:
            >>> cache = APICache()
            >>> cache.set("key1", {"data": "value"}, ttl_seconds=60)
            >>> result = cache.get("key1")
            >>> result
            {'data': 'value'}
        """
        now = int(time.time())

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "SELECT value, expires_at FROM cache WHERE key = ?",
                (key,)
            )
            row = cursor.fetchone()

        if row is None:
            self.stats["misses"] += 1
            logger.debug("cache_miss", key=key)
            return None

        value_json, expires_at = row

        # Check if expired
        if expires_at < now:
            self.stats["misses"] += 1
            self.stats["expirations"] += 1
            logger.debug("cache_expired", key=key, expires_at=expires_at, now=now)

            # Delete expired entry
            self.invalidate(key)
            return None

        # Cache hit
        self.stats["hits"] += 1
        logger.debug("cache_hit", key=key)

        try:
            return json.loads(value_json)
        except json.JSONDecodeError as e:
            logger.error("cache_json_decode_error", key=key, error=str(e))
            self.invalidate(key)  # Remove corrupted entry
            return None

    def set(self, key: str, value: Any, ttl_seconds: int = 2592000):
        """
        Set value in cache with TTL.

        Args:
            key: Cache key
            value: Value to cache (must be JSON-serializable)
            ttl_seconds: Time to live in seconds (default: 30 days)

        Example:
            >>> cache = APICache()
            >>> cache.set("key1", {"data": "value"}, ttl_seconds=3600)
        """
        now = int(time.time())
        expires_at = now + ttl_seconds

        try:
            value_json = json.dumps(value)
        except (TypeError, ValueError) as e:
            logger.error("cache_json_encode_error", key=key, error=str(e))
            return

        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO cache (key, value, expires_at, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (key, value_json, expires_at, now)
            )
            conn.commit()

        self.stats["sets"] += 1
        logger.debug("cache_set", key=key, ttl_seconds=ttl_seconds, expires_at=expires_at)

    def invalidate(self, key: str):
        """
        Invalidate (delete) cache entry.

        Args:
            key: Cache key to invalidate

        Example:
            >>> cache = APICache()
            >>> cache.invalidate("key1")
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("DELETE FROM cache WHERE key = ?", (key,))
            deleted = cursor.rowcount
            conn.commit()

        if deleted > 0:
            self.stats["invalidations"] += 1
            logger.debug("cache_invalidated", key=key)

    def clear_all(self):
        """Clear all cache entries."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("DELETE FROM cache")
            deleted = cursor.rowcount
            conn.commit()

        logger.info("cache_cleared", deleted_count=deleted)

    def get_stats(self) -> Dict[str, Any]:
        """
        Get cache statistics.

        Returns:
            Dict with cache statistics:
            - hits: Number of cache hits
            - misses: Number of cache misses
            - hit_rate: Cache hit rate (0.0-1.0)
            - total_requests: Total cache requests
            - sets: Number of cache sets
            - invalidations: Number of invalidations
            - expirations: Number of expired entries
            - total_entries: Current number of entries in cache

        Example:
            >>> cache = APICache()
            >>> cache.set("key1", "value1")
            >>> cache.get("key1")
            >>> cache.get("key2")
            >>> stats = cache.get_stats()
            >>> stats['hit_rate']
            0.5
        """
        # Get current entry count
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("SELECT COUNT(*) FROM cache")
            total_entries = cursor.fetchone()[0]

        total_requests = self.stats["hits"] + self.stats["misses"]
        hit_rate = self.stats["hits"] / total_requests if total_requests > 0 else 0.0

        return {
            "hits": self.stats["hits"],
            "misses": self.stats["misses"],
            "hit_rate": hit_rate,
            "total_requests": total_requests,
            "sets": self.stats["sets"],
            "invalidations": self.stats["invalidations"],
            "expirations": self.stats["expirations"],
            "total_entries": total_entries
        }

    def get_size_bytes(self) -> int:
        """Get size of cache database in bytes."""
        return self.db_path.stat().st_size if self.db_path.exists() else 0


# ==================== Global Cache Instance ====================
_global_cache: Optional[APICache] = None


def get_cache() -> APICache:
    """Get or create global cache instance."""
    global _global_cache
    if _global_cache is None:
        _global_cache = APICache()
    return _global_cache


# ==================== Cache Decorator ====================
def cached(
    ttl_seconds: int = 2592000,
    key_func: Optional[Callable] = None,
    cache_instance: Optional[APICache] = None
):
    """
    Decorator to cache function results.

    Args:
        ttl_seconds: Time to live in seconds (default: 30 days)
        key_func: Optional function to generate cache key from args/kwargs
                 If None, uses function name + JSON-serialized args
        cache_instance: Optional APICache instance (uses global cache if None)

    Example:
        >>> @cached(ttl_seconds=3600)
        ... def expensive_api_call(url: str) -> dict:
        ...     # Make API call
        ...     return {"data": "from API"}

        >>> @cached(ttl_seconds=3600, key_func=lambda url: f"api:{url}")
        ... def api_with_custom_key(url: str) -> dict:
        ...     return {"data": "from API"}

    Note:
        - Function args must be JSON-serializable if using default key_func
        - Cached functions log cache hits/misses
        - Non-deterministic functions should not be cached
    """
    def decorator(func: Callable) -> Callable:
        cache = cache_instance or get_cache()

        @wraps(func)
        def wrapper(*args, **kwargs):
            # Generate cache key
            if key_func:
                cache_key = key_func(*args, **kwargs)
            else:
                cache_key = _default_key_func(func, args, kwargs)

            # Try to get from cache
            cached_result = cache.get(cache_key)
            if cached_result is not None:
                logger.debug(
                    "cache_decorator_hit",
                    function=func.__name__,
                    cache_key=cache_key
                )
                return cached_result

            # Cache miss - call function
            logger.debug(
                "cache_decorator_miss",
                function=func.__name__,
                cache_key=cache_key
            )
            result = func(*args, **kwargs)

            # Store in cache
            cache.set(cache_key, result, ttl_seconds=ttl_seconds)

            return result

        # Add cache management methods to wrapper
        wrapper._cache = cache
        wrapper._get_cache_key = (
            key_func if key_func
            else lambda *args, **kwargs: _default_key_func(func, args, kwargs)
        )

        return wrapper

    return decorator


def _default_key_func(func: Callable, args: tuple, kwargs: dict) -> str:
    """
    Generate default cache key from function name and arguments.

    Args:
        func: Function being cached
        args: Positional arguments
        kwargs: Keyword arguments

    Returns:
        Cache key string

    Example:
        >>> def my_func(a, b, c=3): pass
        >>> key = _default_key_func(my_func, (1, 2), {"c": 4})
        >>> key.startswith("my_func:")
        True
    """
    # Create key from function name + args hash
    func_name = func.__name__

    # Serialize args and kwargs to create stable key
    try:
        args_str = json.dumps({"args": args, "kwargs": kwargs}, sort_keys=True)
        args_hash = hashlib.md5(args_str.encode()).hexdigest()
        return f"{func_name}:{args_hash}"
    except (TypeError, ValueError) as e:
        # Fallback to string representation if JSON serialization fails
        logger.warning(
            "cache_key_fallback",
            function=func_name,
            error=str(e)
        )
        args_str = f"{args}:{kwargs}"
        args_hash = hashlib.md5(args_str.encode()).hexdigest()
        return f"{func_name}:{args_hash}"
