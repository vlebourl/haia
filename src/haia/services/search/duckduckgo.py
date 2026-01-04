"""
DuckDuckGo search client implementation.

Provides async wrapper for duckduckgo-search library with exponential backoff.
Free search backend with no API key required.
"""
from typing import Any

import asyncio
import logging
import time
from datetime import UTC, datetime

from duckduckgo_search import DDGS

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


class DuckDuckGoClient(BaseSearchBackend):
    """
    DuckDuckGo search client with async wrapper and exponential backoff.

    Uses duckduckgo-search library (synchronous) with thread pool executor
    for async compatibility.
    """

    def __init__(self) -> None:
        """Initialize DuckDuckGo search client."""
        self.timeout = search_backend_settings.search_request_timeout_seconds
        self.max_retries = 3
        self.base_delay = 1.0  # seconds

        # Conservative rate limiting (no official limits, so be careful)
        self.rate_limit_delay = 1.0  # 1 second between requests
        self.last_request_time = 0.0
        self.request_lock = asyncio.Lock()

        logger.info("DuckDuckGoClient initialized")

    @property
    def backend_type(self) -> str:
        """Return backend identifier."""
        return SearchBackendType.DUCKDUCKGO.value

    async def search(self, request: SearchRequest) -> SearchResponse:
        """
        Execute search query via DuckDuckGo.

        Args:
            request: Search request with query and filters

        Returns:
            SearchResponse with normalized results

        Raises:
            RateLimitError: When rate limit is detected
            BackendError: When search fails
            NetworkError: When network connection fails
        """
        start_time = time.time()

        # Apply rate limiting
        await self._apply_rate_limit()

        # Map time range to DuckDuckGo format
        timelimit = None
        if request.time_range != TimeRange.ANY:
            timelimit_map = {
                TimeRange.DAY: "d",
                TimeRange.WEEK: "w",
                TimeRange.MONTH: "m",
                TimeRange.YEAR: "y",
            }
            timelimit = timelimit_map.get(request.time_range)

        # Execute search with exponential backoff
        results_data = await self._search_with_retry(
            request.query,
            request.max_results,
            timelimit,
        )

        # Parse results
        results = self._parse_results(results_data, request)

        execution_time_ms = (time.time() - start_time) * 1000

        return SearchResponse(
            query=request.query,
            backend_used=SearchBackendType.DUCKDUCKGO,
            results=results,
            total_results=len(results),
            execution_time_ms=execution_time_ms,
            from_cache=False,
            cache_key=None,
        )

    async def _search_with_retry(
        self,
        query: str,
        max_results: int,
        timelimit: str | None,
    ) -> list[dict[str, Any]]:
        """
        Execute search with exponential backoff retry logic.

        Args:
            query: Search query string
            max_results: Maximum number of results
            timelimit: Time range filter

        Returns:
            List of result dictionaries

        Raises:
            RateLimitError: When rate limited after all retries
            BackendError: When search fails after all retries
        """
        for attempt in range(self.max_retries):
            try:
                # Run synchronous search in thread pool
                results = await asyncio.to_thread(
                    self._sync_search,
                    query,
                    max_results,
                    timelimit,
                )
                return results

            except Exception as e:
                error_msg = str(e).lower()

                # Detect rate limiting
                if "rate" in error_msg or "limit" in error_msg:
                    if attempt < self.max_retries - 1:
                        delay = self.base_delay * (2**attempt)  # Exponential backoff
                        logger.warning(
                            f"DuckDuckGo rate limit hit, retrying in {delay}s (attempt {attempt + 1}/{self.max_retries})"
                        )
                        await asyncio.sleep(delay)
                        continue
                    else:
                        raise RateLimitError(self.backend_type, retry_after=60)

                # Other errors
                if attempt < self.max_retries - 1:
                    delay = self.base_delay * (2**attempt)
                    logger.warning(
                        f"DuckDuckGo search failed: {e}, retrying in {delay}s (attempt {attempt + 1}/{self.max_retries})"
                    )
                    await asyncio.sleep(delay)
                    continue
                else:
                    raise BackendError(self.backend_type, message=str(e))

        return []

    def _sync_search(
        self,
        query: str,
        max_results: int,
        timelimit: str | None,
    ) -> list[dict[str, Any]]:
        """
        Synchronous search implementation (runs in thread pool).

        Args:
            query: Search query string
            max_results: Maximum number of results
            timelimit: Time range filter

        Returns:
            List of result dictionaries
        """
        with DDGS() as ddgs:
            results = list(
                ddgs.text(
                    keywords=query,
                    region="wt-wt",  # Worldwide
                    safesearch="moderate",
                    timelimit=timelimit,
                    max_results=max_results,
                )
            )
            return results

    def _parse_results(self, data: list[dict[str, Any]], request: SearchRequest) -> list[SearchResult]:
        """
        Parse DuckDuckGo results into SearchResult models.

        Args:
            data: List of result dictionaries from DuckDuckGo
            request: Original search request

        Returns:
            List of SearchResult objects
        """
        results = []

        for item in data:
            try:
                # Skip items missing required fields
                if "href" not in item or "title" not in item:
                    logger.warning(f"Skipping malformed DuckDuckGo result: missing required fields")
                    continue

                # Extract domain
                domain = extract_domain(item["href"])

                # Filter by allowed/blocked domains
                if request.allowed_domains and domain not in request.allowed_domains:
                    continue
                if request.blocked_domains and domain in request.blocked_domains:
                    continue

                # DuckDuckGo doesn't provide publication dates
                published_date = None

                # Detect content type
                content_type = detect_content_type(item["href"], item.get("title", ""))

                result = SearchResult(
                    title=item["title"],
                    url=item["href"],
                    snippet=item.get("body", ""),
                    domain=domain,
                    published_date=published_date,
                    relevance_score=0.0,  # Will be calculated by selector
                    backend_score=None,  # DuckDuckGo doesn't provide scores
                    content_type=content_type,
                )
                results.append(result)
            except (KeyError, ValueError, TypeError) as e:
                # Skip malformed results gracefully
                logger.warning(f"Skipping malformed DuckDuckGo result: {e}")
                continue

        return results

    async def _apply_rate_limit(self) -> None:
        """
        Apply conservative rate limiting to avoid blocks.

        DuckDuckGo has no official rate limits, so we implement
        a conservative 1-second delay between requests.
        """
        async with self.request_lock:
            now = time.time()
            time_since_last = now - self.last_request_time

            if time_since_last < self.rate_limit_delay:
                delay = self.rate_limit_delay - time_since_last
                await asyncio.sleep(delay)

            self.last_request_time = time.time()

    async def health_check(self) -> bool:
        """
        Check if DuckDuckGo is accessible.

        Returns:
            True if search works, False otherwise
        """
        try:
            results = await asyncio.to_thread(
                self._sync_search,
                "test",
                1,
                None,
            )
            return len(results) >= 0  # Even 0 results means it's working
        except Exception:
            return False
