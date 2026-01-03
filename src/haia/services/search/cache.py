"""
Search result caching service.

Provides in-memory LRU cache with TTL expiration and configurable strategies
for different query types (general, version, security).
"""

import asyncio
import logging
import re
from collections import OrderedDict
from datetime import UTC, datetime

from haia.config import search_backend_settings
from haia.models.search import SearchBackendType, SearchCache, SearchResponse
from haia.services.search.base import normalize_query

logger = logging.getLogger(__name__)


class SearchCacheService:
    """
    In-memory search result cache with TTL expiration.

    Features:
    - LRU eviction when cache is full
    - Configurable TTL per query type
    - Thread-safe operations
    - Cache key normalization
    """

    def __init__(
        self,
        max_size: int = 1000,
        default_ttl: int | None = None,
    ):
        """
        Initialize search cache.

        Args:
            max_size: Maximum number of cached queries (LRU eviction)
            default_ttl: Default TTL in seconds (uses config if not provided)
        """
        self.max_size = max_size
        self.default_ttl = default_ttl or search_backend_settings.search_cache_ttl_seconds

        # OrderedDict for LRU cache (move_to_end on access)
        self._cache: OrderedDict[str, SearchCache] = OrderedDict()
        self._lock = asyncio.Lock()

        # TTL strategies for different query patterns
        self._ttl_patterns = {
            r"(latest|newest|current|recent)\s+(version|release)": 3600,  # 1 hour
            r"(cve-|vulnerability|security|exploit|patch)": 300,  # 5 minutes
            r"\d{4}-\d{2}-\d{2}": 3600,  # Date patterns: 1 hour
        }

        logger.info(
            f"SearchCacheService initialized: max_size={max_size}, default_ttl={self.default_ttl}s"
        )

    async def get(
        self,
        query: str,
        backend: SearchBackendType,
    ) -> SearchResponse | None:
        """
        Retrieve cached search result if available and not expired.

        Args:
            query: Search query string
            backend: Backend that generated the result

        Returns:
            Cached SearchResponse or None if not found/expired
        """
        async with self._lock:
            cache_key = self._build_cache_key(query, backend)

            if cache_key not in self._cache:
                logger.debug(f"Cache miss: {cache_key}")
                return None

            cached = self._cache[cache_key]

            # Check expiration
            if cached.is_expired:
                logger.debug(f"Cache expired: {cache_key}")
                del self._cache[cache_key]
                return None

            # Move to end (LRU)
            self._cache.move_to_end(cache_key)

            logger.debug(
                f"Cache hit: {cache_key} (TTL remaining: {cached.remaining_ttl.total_seconds():.0f}s)"
            )
            return cached.response

    async def set(
        self,
        query: str,
        backend: SearchBackendType,
        response: SearchResponse,
    ):
        """
        Store search result in cache with appropriate TTL.

        Args:
            query: Search query string
            backend: Backend that generated the result
            response: Search response to cache
        """
        async with self._lock:
            cache_key = self._build_cache_key(query, backend)

            # Determine TTL based on query pattern
            ttl = self._get_ttl_for_query(query)

            # Create cache entry
            cached = SearchCache(
                query_normalized=normalize_query(query),
                backend=backend,
                response=response,
                cached_at=datetime.now(UTC),
                ttl_seconds=ttl,
            )

            # LRU eviction if cache is full
            if len(self._cache) >= self.max_size and cache_key not in self._cache:
                evicted_key = next(iter(self._cache))
                del self._cache[evicted_key]
                logger.debug(f"Cache eviction (LRU): {evicted_key}")

            # Store and move to end
            self._cache[cache_key] = cached
            self._cache.move_to_end(cache_key)

            logger.debug(f"Cached: {cache_key} (TTL: {ttl}s)")

    async def invalidate(self, query: str, backend: SearchBackendType | None = None):
        """
        Invalidate cached result for a specific query.

        Args:
            query: Search query string
            backend: Specific backend to invalidate (None = all backends)
        """
        async with self._lock:
            if backend:
                cache_key = self._build_cache_key(query, backend)
                if cache_key in self._cache:
                    del self._cache[cache_key]
                    logger.info(f"Invalidated cache: {cache_key}")
            else:
                # Invalidate across all backends
                normalized = normalize_query(query)
                keys_to_delete = [
                    key for key in self._cache if normalized in key
                ]
                for key in keys_to_delete:
                    del self._cache[key]
                    logger.info(f"Invalidated cache: {key}")

    async def clear(self):
        """Clear all cached results."""
        async with self._lock:
            count = len(self._cache)
            self._cache.clear()
            logger.info(f"Cache cleared: {count} entries removed")

    async def get_stats(self) -> dict:
        """
        Get cache statistics.

        Returns:
            Dictionary with cache stats
        """
        async with self._lock:
            total = len(self._cache)
            expired = sum(1 for cached in self._cache.values() if cached.is_expired)
            valid = total - expired

            return {
                "total_entries": total,
                "valid_entries": valid,
                "expired_entries": expired,
                "max_size": self.max_size,
                "utilization": (total / self.max_size) * 100 if self.max_size > 0 else 0,
            }

    def _build_cache_key(self, query: str, backend: SearchBackendType) -> str:
        """
        Build cache key from query and backend.

        Format: search:{normalized_query}:{backend}

        Args:
            query: Search query string
            backend: Backend identifier

        Returns:
            Cache key string
        """
        normalized = normalize_query(query)
        return f"search:{normalized}:{backend.value}"

    def _get_ttl_for_query(self, query: str) -> int:
        """
        Determine appropriate TTL based on query content.

        Checks query against patterns to detect:
        - Version queries: 1 hour TTL
        - Security queries: 5 minutes TTL
        - General queries: 24 hours TTL (default)

        Args:
            query: Search query string

        Returns:
            TTL in seconds
        """
        query_lower = query.lower()

        # Check against pattern-specific TTLs
        for pattern, ttl in self._ttl_patterns.items():
            if re.search(pattern, query_lower):
                logger.debug(f"Query matches pattern '{pattern}', TTL={ttl}s")
                return ttl

        # Default TTL
        return self.default_ttl

    async def cleanup_expired(self):
        """Remove all expired entries from cache (maintenance task)."""
        async with self._lock:
            before_count = len(self._cache)

            # Find expired keys
            expired_keys = [
                key for key, cached in self._cache.items() if cached.is_expired
            ]

            # Remove expired entries
            for key in expired_keys:
                del self._cache[key]

            removed = len(expired_keys)
            if removed > 0:
                logger.info(
                    f"Cache cleanup: removed {removed} expired entries ({before_count} -> {len(self._cache)})"
                )
