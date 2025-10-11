"""
Tests for SQLite-based API response caching.
Validates caching functionality, TTL, and decorator behavior.
"""

import pytest
import time
import tempfile
import os
from pathlib import Path
from src.utils.cache import APICache, cached, get_cache, _default_key_func


class TestAPICacheBasics:
    """Test basic APICache functionality."""

    def test_cache_init_creates_database(self):
        """Test that cache initialization creates database file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test_cache.db")
            cache = APICache(db_path=db_path)

            assert Path(db_path).exists()
            assert cache.get_stats()["total_entries"] == 0

    def test_cache_set_and_get(self):
        """Test basic set and get operations."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = APICache(db_path=os.path.join(tmpdir, "test.db"))

            # Set a value
            cache.set("key1", {"data": "value1"}, ttl_seconds=60)

            # Get the value
            result = cache.get("key1")

            assert result == {"data": "value1"}

    def test_cache_get_nonexistent_returns_none(self):
        """Test that getting nonexistent key returns None."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = APICache(db_path=os.path.join(tmpdir, "test.db"))

            result = cache.get("nonexistent")

            assert result is None

    def test_cache_set_overwrites_existing(self):
        """Test that set overwrites existing value."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = APICache(db_path=os.path.join(tmpdir, "test.db"))

            cache.set("key1", "value1", ttl_seconds=60)
            cache.set("key1", "value2", ttl_seconds=60)

            result = cache.get("key1")

            assert result == "value2"

    def test_cache_handles_complex_types(self):
        """Test caching of complex JSON-serializable types."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = APICache(db_path=os.path.join(tmpdir, "test.db"))

            complex_data = {
                "name": "Test Business",
                "address": {"street": "123 Main St", "city": "Hamilton"},
                "tags": ["manufacturing", "printing"],
                "revenue": 1_200_000,
                "active": True,
                "notes": None
            }

            cache.set("complex", complex_data, ttl_seconds=60)
            result = cache.get("complex")

            assert result == complex_data


class TestCacheTTL:
    """Test TTL (time-to-live) functionality."""

    def test_cache_expires_after_ttl(self):
        """Test that cache entries expire after TTL."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = APICache(db_path=os.path.join(tmpdir, "test.db"))

            # Set with 2 second TTL for more reliable testing
            cache.set("key1", "value1", ttl_seconds=2)

            # Should exist immediately
            assert cache.get("key1") == "value1"

            # Wait for expiration (use 2.5 seconds to be safe)
            time.sleep(2.5)

            # Should be expired
            result = cache.get("key1")
            assert result is None

    def test_cache_respects_different_ttls(self):
        """Test that different keys can have different TTLs."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = APICache(db_path=os.path.join(tmpdir, "test.db"))

            cache.set("short_ttl", "value1", ttl_seconds=2)
            cache.set("long_ttl", "value2", ttl_seconds=60)

            # Wait for short TTL to expire (use 2.5 seconds to be safe)
            time.sleep(2.5)

            assert cache.get("short_ttl") is None
            assert cache.get("long_ttl") == "value2"


class TestCacheInvalidation:
    """Test cache invalidation."""

    def test_invalidate_removes_entry(self):
        """Test that invalidate removes cache entry."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = APICache(db_path=os.path.join(tmpdir, "test.db"))

            cache.set("key1", "value1", ttl_seconds=60)
            assert cache.get("key1") == "value1"

            cache.invalidate("key1")
            assert cache.get("key1") is None

    def test_invalidate_nonexistent_key_silent(self):
        """Test that invalidating nonexistent key doesn't error."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = APICache(db_path=os.path.join(tmpdir, "test.db"))

            # Should not raise error
            cache.invalidate("nonexistent")

    def test_clear_all_removes_everything(self):
        """Test that clear_all removes all entries."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = APICache(db_path=os.path.join(tmpdir, "test.db"))

            cache.set("key1", "value1", ttl_seconds=60)
            cache.set("key2", "value2", ttl_seconds=60)
            cache.set("key3", "value3", ttl_seconds=60)

            assert cache.get_stats()["total_entries"] == 3

            cache.clear_all()

            assert cache.get_stats()["total_entries"] == 0
            assert cache.get("key1") is None
            assert cache.get("key2") is None
            assert cache.get("key3") is None


class TestCacheStatistics:
    """Test cache statistics tracking."""

    def test_stats_track_hits_and_misses(self):
        """Test that statistics track hits and misses."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = APICache(db_path=os.path.join(tmpdir, "test.db"))

            cache.set("key1", "value1", ttl_seconds=60)

            # 1 hit
            cache.get("key1")

            # 2 misses
            cache.get("key2")
            cache.get("key3")

            stats = cache.get_stats()

            assert stats["hits"] == 1
            assert stats["misses"] == 2
            assert stats["total_requests"] == 3
            assert abs(stats["hit_rate"] - 0.333) < 0.01

    def test_stats_track_sets(self):
        """Test that statistics track set operations."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = APICache(db_path=os.path.join(tmpdir, "test.db"))

            cache.set("key1", "value1", ttl_seconds=60)
            cache.set("key2", "value2", ttl_seconds=60)
            cache.set("key3", "value3", ttl_seconds=60)

            stats = cache.get_stats()

            assert stats["sets"] == 3
            assert stats["total_entries"] == 3

    def test_stats_track_invalidations(self):
        """Test that statistics track invalidations."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = APICache(db_path=os.path.join(tmpdir, "test.db"))

            cache.set("key1", "value1", ttl_seconds=60)
            cache.invalidate("key1")
            cache.invalidate("key2")  # Doesn't exist

            stats = cache.get_stats()

            assert stats["invalidations"] == 1  # Only one existed

    def test_stats_track_expirations(self):
        """Test that statistics track expirations."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = APICache(db_path=os.path.join(tmpdir, "test.db"))

            cache.set("key1", "value1", ttl_seconds=2)
            time.sleep(2.5)  # Use 2.5 seconds to be safe

            # This should trigger expiration
            cache.get("key1")

            stats = cache.get_stats()

            assert stats["expirations"] >= 1


class TestCacheDecorator:
    """Test @cached decorator functionality."""

    def test_decorator_caches_function_results(self):
        """Test that decorator caches function results."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = APICache(db_path=os.path.join(tmpdir, "test.db"))

            call_count = 0

            @cached(ttl_seconds=60, cache_instance=cache)
            def expensive_function(x):
                nonlocal call_count
                call_count += 1
                return x * 2

            # First call - should execute function
            result1 = expensive_function(5)
            assert result1 == 10
            assert call_count == 1

            # Second call with same args - should use cache
            result2 = expensive_function(5)
            assert result2 == 10
            assert call_count == 1  # Not incremented

            # Different args - should execute function
            result3 = expensive_function(7)
            assert result3 == 14
            assert call_count == 2

    def test_decorator_with_custom_key_func(self):
        """Test decorator with custom key function."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = APICache(db_path=os.path.join(tmpdir, "test.db"))

            @cached(
                ttl_seconds=60,
                key_func=lambda url: f"api:{url}",
                cache_instance=cache
            )
            def fetch_url(url):
                return f"data from {url}"

            result1 = fetch_url("http://example.com")
            result2 = fetch_url("http://example.com")

            assert result1 == result2

            # Check cache key format
            stats = cache.get_stats()
            assert stats["sets"] == 1

    def test_decorator_respects_ttl(self):
        """Test that decorator respects TTL."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = APICache(db_path=os.path.join(tmpdir, "test.db"))

            call_count = 0

            @cached(ttl_seconds=2, cache_instance=cache)
            def get_timestamp():
                nonlocal call_count
                call_count += 1
                return time.time()

            # First call
            time1 = get_timestamp()
            assert call_count == 1

            # Immediate second call - should use cache
            time2 = get_timestamp()
            assert time1 == time2
            assert call_count == 1

            # Wait for expiration (use 2.5 seconds to be safe)
            time.sleep(2.5)

            # Third call - should re-execute
            time3 = get_timestamp()
            assert time3 > time1
            assert call_count == 2

    def test_decorator_with_multiple_args(self):
        """Test decorator with functions that have multiple arguments."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = APICache(db_path=os.path.join(tmpdir, "test.db"))

            call_count = 0

            @cached(ttl_seconds=60, cache_instance=cache)
            def add(a, b, c=0):
                nonlocal call_count
                call_count += 1
                return a + b + c

            # Different calls
            result1 = add(1, 2)
            result2 = add(1, 2)  # Cache hit
            result3 = add(1, 2, c=3)  # Different args
            result4 = add(1, 2, c=3)  # Cache hit

            assert result1 == 3
            assert result2 == 3
            assert result3 == 6
            assert result4 == 6
            assert call_count == 2  # Only 2 unique calls


class TestCacheKeyGeneration:
    """Test cache key generation."""

    def test_default_key_func_with_simple_args(self):
        """Test default key function with simple arguments."""
        def test_func(a, b):
            pass

        key1 = _default_key_func(test_func, (1, 2), {})
        key2 = _default_key_func(test_func, (1, 2), {})
        key3 = _default_key_func(test_func, (2, 1), {})

        # Same args should produce same key
        assert key1 == key2

        # Different args should produce different key
        assert key1 != key3

        # Key should include function name
        assert "test_func" in key1

    def test_default_key_func_with_kwargs(self):
        """Test default key function with keyword arguments."""
        def test_func(a, b=None):
            pass

        key1 = _default_key_func(test_func, (1,), {"b": 2})
        key2 = _default_key_func(test_func, (1,), {"b": 2})
        key3 = _default_key_func(test_func, (1,), {"b": 3})

        assert key1 == key2
        assert key1 != key3


class TestCacheCleanup:
    """Test automatic cleanup of expired entries."""

    def test_cleanup_removes_expired_entries(self):
        """Test that cleanup removes expired entries."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test.db")

            # Create cache and add entries with short TTL
            cache1 = APICache(db_path=db_path)
            cache1.set("key1", "value1", ttl_seconds=2)
            cache1.set("key2", "value2", ttl_seconds=2)

            assert cache1.get_stats()["total_entries"] == 2

            # Wait for expiration (use 2.5 seconds to be safe)
            time.sleep(2.5)

            # Create new cache instance (triggers cleanup)
            cache2 = APICache(db_path=db_path)

            # Expired entries should be cleaned up
            stats = cache2.get_stats()
            assert stats["expirations"] >= 2


class TestCachePersistence:
    """Test that cache persists across restarts."""

    def test_cache_persists_across_instances(self):
        """Test that cache data persists across cache instances."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test.db")

            # Create cache and set value
            cache1 = APICache(db_path=db_path)
            cache1.set("persistent_key", "persistent_value", ttl_seconds=60)

            # Close first cache (implicit)
            del cache1

            # Create new cache with same database
            cache2 = APICache(db_path=db_path)

            # Value should still exist
            result = cache2.get("persistent_key")
            assert result == "persistent_value"


class TestGlobalCache:
    """Test global cache instance."""

    def test_get_cache_returns_singleton(self):
        """Test that get_cache returns same instance."""
        cache1 = get_cache()
        cache2 = get_cache()

        assert cache1 is cache2


class TestCacheErrorHandling:
    """Test error handling in cache operations."""

    def test_cache_handles_non_serializable_data(self):
        """Test that cache handles non-JSON-serializable data gracefully."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = APICache(db_path=os.path.join(tmpdir, "test.db"))

            # Should not raise error (logs warning instead)
            cache.set("key1", lambda x: x, ttl_seconds=60)

            # Should return None since set failed
            result = cache.get("key1")
            assert result is None

    def test_cache_handles_corrupted_data(self):
        """Test that cache handles corrupted JSON gracefully."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = APICache(db_path=os.path.join(tmpdir, "test.db"))

            # Manually insert corrupted data
            import sqlite3
            with sqlite3.connect(cache.db_path) as conn:
                conn.execute(
                    "INSERT INTO cache (key, value, expires_at, created_at) VALUES (?, ?, ?, ?)",
                    ("corrupted", "{{invalid json}}", int(time.time()) + 60, int(time.time()))
                )
                conn.commit()

            # Should handle gracefully
            result = cache.get("corrupted")
            assert result is None  # Returns None instead of raising


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
