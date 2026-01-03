"""
Unit tests for Google CSE backend client and daily usage tracking (T077-T078).
"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from datetime import datetime, UTC, timedelta
from pathlib import Path
import tempfile

from haia.services.search.google_cse import GoogleCSEClient, DailyUsageTracker
from haia.models.search import SearchBackendType, SearchRequest, SearchResponse
from haia.services.search.base import BackendError, RateLimitError


@pytest.fixture
def temp_usage_file():
    """Create temporary usage file for testing."""
    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".txt") as f:
        yield Path(f.name)
    # Cleanup
    Path(f.name).unlink(missing_ok=True)


@pytest.fixture
def usage_tracker(temp_usage_file):
    """Create usage tracker with temporary storage."""
    tracker = DailyUsageTracker(limit=100)
    tracker.usage_file = temp_usage_file
    return tracker


@pytest.fixture
def google_client():
    """Create Google CSE client with mock API key."""
    with patch("haia.services.search.google_cse.search_backend_settings") as mock_settings:
        mock_settings.google_cse_api_key.get_secret_value.return_value = "test_google_key"
        mock_settings.google_cse_engine_id = "test_cx_id"
        mock_settings.search_request_timeout_seconds = 10
        return GoogleCSEClient(daily_limit=100)


@pytest.fixture
def mock_google_response():
    """Mock Google CSE API response."""
    return {
        "items": [
            {
                "title": "Proxmox VE Official Documentation",
                "link": "https://pve.proxmox.com/wiki/Main_Page",
                "snippet": "Official documentation for Proxmox Virtual Environment...",
                "pagemap": {
                    "metatags": [
                        {
                            "article:published_time": "2025-10-01T12:00:00Z",
                        }
                    ]
                },
            },
            {
                "title": "Proxmox Setup Guide",
                "link": "https://docs.proxmox.com/setup",
                "snippet": "Step-by-step guide for setting up Proxmox VE...",
            },
        ]
    }


class TestDailyUsageTracker:
    """Test suite for Google CSE daily usage tracking (T078)."""

    def test_initialization(self, usage_tracker):
        """Test usage tracker initialization."""
        assert usage_tracker.limit == 100
        assert usage_tracker.count == 0
        assert usage_tracker.today == datetime.now(UTC).date()

    def test_can_query_under_limit(self, usage_tracker):
        """Test can_query returns True when under limit."""
        usage_tracker.count = 50
        assert usage_tracker.can_query() is True

    def test_can_query_at_limit(self, usage_tracker):
        """Test can_query returns False at limit."""
        usage_tracker.count = 100
        assert usage_tracker.can_query() is False

    def test_can_query_over_limit(self, usage_tracker):
        """Test can_query returns False over limit."""
        usage_tracker.count = 150
        assert usage_tracker.can_query() is False

    def test_increment(self, usage_tracker):
        """Test incrementing query count."""
        assert usage_tracker.count == 0
        usage_tracker.increment()
        assert usage_tracker.count == 1
        usage_tracker.increment()
        assert usage_tracker.count == 2

    def test_persistence(self, temp_usage_file):
        """Test usage data persists across instances."""
        # First tracker - make some queries
        tracker1 = DailyUsageTracker(limit=100)
        tracker1.usage_file = temp_usage_file
        tracker1.increment()
        tracker1.increment()
        tracker1.increment()
        assert tracker1.count == 3

        # Second tracker - should load previous count
        tracker2 = DailyUsageTracker(limit=100)
        tracker2.usage_file = temp_usage_file
        tracker2._load_usage()
        assert tracker2.count == 3

    def test_daily_reset(self, usage_tracker):
        """Test count resets on new day."""
        # Set count from "yesterday"
        usage_tracker.count = 50
        usage_tracker.today = datetime.now(UTC).date() - timedelta(days=1)

        # Check if can query (should reset to 0)
        assert usage_tracker.can_query() is True
        assert usage_tracker.today == datetime.now(UTC).date()

    def test_get_usage(self, usage_tracker):
        """Test get_usage returns correct stats."""
        usage_tracker.count = 25

        usage = usage_tracker.get_usage()

        assert usage["count"] == 25
        assert usage["limit"] == 100
        assert usage["remaining"] == 75
        assert usage["date"] == datetime.now(UTC).date().isoformat()


class TestGoogleCSEClient:
    """Test suite for Google CSE backend client (T077)."""

    def test_initialization(self, google_client):
        """Test client initialization with API key and engine ID."""
        assert google_client.api_key == "test_google_key"
        assert google_client.engine_id == "test_cx_id"
        assert google_client.backend_type == SearchBackendType.GOOGLE_CSE.value
        assert google_client.endpoint == "https://www.googleapis.com/customsearch/v1"

    @pytest.mark.asyncio
    async def test_successful_search(self, google_client, mock_google_response):
        """Test successful search query with results."""
        request = SearchRequest(query="proxmox documentation", max_results=5)

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_response = AsyncMock()
            mock_response.status_code = 200
            mock_response.json.return_value = mock_google_response

            mock_client = AsyncMock()
            mock_client.get.return_value = mock_response
            mock_client_class.return_value.__aenter__.return_value = mock_client

            response = await google_client.search(request)

            # Verify response structure
            assert isinstance(response, SearchResponse)
            assert response.backend_used == SearchBackendType.GOOGLE_CSE
            assert len(response.results) == 2
            assert response.total_results == 2

            # Verify first result
            result = response.results[0]
            assert result.title == "Proxmox VE Official Documentation"
            assert result.url == "https://pve.proxmox.com/wiki/Main_Page"
            assert result.domain == "pve.proxmox.com"
            assert result.backend_score is None  # Google CSE doesn't provide scores

            # Verify published date was parsed from pagemap
            assert result.published_date is not None

            # Verify API call
            mock_client.get.assert_called_once()
            call_args = mock_client.get.call_args
            assert call_args[0][0] == "https://www.googleapis.com/customsearch/v1"
            params = call_args[1]["params"]
            assert params["q"] == "proxmox documentation"
            assert params["key"] == "test_google_key"
            assert params["cx"] == "test_cx_id"
            assert params["num"] == 5

    @pytest.mark.asyncio
    async def test_daily_limit_reached(self, google_client):
        """Test error when daily limit is reached (T078)."""
        request = SearchRequest(query="test", max_results=5)

        # Set usage to limit
        google_client.usage_tracker.count = 100

        with pytest.raises(RateLimitError) as exc_info:
            await google_client.search(request)

        assert exc_info.value.backend == SearchBackendType.GOOGLE_CSE.value
        # Should have retry_after set to seconds until midnight
        assert exc_info.value.retry_after > 0

    @pytest.mark.asyncio
    async def test_usage_increment_on_success(self, google_client, mock_google_response):
        """Test usage counter increments on successful query (T078)."""
        request = SearchRequest(query="test", max_results=5)

        initial_count = google_client.usage_tracker.count

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_response = AsyncMock()
            mock_response.status_code = 200
            mock_response.json.return_value = mock_google_response

            mock_client = AsyncMock()
            mock_client.get.return_value = mock_response
            mock_client_class.return_value.__aenter__.return_value = mock_client

            await google_client.search(request)

            # Verify usage incremented
            assert google_client.usage_tracker.count == initial_count + 1

    @pytest.mark.asyncio
    async def test_rate_limit_error(self, google_client):
        """Test rate limit handling."""
        request = SearchRequest(query="test", max_results=5)

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_response = AsyncMock()
            mock_response.status_code = 429
            mock_response.headers = {"Retry-After": "60"}

            mock_client = AsyncMock()
            mock_client.get.return_value = mock_response
            mock_client_class.return_value.__aenter__.return_value = mock_client

            with pytest.raises(RateLimitError) as exc_info:
                await google_client.search(request)

            assert exc_info.value.backend == SearchBackendType.GOOGLE_CSE.value

    @pytest.mark.asyncio
    async def test_no_api_credentials(self):
        """Test error when API credentials not configured."""
        with patch("haia.services.search.google_cse.search_backend_settings") as mock_settings:
            mock_settings.google_cse_api_key = None
            mock_settings.google_cse_engine_id = None
            mock_settings.search_request_timeout_seconds = 10
            client = GoogleCSEClient()

            request = SearchRequest(query="test", max_results=5)

            with pytest.raises(BackendError) as exc_info:
                await client.search(request)

            assert "not configured" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_get_daily_usage(self, google_client):
        """Test get_daily_usage returns correct stats."""
        google_client.usage_tracker.count = 42

        usage = google_client.get_daily_usage()

        assert usage["count"] == 42
        assert usage["limit"] == 100
        assert usage["remaining"] == 58
