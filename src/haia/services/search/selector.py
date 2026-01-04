"""
Backend selection and failover logic for web search.

Provides automatic backend selection, failover, and result processing
with relevance scoring and ranking.
"""

import asyncio
import logging
import re
import time
from datetime import UTC, datetime, timedelta
from enum import Enum

from haia.config import search_backend_settings
from haia.models.search import (
    ContentType,
    SearchBackendType,
    SearchRequest,
    SearchResponse,
    SearchResult,
)
from haia.services.search.base import (
    AuthenticationError,
    BackendError,
    BaseSearchBackend,
    NetworkError,
    RateLimitError,
)
from haia.services.search.brave import BraveSearchClient
from haia.services.search.cache import SearchCacheService
from haia.services.search.duckduckgo import DuckDuckGoClient
from haia.services.search.google_cse import GoogleCSEClient
from haia.services.search.metrics import SearchMetricsService
from haia.services.search.tavily import TavilySearchClient

logger = logging.getLogger(__name__)


class BackendHealth(str, Enum):
    """Backend health status."""

    ACTIVE = "active"
    RATE_LIMITED = "rate_limited"
    FAILED = "failed"


class SearchBackendSelector:
    """
    Orchestrates search backends with automatic failover and caching.

    Features:
    - Priority-based backend selection
    - Automatic failover when backend fails
    - Cache integration
    - Backend health tracking
    - Relevance scoring and ranking
    """

    def __init__(
        self,
        cache: SearchCacheService | None = None,
        metrics: SearchMetricsService | None = None,
    ):
        """
        Initialize backend selector.

        Args:
            cache: Search cache service (creates new if not provided)
            metrics: Metrics service for cost tracking (creates new if not provided)
        """
        self.cache = cache or SearchCacheService()
        self.metrics = metrics or SearchMetricsService()

        # Initialize backends (T064)
        self.backends = {
            SearchBackendType.BRAVE: BraveSearchClient(),
            SearchBackendType.DUCKDUCKGO: DuckDuckGoClient(),
            SearchBackendType.TAVILY: TavilySearchClient(),
            SearchBackendType.GOOGLE_CSE: GoogleCSEClient(),
        }

        # Parse backend priority from config
        self.priority_order = self._parse_priority_order()

        # Track backend health
        self.backend_health: dict[SearchBackendType, BackendHealth] = {
            backend: BackendHealth.ACTIVE for backend in self.backends
        }
        self.rate_limit_until: dict[SearchBackendType, datetime] = {}

        logger.info(
            f"SearchBackendSelector initialized with priority: {[b.value for b in self.priority_order]}"
        )

    def _parse_priority_order(self) -> list[SearchBackendType]:
        """
        Parse backend priority from configuration.

        Returns:
            List of SearchBackendType in priority order
        """
        priority_str = search_backend_settings.backend_priority
        priority_list = [p.strip() for p in priority_str.split(",")]

        order = []
        for name in priority_list:
            try:
                backend_type = SearchBackendType(name)
                if backend_type in self.backends:
                    order.append(backend_type)
            except ValueError:
                logger.warning(f"Unknown backend in priority list: {name}")

        if not order:
            # Default fallback
            order = [SearchBackendType.BRAVE, SearchBackendType.DUCKDUCKGO]
            logger.warning(f"No valid backends in config, using default: {order}")

        return order

    async def search(self, request: SearchRequest) -> SearchResponse:
        """
        Execute search with automatic backend selection and failover.

        Workflow:
        1. Check cache if enabled
        2. Try backends in priority order
        3. Apply relevance scoring and ranking
        4. Cache results

        Args:
            request: Search request

        Returns:
            SearchResponse with ranked results

        Raises:
            BackendError: If all backends fail
        """
        # Check cache first
        if request.use_cache and search_backend_settings.search_cache_enabled:
            for backend_type in self.priority_order:
                cached = await self.cache.get(request.query, backend_type)
                if cached:
                    logger.info(
                        f"Cache hit for '{request.query}' (backend: {backend_type.value})"
                    )
                    # Track cache hit (T074)
                    self.metrics.record_query(backend_type, from_cache=True)
                    # Mark as from cache
                    cached.from_cache = True
                    return cached

        # Try backends in priority order
        errors = []
        for backend_type in self._get_available_backends(request):
            try:
                backend = self.backends[backend_type]
                logger.info(f"Attempting search with {backend_type.value}")

                response = await backend.search(request)

                # Track successful query (T074)
                self.metrics.record_query(backend_type, from_cache=False)

                # Apply relevance scoring and ranking
                response = self._process_results(response, request)

                # Cache results
                if search_backend_settings.search_cache_enabled:
                    await self.cache.set(request.query, backend_type, response)

                # Mark backend as healthy
                self.backend_health[backend_type] = BackendHealth.ACTIVE

                return response

            except AuthenticationError as e:
                logger.error(f"Authentication failed for {backend_type.value}: {e}")
                self.backend_health[backend_type] = BackendHealth.FAILED
                # Track error (T086)
                self.metrics.record_query(backend_type, from_cache=False, error=True)
                errors.append(f"{backend_type.value}: {e}")
                # Don't retry authentication errors - they're configuration issues
                continue

            except RateLimitError as e:
                logger.warning(f"Rate limit hit for {backend_type.value}: {e}")
                self.backend_health[backend_type] = BackendHealth.RATE_LIMITED
                # Track error (T087)
                self.metrics.record_query(backend_type, from_cache=False, error=True)
                if e.retry_after:
                    self.rate_limit_until[backend_type] = datetime.now(UTC) + timedelta(
                        seconds=e.retry_after
                    )
                errors.append(f"{backend_type.value}: {e}")
                continue

            except (BackendError, NetworkError) as e:
                logger.warning(f"Backend error for {backend_type.value}: {e}")
                self.backend_health[backend_type] = BackendHealth.FAILED
                # Track error (T085)
                self.metrics.record_query(backend_type, from_cache=False, error=True)
                errors.append(f"{backend_type.value}: {e}")
                continue

        # All backends failed
        error_msg = f"All backends failed. Errors: {'; '.join(errors)}"
        logger.error(error_msg)
        raise BackendError("all", message=error_msg)

    def _get_available_backends(self, request: SearchRequest) -> list[SearchBackendType]:
        """
        Get list of available backends in priority order.

        Filters out:
        - Rate-limited backends (until retry time)
        - Failed backends (temporarily)
        - Backends not matching user preference

        Args:
            request: Search request (may specify backend preference)

        Returns:
            List of available backends in priority order
        """
        # If user specified a preference, try that first
        if request.backend_preference and request.backend_preference in self.backends:
            preferred = [request.backend_preference]
            others = [b for b in self.priority_order if b != request.backend_preference]
            candidates = preferred + others
        else:
            candidates = self.priority_order

        # Filter out unavailable backends
        available = []
        for backend in candidates:
            # Skip if backend not initialized
            if backend not in self.backends:
                continue

            # Check if rate limited
            if backend in self.rate_limit_until:
                if datetime.now(UTC) < self.rate_limit_until[backend]:
                    logger.debug(f"Skipping {backend.value}: rate limited")
                    continue
                else:
                    # Rate limit expired, reset
                    del self.rate_limit_until[backend]
                    self.backend_health[backend] = BackendHealth.ACTIVE

            available.append(backend)

        return available

    def _process_results(
        self,
        response: SearchResponse,
        request: SearchRequest,
    ) -> SearchResponse:
        """
        Process results: scoring, ranking, filtering.

        Args:
            response: Raw search response
            request: Original search request

        Returns:
            Processed SearchResponse with scored and ranked results
        """
        # Calculate relevance scores
        for result in response.results:
            result.relevance_score = self._calculate_relevance(result, request.query)

        # Filter by domain (allowed/blocked lists)
        response.results = self._filter_by_domains(response.results, request)

        # Filter by minimum relevance
        min_score = search_backend_settings.search_min_relevance_score
        response.results = [
            r for r in response.results if r.relevance_score >= min_score
        ]

        # Remove duplicates (same URL)
        seen_urls = set()
        unique_results = []
        for result in response.results:
            if result.url not in seen_urls:
                seen_urls.add(result.url)
                unique_results.append(result)
        response.results = unique_results

        # Sort by relevance score (descending)
        response.results.sort(key=lambda r: r.relevance_score, reverse=True)

        # Limit to top N results
        top_n = search_backend_settings.search_default_top_results
        response.results = response.results[:top_n]

        return response

    def _filter_by_domains(
        self,
        results: list[SearchResult],
        request: SearchRequest,
    ) -> list[SearchResult]:
        """
        Filter results by allowed/blocked domain lists.

        Args:
            results: List of search results to filter
            request: Original search request with domain filters

        Returns:
            Filtered list of search results
        """
        filtered = []

        for result in results:
            # Check blocked domains first (highest priority)
            if request.blocked_domains:
                if any(blocked in result.domain for blocked in request.blocked_domains):
                    logger.debug(f"Blocking result from {result.domain} (matches blocked list)")
                    continue

            # Check allowed domains (if specified, only include these)
            if request.allowed_domains:
                if not any(allowed in result.domain for allowed in request.allowed_domains):
                    logger.debug(f"Skipping result from {result.domain} (not in allowed list)")
                    continue

            filtered.append(result)

        return filtered

    def _calculate_relevance(self, result: SearchResult, query: str) -> float:
        """
        Calculate relevance score for a search result.

        Scoring factors:
        - Domain reputation: +0.3 for high-quality domains
        - Documentation content: +0.25 for official docs
        - Recency: +0.2 if published within 30 days
        - Title keyword match: +0.2 if query keywords in title
        - Snippet keyword match: +0.1 if query keywords in snippet
        - Backend score: Use if available (Tavily provides this)

        Args:
            result: Search result to score
            query: Original search query

        Returns:
            Relevance score (0.0-1.0)
        """
        score = 0.0

        # Use backend score as base if available
        if result.backend_score is not None:
            score = result.backend_score
        else:
            score = 0.3  # Base score

        # Official documentation domain whitelist (US2 - T053)
        official_doc_domains = [
            "docs.python.org",
            "pve.proxmox.com",
            "proxmox.com/en/proxmox-ve",
            "home-assistant.io/docs",
            "docs.docker.com",
            "kubernetes.io/docs",
            "docs.ceph.com",
            "wiki.archlinux.org",
            "docs.ansible.com",
            "grafana.com/docs",
            "prometheus.io/docs",
        ]

        # Domain reputation scoring
        high_quality_domains = [
            "github.com",
            "docs.python.org",
            "stackoverflow.com",
            "proxmox.com",
            "home-assistant.io",
            "docker.com",
            "kubernetes.io",
        ]
        if any(domain in result.domain for domain in high_quality_domains):
            score += 0.3

        # Documentation content type bonus (US2 - T052)
        if result.content_type == ContentType.DOCUMENTATION:
            score += 0.25
            # Extra bonus for official documentation domains
            if any(doc_domain in result.domain for doc_domain in official_doc_domains):
                score += 0.15  # Total +0.40 for official docs

        # Recency scoring (published within 30 days)
        if result.published_date:
            age_days = (datetime.now(UTC) - result.published_date).days
            if age_days <= 30:
                score += 0.2

        # Keyword matching in title
        query_keywords = set(query.lower().split())
        title_words = set(result.title.lower().split())
        if query_keywords & title_words:  # Intersection
            score += 0.2

        # Keyword matching in snippet
        snippet_words = set(result.snippet.lower().split())
        if query_keywords & snippet_words:
            score += 0.1

        # Normalize to 0.0-1.0 range
        return min(1.0, score)

    async def multi_source_search(
        self,
        request: SearchRequest,
        backends: list[SearchBackendType] | None = None,
    ) -> SearchResponse:
        """
        Query multiple backends simultaneously and aggregate results (T065-T066).

        This method enables cross-referencing information from multiple sources
        for high-stakes decisions where verification is critical.

        Workflow:
        1. Query multiple backends in parallel
        2. Aggregate results from all sources
        3. Deduplicate by URL (track which backends returned each result)
        4. Apply relevance scoring
        5. Sort by relevance

        Args:
            request: Search request
            backends: List of backends to query (defaults to all available)

        Returns:
            SearchResponse with aggregated results and source attribution

        Raises:
            BackendError: If all backends fail
        """
        # Determine which backends to query
        if backends is None:
            # Use all available backends
            backend_list = self._get_available_backends(request)
        else:
            # Filter to only available backends from the specified list
            available = self._get_available_backends(request)
            backend_list = [b for b in backends if b in available]

        if not backend_list:
            raise BackendError("all", message="No backends available for multi-source search")

        logger.info(
            f"Multi-source search: querying {len(backend_list)} backends ({[b.value for b in backend_list]})"
        )

        # Query all backends in parallel
        start_time = time.time()
        tasks = []
        for backend_type in backend_list:
            backend = self.backends[backend_type]
            tasks.append(self._query_backend_safe(backend, backend_type, request))

        # Wait for all queries to complete
        responses = await asyncio.gather(*tasks, return_exceptions=True)

        # Aggregate results from successful queries
        aggregated_results: dict[str, SearchResult] = {}  # URL -> SearchResult
        successful_backends = []

        for backend_type, response in zip(backend_list, responses):
            if isinstance(response, Exception):
                logger.warning(f"Backend {backend_type.value} failed: {response}")
                continue

            if isinstance(response, SearchResponse):
                successful_backends.append(backend_type)

                for result in response.results:
                    url = result.url

                    if url in aggregated_results:
                        # Deduplicate: same URL found in multiple backends
                        # Track source attribution
                        if backend_type not in aggregated_results[url].source_backends:
                            aggregated_results[url].source_backends.append(backend_type)

                        # Keep the result with higher backend_score if available
                        if result.backend_score is not None:
                            if (
                                aggregated_results[url].backend_score is None
                                or result.backend_score > aggregated_results[url].backend_score
                            ):
                                aggregated_results[url].backend_score = result.backend_score
                    else:
                        # New result
                        result.source_backends = [backend_type]
                        aggregated_results[url] = result

        if not successful_backends:
            raise BackendError("all", message="All backends failed in multi-source search")

        # Convert to list
        results = list(aggregated_results.values())

        # Apply relevance scoring and ranking
        for result in results:
            result.relevance_score = self._calculate_relevance(result, request.query)

        # Filter by minimum relevance
        min_score = search_backend_settings.search_min_relevance_score
        results = [r for r in results if r.relevance_score >= min_score]

        # Sort by relevance score (descending)
        results.sort(key=lambda r: r.relevance_score, reverse=True)

        # Limit to top N results
        top_n = search_backend_settings.search_default_top_results
        results = results[:top_n]

        execution_time_ms = (time.time() - start_time) * 1000

        # Determine primary backend (most results contributed)
        backend_contributions = {}
        for result in results:
            for backend in result.source_backends:
                backend_contributions[backend] = backend_contributions.get(backend, 0) + 1

        primary_backend = (
            max(backend_contributions.items(), key=lambda x: x[1])[0]
            if backend_contributions
            else successful_backends[0]
        )

        logger.info(
            f"Multi-source search completed: {len(results)} unique results from "
            f"{len(successful_backends)} backends in {execution_time_ms:.0f}ms"
        )

        return SearchResponse(
            query=request.query,
            backend_used=primary_backend,  # Primary backend that contributed most
            results=results,
            total_results=len(results),
            execution_time_ms=execution_time_ms,
            from_cache=False,
            cache_key=None,
        )

    async def _query_backend_safe(
        self,
        backend: BaseSearchBackend,
        backend_type: SearchBackendType,
        request: SearchRequest,
    ) -> SearchResponse | Exception:
        """
        Query a backend with exception handling.

        Returns:
            SearchResponse on success, Exception on failure
        """
        try:
            return await backend.search(request)
        except Exception as e:
            logger.debug(f"Backend {backend_type.value} query failed: {e}")
            return e

    async def get_health_status(self) -> dict:
        """
        Get health status of all backends.

        Returns:
            Dictionary mapping backend to health status
        """
        return {
            backend.value: status.value
            for backend, status in self.backend_health.items()
        }
