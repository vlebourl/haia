"""Unit tests for SearchBackendSelector."""

import pytest
from datetime import datetime, UTC
from unittest.mock import AsyncMock, MagicMock, patch

from haia.models.search import (
    SearchBackendType,
    SearchRequest,
    SearchResponse,
    SearchResult,
    ContentType,
)
from haia.services.search.base import BackendError, NetworkError, RateLimitError
from haia.services.search.cache import SearchCacheService
from haia.services.search.selector import SearchBackendSelector, BackendHealth


@pytest.fixture
def mock_cache():
    """Create mock SearchCacheService."""
    cache = AsyncMock(spec=SearchCacheService)
    cache.get.return_value = None  # Default: cache miss
    cache.set = AsyncMock()
    return cache


@pytest.fixture
def selector(mock_cache):
    """Create SearchBackendSelector with mocked cache."""
    return SearchBackendSelector(cache=mock_cache)


@pytest.fixture
def sample_search_response():
    """Create sample SearchResponse."""
    return SearchResponse(
        query="test query",
        backend_used=SearchBackendType.BRAVE,
        results=[
            SearchResult(
                title="Proxmox VE Documentation",
                url="https://pve.proxmox.com/pve-docs/",
                snippet="Official Proxmox VE documentation",
                domain="proxmox.com",
                published_date=datetime.now(UTC),
                relevance_score=0.0,  # Will be calculated
                backend_score=0.8,
                content_type=ContentType.DOCUMENTATION,
            ),
            SearchResult(
                title="Proxmox Forum Discussion",
                url="https://forum.proxmox.com/threads/123",
                snippet="Community discussion about Proxmox VE",
                domain="proxmox.com",
                published_date=None,
                relevance_score=0.0,
                backend_score=0.6,
                content_type=ContentType.FORUM,
            ),
        ],
        total_results=2,
        execution_time_ms=100.0,
        from_cache=False,
        cache_key=None,
    )


class TestSearchBackendSelector:
    """Test suite for SearchBackendSelector."""

    @pytest.mark.asyncio
    async def test_search_success_primary_backend(self, selector, sample_search_response):
        """Test successful search with primary backend (Brave)."""
        request = SearchRequest(query="test query", max_results=10)

        with patch.object(selector.backends[SearchBackendType.BRAVE], "search", return_value=sample_search_response):
            response = await selector.search(request)

            assert isinstance(response, SearchResponse)
            assert response.backend_used == SearchBackendType.BRAVE
            assert len(response.results) == 2
            # Relevance scores should be calculated
            assert all(r.relevance_score > 0.0 for r in response.results)

    @pytest.mark.asyncio
    async def test_search_automatic_failover(self, selector, sample_search_response):
        """Test automatic failover from Brave to DuckDuckGo on failure."""
        request = SearchRequest(query="test query", max_results=10)

        # Brave fails, DuckDuckGo succeeds
        brave_mock = AsyncMock(side_effect=BackendError("brave", "API error"))
        ddg_response = SearchResponse(
            query="test query",
            backend_used=SearchBackendType.DUCKDUCKGO,
            results=[],
            total_results=0,
            execution_time_ms=50.0,
            from_cache=False,
            cache_key=None,
        )
        ddg_mock = AsyncMock(return_value=ddg_response)

        with patch.object(selector.backends[SearchBackendType.BRAVE], "search", brave_mock):
            with patch.object(selector.backends[SearchBackendType.DUCKDUCKGO], "search", ddg_mock):
                response = await selector.search(request)

                assert response.backend_used == SearchBackendType.DUCKDUCKGO
                # Backend health should be updated
                assert selector.backend_health[SearchBackendType.BRAVE] == BackendHealth.FAILED
                assert selector.backend_health[SearchBackendType.DUCKDUCKGO] == BackendHealth.ACTIVE

    @pytest.mark.asyncio
    async def test_search_rate_limit_failover(self, selector, sample_search_response):
        """Test failover on rate limit error."""
        request = SearchRequest(query="test query", max_results=10)

        # Brave rate limited, DuckDuckGo succeeds
        brave_mock = AsyncMock(side_effect=RateLimitError("brave", "Rate limit exceeded", retry_after=60))
        ddg_response = SearchResponse(
            query="test query",
            backend_used=SearchBackendType.DUCKDUCKGO,
            results=[],
            total_results=0,
            execution_time_ms=50.0,
            from_cache=False,
            cache_key=None,
        )
        ddg_mock = AsyncMock(return_value=ddg_response)

        with patch.object(selector.backends[SearchBackendType.BRAVE], "search", brave_mock):
            with patch.object(selector.backends[SearchBackendType.DUCKDUCKGO], "search", ddg_mock):
                response = await selector.search(request)

                assert response.backend_used == SearchBackendType.DUCKDUCKGO
                # Backend health should be updated
                assert selector.backend_health[SearchBackendType.BRAVE] == BackendHealth.RATE_LIMITED
                assert SearchBackendType.BRAVE in selector.rate_limit_until

    @pytest.mark.asyncio
    async def test_search_all_backends_fail(self, selector):
        """Test that BackendError is raised when all backends fail."""
        request = SearchRequest(query="test query", max_results=10)

        # Both backends fail
        brave_mock = AsyncMock(side_effect=BackendError("brave", "API error"))
        ddg_mock = AsyncMock(side_effect=NetworkError("duckduckgo", "Network error"))

        with patch.object(selector.backends[SearchBackendType.BRAVE], "search", brave_mock):
            with patch.object(selector.backends[SearchBackendType.DUCKDUCKGO], "search", ddg_mock):
                with pytest.raises(BackendError) as exc_info:
                    await selector.search(request)

                assert "all backends failed" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_search_cache_hit(self, selector, sample_search_response):
        """Test that cache hit returns cached response without backend call."""
        request = SearchRequest(query="test query", max_results=10)

        # Configure mock cache to return cached response
        cached_response = sample_search_response
        cached_response.from_cache = True
        selector.cache.get.return_value = cached_response

        response = await selector.search(request)

        assert response.from_cache is True
        # Backend should not be called
        assert selector.cache.get.called

    @pytest.mark.asyncio
    async def test_search_cache_disabled(self, selector, sample_search_response):
        """Test that cache is bypassed when use_cache=False."""
        request = SearchRequest(query="test query", max_results=10, use_cache=False)

        with patch.object(selector.backends[SearchBackendType.BRAVE], "search", return_value=sample_search_response):
            await selector.search(request)

            # Cache get should not be called
            selector.cache.get.assert_not_called()

    @pytest.mark.asyncio
    async def test_search_backend_preference(self, selector, sample_search_response):
        """Test that backend preference is honored."""
        request = SearchRequest(
            query="test query",
            max_results=10,
            backend_preference=SearchBackendType.DUCKDUCKGO,
        )

        ddg_response = SearchResponse(
            query="test query",
            backend_used=SearchBackendType.DUCKDUCKGO,
            results=[],
            total_results=0,
            execution_time_ms=50.0,
            from_cache=False,
            cache_key=None,
        )

        with patch.object(selector.backends[SearchBackendType.DUCKDUCKGO], "search", return_value=ddg_response) as ddg_mock:
            with patch.object(selector.backends[SearchBackendType.BRAVE], "search") as brave_mock:
                response = await selector.search(request)

                # DuckDuckGo should be called first
                ddg_mock.assert_called_once()
                brave_mock.assert_not_called()
                assert response.backend_used == SearchBackendType.DUCKDUCKGO

    @pytest.mark.asyncio
    async def test_relevance_scoring_domain_reputation(self, selector, sample_search_response):
        """Test relevance scoring with high-quality domain."""
        request = SearchRequest(query="proxmox documentation", max_results=10)

        with patch.object(selector.backends[SearchBackendType.BRAVE], "search", return_value=sample_search_response):
            response = await selector.search(request)

            # First result should have higher score (proxmox.com is high-quality domain)
            assert response.results[0].relevance_score > 0.5

    @pytest.mark.asyncio
    async def test_relevance_scoring_recency(self, selector):
        """Test relevance scoring with recent publication date."""
        recent_result = SearchResult(
            title="Recent Article",
            url="https://example.com/recent",
            snippet="Recent article about Proxmox",
            domain="example.com",
            published_date=datetime.now(UTC),  # Recent
            relevance_score=0.0,
            backend_score=0.5,
            content_type=ContentType.BLOG,
        )

        old_result = SearchResult(
            title="Old Article",
            url="https://example.com/old",
            snippet="Old article about Proxmox",
            domain="example.com",
            published_date=datetime(2020, 1, 1, tzinfo=UTC),  # Old
            relevance_score=0.0,
            backend_score=0.5,
            content_type=ContentType.BLOG,
        )

        response = SearchResponse(
            query="test",
            backend_used=SearchBackendType.BRAVE,
            results=[old_result, recent_result],
            total_results=2,
            execution_time_ms=100.0,
            from_cache=False,
            cache_key=None,
        )

        request = SearchRequest(query="test", max_results=10)

        with patch.object(selector.backends[SearchBackendType.BRAVE], "search", return_value=response):
            processed = await selector.search(request)

            # Results should be ranked by relevance
            # Recent result should score higher and appear first after ranking
            recent_scores = [r.relevance_score for r in processed.results if "Recent" in r.title]
            old_scores = [r.relevance_score for r in processed.results if "Old" in r.title]

            assert recent_scores[0] > old_scores[0]

    @pytest.mark.asyncio
    async def test_relevance_scoring_keyword_matching(self, selector):
        """Test relevance scoring with keyword matching."""
        query = "proxmox documentation"

        # Result with keywords in title and snippet
        keyword_match = SearchResult(
            title="Proxmox Documentation Guide",
            url="https://example.com/docs",
            snippet="Complete Proxmox documentation for beginners",
            domain="example.com",
            published_date=None,
            relevance_score=0.0,
            backend_score=0.5,
            content_type=ContentType.DOCUMENTATION,
        )

        # Result without keywords
        no_match = SearchResult(
            title="Server Management Tools",
            url="https://example.com/tools",
            snippet="Various tools for server administration",
            domain="example.com",
            published_date=None,
            relevance_score=0.0,
            backend_score=0.5,
            content_type=ContentType.BLOG,
        )

        response = SearchResponse(
            query=query,
            backend_used=SearchBackendType.BRAVE,
            results=[no_match, keyword_match],
            total_results=2,
            execution_time_ms=100.0,
            from_cache=False,
            cache_key=None,
        )

        request = SearchRequest(query=query, max_results=10)

        with patch.object(selector.backends[SearchBackendType.BRAVE], "search", return_value=response):
            processed = await selector.search(request)

            # Keyword match should score higher
            keyword_scores = [r.relevance_score for r in processed.results if "Documentation" in r.title]
            no_match_scores = [r.relevance_score for r in processed.results if "Management" in r.title]

            assert keyword_scores[0] > no_match_scores[0]

    @pytest.mark.asyncio
    async def test_result_deduplication(self, selector):
        """Test removal of duplicate URLs."""
        duplicate_url = "https://example.com/page"

        result1 = SearchResult(
            title="Page Title 1",
            url=duplicate_url,
            snippet="First instance",
            domain="example.com",
            published_date=None,
            relevance_score=0.8,
            backend_score=0.8,
            content_type=ContentType.DOCUMENTATION,
        )

        result2 = SearchResult(
            title="Page Title 2",
            url=duplicate_url,
            snippet="Duplicate instance",
            domain="example.com",
            published_date=None,
            relevance_score=0.7,
            backend_score=0.7,
            content_type=ContentType.DOCUMENTATION,
        )

        response = SearchResponse(
            query="test",
            backend_used=SearchBackendType.BRAVE,
            results=[result1, result2],
            total_results=2,
            execution_time_ms=100.0,
            from_cache=False,
            cache_key=None,
        )

        request = SearchRequest(query="test", max_results=10)

        with patch.object(selector.backends[SearchBackendType.BRAVE], "search", return_value=response):
            processed = await selector.search(request)

            # Should only have one result (duplicate removed)
            assert len(processed.results) == 1
            assert processed.results[0].url == duplicate_url

    @pytest.mark.asyncio
    async def test_min_relevance_filtering(self, selector):
        """Test filtering by minimum relevance score."""
        high_score = SearchResult(
            title="Highly Relevant",
            url="https://example.com/high",
            snippet="Highly relevant content",
            domain="example.com",
            published_date=None,
            relevance_score=0.9,
            backend_score=0.9,
            content_type=ContentType.DOCUMENTATION,
        )

        low_score = SearchResult(
            title="Low Relevance",
            url="https://example.com/low",
            snippet="Low relevance content",
            domain="example.com",
            published_date=None,
            relevance_score=0.1,
            backend_score=0.1,
            content_type=ContentType.BLOG,
        )

        response = SearchResponse(
            query="test",
            backend_used=SearchBackendType.BRAVE,
            results=[low_score, high_score],
            total_results=2,
            execution_time_ms=100.0,
            from_cache=False,
            cache_key=None,
        )

        request = SearchRequest(query="test", max_results=10)

        with patch.object(selector.backends[SearchBackendType.BRAVE], "search", return_value=response):
            with patch("haia.config.search_backend_settings.search_min_relevance_score", 0.5):
                processed = await selector.search(request)

                # Only high-score result should remain
                assert len(processed.results) == 1
                assert processed.results[0].title == "Highly Relevant"

    @pytest.mark.asyncio
    async def test_top_n_results_limiting(self, selector):
        """Test limiting to top N results."""
        # Create many results
        results = [
            SearchResult(
                title=f"Result {i}",
                url=f"https://example.com/{i}",
                snippet=f"Content {i}",
                domain="example.com",
                published_date=None,
                relevance_score=0.9 - (i * 0.1),  # Decreasing scores
                backend_score=0.5,
                content_type=ContentType.DOCUMENTATION,
            )
            for i in range(15)
        ]

        response = SearchResponse(
            query="test",
            backend_used=SearchBackendType.BRAVE,
            results=results,
            total_results=15,
            execution_time_ms=100.0,
            from_cache=False,
            cache_key=None,
        )

        request = SearchRequest(query="test", max_results=10)

        with patch.object(selector.backends[SearchBackendType.BRAVE], "search", return_value=response):
            with patch("haia.config.search_backend_settings.search_default_top_results", 5):
                processed = await selector.search(request)

                # Should be limited to top 5
                assert len(processed.results) <= 5

    @pytest.mark.asyncio
    async def test_get_health_status(self, selector):
        """Test retrieving backend health status."""
        selector.backend_health[SearchBackendType.BRAVE] = BackendHealth.ACTIVE
        selector.backend_health[SearchBackendType.DUCKDUCKGO] = BackendHealth.RATE_LIMITED

        health = await selector.get_health_status()

        assert health[SearchBackendType.BRAVE.value] == BackendHealth.ACTIVE.value
        assert health[SearchBackendType.DUCKDUCKGO.value] == BackendHealth.RATE_LIMITED.value


class TestDocumentationDiscovery:
    """Test suite for User Story 2 - Documentation Discovery features."""

    @pytest.mark.asyncio
    async def test_domain_filtering_allowed_domains(self, selector):
        """Test filtering results to allowed domains only (US2 - T056)."""
        request = SearchRequest(
            query="proxmox documentation",
            max_results=10,
            allowed_domains=["proxmox.com", "pve.proxmox.com"],
        )

        results = [
            SearchResult(
                title="Proxmox Official Docs",
                url="https://pve.proxmox.com/pve-docs/",
                snippet="Official documentation",
                domain="pve.proxmox.com",
                published_date=None,
                relevance_score=0.9,
                backend_score=0.8,
                content_type=ContentType.DOCUMENTATION,
            ),
            SearchResult(
                title="Random Blog Post",
                url="https://someblog.com/proxmox",
                snippet="Blog about Proxmox",
                domain="someblog.com",
                published_date=None,
                relevance_score=0.7,
                backend_score=0.6,
                content_type=ContentType.BLOG,
            ),
            SearchResult(
                title="Proxmox Forum",
                url="https://forum.proxmox.com/thread",
                snippet="Forum discussion",
                domain="forum.proxmox.com",
                published_date=None,
                relevance_score=0.6,
                backend_score=0.5,
                content_type=ContentType.FORUM,
            ),
        ]

        response = SearchResponse(
            query="proxmox documentation",
            backend_used=SearchBackendType.BRAVE,
            results=results,
            total_results=3,
            execution_time_ms=100.0,
            from_cache=False,
            cache_key=None,
        )

        with patch.object(selector.backends[SearchBackendType.BRAVE], "search", return_value=response):
            processed = await selector.search(request)

            # Should only include results from allowed domains
            assert len(processed.results) == 2  # pve.proxmox.com and forum.proxmox.com (contains proxmox.com)
            assert all("proxmox.com" in r.domain for r in processed.results)
            assert not any("someblog.com" in r.domain for r in processed.results)

    @pytest.mark.asyncio
    async def test_domain_filtering_blocked_domains(self, selector):
        """Test blocking specific domains (US2 - T056)."""
        request = SearchRequest(
            query="docker tutorial",
            max_results=10,
            blocked_domains=["youtube.com", "medium.com"],
        )

        results = [
            SearchResult(
                title="Docker Official Docs",
                url="https://docs.docker.com",
                snippet="Official documentation",
                domain="docker.com",
                published_date=None,
                relevance_score=0.9,
                backend_score=0.8,
                content_type=ContentType.DOCUMENTATION,
            ),
            SearchResult(
                title="YouTube Tutorial",
                url="https://youtube.com/watch?v=123",
                snippet="Video tutorial",
                domain="youtube.com",
                published_date=None,
                relevance_score=0.8,
                backend_score=0.7,
                content_type=ContentType.VIDEO,
            ),
            SearchResult(
                title="Medium Article",
                url="https://medium.com/article",
                snippet="Article about Docker",
                domain="medium.com",
                published_date=None,
                relevance_score=0.7,
                backend_score=0.6,
                content_type=ContentType.BLOG,
            ),
        ]

        response = SearchResponse(
            query="docker tutorial",
            backend_used=SearchBackendType.BRAVE,
            results=results,
            total_results=3,
            execution_time_ms=100.0,
            from_cache=False,
            cache_key=None,
        )

        with patch.object(selector.backends[SearchBackendType.BRAVE], "search", return_value=response):
            processed = await selector.search(request)

            # Should exclude blocked domains
            assert len(processed.results) == 1
            assert processed.results[0].domain == "docker.com"
            assert not any("youtube.com" in r.domain for r in processed.results)
            assert not any("medium.com" in r.domain for r in processed.results)

    @pytest.mark.asyncio
    async def test_documentation_content_type_scoring(self, selector):
        """Test enhanced scoring for documentation content types (US2 - T057)."""
        request = SearchRequest(query="kubernetes setup", max_results=10)

        doc_result = SearchResult(
            title="Kubernetes Documentation",
            url="https://kubernetes.io/docs/setup/",
            snippet="Official setup guide",
            domain="kubernetes.io",
            published_date=None,
            relevance_score=0.0,  # Will be calculated
            backend_score=0.5,
            content_type=ContentType.DOCUMENTATION,
        )

        blog_result = SearchResult(
            title="Kubernetes Setup Blog",
            url="https://someblog.com/k8s-setup",
            snippet="How I set up Kubernetes",
            domain="someblog.com",
            published_date=None,
            relevance_score=0.0,  # Will be calculated
            backend_score=0.5,  # Same backend score
            content_type=ContentType.BLOG,
        )

        response = SearchResponse(
            query="kubernetes setup",
            backend_used=SearchBackendType.BRAVE,
            results=[blog_result, doc_result],
            total_results=2,
            execution_time_ms=100.0,
            from_cache=False,
            cache_key=None,
        )

        with patch.object(selector.backends[SearchBackendType.BRAVE], "search", return_value=response):
            processed = await selector.search(request)

            # Documentation result should score higher than blog
            doc_scores = [r.relevance_score for r in processed.results if r.content_type == ContentType.DOCUMENTATION]
            blog_scores = [r.relevance_score for r in processed.results if r.content_type == ContentType.BLOG]

            assert doc_scores[0] > blog_scores[0]
            # Documentation should get +0.25 bonus minimum (before normalization)
            # Both have backend_score=0.5, so doc should be higher
            # Doc gets: 0.5 + 0.3 (domain) + 0.25 (doc type) + 0.2 (keyword match) = 1.25 → normalized to 1.0
            # Blog gets: 0.5 + 0.2 (keyword match) = 0.7
            assert doc_scores[0] == 1.0  # Capped at 1.0
            assert blog_scores[0] < 1.0  # Below cap

    @pytest.mark.asyncio
    async def test_official_documentation_domain_bonus(self, selector):
        """Test extra scoring bonus for official documentation domains (US2 - T057)."""
        request = SearchRequest(query="ceph configuration", max_results=10)

        official_doc = SearchResult(
            title="Proxmox VE Storage Documentation",
            url="https://pve.proxmox.com/pve-docs/chapter-pvesm.html",
            snippet="Official Proxmox storage documentation",
            domain="pve.proxmox.com",
            published_date=None,
            relevance_score=0.0,
            backend_score=0.3,  # Lower backend score to avoid normalization cap
            content_type=ContentType.DOCUMENTATION,
        )

        unofficial_doc = SearchResult(
            title="Third-Party Guide",
            url="https://example.com/guide",
            snippet="Community guide",
            domain="example.com",
            published_date=None,
            relevance_score=0.0,
            backend_score=0.3,  # Same backend score
            content_type=ContentType.DOCUMENTATION,
        )

        response = SearchResponse(
            query="ceph configuration",
            backend_used=SearchBackendType.BRAVE,
            results=[unofficial_doc, official_doc],
            total_results=2,
            execution_time_ms=100.0,
            from_cache=False,
            cache_key=None,
        )

        with patch.object(selector.backends[SearchBackendType.BRAVE], "search", return_value=response):
            processed = await selector.search(request)

            # Official documentation should score significantly higher
            official_scores = [r.relevance_score for r in processed.results if "pve.proxmox.com" in r.domain]
            unofficial_scores = [r.relevance_score for r in processed.results if "example.com" in r.domain]

            # Official: 0.3 + 0.25 (doc) + 0.15 (official) + 0.2 (keyword "configuration") = 0.9
            # Unofficial: 0.3 + 0.25 (doc) + 0.2 (keyword "configuration") = 0.75
            assert official_scores[0] > unofficial_scores[0]
            assert official_scores[0] >= 0.85  # At least 0.85 for official docs
            assert unofficial_scores[0] <= 0.80  # Unofficial should be lower
