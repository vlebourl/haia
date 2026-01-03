"""
Unit tests for Tavily Search backend client (T076).
"""

import pytest
from unittest.mock import AsyncMock, patch
from datetime import datetime, UTC

from haia.services.search.tavily import TavilySearchClient
from haia.models.search import SearchBackendType, SearchRequest, SearchResponse
from haia.services.search.base import BackendError, RateLimitError, NetworkError


@pytest.fixture
def tavily_client():
    """Create Tavily client with mock API key."""
    with patch("haia.services.search.tavily.search_backend_settings") as mock_settings:
        mock_settings.tavily_api_key.get_secret_value.return_value = "test_tavily_key"
        mock_settings.search_request_timeout_seconds = 10
        return TavilySearchClient()


@pytest.fixture
def mock_tavily_response():
    """Mock Tavily API response."""
    return {
        "results": [
            {
                "title": "Proxmox VE 8.1 Documentation",
                "url": "https://pve.proxmox.com/wiki/Proxmox_VE_8.1",
                "content": "Official documentation for Proxmox VE 8.1 with installation guides...",
                "score": 0.95,
                "published_date": "2025-11-15T10:00:00Z",
            },
            {
                "title": "Proxmox Community Guide",
                "url": "https://forum.proxmox.com/threads/guide.123",
                "content": "Community guide for Proxmox setup and configuration...",
                "score": 0.78,
            },
        ]
    }


class TestTavilySearchClient:
    """Test suite for Tavily Search backend client."""

    def test_initialization(self, tavily_client):
        """Test client initialization with API key."""
        assert tavily_client.api_key == "test_tavily_key"
        assert tavily_client.backend_type == SearchBackendType.TAVILY.value
        assert tavily_client.endpoint == "https://api.tavily.com/search"

    @pytest.mark.asyncio
    async def test_successful_search(self, tavily_client, mock_tavily_response):
        """Test successful search query with results."""
        request = SearchRequest(query="proxmox documentation", max_results=5)

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_response = AsyncMock()
            mock_response.status_code = 200
            mock_response.json.return_value = mock_tavily_response

            mock_client = AsyncMock()
            mock_client.post.return_value = mock_response
            mock_client_class.return_value.__aenter__.return_value = mock_client

            response = await tavily_client.search(request)

            # Verify response structure
            assert isinstance(response, SearchResponse)
            assert response.backend_used == SearchBackendType.TAVILY
            assert len(response.results) == 2
            assert response.total_results == 2

            # Verify first result
            result = response.results[0]
            assert result.title == "Proxmox VE 8.1 Documentation"
            assert result.url == "https://pve.proxmox.com/wiki/Proxmox_VE_8.1"
            assert result.backend_score == 0.95
            assert result.domain == "pve.proxmox.com"

            # Verify API call
            mock_client.post.assert_called_once()
            call_args = mock_client.post.call_args
            assert call_args[0][0] == "https://api.tavily.com/search"
            payload = call_args[1]["json"]
            assert payload["query"] == "proxmox documentation"
            assert payload["max_results"] == 5
            assert payload["search_depth"] == "advanced"

    @pytest.mark.asyncio
    async def test_search_with_domain_filters(self, tavily_client, mock_tavily_response):
        """Test search with allowed/blocked domains."""
        request = SearchRequest(
            query="proxmox",
            max_results=5,
            allowed_domains=["proxmox.com"],
            blocked_domains=["spam.com"],
        )

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_response = AsyncMock()
            mock_response.status_code = 200
            mock_response.json.return_value = mock_tavily_response

            mock_client = AsyncMock()
            mock_client.post.return_value = mock_response
            mock_client_class.return_value.__aenter__.return_value = mock_client

            await tavily_client.search(request)

            # Verify domain filters in payload
            call_args = mock_client.post.call_args
            payload = call_args[1]["json"]
            assert payload["include_domains"] == ["proxmox.com"]
            assert payload["exclude_domains"] == ["spam.com"]

    @pytest.mark.asyncio
    async def test_rate_limit_error(self, tavily_client):
        """Test rate limit handling."""
        request = SearchRequest(query="test", max_results=5)

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_response = AsyncMock()
            mock_response.status_code = 429
            mock_response.headers = {"Retry-After": "60"}

            mock_client = AsyncMock()
            mock_client.post.return_value = mock_response
            mock_client_class.return_value.__aenter__.return_value = mock_client

            with pytest.raises(RateLimitError) as exc_info:
                await tavily_client.search(request)

            assert exc_info.value.backend == SearchBackendType.TAVILY.value
            assert exc_info.value.retry_after == 60

    @pytest.mark.asyncio
    async def test_backend_error(self, tavily_client):
        """Test backend error handling."""
        request = SearchRequest(query="test", max_results=5)

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_response = AsyncMock()
            mock_response.status_code = 500
            mock_response.text = "Internal server error"

            mock_client = AsyncMock()
            mock_client.post.return_value = mock_response
            mock_client_class.return_value.__aenter__.return_value = mock_client

            with pytest.raises(BackendError) as exc_info:
                await tavily_client.search(request)

            assert exc_info.value.backend == SearchBackendType.TAVILY.value

    @pytest.mark.asyncio
    async def test_no_api_key(self):
        """Test error when API key is not configured."""
        with patch("haia.services.search.tavily.search_backend_settings") as mock_settings:
            mock_settings.tavily_api_key = None
            mock_settings.search_request_timeout_seconds = 10
            client = TavilySearchClient()

            request = SearchRequest(query="test", max_results=5)

            with pytest.raises(BackendError) as exc_info:
                await client.search(request)

            assert "not configured" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_health_check_success(self, tavily_client):
        """Test health check with healthy backend."""
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_response = AsyncMock()
            mock_response.status_code = 200

            mock_client = AsyncMock()
            mock_client.post.return_value = mock_response
            mock_client_class.return_value.__aenter__.return_value = mock_client

            is_healthy = await tavily_client.health_check()
            assert is_healthy is True

    @pytest.mark.asyncio
    async def test_health_check_failure(self, tavily_client):
        """Test health check with unhealthy backend."""
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.post.side_effect = Exception("Connection failed")
            mock_client_class.return_value.__aenter__.return_value = mock_client

            is_healthy = await tavily_client.health_check()
            assert is_healthy is False
