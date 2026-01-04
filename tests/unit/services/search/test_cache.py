"""Unit tests for SearchCacheService."""

import pytest
import asyncio
from datetime import datetime, timedelta, UTC

from haia.models.search import SearchBackendType, SearchResponse, SearchResult, ContentType
from haia.services.search.cache import SearchCacheService


@pytest.fixture
def cache_service():
    """Create SearchCacheService with short default TTL for testing."""
    return SearchCacheService(max_size=5, default_ttl=10)


@pytest.fixture
def sample_response():
    """Create sample SearchResponse for testing."""
    return SearchResponse(
        query="test query",
        backend_used=SearchBackendType.BRAVE,
        results=[
            SearchResult(
                title="Test Result",
                url="https://test.com",
                snippet="Test snippet",
                domain="test.com",
                published_date=None,
                relevance_score=0.8,
                backend_score=0.7,
                content_type=ContentType.DOCUMENTATION,
            )
        ],
        total_results=1,
        execution_time_ms=100.0,
        from_cache=False,
        cache_key=None,
    )


class TestSearchCacheService:
    """Test suite for SearchCacheService."""

    @pytest.mark.asyncio
    async def test_cache_set_and_get(self, cache_service, sample_response):
        """Test basic cache set and get operations."""
        query = "test query"
        backend = SearchBackendType.BRAVE

        # Set cache
        await cache_service.set(query, backend, sample_response)

        # Get from cache
        cached = await cache_service.get(query, backend)

        assert cached is not None
        assert cached.query == sample_response.query
        assert cached.backend_used == sample_response.backend_used
        assert len(cached.results) == 1
        assert cached.results[0].title == "Test Result"

    @pytest.mark.asyncio
    async def test_cache_miss(self, cache_service):
        """Test cache miss returns None."""
        cached = await cache_service.get("nonexistent query", SearchBackendType.BRAVE)

        assert cached is None

    @pytest.mark.asyncio
    async def test_cache_expiration(self, cache_service, sample_response):
        """Test that expired entries are automatically removed."""
        query = "test query"
        backend = SearchBackendType.BRAVE

        # Create cache service with very short TTL
        short_ttl_cache = SearchCacheService(max_size=10, default_ttl=1)

        # Set cache
        await short_ttl_cache.set(query, backend, sample_response)

        # Verify it's cached
        cached = await short_ttl_cache.get(query, backend)
        assert cached is not None

        # Wait for expiration
        await asyncio.sleep(1.5)

        # Should be expired now
        cached = await short_ttl_cache.get(query, backend)
        assert cached is None

    @pytest.mark.asyncio
    async def test_lru_eviction(self, cache_service, sample_response):
        """Test LRU eviction when cache is full."""
        # Cache has max_size=5
        for i in range(6):
            query = f"query {i}"
            await cache_service.set(query, SearchBackendType.BRAVE, sample_response)

        # First query should be evicted
        cached = await cache_service.get("query 0", SearchBackendType.BRAVE)
        assert cached is None

        # Last 5 queries should still be cached
        for i in range(1, 6):
            cached = await cache_service.get(f"query {i}", SearchBackendType.BRAVE)
            assert cached is not None

    @pytest.mark.asyncio
    async def test_lru_access_updates_order(self, cache_service, sample_response):
        """Test that accessing an entry moves it to the end (most recent)."""
        # Fill cache to capacity
        for i in range(5):
            query = f"query {i}"
            await cache_service.set(query, SearchBackendType.BRAVE, sample_response)

        # Access query 0 (should move to end)
        await cache_service.get("query 0", SearchBackendType.BRAVE)

        # Add new query (should evict query 1, not query 0)
        await cache_service.set("query 5", SearchBackendType.BRAVE, sample_response)

        # query 0 should still be cached
        cached = await cache_service.get("query 0", SearchBackendType.BRAVE)
        assert cached is not None

        # query 1 should be evicted
        cached = await cache_service.get("query 1", SearchBackendType.BRAVE)
        assert cached is None

    @pytest.mark.asyncio
    async def test_different_backends_separate_cache(self, cache_service, sample_response):
        """Test that different backends have separate cache entries."""
        query = "test query"

        # Set same query for two different backends
        await cache_service.set(query, SearchBackendType.BRAVE, sample_response)

        response_ddg = SearchResponse(
            query=query,
            backend_used=SearchBackendType.DUCKDUCKGO,
            results=[],
            total_results=0,
            execution_time_ms=50.0,
            from_cache=False,
            cache_key=None,
        )
        await cache_service.set(query, SearchBackendType.DUCKDUCKGO, response_ddg)

        # Get should return correct backend response
        cached_brave = await cache_service.get(query, SearchBackendType.BRAVE)
        assert cached_brave.backend_used == SearchBackendType.BRAVE

        cached_ddg = await cache_service.get(query, SearchBackendType.DUCKDUCKGO)
        assert cached_ddg.backend_used == SearchBackendType.DUCKDUCKGO

    @pytest.mark.asyncio
    async def test_ttl_pattern_version_query(self, cache_service, sample_response):
        """Test that version queries get shorter TTL (1 hour)."""
        query = "latest version of Proxmox"

        await cache_service.set(query, SearchBackendType.BRAVE, sample_response)

        # Check that TTL was set to 3600 seconds (1 hour)
        cache_key = cache_service._build_cache_key(query, SearchBackendType.BRAVE)
        cached_entry = cache_service._cache[cache_key]

        assert cached_entry.ttl_seconds == 3600

    @pytest.mark.asyncio
    async def test_ttl_pattern_security_query(self, cache_service, sample_response):
        """Test that security queries get very short TTL (5 minutes)."""
        query = "CVE-2024-1234 vulnerability fix"

        await cache_service.set(query, SearchBackendType.BRAVE, sample_response)

        # Check that TTL was set to 300 seconds (5 minutes)
        cache_key = cache_service._build_cache_key(query, SearchBackendType.BRAVE)
        cached_entry = cache_service._cache[cache_key]

        assert cached_entry.ttl_seconds == 300

    @pytest.mark.asyncio
    async def test_ttl_pattern_general_query(self, cache_service, sample_response):
        """Test that general queries get default TTL."""
        query = "how to configure docker"

        await cache_service.set(query, SearchBackendType.BRAVE, sample_response)

        # Check that TTL was set to default (10 seconds in our test fixture)
        cache_key = cache_service._build_cache_key(query, SearchBackendType.BRAVE)
        cached_entry = cache_service._cache[cache_key]

        assert cached_entry.ttl_seconds == 10

    @pytest.mark.asyncio
    async def test_invalidate_specific_backend(self, cache_service, sample_response):
        """Test invalidating cache for specific backend."""
        query = "test query"

        # Set cache for two backends
        await cache_service.set(query, SearchBackendType.BRAVE, sample_response)
        await cache_service.set(query, SearchBackendType.DUCKDUCKGO, sample_response)

        # Invalidate only Brave backend
        await cache_service.invalidate(query, SearchBackendType.BRAVE)

        # Brave should be invalidated
        cached_brave = await cache_service.get(query, SearchBackendType.BRAVE)
        assert cached_brave is None

        # DuckDuckGo should still be cached
        cached_ddg = await cache_service.get(query, SearchBackendType.DUCKDUCKGO)
        assert cached_ddg is not None

    @pytest.mark.asyncio
    async def test_invalidate_all_backends(self, cache_service, sample_response):
        """Test invalidating cache for all backends."""
        query = "test query"

        # Set cache for two backends
        await cache_service.set(query, SearchBackendType.BRAVE, sample_response)
        await cache_service.set(query, SearchBackendType.DUCKDUCKGO, sample_response)

        # Invalidate all backends
        await cache_service.invalidate(query, backend=None)

        # Both should be invalidated
        cached_brave = await cache_service.get(query, SearchBackendType.BRAVE)
        assert cached_brave is None

        cached_ddg = await cache_service.get(query, SearchBackendType.DUCKDUCKGO)
        assert cached_ddg is None

    @pytest.mark.asyncio
    async def test_clear_cache(self, cache_service, sample_response):
        """Test clearing entire cache."""
        # Add multiple entries
        for i in range(3):
            await cache_service.set(f"query {i}", SearchBackendType.BRAVE, sample_response)

        # Clear cache
        await cache_service.clear()

        # All entries should be gone
        for i in range(3):
            cached = await cache_service.get(f"query {i}", SearchBackendType.BRAVE)
            assert cached is None

    @pytest.mark.asyncio
    async def test_get_stats(self, cache_service, sample_response):
        """Test cache statistics."""
        # Add some entries
        await cache_service.set("query 1", SearchBackendType.BRAVE, sample_response)
        await cache_service.set("query 2", SearchBackendType.BRAVE, sample_response)

        stats = await cache_service.get_stats()

        assert stats["total_entries"] == 2
        assert stats["valid_entries"] == 2
        assert stats["expired_entries"] == 0
        assert stats["max_size"] == 5
        assert stats["utilization"] == 40.0  # 2/5 = 40%

    @pytest.mark.asyncio
    async def test_cleanup_expired(self, cache_service, sample_response):
        """Test manual cleanup of expired entries."""
        # Create cache with very short TTL
        short_ttl_cache = SearchCacheService(max_size=10, default_ttl=1)

        # Add entries
        await short_ttl_cache.set("query 1", SearchBackendType.BRAVE, sample_response)
        await short_ttl_cache.set("query 2", SearchBackendType.BRAVE, sample_response)

        # Wait for expiration
        await asyncio.sleep(1.5)

        # Add a fresh entry
        await short_ttl_cache.set("query 3", SearchBackendType.BRAVE, sample_response)

        # Run cleanup
        await short_ttl_cache.cleanup_expired()

        # Expired entries should be removed
        stats = await short_ttl_cache.get_stats()
        assert stats["total_entries"] == 1  # Only query 3 remains
        assert stats["valid_entries"] == 1

    @pytest.mark.asyncio
    async def test_cache_key_normalization(self, cache_service, sample_response):
        """Test that cache keys are normalized (case-insensitive, whitespace trimmed)."""
        # Set with one variation
        await cache_service.set("  Test Query  ", SearchBackendType.BRAVE, sample_response)

        # Get with different variation should hit cache
        cached = await cache_service.get("test query", SearchBackendType.BRAVE)
        assert cached is not None

        # Another variation
        cached = await cache_service.get("TEST  QUERY", SearchBackendType.BRAVE)
        assert cached is not None

    @pytest.mark.asyncio
    async def test_concurrent_access(self, cache_service, sample_response):
        """Test thread-safe concurrent access."""
        query = "concurrent query"
        backend = SearchBackendType.BRAVE

        # Set cache
        await cache_service.set(query, backend, sample_response)

        # Concurrent reads
        tasks = [cache_service.get(query, backend) for _ in range(10)]
        results = await asyncio.gather(*tasks)

        # All should succeed
        assert all(r is not None for r in results)
        # Cached responses have the original query from sample_response
        assert all(r.query == sample_response.query for r in results)
