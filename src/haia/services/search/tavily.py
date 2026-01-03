"""
Tavily Search API client implementation.

Provides async client for Tavily Search API with AI-optimized search results.
Tavily is specifically designed for LLM applications with relevance scoring
and content extraction.
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


class TavilySearchClient(BaseSearchBackend):
    """
    Tavily Search API client with AI-optimized results and relevance scoring.

    API Documentation: https://docs.tavily.com/

    Features:
    - AI-optimized search results
    - Relevance scores (0.0-1.0)
    - Content extraction
    - Source attribution
    """

    def __init__(self, api_key: str | None = None):
        """
        Initialize Tavily Search client.

        Args:
            api_key: Tavily API key (defaults to config if not provided)
        """
        self.api_key = api_key or (
            search_backend_settings.tavily_api_key.get_secret_value()
            if search_backend_settings.tavily_api_key
            else None
        )
        self.endpoint = "https://api.tavily.com/search"
        self.timeout = search_backend_settings.search_request_timeout_seconds

        # Rate limiting (100 req/min for free tier)
        self.rate_limit_per_minute = 100.0
        self.last_request_time = 0.0
        self.request_lock = asyncio.Lock()

        logger.info("TavilySearchClient initialized")

    @property
    def backend_type(self) -> str:
        """Return backend identifier."""
        return SearchBackendType.TAVILY.value

    async def search(self, request: SearchRequest) -> SearchResponse:
        """
        Execute search query via Tavily Search API.

        Args:
            request: Search request with query and filters

        Returns:
            SearchResponse with normalized results (includes backend_score from Tavily)

        Raises:
            RateLimitError: When rate limit is exceeded
            BackendError: When API returns error
            NetworkError: When network connection fails
        """
        if not self.api_key:
            raise AuthenticationError(
                self.backend_type,
                message="Tavily API key not configured. Set SEARCH_TAVILY_API_KEY environment variable.",
            )

        start_time = time.time()

        # Apply rate limiting
        await self._apply_rate_limit()

        # Build request payload (Tavily uses POST)
        payload = {
            "api_key": self.api_key,
            "query": request.query,
            "max_results": request.max_results,
            "search_depth": "advanced",  # Use advanced search for better results
            "include_domains": request.allowed_domains or [],
            "exclude_domains": request.blocked_domains or [],
        }

        # Add time range filter (days parameter)
        if request.time_range != TimeRange.ANY:
            days_map = {
                TimeRange.DAY: 1,
                TimeRange.WEEK: 7,
                TimeRange.MONTH: 30,
                TimeRange.YEAR: 365,
            }
            payload["days"] = days_map.get(request.time_range, None)

        # Execute request (T085-T087)
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    self.endpoint,
                    json=payload,
                    timeout=self.timeout,
                )

                # Handle authentication errors (T086)
                if response.status_code in (401, 403):
                    error_detail = response.text[:200] if response.text else "Invalid or expired API key"
                    raise AuthenticationError(
                        self.backend_type,
                        message=f"{error_detail}. Check SEARCH_TAVILY_API_KEY configuration.",
                    )

                # Handle rate limiting (T087)
                if response.status_code == 429:
                    retry_after = int(response.headers.get("Retry-After", 60))
                    logger.warning(
                        f"Tavily Search rate limit exceeded. Retry after {retry_after} seconds."
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
            logger.error(f"Tavily Search request timeout after {self.timeout}s: {e}")
            raise NetworkError(self.backend_type, e)
        except httpx.ConnectError as e:
            logger.error(f"Failed to connect to Tavily Search API: {e}")
            raise NetworkError(self.backend_type, e)
        except httpx.RequestError as e:
            logger.error(f"Tavily Search network error: {e}")
            raise NetworkError(self.backend_type, e)

        # Parse results
        results = self._parse_results(data, request)

        execution_time_ms = (time.time() - start_time) * 1000

        return SearchResponse(
            query=request.query,
            backend_used=SearchBackendType.TAVILY,
            results=results,
            total_results=len(results),
            execution_time_ms=execution_time_ms,
            from_cache=False,
            cache_key=None,
        )

    def _parse_results(self, data: dict, request: SearchRequest) -> list[SearchResult]:
        """
        Parse Tavily API response into SearchResult models.

        Tavily provides relevance scores (0.0-1.0) which we preserve as backend_score.

        Args:
            data: JSON response from Tavily API
            request: Original search request

        Returns:
            List of SearchResult objects with backend_score populated
        """
        results = []

        # Tavily returns results in "results" array
        tavily_results = data.get("results", [])

        for item in tavily_results:
            # Extract domain
            domain = extract_domain(item["url"])

            # Parse published date (if available)
            published_date = None
            if "published_date" in item and item["published_date"]:
                try:
                    published_date = datetime.fromisoformat(
                        item["published_date"].replace("Z", "+00:00")
                    )
                except (ValueError, AttributeError):
                    pass

            # Detect content type
            content_type = detect_content_type(item["url"], item.get("title", ""))

            # Tavily provides relevance score (0.0-1.0)
            backend_score = item.get("score", None)

            result = SearchResult(
                title=item["title"],
                url=item["url"],
                snippet=item.get("content", ""),  # Tavily uses "content" not "description"
                domain=domain,
                published_date=published_date,
                relevance_score=0.0,  # Will be calculated by selector
                backend_score=backend_score,  # Preserve Tavily's relevance score
                content_type=content_type,
            )
            results.append(result)

        return results

    async def _apply_rate_limit(self):
        """
        Apply rate limiting to prevent exceeding API limits.

        Tavily free tier: 100 requests/minute
        """
        async with self.request_lock:
            now = time.time()
            time_since_last = now - self.last_request_time

            # Calculate required delay
            min_interval = 60.0 / self.rate_limit_per_minute
            if time_since_last < min_interval:
                delay = min_interval - time_since_last
                await asyncio.sleep(delay)

            self.last_request_time = time.time()

    async def health_check(self) -> bool:
        """
        Check if Tavily Search API is accessible.

        Returns:
            True if API is healthy, False otherwise
        """
        if not self.api_key:
            return False

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    self.endpoint,
                    json={
                        "api_key": self.api_key,
                        "query": "test",
                        "max_results": 1,
                    },
                    timeout=5.0,
                )
                return response.status_code in (200, 429)  # 429 means API is up but rate limited
        except Exception:
            return False
