"""
Google Custom Search Engine (CSE) API client implementation.

Provides async client for Google CSE API with daily quota tracking.
Google CSE is expensive and used as a last resort fallback.

Free tier: 100 queries/day
Paid tier: $5 per 1000 queries
"""

import asyncio
import logging
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path

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
    BackendError,
    BaseSearchBackend,
    NetworkError,
    RateLimitError,
    detect_content_type,
    extract_domain,
)

logger = logging.getLogger(__name__)


class DailyUsageTracker:
    """
    Track daily API usage for Google CSE free tier limit (100/day).

    Uses simple file-based persistence to track queries across restarts.
    """

    def __init__(self, limit: int = 100):
        """
        Initialize usage tracker.

        Args:
            limit: Daily query limit (default: 100 for free tier)
        """
        self.limit = limit
        self.usage_file = Path.home() / ".haia" / "google_cse_usage.txt"
        self.usage_file.parent.mkdir(parents=True, exist_ok=True)
        self._load_usage()

    def _load_usage(self):
        """Load usage data from file."""
        self.today = datetime.now(UTC).date()
        self.count = 0

        if self.usage_file.exists():
            try:
                with open(self.usage_file) as f:
                    data = f.read().strip().split(",")
                    if len(data) == 2:
                        stored_date = datetime.fromisoformat(data[0]).date()
                        stored_count = int(data[1])

                        # Only restore if same day
                        if stored_date == self.today:
                            self.count = stored_count
                            logger.info(f"Loaded Google CSE usage: {self.count}/{self.limit}")
            except Exception as e:
                logger.warning(f"Failed to load usage data: {e}")

    def _save_usage(self):
        """Save usage data to file."""
        try:
            with open(self.usage_file, "w") as f:
                f.write(f"{self.today.isoformat()},{self.count}")
        except Exception as e:
            logger.warning(f"Failed to save usage data: {e}")

    def can_query(self) -> bool:
        """
        Check if we can make another query today.

        Returns:
            True if under daily limit, False otherwise
        """
        # Reset counter if new day
        today = datetime.now(UTC).date()
        if today != self.today:
            self.today = today
            self.count = 0

        return self.count < self.limit

    def increment(self):
        """Record a query being made."""
        self.count += 1
        self._save_usage()
        logger.debug(f"Google CSE usage: {self.count}/{self.limit}")

    def get_usage(self) -> dict:
        """
        Get current usage statistics.

        Returns:
            Dict with count, limit, and remaining queries
        """
        today = datetime.now(UTC).date()
        if today != self.today:
            # New day, reset
            return {"count": 0, "limit": self.limit, "remaining": self.limit, "date": today.isoformat()}

        return {
            "count": self.count,
            "limit": self.limit,
            "remaining": max(0, self.limit - self.count),
            "date": self.today.isoformat(),
        }


class GoogleCSEClient(BaseSearchBackend):
    """
    Google Custom Search Engine API client with daily quota tracking.

    API Documentation: https://developers.google.com/custom-search/v1/overview

    Features:
    - Comprehensive search results
    - Page metadata (pagemap)
    - Daily quota tracking (100/day free tier)

    Cost:
    - Free tier: 100 queries/day
    - Paid: $5 per 1000 queries (beyond 100/day)
    """

    def __init__(
        self,
        api_key: str | None = None,
        engine_id: str | None = None,
        daily_limit: int = 100,
    ):
        """
        Initialize Google CSE client.

        Args:
            api_key: Google API key (defaults to config if not provided)
            engine_id: Custom Search Engine ID (CX parameter)
            daily_limit: Daily query limit (default: 100 for free tier)
        """
        self.api_key = api_key or (
            search_backend_settings.google_cse_api_key.get_secret_value()
            if search_backend_settings.google_cse_api_key
            else None
        )
        self.engine_id = engine_id or search_backend_settings.google_cse_engine_id
        self.endpoint = "https://www.googleapis.com/customsearch/v1"
        self.timeout = search_backend_settings.search_request_timeout_seconds

        # Daily usage tracking (T063)
        self.usage_tracker = DailyUsageTracker(limit=daily_limit)

        # Rate limiting (10 queries/second for paid, conservative 1/sec for free)
        self.rate_limit_per_second = 1.0
        self.last_request_time = 0.0
        self.request_lock = asyncio.Lock()

        logger.info("GoogleCSEClient initialized")

    @property
    def backend_type(self) -> str:
        """Return backend identifier."""
        return SearchBackendType.GOOGLE_CSE.value

    async def search(self, request: SearchRequest) -> SearchResponse:
        """
        Execute search query via Google CSE API.

        Args:
            request: Search request with query and filters

        Returns:
            SearchResponse with normalized results

        Raises:
            RateLimitError: When daily quota is exceeded
            BackendError: When API returns error
            NetworkError: When network connection fails
        """
        if not self.api_key or not self.engine_id:
            raise BackendError(
                self.backend_type,
                message="Google CSE API key or engine ID not configured",
            )

        # Check daily usage limit (T063)
        if not self.usage_tracker.can_query():
            usage = self.usage_tracker.get_usage()
            logger.warning(
                f"Google CSE daily limit reached: {usage['count']}/{usage['limit']}"
            )
            # Calculate retry_after (seconds until midnight UTC)
            now = datetime.now(UTC)
            midnight = datetime.combine(now.date() + timedelta(days=1), datetime.min.time(), UTC)
            retry_after = int((midnight - now).total_seconds())
            raise RateLimitError(self.backend_type, retry_after)

        start_time = time.time()

        # Apply rate limiting
        await self._apply_rate_limit()

        # Build query parameters
        params = {
            "key": self.api_key,
            "cx": self.engine_id,
            "q": request.query,
            "num": min(request.max_results, 10),  # Google CSE max is 10
        }

        # Add time range filter
        if request.time_range != TimeRange.ANY:
            date_restrict_map = {
                TimeRange.DAY: "d1",
                TimeRange.WEEK: "w1",
                TimeRange.MONTH: "m1",
                TimeRange.YEAR: "y1",
            }
            params["dateRestrict"] = date_restrict_map.get(request.time_range, "")

        # Execute request
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    self.endpoint,
                    params=params,
                    timeout=self.timeout,
                )

                # Handle rate limiting
                if response.status_code == 429:
                    retry_after = int(response.headers.get("Retry-After", 60))
                    raise RateLimitError(self.backend_type, retry_after)

                # Handle errors
                if response.status_code != 200:
                    error_data = response.json() if response.headers.get("content-type", "").startswith("application/json") else {}
                    error_msg = error_data.get("error", {}).get("message", response.text[:200])
                    raise BackendError(
                        self.backend_type,
                        response.status_code,
                        error_msg,
                    )

                data = response.json()

                # Increment usage counter (T063)
                self.usage_tracker.increment()

        except httpx.TimeoutException as e:
            raise NetworkError(self.backend_type, e)
        except httpx.RequestError as e:
            raise NetworkError(self.backend_type, e)

        # Parse results
        results = self._parse_results(data, request)

        execution_time_ms = (time.time() - start_time) * 1000

        return SearchResponse(
            query=request.query,
            backend_used=SearchBackendType.GOOGLE_CSE,
            results=results,
            total_results=len(results),
            execution_time_ms=execution_time_ms,
            from_cache=False,
            cache_key=None,
        )

    def _parse_results(self, data: dict, request: SearchRequest) -> list[SearchResult]:
        """
        Parse Google CSE API response into SearchResult models.

        Google CSE provides rich pagemap metadata which we extract when available.

        Args:
            data: JSON response from Google CSE API
            request: Original search request

        Returns:
            List of SearchResult objects
        """
        results = []

        # Google CSE returns results in "items" array
        items = data.get("items", [])

        for item in items:
            # Extract domain
            domain = extract_domain(item["link"])

            # Filter by allowed/blocked domains
            if request.allowed_domains and not any(allowed in domain for allowed in request.allowed_domains):
                continue
            if request.blocked_domains and any(blocked in domain for blocked in request.blocked_domains):
                continue

            # Parse published date from pagemap metadata (if available)
            published_date = None
            pagemap = item.get("pagemap", {})

            # Try various metadata sources
            metatags = pagemap.get("metatags", [{}])[0]
            article_date = (
                metatags.get("article:published_time")
                or metatags.get("datePublished")
                or metatags.get("pubdate")
            )

            if article_date:
                try:
                    published_date = datetime.fromisoformat(
                        article_date.replace("Z", "+00:00")
                    )
                except (ValueError, AttributeError):
                    pass

            # Detect content type
            content_type = detect_content_type(item["link"], item.get("title", ""))

            result = SearchResult(
                title=item["title"],
                url=item["link"],
                snippet=item.get("snippet", ""),
                domain=domain,
                published_date=published_date,
                relevance_score=0.0,  # Will be calculated by selector
                backend_score=None,  # Google CSE doesn't provide relevance scores
                content_type=content_type,
            )
            results.append(result)

        return results

    async def _apply_rate_limit(self):
        """
        Apply rate limiting to prevent exceeding API limits.

        Conservative 1 query/second for free tier.
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
        Check if Google CSE API is accessible.

        Returns:
            True if API is healthy, False otherwise
        """
        if not self.api_key or not self.engine_id:
            return False

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    self.endpoint,
                    params={
                        "key": self.api_key,
                        "cx": self.engine_id,
                        "q": "test",
                        "num": 1,
                    },
                    timeout=5.0,
                )
                return response.status_code in (200, 429)  # 429 means API is up but rate limited
        except Exception:
            return False

    def get_daily_usage(self) -> dict:
        """
        Get current daily usage statistics.

        Returns:
            Dict with count, limit, remaining, and date
        """
        return self.usage_tracker.get_usage()
