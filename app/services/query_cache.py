"""
Query Result Cache

Simple in-memory cache for observability query results.
Reduces load on backends by caching recent query results.
"""

from typing import Dict, Optional, Any
from datetime import datetime, timedelta
from pydantic import BaseModel
import hashlib
import json
import logging

logger = logging.getLogger(__name__)


class CacheEntry(BaseModel):
    """A cached query result"""
    key: str
    result: Any
    created_at: datetime
    expires_at: datetime
    hit_count: int = 0


class QueryCache:
    """
    In-memory cache for observability query results.

    Features:
    - TTL-based expiration
    - LRU-style eviction when cache is full
    - Cache hit/miss tracking
    """

    def __init__(self, max_size: int = 1000, default_ttl_seconds: int = 300):
        """
        Initialize query cache.

        Args:
            max_size: Maximum number of entries to cache
            default_ttl_seconds: Default TTL in seconds (5 minutes)
        """
        self.max_size = max_size
        self.default_ttl = timedelta(seconds=default_ttl_seconds)
        self._cache: Dict[str, CacheEntry] = {}
        self._hits = 0
        self._misses = 0

    def get(self, query: str, app_context: Optional[Dict[str, Any]] = None) -> Optional[Any]:
        """
        Get cached result for a query.

        Args:
            query: Natural language query
            app_context: Optional application context

        Returns:
            Cached result or None if not found/expired
        """
        key = self._generate_key(query, app_context)

        # Check if key exists
        if key not in self._cache:
            self._misses += 1
            logger.debug(f"Cache miss for query: {query}")
            return None

        entry = self._cache[key]

        # Check if expired
        if datetime.now() > entry.expires_at:
            del self._cache[key]
            self._misses += 1
            logger.debug(f"Cache expired for query: {query}")
            return None

        # Cache hit
        entry.hit_count += 1
        self._hits += 1
        logger.debug(f"Cache hit for query: {query} (hits: {entry.hit_count})")

        return entry.result

    def set(
        self,
        query: str,
        result: Any,
        app_context: Optional[Dict[str, Any]] = None,
        ttl: Optional[timedelta] = None
    ):
        """
        Cache a query result.

        Args:
            query: Natural language query
            result: Query result to cache
            app_context: Optional application context
            ttl: Optional TTL override
        """
        key = self._generate_key(query, app_context)

        # Evict oldest entry if cache is full
        if len(self._cache) >= self.max_size:
            self._evict_lru()

        # Create cache entry
        ttl = ttl or self.default_ttl
        entry = CacheEntry(
            key=key,
            result=result,
            created_at=datetime.now(),
            expires_at=datetime.now() + ttl
        )

        self._cache[key] = entry
        logger.debug(f"Cached result for query: {query} (TTL: {ttl.total_seconds()}s)")

    def invalidate(self, query: str, app_context: Optional[Dict[str, Any]] = None):
        """
        Invalidate a cached query.

        Args:
            query: Natural language query
            app_context: Optional application context
        """
        key = self._generate_key(query, app_context)

        if key in self._cache:
            del self._cache[key]
            logger.debug(f"Invalidated cache for query: {query}")

    def clear(self):
        """Clear all cached entries."""
        count = len(self._cache)
        self._cache.clear()
        self._hits = 0
        self._misses = 0
        logger.info(f"Cleared cache ({count} entries)")

    def get_stats(self) -> Dict[str, Any]:
        """
        Get cache statistics.

        Returns:
            Dictionary with cache stats
        """
        total_requests = self._hits + self._misses
        hit_rate = (self._hits / total_requests * 100) if total_requests > 0 else 0

        return {
            "size": len(self._cache),
            "max_size": self.max_size,
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate_pct": round(hit_rate, 2),
            "total_requests": total_requests
        }

    def _generate_key(self, query: str, app_context: Optional[Dict[str, Any]] = None) -> str:
        """Generate cache key from query and context."""
        # Normalize query (lowercase, strip whitespace)
        normalized_query = query.lower().strip()

        # Include app context in key if provided
        context_str = ""
        if app_context:
            # Sort keys for consistent hashing
            context_str = json.dumps(app_context, sort_keys=True)

        # Create hash
        combined = f"{normalized_query}:{context_str}"
        return hashlib.sha256(combined.encode()).hexdigest()

    def _evict_lru(self):
        """Evict least recently used entry."""
        if not self._cache:
            return

        # Find entry with lowest hit count and oldest created_at
        lru_key = min(
            self._cache.keys(),
            key=lambda k: (self._cache[k].hit_count, self._cache[k].created_at)
        )

        logger.debug(f"Evicting LRU entry: {lru_key}")
        del self._cache[lru_key]


# Global cache instance
_query_cache: Optional[QueryCache] = None


def get_query_cache() -> QueryCache:
    """
    Get global query cache instance.

    Returns:
        Singleton QueryCache instance
    """
    global _query_cache
    if _query_cache is None:
        _query_cache = QueryCache()
    return _query_cache
