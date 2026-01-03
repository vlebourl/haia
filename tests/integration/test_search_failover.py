"""Integration tests for backend failover scenarios."""

import pytest
from datetime import datetime, timedelta, UTC
from unittest.mock import AsyncMock, MagicMock, patch

from haia.models.search import SearchBackendType, SearchRequest, SearchResponse, SearchResult, ContentType
from haia.services.search.base import BackendError, NetworkError, RateLimitError
from haia.services.search.cache import SearchCacheService
from haia.services.search.selector import SearchBackendSelector, BackendHealth


@pytest.fixture
def selector():
    """Create SearchBackendSelector with fresh cache."""
    cache = SearchCacheService(max_size=100, default_ttl=3600)
    return SearchBackendSelector(cache=cache)


@pytest.fixture
def sample_ddg_results():
    """Sample DuckDuckGo results for mocking."""
    return [
        {
            "title": "Fallback Result 1",
            "href": "https://example.com/1",
            "body": "This is from DuckDuckGo fallback",
        },
        {
            "title": "Fallback Result 2",
            "href": "https://example.com/2",
            "body": "Another DuckDuckGo result",
        },
    ]


class TestBraveFailover:
    """Test failover scenarios when Brave backend fails."""

    @pytest.mark.asyncio
    async def test_brave_api_error_failover(self, selector, sample_ddg_results):
        """Test failover when Brave API returns error."""
        request = SearchRequest(query="test query", max_results=5)

        # Mock Brave to fail with API error
        with patch.object(
            selector.backends[SearchBackendType.BRAVE],
            "search",
            side_effect=BackendError("brave", "API authentication failed")
        ):
            # Mock DuckDuckGo to succeed
            with patch.object(
                selector.backends[SearchBackendType.DUCKDUCKGO],
                "_sync_search",
                return_value=sample_ddg_results
            ):
                response = await selector.search(request)

                # Should have failed over to DuckDuckGo
                assert response.backend_used == SearchBackendType.DUCKDUCKGO
                assert len(response.results) > 0
                assert selector.backend_health[SearchBackendType.BRAVE] == BackendHealth.FAILED

    @pytest.mark.asyncio
    async def test_brave_rate_limit_failover(self, selector, sample_ddg_results):
        """Test failover when Brave hits rate limit."""
        request = SearchRequest(query="test query", max_results=5)

        # Mock Brave to return rate limit error
        with patch.object(
            selector.backends[SearchBackendType.BRAVE],
            "search",
            side_effect=RateLimitError("brave", "Rate limit exceeded", retry_after=60)
        ):
            # Mock DuckDuckGo to succeed
            with patch.object(
                selector.backends[SearchBackendType.DUCKDUCKGO],
                "_sync_search",
                return_value=sample_ddg_results
            ):
                response = await selector.search(request)

                # Should have failed over to DuckDuckGo
                assert response.backend_used == SearchBackendType.DUCKDUCKGO
                assert selector.backend_health[SearchBackendType.BRAVE] == BackendHealth.RATE_LIMITED
                # Should track rate limit expiration
                assert SearchBackendType.BRAVE in selector.rate_limit_until

    @pytest.mark.asyncio
    async def test_brave_network_error_failover(self, selector, sample_ddg_results):
        """Test failover when Brave has network connectivity issues."""
        request = SearchRequest(query="test query", max_results=5)

        # Mock Brave to fail with network error
        with patch.object(
            selector.backends[SearchBackendType.BRAVE],
            "search",
            side_effect=NetworkError("brave", "Connection timeout")
        ):
            # Mock DuckDuckGo to succeed
            with patch.object(
                selector.backends[SearchBackendType.DUCKDUCKGO],
                "_sync_search",
                return_value=sample_ddg_results
            ):
                response = await selector.search(request)

                # Should have failed over to DuckDuckGo
                assert response.backend_used == SearchBackendType.DUCKDUCKGO
                assert selector.backend_health[SearchBackendType.BRAVE] == BackendHealth.FAILED


class TestDuckDuckGoFailover:
    """Test scenarios when DuckDuckGo is primary or Brave is unavailable."""

    @pytest.mark.asyncio
    async def test_brave_unavailable_uses_ddg(self, selector, sample_ddg_results):
        """Test that DuckDuckGo is used when Brave is unavailable."""
        # Manually mark Brave as rate-limited
        selector.backend_health[SearchBackendType.BRAVE] = BackendHealth.RATE_LIMITED
        selector.rate_limit_until[SearchBackendType.BRAVE] = datetime.now(UTC) + timedelta(seconds=60)

        request = SearchRequest(query="test query", max_results=5)

        # Mock DuckDuckGo to succeed
        with patch.object(
            selector.backends[SearchBackendType.DUCKDUCKGO],
            "_sync_search",
            return_value=sample_ddg_results
        ):
            response = await selector.search(request)

            # Should use DuckDuckGo without trying Brave
            assert response.backend_used == SearchBackendType.DUCKDUCKGO
            assert len(response.results) > 0

    @pytest.mark.asyncio
    async def test_ddg_preference_bypasses_brave(self, selector, sample_ddg_results):
        """Test that explicit DuckDuckGo preference is honored."""
        request = SearchRequest(
            query="test query",
            max_results=5,
            backend_preference=SearchBackendType.DUCKDUCKGO,
        )

        brave_search_called = False

        def brave_search_mock(*args, **kwargs):
            nonlocal brave_search_called
            brave_search_called = True
            raise Exception("Brave should not be called")

        with patch.object(selector.backends[SearchBackendType.BRAVE], "search", brave_search_mock):
            with patch.object(
                selector.backends[SearchBackendType.DUCKDUCKGO],
                "_sync_search",
                return_value=sample_ddg_results
            ):
                response = await selector.search(request)

                # Should use DuckDuckGo directly
                assert not brave_search_called
                assert response.backend_used == SearchBackendType.DUCKDUCKGO


class TestMultipleFailoverAttempts:
    """Test scenarios requiring multiple failover attempts."""

    @pytest.mark.asyncio
    async def test_all_backends_fail(self, selector):
        """Test that proper error is raised when all backends fail."""
        request = SearchRequest(query="test query", max_results=5)

        # Mock both backends to fail
        with patch.object(
            selector.backends[SearchBackendType.BRAVE],
            "search",
            side_effect=BackendError("brave", "API error")
        ):
            with patch.object(
                selector.backends[SearchBackendType.DUCKDUCKGO],
                "search",
                side_effect=NetworkError("duckduckgo", "Network timeout")
            ):
                with pytest.raises(BackendError) as exc_info:
                    await selector.search(request)

                # Error should mention all backends failed
                error_msg = str(exc_info.value).lower()
                assert "all backends failed" in error_msg

    @pytest.mark.asyncio
    async def test_failover_chain_preserves_errors(self, selector):
        """Test that failover chain preserves error information."""
        request = SearchRequest(query="test query", max_results=5)

        brave_error = BackendError("brave", "Brave specific error")
        ddg_error = NetworkError("duckduckgo", "DuckDuckGo network issue")

        with patch.object(selector.backends[SearchBackendType.BRAVE], "search", side_effect=brave_error):
            with patch.object(selector.backends[SearchBackendType.DUCKDUCKGO], "search", side_effect=ddg_error):
                with pytest.raises(BackendError) as exc_info:
                    await selector.search(request)

                # Both backend errors should be mentioned
                error_msg = str(exc_info.value).lower()
                assert "brave" in error_msg or "duckduckgo" in error_msg


class TestRateLimitRecovery:
    """Test recovery from rate limit scenarios."""

    @pytest.mark.asyncio
    async def test_rate_limit_expires_and_retries(self, selector, sample_ddg_results):
        """Test that backend is retried after rate limit expires."""
        request = SearchRequest(query="test query", max_results=5)

        # Set Brave as rate-limited with expired timeout
        selector.backend_health[SearchBackendType.BRAVE] = BackendHealth.RATE_LIMITED
        selector.rate_limit_until[SearchBackendType.BRAVE] = datetime.now(UTC) - timedelta(seconds=1)

        # Mock Brave to succeed (rate limit has expired)
        brave_response = SearchResponse(
            query="test query",
            backend_used=SearchBackendType.BRAVE,
            results=[
                SearchResult(
                    title="Brave Result",
                    url="https://brave.com",
                    snippet="From Brave",
                    domain="brave.com",
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

        with patch.object(selector.backends[SearchBackendType.BRAVE], "search", return_value=brave_response):
            response = await selector.search(request)

            # Should retry Brave since rate limit expired
            assert response.backend_used == SearchBackendType.BRAVE
            # Health should be restored to active
            assert selector.backend_health[SearchBackendType.BRAVE] == BackendHealth.ACTIVE
            # Rate limit entry should be cleared
            assert SearchBackendType.BRAVE not in selector.rate_limit_until

    @pytest.mark.asyncio
    async def test_rate_limit_not_expired_skips_backend(self, selector, sample_ddg_results):
        """Test that rate-limited backend is skipped if timeout not expired."""
        request = SearchRequest(query="test query", max_results=5)

        # Set Brave as rate-limited with future timeout
        selector.backend_health[SearchBackendType.BRAVE] = BackendHealth.RATE_LIMITED
        selector.rate_limit_until[SearchBackendType.BRAVE] = datetime.now(UTC) + timedelta(seconds=60)

        brave_called = False

        def brave_mock(*args, **kwargs):
            nonlocal brave_called
            brave_called = True

        with patch.object(selector.backends[SearchBackendType.BRAVE], "search", brave_mock):
            with patch.object(
                selector.backends[SearchBackendType.DUCKDUCKGO],
                "_sync_search",
                return_value=sample_ddg_results
            ):
                response = await selector.search(request)

                # Brave should not be called (still rate limited)
                assert not brave_called
                assert response.backend_used == SearchBackendType.DUCKDUCKGO


class TestBackendHealthTracking:
    """Test backend health status tracking during failover."""

    @pytest.mark.asyncio
    async def test_failed_backend_marked_unhealthy(self, selector, sample_ddg_results):
        """Test that failed backend is marked as unhealthy."""
        request = SearchRequest(query="test query", max_results=5)

        # Initially both backends are active
        assert selector.backend_health[SearchBackendType.BRAVE] == BackendHealth.ACTIVE
        assert selector.backend_health[SearchBackendType.DUCKDUCKGO] == BackendHealth.ACTIVE

        with patch.object(
            selector.backends[SearchBackendType.BRAVE],
            "search",
            side_effect=BackendError("brave", "API error")
        ):
            with patch.object(
                selector.backends[SearchBackendType.DUCKDUCKGO],
                "_sync_search",
                return_value=sample_ddg_results
            ):
                await selector.search(request)

                # Brave should be marked as failed
                assert selector.backend_health[SearchBackendType.BRAVE] == BackendHealth.FAILED
                # DuckDuckGo should remain active
                assert selector.backend_health[SearchBackendType.DUCKDUCKGO] == BackendHealth.ACTIVE

    @pytest.mark.asyncio
    async def test_successful_backend_marked_healthy(self, selector, sample_ddg_results):
        """Test that successful backend is marked as healthy."""
        request = SearchRequest(query="test query", max_results=5)

        # Mark Brave as failed initially
        selector.backend_health[SearchBackendType.BRAVE] = BackendHealth.FAILED

        # Mock Brave to succeed
        brave_response = SearchResponse(
            query="test query",
            backend_used=SearchBackendType.BRAVE,
            results=[
                SearchResult(
                    title="Test",
                    url="https://test.com",
                    snippet="Test",
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

        with patch.object(selector.backends[SearchBackendType.BRAVE], "search", return_value=brave_response):
            await selector.search(request)

            # Brave should be restored to active
            assert selector.backend_health[SearchBackendType.BRAVE] == BackendHealth.ACTIVE

    @pytest.mark.asyncio
    async def test_health_status_query(self, selector):
        """Test querying backend health status."""
        # Set up mixed health states
        selector.backend_health[SearchBackendType.BRAVE] = BackendHealth.RATE_LIMITED
        selector.backend_health[SearchBackendType.DUCKDUCKGO] = BackendHealth.ACTIVE

        health = await selector.get_health_status()

        assert health[SearchBackendType.BRAVE.value] == BackendHealth.RATE_LIMITED.value
        assert health[SearchBackendType.DUCKDUCKGO.value] == BackendHealth.ACTIVE.value
