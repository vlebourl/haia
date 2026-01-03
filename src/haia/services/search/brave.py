"""
Brave Search API client implementation.

Provides async client for Brave Search API with rate limiting and error handling.
High-quality search results optimized for technical content.
"""

import asyncio
import logging
import time
from datetime import UTC, datetime

import httpx

from haia.config import search_backend_settings
from haia.models.search import (
    SearchBackendType,
    SearchRequest,
    SearchResponse,
    SearchResult,
    TimeRange,
)
from haia.services.search.base import (
    AuthenticationError,
    BackendError,
    BaseSearchBackend,
    NetworkError,
    RateLimitError,
    detect_content_type,
    extract_domain,
)

logger = logging.getLogger(__name__)


class BraveSearchClient(BaseSearchBackend):
    """
    Brave Search API client with rate limiting and exponential backoff.

    API Documentation: https://brave.com/search/api/
    """

    def __init__(self, api_key: str | None = None):
        """
        Initialize Brave Search client.

        Args:
            api_key: Brave Search API key (defaults to config if not provided)
        """
        self.api_key = api_key or (
            search_backend_settings.brave_api_key.get_secret_value()
            if search_backend_settings.brave_api_key
            else None
        )
        self.endpoint = "https://api.search.brave.com/res/v1/web/search"
        self.timeout = search_backend_settings.search_request_timeout_seconds

        # Rate limiting (15 req/sec for free tier)
        self.rate_limit_per_second = 15.0
        self.last_request_time = 0.0
        self.request_lock = asyncio.Lock()

        logger.info("BraveSearchClient initialized")

    @property
    def backend_type(self) -> str:
        """Return backend identifier."""
        return SearchBackendType.BRAVE.value

    async def search(self, request: SearchRequest) -> SearchResponse:
        """
        Execute search query via Brave Search API.

        Args:
            request: Search request with query and filters

        Returns:
            SearchResponse with normalized results

        Raises:
            RateLimitError: When rate limit is exceeded
            BackendError: When API returns error
            NetworkError: When network connection fails
        """
        if not self.api_key:
            raise AuthenticationError(
                self.backend_type,
                message="Brave API key not configured. Set SEARCH_BRAVE_API_KEY environment variable.",
            )

        start_time = time.time()

        # Apply rate limiting
        await self._apply_rate_limit()

        # Build query parameters
        params = {
            "q": request.query,
            "count": request.max_results,
        }

        # Add time range filter
        if request.time_range != TimeRange.ANY:
            freshness_map = {
                TimeRange.DAY: "pd",
                TimeRange.WEEK: "pw",
                TimeRange.MONTH: "pm",
                TimeRange.YEAR: "py",
            }
            params["freshness"] = freshness_map.get(request.time_range, "")

        # Execute request
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    self.endpoint,
                    params=params,
                    headers={"X-Subscription-Token": self.api_key},
                    timeout=self.timeout,
                )

                # Handle authentication errors (T086)
                if response.status_code in (401, 403):
                    error_detail = response.text[:200] if response.text else "Invalid or expired API key"
                    raise AuthenticationError(
                        self.backend_type,
                        message=f"{error_detail}. Check SEARCH_BRAVE_API_KEY configuration.",
                    )

                # Handle rate limiting (T087)
                if response.status_code == 429:
                    retry_after = int(response.headers.get("Retry-After", 60))
                    logger.warning(
                        f"Brave Search rate limit exceeded. Retry after {retry_after} seconds."
                    )
                    raise RateLimitError(self.backend_type, retry_after)

                # Handle other errors
                if response.status_code != 200:
                    raise BackendError(
                        self.backend_type,
                        response.status_code,
                        response.text[:200],
                    )

                data = response.json()

        except httpx.TimeoutException as e:
            logger.error(f"Brave Search request timeout after {self.timeout}s: {e}")
            raise NetworkError(self.backend_type, e)
        except httpx.ConnectError as e:
            logger.error(f"Failed to connect to Brave Search API: {e}")
            raise NetworkError(self.backend_type, e)
        except httpx.RequestError as e:
            logger.error(f"Brave Search network error: {e}")
            raise NetworkError(self.backend_type, e)

        # Parse results
        results = self._parse_results(data, request)

        execution_time_ms = (time.time() - start_time) * 1000

        return SearchResponse(
            query=request.query,
            backend_used=SearchBackendType.BRAVE,
            results=results,
            total_results=len(results),
            execution_time_ms=execution_time_ms,
            from_cache=False,
            cache_key=None,
        )

    def _parse_results(self, data: dict, request: SearchRequest) -> list[SearchResult]:
        """
        Parse Brave API response into SearchResult models.

        Args:
            data: JSON response from Brave API
            request: Original search request

        Returns:
            List of SearchResult objects
        """
        results = []
        web_results = data.get("web", {}).get("results", [])

        for item in web_results:
            # Extract domain
            domain = extract_domain(item["url"])

            # Filter by allowed/blocked domains
            if request.allowed_domains and domain not in request.allowed_domains:
                continue
            if request.blocked_domains and domain in request.blocked_domains:
                continue

            # Parse published date
            published_date = None
            if "page_age" in item and item["page_age"]:
                try:
                    published_date = datetime.fromisoformat(
                        item["page_age"].replace("Z", "+00:00")
                    )
                except (ValueError, AttributeError):
                    pass

            # Detect content type
            content_type = detect_content_type(item["url"], item.get("title", ""))

            result = SearchResult(
                title=item["title"],
                url=item["url"],
                snippet=item.get("description", ""),
                domain=domain,
                published_date=published_date,
                relevance_score=0.0,  # Will be calculated by selector
                backend_score=None,  # Brave doesn't provide scores
                content_type=content_type,
            )
            results.append(result)

        return results

    async def _apply_rate_limit(self):
        """
        Apply rate limiting to prevent exceeding API limits.

        Uses token bucket algorithm with per-second rate limit.
        """
        async with self.request_lock:
            now = time.time()
            time_since_last = now - self.last_request_time

            # Calculate required delay
            min_interval = 1.0 / self.rate_limit_per_second
            if time_since_last < min_interval:
                delay = min_interval - time_since_last
                await asyncio.sleep(delay)

            self.last_request_time = time.time()

    async def health_check(self) -> bool:
        """
        Check if Brave Search API is accessible.

        Returns:
            True if API is healthy, False otherwise
        """
        if not self.api_key:
            return False

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    self.endpoint,
                    params={"q": "test", "count": 1},
                    headers={"X-Subscription-Token": self.api_key},
                    timeout=5.0,
                )
                return response.status_code in (200, 429)  # 429 means API is up but rate limited
        except Exception:
            return False
