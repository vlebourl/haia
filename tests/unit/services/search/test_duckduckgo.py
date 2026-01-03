"""Unit tests for DuckDuckGoClient."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from haia.models.search import SearchBackendType, SearchRequest, SearchResponse, TimeRange
from haia.services.search.base import BackendError, NetworkError
from haia.services.search.duckduckgo import DuckDuckGoClient


@pytest.fixture
def ddg_client():
    """Create DuckDuckGoClient."""
    return DuckDuckGoClient()


@pytest.fixture
def mock_ddg_results():
    """Mock DuckDuckGo search results."""
    return [
        {
            "title": "Proxmox VE - Open-Source Server Virtualization Platform",
            "href": "https://www.proxmox.com/en/proxmox-virtual-environment/overview",
            "body": "Proxmox VE is a complete, open-source server management platform for enterprise virtualization.",
        },
        {
            "title": "Proxmox VE Documentation",
            "href": "https://pve.proxmox.com/pve-docs/",
            "body": "Official documentation for Proxmox Virtual Environment.",
        },
        {
            "title": "Download Proxmox VE",
            "href": "https://www.proxmox.com/en/downloads",
            "body": "Download the latest version of Proxmox VE ISO installer.",
        },
    ]


class TestDuckDuckGoClient:
    """Test suite for DuckDuckGoClient."""

    @pytest.mark.asyncio
    async def test_search_success(self, ddg_client, mock_ddg_results):
        """Test successful search with DuckDuckGo."""
        request = SearchRequest(
            query="Proxmox VE",
            max_results=10,
        )

        with patch.object(ddg_client, "_sync_search", return_value=mock_ddg_results):
            response = await ddg_client.search(request)

            assert isinstance(response, SearchResponse)
            assert response.backend_used == SearchBackendType.DUCKDUCKGO
            assert response.query == request.query
            assert len(response.results) == 3
            assert response.results[0].title == "Proxmox VE - Open-Source Server Virtualization Platform"
            assert response.results[0].domain == "proxmox.com"
            assert not response.from_cache

    @pytest.mark.asyncio
    async def test_search_with_time_range(self, ddg_client, mock_ddg_results):
        """Test search with time range filter."""
        request = SearchRequest(
            query="Proxmox VE",
            max_results=10,
            time_range=TimeRange.PAST_MONTH,
        )

        with patch.object(ddg_client, "_sync_search", return_value=mock_ddg_results) as mock_sync:
            await ddg_client.search(request)

            # Verify timelimit parameter was passed
            call_args = mock_sync.call_args
            assert call_args[0][2] == "m"  # Third argument is timelimit

    @pytest.mark.asyncio
    async def test_search_retry_on_failure(self, ddg_client, mock_ddg_results):
        """Test exponential backoff retry logic."""
        request = SearchRequest(query="test query", max_results=10)

        call_count = 0

        def side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise Exception("Temporary failure")
            return mock_ddg_results

        with patch.object(ddg_client, "_sync_search", side_effect=side_effect):
            response = await ddg_client.search(request)

            assert call_count == 2  # Failed once, succeeded on retry
            assert isinstance(response, SearchResponse)
            assert len(response.results) == 3

    @pytest.mark.asyncio
    async def test_search_max_retries_exceeded(self, ddg_client):
        """Test that search fails after max retries."""
        request = SearchRequest(query="test query", max_results=10)

        with patch.object(ddg_client, "_sync_search", side_effect=Exception("Persistent failure")):
            with pytest.raises(BackendError) as exc_info:
                await ddg_client.search(request)

            assert exc_info.value.backend == "duckduckgo"
            assert "max retries" in str(exc_info.value).lower() or "failed" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_search_empty_results(self, ddg_client):
        """Test handling of empty search results."""
        request = SearchRequest(query="nonexistent query xyz123", max_results=10)

        with patch.object(ddg_client, "_sync_search", return_value=[]):
            response = await ddg_client.search(request)

            assert isinstance(response, SearchResponse)
            assert len(response.results) == 0
            assert response.total_results == 0

    @pytest.mark.asyncio
    async def test_search_malformed_result(self, ddg_client):
        """Test handling of malformed search results."""
        request = SearchRequest(query="test", max_results=10)

        malformed_results = [
            {
                "title": "Valid Result",
                "href": "https://example.com",
                "body": "Description",
            },
            {
                # Missing href
                "title": "Invalid Result",
                "body": "Description",
            },
            {
                "title": "Another Valid Result",
                "href": "https://example.org",
                "body": "Another description",
            },
        ]

        with patch.object(ddg_client, "_sync_search", return_value=malformed_results):
            response = await ddg_client.search(request)

            # Should skip malformed results
            assert len(response.results) == 2
            assert response.results[0].title == "Valid Result"
            assert response.results[1].title == "Another Valid Result"

    @pytest.mark.asyncio
    async def test_health_check_success(self, ddg_client):
        """Test successful health check."""
        with patch.object(ddg_client, "_sync_search", return_value=[{"title": "Test", "href": "https://test.com", "body": "Test"}]):
            is_healthy = await ddg_client.health_check()

            assert is_healthy is True

    @pytest.mark.asyncio
    async def test_health_check_failure(self, ddg_client):
        """Test failed health check."""
        with patch.object(ddg_client, "_sync_search", side_effect=Exception("Connection failed")):
            is_healthy = await ddg_client.health_check()

            assert is_healthy is False

    @pytest.mark.asyncio
    async def test_rate_limiting_delay(self, ddg_client, mock_ddg_results):
        """Test that rate limiting adds appropriate delay between requests."""
        import time

        request = SearchRequest(query="test", max_results=10)

        with patch.object(ddg_client, "_sync_search", return_value=mock_ddg_results):
            # Make two requests back-to-back
            start_time = time.time()
            await ddg_client.search(request)
            await ddg_client.search(request)
            elapsed = time.time() - start_time

            # Should have delay between requests (rate limit = 1/sec)
            # Two requests should take at least 1 second
            assert elapsed >= 0.9  # Allow some tolerance

    def test_sync_search(self, ddg_client):
        """Test sync search wrapper function."""
        with patch("haia.services.search.duckduckgo.DDGS") as mock_ddgs_class:
            mock_ddgs = MagicMock()
            mock_ddgs_class.return_value.__enter__.return_value = mock_ddgs
            mock_ddgs.text.return_value = [
                {
                    "title": "Test Result",
                    "href": "https://test.com",
                    "body": "Test description",
                }
            ]

            results = ddg_client._sync_search("test query", 10, None)

            assert len(results) == 1
            assert results[0]["title"] == "Test Result"
            mock_ddgs.text.assert_called_once_with(
                keywords="test query",
                max_results=10,
                timelimit=None,
            )

    def test_sync_search_with_timelimit(self, ddg_client):
        """Test sync search with time limit parameter."""
        with patch("haia.services.search.duckduckgo.DDGS") as mock_ddgs_class:
            mock_ddgs = MagicMock()
            mock_ddgs_class.return_value.__enter__.return_value = mock_ddgs
            mock_ddgs.text.return_value = []

            ddg_client._sync_search("test query", 10, "w")

            mock_ddgs.text.assert_called_once_with(
                keywords="test query",
                max_results=10,
                timelimit="w",
            )
