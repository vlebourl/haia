"""Integration tests for end-to-end search functionality."""

import pytest
import os
from unittest.mock import patch

from haia.models.search import SearchBackendType, SearchRequest
from haia.services.search.brave import BraveSearchClient
from haia.services.search.duckduckgo import DuckDuckGoClient
from haia.services.search.cache import SearchCacheService
from haia.services.search.selector import SearchBackendSelector


# Skip integration tests if API keys not available or in CI
skip_if_no_brave_key = pytest.mark.skipif(
    not os.getenv("SEARCH_BRAVE_API_KEY"),
    reason="Brave API key not available (set SEARCH_BRAVE_API_KEY to run this test)"
)

skip_in_ci = pytest.mark.skipif(
    os.getenv("CI") == "true",
    reason="Skipping live API tests in CI environment"
)


@pytest.fixture
def cache_service():
    """Create fresh cache service for each test."""
    return SearchCacheService(max_size=100, default_ttl=3600)


@pytest.fixture
def selector(cache_service):
    """Create SearchBackendSelector with fresh cache."""
    return SearchBackendSelector(cache=cache_service)


class TestBraveIntegration:
    """Integration tests for Brave Search backend."""

    @skip_if_no_brave_key
    @skip_in_ci
    @pytest.mark.asyncio
    async def test_brave_search_live(self):
        """Test live Brave search with real API."""
        client = BraveSearchClient()
        request = SearchRequest(
            query="Proxmox VE documentation",
            max_results=5,
        )

        response = await client.search(request)

        # Verify response structure
        assert response.backend_used == SearchBackendType.BRAVE
        assert response.query == request.query
        assert len(response.results) > 0
        assert response.total_results > 0
        assert response.execution_time_ms > 0
        assert not response.from_cache

        # Verify result structure
        first_result = response.results[0]
        assert first_result.title
        assert first_result.url.startswith("http")
        assert first_result.snippet
        assert first_result.domain
        assert 0.0 <= first_result.relevance_score <= 1.0

    @skip_if_no_brave_key
    @skip_in_ci
    @pytest.mark.asyncio
    async def test_brave_health_check_live(self):
        """Test Brave health check with real API."""
        client = BraveSearchClient()

        is_healthy = await client.health_check()

        assert is_healthy is True


class TestDuckDuckGoIntegration:
    """Integration tests for DuckDuckGo backend."""

    @skip_in_ci
    @pytest.mark.asyncio
    async def test_duckduckgo_search_live(self):
        """Test live DuckDuckGo search (no API key required)."""
        client = DuckDuckGoClient()
        request = SearchRequest(
            query="Docker documentation",
            max_results=5,
        )

        response = await client.search(request)

        # Verify response structure
        assert response.backend_used == SearchBackendType.DUCKDUCKGO
        assert response.query == request.query
        assert len(response.results) > 0
        assert response.total_results > 0
        assert response.execution_time_ms > 0
        assert not response.from_cache

        # Verify result structure
        first_result = response.results[0]
        assert first_result.title
        assert first_result.url.startswith("http")
        assert first_result.snippet
        assert first_result.domain
        assert 0.0 <= first_result.relevance_score <= 1.0

    @skip_in_ci
    @pytest.mark.asyncio
    async def test_duckduckgo_health_check_live(self):
        """Test DuckDuckGo health check."""
        client = DuckDuckGoClient()

        is_healthy = await client.health_check()

        assert is_healthy is True


class TestBackendFailoverIntegration:
    """Integration tests for automatic backend failover."""

    @pytest.mark.asyncio
    async def test_failover_brave_to_duckduckgo(self, selector):
        """Test automatic failover from Brave to DuckDuckGo on Brave failure."""
        request = SearchRequest(
            query="Docker containers",
            max_results=5,
        )

        # Mock Brave to fail, let DuckDuckGo work
        with patch.object(
            selector.backends[SearchBackendType.BRAVE],
            "search",
            side_effect=Exception("Brave API error")
        ):
            # DuckDuckGo should work (using real implementation)
            with patch("haia.services.search.duckduckgo.DDGS") as mock_ddgs_class:
                # Mock DDGS to return sample data
                from unittest.mock import MagicMock
                mock_ddgs = MagicMock()
                mock_ddgs_class.return_value.__enter__.return_value = mock_ddgs
                mock_ddgs.text.return_value = [
                    {
                        "title": "Docker Documentation",
                        "href": "https://docs.docker.com",
                        "body": "Official Docker documentation",
                    }
                ]

                response = await selector.search(request)

                # Should have failed over to DuckDuckGo
                assert response.backend_used == SearchBackendType.DUCKDUCKGO
                assert len(response.results) > 0

    @pytest.mark.asyncio
    async def test_failover_preserves_backend_health(self, selector):
        """Test that failover updates backend health tracking."""
        request = SearchRequest(query="test query", max_results=5)

        # Both backends work initially
        from haia.services.search.selector import BackendHealth
        assert selector.backend_health[SearchBackendType.BRAVE] == BackendHealth.ACTIVE
        assert selector.backend_health[SearchBackendType.DUCKDUCKGO] == BackendHealth.ACTIVE

        # Make Brave fail
        with patch.object(
            selector.backends[SearchBackendType.BRAVE],
            "search",
            side_effect=Exception("Brave failure")
        ):
            # Mock DuckDuckGo to succeed
            with patch("haia.services.search.duckduckgo.DDGS") as mock_ddgs_class:
                mock_ddgs = MagicMock()
                mock_ddgs_class.return_value.__enter__.return_value = mock_ddgs
                mock_ddgs.text.return_value = [
                    {"title": "Test", "href": "https://test.com", "body": "Test"}
                ]

                await selector.search(request)

                # Brave should be marked as failed
                assert selector.backend_health[SearchBackendType.BRAVE] == BackendHealth.FAILED
                # DuckDuckGo should still be active
                assert selector.backend_health[SearchBackendType.DUCKDUCKGO] == BackendHealth.ACTIVE


class TestCacheIntegration:
    """Integration tests for cache hit/miss behavior."""

    @pytest.mark.asyncio
    async def test_cache_miss_then_hit(self, selector):
        """Test cache miss on first request, hit on second."""
        request = SearchRequest(
            query="Kubernetes documentation",
            max_results=5,
        )

        # Mock DuckDuckGo to succeed
        with patch("haia.services.search.duckduckgo.DDGS") as mock_ddgs_class:
            from unittest.mock import MagicMock
            mock_ddgs = MagicMock()
            mock_ddgs_class.return_value.__enter__.return_value = mock_ddgs
            mock_ddgs.text.return_value = [
                {
                    "title": "Kubernetes Docs",
                    "href": "https://kubernetes.io/docs/",
                    "body": "Official Kubernetes documentation",
                }
            ]

            # First request - cache miss
            response1 = await selector.search(request)
            assert not response1.from_cache
            assert response1.backend_used in [SearchBackendType.BRAVE, SearchBackendType.DUCKDUCKGO]

            # Second request - should hit cache
            response2 = await selector.search(request)
            assert response2.from_cache
            assert response2.query == request.query
            assert len(response2.results) == len(response1.results)

    @pytest.mark.asyncio
    async def test_cache_different_backends_separate(self, selector):
        """Test that different backends maintain separate cache entries."""
        request = SearchRequest(
            query="Docker containers",
            max_results=5,
        )

        # Mock both backends
        with patch("haia.services.search.duckduckgo.DDGS") as mock_ddgs_class:
            from unittest.mock import MagicMock, AsyncMock

            # Mock DuckDuckGo
            mock_ddgs = MagicMock()
            mock_ddgs_class.return_value.__enter__.return_value = mock_ddgs
            mock_ddgs.text.return_value = [
                {"title": "DDG Result", "href": "https://ddg.com", "body": "From DDG"}
            ]

            # Mock Brave
            brave_response = MagicMock()
            brave_response.status_code = 200
            brave_response.json.return_value = {
                "web": {
                    "results": [
                        {
                            "title": "Brave Result",
                            "url": "https://brave.com",
                            "description": "From Brave",
                        }
                    ]
                }
            }

            with patch("httpx.AsyncClient") as mock_client_class:
                mock_client = AsyncMock()
                mock_client_class.return_value.__aenter__.return_value = mock_client
                mock_client.get.return_value = brave_response

                # Request with Brave preference
                request_brave = SearchRequest(
                    query="Docker containers",
                    max_results=5,
                    backend_preference=SearchBackendType.BRAVE,
                )
                response_brave = await selector.search(request_brave)

            # Request with DuckDuckGo preference
            request_ddg = SearchRequest(
                query="Docker containers",
                max_results=5,
                backend_preference=SearchBackendType.DUCKDUCKGO,
            )
            response_ddg = await selector.search(request_ddg)

            # Responses should be different (from different backends)
            assert response_brave.backend_used == SearchBackendType.BRAVE
            assert response_ddg.backend_used == SearchBackendType.DUCKDUCKGO

    @pytest.mark.asyncio
    async def test_cache_bypass_when_disabled(self, selector):
        """Test that cache is bypassed when use_cache=False."""
        request = SearchRequest(
            query="Home Assistant",
            max_results=5,
            use_cache=False,  # Disable cache
        )

        # Mock DuckDuckGo
        with patch("haia.services.search.duckduckgo.DDGS") as mock_ddgs_class:
            from unittest.mock import MagicMock
            mock_ddgs = MagicMock()
            mock_ddgs_class.return_value.__enter__.return_value = mock_ddgs
            mock_ddgs.text.return_value = [
                {"title": "HA Docs", "href": "https://home-assistant.io", "body": "HA docs"}
            ]

            # First request
            response1 = await selector.search(request)
            assert not response1.from_cache

            # Second request - should still not use cache
            response2 = await selector.search(request)
            assert not response2.from_cache

    @pytest.mark.asyncio
    async def test_cache_stores_processed_results(self, selector):
        """Test that cache stores results after processing (scoring, ranking)."""
        request = SearchRequest(
            query="Proxmox VE",
            max_results=10,
        )

        # Mock DuckDuckGo
        with patch("haia.services.search.duckduckgo.DDGS") as mock_ddgs_class:
            from unittest.mock import MagicMock
            mock_ddgs = MagicMock()
            mock_ddgs_class.return_value.__enter__.return_value = mock_ddgs
            mock_ddgs.text.return_value = [
                {
                    "title": "Proxmox VE Documentation",
                    "href": "https://pve.proxmox.com/pve-docs/",
                    "body": "Official Proxmox documentation",
                },
                {
                    "title": "Proxmox Forum",
                    "href": "https://forum.proxmox.com",
                    "body": "Community forum",
                },
            ]

            # First request - results should be processed (scored, ranked)
            response1 = await selector.search(request)
            assert all(r.relevance_score > 0.0 for r in response1.results)

            # Second request from cache - should have same processed results
            response2 = await selector.search(request)
            assert response2.from_cache
            assert len(response2.results) == len(response1.results)
            # Cached results should preserve relevance scores
            for i in range(len(response1.results)):
                assert response2.results[i].relevance_score == response1.results[i].relevance_score


class TestEndToEndSearch:
    """End-to-end integration tests for complete search workflow."""

    @skip_in_ci
    @pytest.mark.asyncio
    async def test_e2e_search_with_selector(self, selector):
        """Test complete search workflow with backend selection and caching."""
        request = SearchRequest(
            query="latest version of Proxmox VE",
            max_results=5,
        )

        # Mock DuckDuckGo (free, always available)
        with patch("haia.services.search.duckduckgo.DDGS") as mock_ddgs_class:
            from unittest.mock import MagicMock
            mock_ddgs = MagicMock()
            mock_ddgs_class.return_value.__enter__.return_value = mock_ddgs
            mock_ddgs.text.return_value = [
                {
                    "title": "Proxmox VE 8.1 Released",
                    "href": "https://www.proxmox.com/en/news/proxmox-ve-8-1",
                    "body": "Latest version of Proxmox VE is 8.1",
                },
                {
                    "title": "Proxmox VE Downloads",
                    "href": "https://www.proxmox.com/en/downloads",
                    "body": "Download Proxmox VE",
                },
            ]

            # Execute search
            response = await selector.search(request)

            # Verify complete workflow
            assert response.query == request.query
            assert response.backend_used in [SearchBackendType.BRAVE, SearchBackendType.DUCKDUCKGO]
            assert len(response.results) > 0
            assert response.execution_time_ms > 0

            # Verify result processing
            for result in response.results:
                assert result.title
                assert result.url.startswith("http")
                assert result.domain
                assert 0.0 <= result.relevance_score <= 1.0
                assert result.content_type

            # Verify results are ranked by relevance
            scores = [r.relevance_score for r in response.results]
            assert scores == sorted(scores, reverse=True)


class TestDocumentationDiscoveryIntegration:
    """Integration tests for User Story 2 - Documentation Discovery (US2 - T058)."""

    @pytest.mark.asyncio
    async def test_documentation_query_with_domain_filtering(self, selector):
        """Test documentation query applies domain whitelist automatically."""
        request = SearchRequest(
            query="Proxmox VE storage configuration documentation",
            max_results=5,
            allowed_domains=["proxmox.com", "pve.proxmox.com"],
        )

        # Mock DuckDuckGo to return mixed results
        with patch("haia.services.search.duckduckgo.DDGS") as mock_ddgs_class:
            from unittest.mock import MagicMock
            mock_ddgs = MagicMock()
            mock_ddgs_class.return_value.__enter__.return_value = mock_ddgs
            mock_ddgs.text.return_value = [
                {
                    "title": "Proxmox VE Storage Documentation",
                    "href": "https://pve.proxmox.com/pve-docs/chapter-pvesm.html",
                    "body": "Official Proxmox storage documentation",
                },
                {
                    "title": "Random Blog About Proxmox",
                    "href": "https://randomblog.com/proxmox-storage",
                    "body": "My experience with Proxmox storage",
                },
                {
                    "title": "Proxmox Community Forum",
                    "href": "https://forum.proxmox.com/threads/storage",
                    "body": "Forum discussion about storage",
                },
            ]

            response = await selector.search(request)

            # Should only return results from allowed domains
            assert len(response.results) > 0
            for result in response.results:
                assert any(domain in result.domain for domain in ["proxmox.com", "pve.proxmox.com"])

    @pytest.mark.asyncio
    async def test_documentation_scoring_prioritizes_official_docs(self, selector):
        """Test that official documentation ranks higher than other content."""
        request = SearchRequest(
            query="Docker container networking",
            max_results=10,
        )

        # Mock DuckDuckGo to return mixed content types
        with patch("haia.services.search.duckduckgo.DDGS") as mock_ddgs_class:
            from unittest.mock import MagicMock
            mock_ddgs = MagicMock()
            mock_ddgs_class.return_value.__enter__.return_value = mock_ddgs
            mock_ddgs.text.return_value = [
                {
                    "title": "Docker Networking Guide",
                    "href": "https://docs.docker.com/network/",
                    "body": "Official Docker networking documentation",
                },
                {
                    "title": "Blog: Docker Networking Tips",
                    "href": "https://techblog.com/docker-networking",
                    "body": "Tips and tricks for Docker networking",
                },
                {
                    "title": "Stack Overflow: Docker Network Question",
                    "href": "https://stackoverflow.com/questions/123/docker-network",
                    "body": "How to configure Docker networks?",
                },
            ]

            response = await selector.search(request)

            # Official docs should rank first
            assert len(response.results) >= 1
            # First result should be from official docs domain
            first_result = response.results[0]
            assert "docs.docker.com" in first_result.url or "docker.com" in first_result.domain

    @pytest.mark.asyncio
    async def test_documentation_query_filters_low_relevance_results(self, selector):
        """Test that low-relevance results are filtered out."""
        request = SearchRequest(
            query="Kubernetes installation guide",
            max_results=10,
        )

        # Mock DuckDuckGo
        with patch("haia.services.search.duckduckgo.DDGS") as mock_ddgs_class:
            from unittest.mock import MagicMock
            mock_ddgs = MagicMock()
            mock_ddgs_class.return_value.__enter__.return_value = mock_ddgs
            mock_ddgs.text.return_value = [
                {
                    "title": "Kubernetes Installation Documentation",
                    "href": "https://kubernetes.io/docs/setup/",
                    "body": "Official installation guide for Kubernetes",
                },
                {
                    "title": "Completely Unrelated Article",
                    "href": "https://example.com/random",
                    "body": "This has nothing to do with Kubernetes",
                },
            ]

            response = await selector.search(request)

            # Should have filtered low-relevance results
            assert len(response.results) >= 1
            # All results should have reasonable relevance scores
            for result in response.results:
                assert result.relevance_score > 0.3  # Minimum threshold
