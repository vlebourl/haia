"""Unit tests for BraveSearchClient."""

import pytest
from datetime import datetime, UTC
from unittest.mock import AsyncMock, MagicMock, patch

import httpx

from haia.models.search import SearchBackendType, SearchRequest, SearchResponse, TimeRange
from haia.services.search.base import (
    AuthenticationError,
    BackendError,
    NetworkError,
    RateLimitError,
)
from haia.services.search.brave import BraveSearchClient


@pytest.fixture
def brave_client():
    """Create BraveSearchClient with test API key."""
    return BraveSearchClient(api_key="test_api_key")


@pytest.fixture
def mock_brave_response():
    """Mock Brave API response."""
    return {
        "web": {
            "results": [
                {
                    "title": "Proxmox VE 8.1 Released",
                    "url": "https://www.proxmox.com/en/news/press-releases/proxmox-virtual-environment-8-1",
                    "description": "Proxmox Server Solutions GmbH, the developer of the open-source Proxmox software stack, released Proxmox Virtual Environment 8.1.",
                    "age": "2023-11-22T10:00:00Z",
                    "page_age": "2023-11-22T10:00:00Z",
                },
                {
                    "title": "Proxmox VE Download",
                    "url": "https://www.proxmox.com/en/downloads",
                    "description": "Download the latest version of Proxmox VE.",
                    "age": "2024-01-15T12:00:00Z",
                },
                {
                    "title": "Proxmox VE Documentation",
                    "url": "https://pve.proxmox.com/pve-docs/",
                    "description": "Official Proxmox VE documentation",
                },
            ]
        }
    }


class TestBraveSearchClient:
    """Test suite for BraveSearchClient."""

    @pytest.mark.asyncio
    async def test_search_success(self, brave_client, mock_brave_response):
        """Test successful search with Brave API."""
        request = SearchRequest(
            query="latest version of Proxmox VE",
            max_results=10,
        )

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client

            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = mock_brave_response
            mock_client.get.return_value = mock_response

            response = await brave_client.search(request)

            assert isinstance(response, SearchResponse)
            assert response.backend_used == SearchBackendType.BRAVE
            assert response.query == request.query
            assert len(response.results) == 3
            assert response.results[0].title == "Proxmox VE 8.1 Released"
            assert response.results[0].domain == "proxmox.com"
            assert not response.from_cache

    @pytest.mark.asyncio
    async def test_search_with_time_range(self, brave_client, mock_brave_response):
        """Test search with time range filter."""
        request = SearchRequest(
            query="Proxmox VE",
            max_results=10,
            time_range=TimeRange.WEEK,
        )

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client

            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = mock_brave_response
            mock_client.get.return_value = mock_response

            await brave_client.search(request)

            # Verify that freshness parameter was passed
            call_args = mock_client.get.call_args
            assert "params" in call_args.kwargs
            assert call_args.kwargs["params"]["freshness"] == "pw"

    @pytest.mark.asyncio
    async def test_search_rate_limit_error(self, brave_client):
        """Test handling of rate limit error (429)."""
        request = SearchRequest(query="test query", max_results=10)

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client

            mock_response = MagicMock()
            mock_response.status_code = 429
            mock_response.headers = {"Retry-After": "60"}
            mock_client.get.return_value = mock_response

            with pytest.raises(RateLimitError) as exc_info:
                await brave_client.search(request)

            assert exc_info.value.backend == "brave"
            assert exc_info.value.retry_after == 60

    @pytest.mark.asyncio
    async def test_search_authentication_error(self, brave_client):
        """Test handling of authentication error (401)."""
        request = SearchRequest(query="test query", max_results=10)

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client

            mock_response = MagicMock()
            mock_response.status_code = 401
            mock_client.get.return_value = mock_response

            with pytest.raises(AuthenticationError) as exc_info:
                await brave_client.search(request)

            assert exc_info.value.backend == "brave"
            assert "authentication" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_search_network_error(self, brave_client):
        """Test handling of network errors."""
        request = SearchRequest(query="test query", max_results=10)

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client

            mock_client.get.side_effect = httpx.ConnectError("Connection failed")

            with pytest.raises(NetworkError) as exc_info:
                await brave_client.search(request)

            assert exc_info.value.backend == "brave"

    @pytest.mark.asyncio
    async def test_search_empty_results(self, brave_client):
        """Test handling of empty search results."""
        request = SearchRequest(query="nonexistent query xyz123", max_results=10)

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client

            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"web": {"results": []}}
            mock_client.get.return_value = mock_response

            response = await brave_client.search(request)

            assert isinstance(response, SearchResponse)
            assert len(response.results) == 0
            assert response.total_results == 0

    @pytest.mark.asyncio
    async def test_search_no_api_key(self):
        """Test that missing API key raises error."""
        with patch("haia.config.search_backend_settings") as mock_settings:
            mock_settings.brave_api_key = None

            client = BraveSearchClient()
            request = SearchRequest(query="test", max_results=10)

            with pytest.raises(AuthenticationError) as exc_info:
                await client.search(request)

            assert "api key" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_health_check_success(self, brave_client):
        """Test successful health check."""
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client

            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"web": {"results": []}}
            mock_client.get.return_value = mock_response

            is_healthy = await brave_client.health_check()

            assert is_healthy is True

    @pytest.mark.asyncio
    async def test_health_check_failure(self, brave_client):
        """Test failed health check."""
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client

            mock_client.get.side_effect = httpx.ConnectError("Connection failed")

            is_healthy = await brave_client.health_check()

            assert is_healthy is False

    @pytest.mark.asyncio
    async def test_rate_limiting_delay(self, brave_client, mock_brave_response):
        """Test that rate limiting adds appropriate delay between requests."""
        import time

        request = SearchRequest(query="test", max_results=10)

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client

            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = mock_brave_response
            mock_client.get.return_value = mock_response

            # Make two requests back-to-back
            start_time = time.time()
            await brave_client.search(request)
            await brave_client.search(request)
            elapsed = time.time() - start_time

            # Should have delay between requests (rate limit = 15/sec = 0.067s per request)
            # Two requests should take at least 0.067 seconds
            assert elapsed >= 0.05  # Allow some tolerance
