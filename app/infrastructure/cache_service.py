"""
Centralized caching service with TTL and LRU eviction.

This replaces the two separate username caches in:
- app/repositories/message_repository.py (class-level cache)
- app/api/ui.py (module-level cache)

Features:
- TTL-based expiration (default: 24 hours)
- LRU eviction when at capacity
- Thread-safe access
- Generic key-value storage
"""

import asyncio
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Dict, Generic, Optional, TypeVar
from collections import OrderedDict
import logging

logger = logging.getLogger(__name__)

T = TypeVar('T')


@dataclass
class CacheEntry(Generic[T]):
    """Cache entry with value and expiration"""
    value: T
    expires_at: datetime

    def is_expired(self) -> bool:
        """Check if entry has expired"""
        return datetime.now(timezone.utc) > self.expires_at


class TTLCache(Generic[T]):
    """
    Time-To-Live cache with LRU eviction.

    Thread-safe cache with automatic expiration and size limits.
    Uses OrderedDict for efficient LRU eviction.
    """

    def __init__(
        self,
        ttl_hours: int = 24,
        max_size: int = 10000,
        name: str = "cache"
    ):
        """
        Initialize cache.

        Args:
            ttl_hours: Time-to-live for entries in hours
            max_size: Maximum number of entries
            name: Cache name for logging
        """
        self._ttl = timedelta(hours=ttl_hours)
        self._max_size = max_size
        self._name = name
        self._cache: OrderedDict[str, CacheEntry[T]] = OrderedDict()
        self._lock = asyncio.Lock()
        self._hits = 0
        self._misses = 0

    async def get(self, key: str) -> Optional[T]:
        """
        Get value from cache.

        Args:
            key: Cache key

        Returns:
            Cached value if present and not expired, None otherwise
        """
        async with self._lock:
            entry = self._cache.get(key)

            if entry is None:
                self._misses += 1
                return None

            if entry.is_expired():
                # Remove expired entry
                del self._cache[key]
                self._misses += 1
                logger.debug(f"{self._name}: Expired key '{key}'")
                return None

            # Move to end (mark as recently used)
            self._cache.move_to_end(key)
            self._hits += 1
            return entry.value

    async def set(self, key: str, value: T) -> None:
        """
        Store value in cache with TTL.

        Args:
            key: Cache key
            value: Value to store
        """
        async with self._lock:
            # Check if at capacity
            if len(self._cache) >= self._max_size and key not in self._cache:
                # Evict oldest entry (LRU)
                oldest_key = next(iter(self._cache))
                del self._cache[oldest_key]
                logger.debug(f"{self._name}: Evicted oldest key '{oldest_key}' (LRU)")

            # Calculate expiration
            expires_at = datetime.now(timezone.utc) + self._ttl

            # Store entry
            self._cache[key] = CacheEntry(value=value, expires_at=expires_at)

            # Move to end (most recently used)
            self._cache.move_to_end(key)

            logger.debug(f"{self._name}: Set key '{key}' (expires in {self._ttl.total_seconds() / 3600:.1f}h)")

    async def delete(self, key: str) -> bool:
        """
        Delete key from cache.

        Args:
            key: Cache key

        Returns:
            True if key was deleted, False if not found
        """
        async with self._lock:
            if key in self._cache:
                del self._cache[key]
                logger.debug(f"{self._name}: Deleted key '{key}'")
                return True
            return False

    async def clear(self) -> None:
        """Clear all entries from cache"""
        async with self._lock:
            count = len(self._cache)
            self._cache.clear()
            self._hits = 0
            self._misses = 0
            logger.info(f"{self._name}: Cleared {count} entries")

    async def cleanup_expired(self) -> int:
        """
        Remove all expired entries.

        Returns:
            Number of entries removed
        """
        async with self._lock:
            expired_keys = [
                key for key, entry in self._cache.items()
                if entry.is_expired()
            ]

            for key in expired_keys:
                del self._cache[key]

            if expired_keys:
                logger.debug(f"{self._name}: Cleaned up {len(expired_keys)} expired entries")

            return len(expired_keys)

    @property
    def size(self) -> int:
        """Get current cache size"""
        return len(self._cache)

    @property
    def hit_rate(self) -> float:
        """
        Get cache hit rate.

        Returns:
            Hit rate as percentage (0-100)
        """
        total = self._hits + self._misses
        if total == 0:
            return 0.0
        return (self._hits / total) * 100

    def get_stats(self) -> Dict:
        """
        Get cache statistics.

        Returns:
            Dictionary with cache stats
        """
        return {
            "name": self._name,
            "size": self.size,
            "max_size": self._max_size,
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate_pct": round(self.hit_rate, 2),
            "ttl_hours": self._ttl.total_seconds() / 3600
        }


# Global username cache (replaces separate caches in repository and UI)
username_cache = TTLCache[str](
    ttl_hours=24,
    max_size=10000,
    name="username_cache"
)


async def get_cached_username(
    user_id: str,
    fetch_func: Optional[callable] = None
) -> Optional[str]:
    """
    Get Instagram username with caching.

    Args:
        user_id: Instagram user ID
        fetch_func: Optional async function to fetch username if not cached

    Returns:
        Username if found (cached or fetched), None otherwise

    Example:
        async def fetch_from_api(user_id):
            return await instagram_client.get_username(user_id)

        username = await get_cached_username(
            user_id="123456",
            fetch_func=fetch_from_api
        )
    """
    # Try cache first
    cached = await username_cache.get(user_id)
    if cached:
        return cached

    # Fetch if function provided
    if fetch_func:
        try:
            username = await fetch_func(user_id)
            if username:
                await username_cache.set(user_id, username)
                return username
        except Exception as e:
            logger.error(f"Failed to fetch username for {user_id}: {e}")

    return None
