"""Unit tests for web search tool and intent detection."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from pydantic_ai import RunContext

from haia.models.search import SearchBackendType, SearchResponse, SearchResult, ContentType
from haia.tools.search import should_trigger_search, web_search, get_search_selector


class TestIntentDetection:
    """Test suite for search intent detection."""

    def test_trigger_explicit_search_request(self):
        """Test triggering on explicit search requests."""
        queries = [
            "search the web for Proxmox documentation",
            "google the latest version of Docker",
            "look up online how to configure Ceph",
            "search for Kubernetes troubleshooting",
        ]

        for query in queries:
            assert should_trigger_search(query), f"Should trigger for: {query}"

    def test_trigger_version_queries(self):
        """Test triggering on version/release queries."""
        queries = [
            "what is the latest version of Proxmox VE",
            "newest release of Docker",
            "current version of Kubernetes",
            "most recent version of Home Assistant",
        ]

        for query in queries:
            assert should_trigger_search(query), f"Should trigger for: {query}"

    def test_trigger_time_sensitive_queries(self):
        """Test triggering on time-sensitive queries."""
        queries = [
            "recent updates to Proxmox",
            "news from today about Docker",
            "this week's Kubernetes releases",
            "what's new in 2026 for Home Assistant",
        ]

        for query in queries:
            assert should_trigger_search(query), f"Should trigger for: {query}"

    def test_trigger_error_queries(self):
        """Test triggering on error and troubleshooting queries."""
        queries = [
            "error ECONNREFUSED in Docker",
            "errno 111 connection refused",
            "fix authentication failed error",
            "troubleshoot container startup issue",
        ]

        for query in queries:
            assert should_trigger_search(query), f"Should trigger for: {query}"

    def test_trigger_documentation_queries(self):
        """Test triggering on documentation queries."""
        queries = [
            "documentation for Proxmox VE installation",
            "guide on setting up Ceph storage",
            "how to configure Docker networking",
            "tutorial for Home Assistant automation",
        ]

        for query in queries:
            assert should_trigger_search(query), f"Should trigger for: {query}"

    def test_trigger_release_notes_queries(self):
        """Test triggering on release notes and changelog queries."""
        queries = [
            "release notes for Proxmox 8.1",
            "changelog for Docker 24.0",
            "what's new in Kubernetes 1.28",
            "new features in Home Assistant",
        ]

        for query in queries:
            assert should_trigger_search(query), f"Should trigger for: {query}"

    def test_trigger_version_number_queries(self):
        """Test triggering on queries with version numbers."""
        queries = [
            "Proxmox VE 8.1 features",
            "Docker 24.0 documentation",
            "issues with Kubernetes 1.28",
        ]

        for query in queries:
            assert should_trigger_search(query), f"Should trigger for: {query}"

    def test_no_trigger_conceptual_questions(self):
        """Test not triggering on conceptual questions."""
        queries = [
            "what is Docker",
            "explain how Kubernetes works",
            "why does Proxmox use Ceph",
            "why do containers restart",
        ]

        for query in queries:
            assert not should_trigger_search(query), f"Should NOT trigger for: {query}"

    def test_no_trigger_historical_questions(self):
        """Test not triggering on historical questions."""
        queries = [
            "history of Docker",
            "who invented Kubernetes",
            "who created Proxmox",
            "who discovered virtualization",
        ]

        for query in queries:
            assert not should_trigger_search(query), f"Should NOT trigger for: {query}"

    def test_no_trigger_explicit_exclusion(self):
        """Test not triggering when user explicitly says not to search."""
        queries = [
            "don't search the web, just tell me about Docker",
            "answer without searching online",
            "do not google this, explain Kubernetes",
        ]

        for query in queries:
            assert not should_trigger_search(query), f"Should NOT trigger for: {query}"

    def test_case_insensitive_matching(self):
        """Test that pattern matching is case-insensitive."""
        queries = [
            "SEARCH THE WEB for Docker",
            "What is the LATEST VERSION of Proxmox",
            "ERROR in Docker container",
        ]

        for query in queries:
            # Should still trigger despite uppercase
            should_match = should_trigger_search(query)
            # The first two should trigger, third should trigger
            assert should_match, f"Should trigger for: {query}"


class TestWebSearchTool:
    """Test suite for web_search PydanticAI tool function."""

    @pytest.fixture
    def mock_run_context(self):
        """Create mock RunContext for PydanticAI tool."""
        return MagicMock(spec=RunContext)

    @pytest.fixture
    def mock_search_response(self):
        """Create mock SearchResponse."""
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

    @pytest.mark.asyncio
    async def test_web_search_success(self, mock_run_context, mock_search_response):
        """Test successful web search execution."""
        query = "latest version of Proxmox VE"

        with patch("haia.tools.search.get_search_selector") as mock_get_selector:
            mock_selector = AsyncMock()
            mock_selector.search.return_value = mock_search_response
            mock_get_selector.return_value = mock_selector

            result = await web_search(mock_run_context, query, max_results=10)

            assert isinstance(result, str)
            assert "Test Result" in result
            assert "test.com" in result
            assert "brave" in result.lower()
            assert "100ms" in result or "100.0ms" in result

    @pytest.mark.asyncio
    async def test_web_search_with_custom_max_results(self, mock_run_context, mock_search_response):
        """Test web search with custom max_results parameter."""
        query = "Docker documentation"

        with patch("haia.tools.search.get_search_selector") as mock_get_selector:
            mock_selector = AsyncMock()
            mock_selector.search.return_value = mock_search_response
            mock_get_selector.return_value = mock_selector

            await web_search(mock_run_context, query, max_results=5)

            # Verify SearchRequest was created with correct max_results
            call_args = mock_selector.search.call_args
            search_request = call_args[0][0]
            assert search_request.max_results == 5

    @pytest.mark.asyncio
    async def test_web_search_respects_max_results_limit(self, mock_run_context, mock_search_response):
        """Test that max_results is capped at configured maximum."""
        query = "test query"

        with patch("haia.tools.search.get_search_selector") as mock_get_selector:
            with patch("haia.config.search_backend_settings.search_default_max_results", 10):
                mock_selector = AsyncMock()
                mock_selector.search.return_value = mock_search_response
                mock_get_selector.return_value = mock_selector

                await web_search(mock_run_context, query, max_results=50)

                # Should be capped at 10
                call_args = mock_selector.search.call_args
                search_request = call_args[0][0]
                assert search_request.max_results == 10

    @pytest.mark.asyncio
    async def test_web_search_disabled(self, mock_run_context):
        """Test web search when feature is disabled."""
        query = "test query"

        with patch("haia.config.search_backend_settings.search_enabled", False):
            result = await web_search(mock_run_context, query)

            assert "disabled" in result.lower()
            assert "enable" in result.lower()

    @pytest.mark.asyncio
    async def test_web_search_backend_error(self, mock_run_context):
        """Test web search handling of backend errors."""
        query = "test query"

        with patch("haia.tools.search.get_search_selector") as mock_get_selector:
            mock_selector = AsyncMock()
            mock_selector.search.side_effect = Exception("Backend failure")
            mock_get_selector.return_value = mock_selector

            result = await web_search(mock_run_context, query)

            assert "failed" in result.lower()
            assert "backend failure" in result.lower()
            assert "training data" in result.lower()

    @pytest.mark.asyncio
    async def test_web_search_from_cache(self, mock_run_context, mock_search_response):
        """Test web search with cached result."""
        query = "test query"

        # Mark response as from cache
        mock_search_response.from_cache = True

        with patch("haia.tools.search.get_search_selector") as mock_get_selector:
            mock_selector = AsyncMock()
            mock_selector.search.return_value = mock_search_response
            mock_get_selector.return_value = mock_selector

            result = await web_search(mock_run_context, query)

            assert "(cached)" in result.lower()

    @pytest.mark.asyncio
    async def test_web_search_format_for_llm(self, mock_run_context):
        """Test that results are properly formatted for LLM consumption."""
        query = "Proxmox documentation"

        response = SearchResponse(
            query=query,
            backend_used=SearchBackendType.BRAVE,
            results=[
                SearchResult(
                    title="Proxmox VE Documentation",
                    url="https://pve.proxmox.com/pve-docs/",
                    snippet="Official Proxmox VE documentation and guides",
                    domain="proxmox.com",
                    published_date=None,
                    relevance_score=0.9,
                    backend_score=0.8,
                    content_type=ContentType.DOCUMENTATION,
                ),
                SearchResult(
                    title="Proxmox VE Installation Guide",
                    url="https://pve.proxmox.com/pve-docs/installation.html",
                    snippet="Step-by-step installation instructions for Proxmox VE",
                    domain="proxmox.com",
                    published_date=None,
                    relevance_score=0.85,
                    backend_score=0.75,
                    content_type=ContentType.DOCUMENTATION,
                ),
            ],
            total_results=2,
            execution_time_ms=150.0,
            from_cache=False,
            cache_key=None,
        )

        with patch("haia.tools.search.get_search_selector") as mock_get_selector:
            mock_selector = AsyncMock()
            mock_selector.search.return_value = response
            mock_get_selector.return_value = mock_selector

            result = await web_search(mock_run_context, query)

            # Should be markdown formatted
            assert "## " in result or "**" in result  # Markdown headers or bold
            assert "Proxmox VE Documentation" in result
            assert "pve.proxmox.com" in result
            assert "2 results" in result or "2" in result

    @pytest.mark.asyncio
    async def test_web_search_empty_results(self, mock_run_context):
        """Test web search with no results found."""
        query = "nonexistent query xyz123"

        response = SearchResponse(
            query=query,
            backend_used=SearchBackendType.BRAVE,
            results=[],
            total_results=0,
            execution_time_ms=50.0,
            from_cache=False,
            cache_key=None,
        )

        with patch("haia.tools.search.get_search_selector") as mock_get_selector:
            mock_selector = AsyncMock()
            mock_selector.search.return_value = response
            mock_get_selector.return_value = mock_selector

            result = await web_search(mock_run_context, query)

            assert "0 results" in result or "no results" in result.lower()

    def test_get_search_selector_singleton(self):
        """Test that get_search_selector returns singleton instance."""
        selector1 = get_search_selector()
        selector2 = get_search_selector()

        # Should be the same instance
        assert selector1 is selector2
