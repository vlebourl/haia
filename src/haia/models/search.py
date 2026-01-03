"""
Pydantic models for web search functionality.

Defines data structures for search requests, results, caching, and metrics.
"""

from datetime import UTC, datetime, timedelta
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, SecretStr


# ============================================================================
# Enums (T004)
# ============================================================================

class SearchBackendType(str, Enum):
    """Available search backend providers."""

    BRAVE = "brave"
    DUCKDUCKGO = "duckduckgo"
    GOOGLE_CSE = "google_cse"
    TAVILY = "tavily"


class TimeRange(str, Enum):
    """Time range filters for search results."""

    ANY = "any"
    DAY = "day"
    WEEK = "week"
    MONTH = "month"
    YEAR = "year"


class ContentType(str, Enum):
    """Type of content in search result."""

    DOCUMENTATION = "documentation"
    FORUM = "forum"
    BLOG = "blog"
    VIDEO = "video"
    CODE = "code"
    NEWS = "news"
    UNKNOWN = "unknown"


# ============================================================================
# Request/Response Models (T005-T007)
# ============================================================================

class SearchRequest(BaseModel):
    """
    User search query with optional filters and backend preferences.

    Used by search tool to execute queries against configured backends.
    """

    query: str = Field(
        ...,
        min_length=1,
        max_length=500,
        description="User's search query text",
    )
    backend_preference: SearchBackendType | None = Field(
        None,
        description="Preferred backend (if None, use selector logic)",
    )
    max_results: int = Field(
        default=10,
        ge=1,
        le=20,
        description="Maximum number of results to fetch from backend",
    )
    time_range: TimeRange = Field(
        default=TimeRange.ANY,
        description="Filter results by publication time",
    )
    allowed_domains: list[str] = Field(
        default_factory=list,
        description="Whitelist of domains to include (empty = no filter)",
    )
    blocked_domains: list[str] = Field(
        default_factory=list,
        description="Blacklist of domains to exclude",
    )
    use_cache: bool = Field(
        default=True,
        description="Whether to use cached results if available",
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "query": "latest version of Proxmox VE 8.x",
                "backend_preference": "brave",
                "max_results": 5,
                "time_range": "month",
                "allowed_domains": ["proxmox.com"],
                "use_cache": True,
            }
        }
    )


class SearchResult(BaseModel):
    """
    Individual search result with metadata and relevance scoring.

    Normalized format across all search backends.
    """

    title: str = Field(..., description="Result title from search backend")
    url: str = Field(..., description="Full URL to the result page")
    snippet: str = Field(..., description="Text snippet/description from search backend")
    domain: str = Field(..., description="Domain name extracted from URL")
    published_date: datetime | None = Field(
        None,
        description="Publication date if available from backend",
    )
    relevance_score: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Calculated relevance score (0.0-1.0)",
    )
    backend_score: float | None = Field(
        None,
        ge=0.0,
        le=1.0,
        description="Original score from backend (if provided)",
    )
    content_type: ContentType = Field(
        default=ContentType.UNKNOWN,
        description="Detected content type",
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "title": "Proxmox VE 8.1 Released",
                "url": "https://www.proxmox.com/en/news/press-releases/proxmox-virtual-environment-8-1",
                "snippet": "Proxmox releases version 8.1 with improved Ceph integration...",
                "domain": "proxmox.com",
                "published_date": "2025-12-15T10:00:00Z",
                "relevance_score": 0.92,
                "backend_score": 0.85,
                "content_type": "news",
            }
        }
    )


class SearchResponse(BaseModel):
    """
    Aggregated search response with results and execution metadata.

    Returned by search tool to agent for context injection.
    """

    query: str = Field(..., description="Original search query")
    backend_used: SearchBackendType = Field(..., description="Backend that executed the search")
    results: list[SearchResult] = Field(
        default_factory=list,
        description="Ranked search results (top N)",
    )
    total_results: int = Field(
        ...,
        ge=0,
        description="Total number of results available from backend",
    )
    execution_time_ms: float = Field(
        ...,
        ge=0.0,
        description="Time taken to execute search (milliseconds)",
    )
    from_cache: bool = Field(..., description="Whether results came from cache")
    cache_key: str | None = Field(None, description="Cache key used (for debugging)")

    @property
    def top_result(self) -> SearchResult | None:
        """Get the highest-ranked result."""
        return self.results[0] if self.results else None

    def format_for_llm(self) -> str:
        """
        Format search results as context for LLM injection.

        Returns markdown-formatted string with top results.
        """
        if not self.results:
            return f"No results found for query: {self.query}"

        lines = [f"# Web Search Results for: {self.query}\n"]
        for i, result in enumerate(self.results[:5], 1):
            lines.append(f"## {i}. {result.title}")
            lines.append(f"**Source**: {result.url}")
            if result.published_date:
                lines.append(f"**Published**: {result.published_date.strftime('%Y-%m-%d')}")
            lines.append(f"**Relevance**: {result.relevance_score:.2f}")
            lines.append(f"\n{result.snippet}\n")

        return "\n".join(lines)

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "query": "latest Proxmox VE version",
                "backend_used": "brave",
                "results": [],
                "total_results": 127,
                "execution_time_ms": 850.5,
                "from_cache": False,
            }
        }
    )


# ============================================================================
# Configuration Models (T008)
# ============================================================================

class SearchBackendConfig(BaseModel):
    """
    Configuration for a search backend provider.

    Loaded from environment variables via pydantic-settings.
    """

    backend_type: SearchBackendType = Field(..., description="Backend identifier")
    enabled: bool = Field(default=True, description="Whether this backend is active")
    api_key: SecretStr | None = Field(None, description="API key for authenticated backends")
    api_endpoint: str | None = Field(None, description="Custom API endpoint URL (if applicable)")
    rate_limit_per_second: float = Field(
        default=1.0,
        gt=0.0,
        description="Max requests per second (for rate limiting)",
    )
    rate_limit_per_day: int = Field(
        default=1000,
        gt=0,
        description="Max requests per day",
    )
    cost_per_query: float = Field(
        default=0.0,
        ge=0.0,
        description="Cost per query in USD",
    )
    timeout_seconds: int = Field(
        default=10,
        gt=0,
        description="HTTP request timeout",
    )
    priority: int = Field(
        default=100,
        ge=0,
        description="Backend priority (lower = higher priority)",
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "backend_type": "brave",
                "enabled": True,
                "api_key": "sk-...",
                "rate_limit_per_second": 15.0,
                "rate_limit_per_day": 2000,
                "cost_per_query": 0.0025,
                "timeout_seconds": 10,
                "priority": 1,
            }
        }
    )


# ============================================================================
# Caching Models (T009)
# ============================================================================

class SearchCache(BaseModel):
    """
    Cached search result with expiration metadata.

    Stored in in-memory cache or Redis.
    """

    query_normalized: str = Field(..., description="Normalized query text (lowercase, stripped)")
    backend: SearchBackendType = Field(..., description="Backend that generated results")
    response: SearchResponse = Field(..., description="Cached search response")
    cached_at: datetime = Field(..., description="When results were cached")
    ttl_seconds: int = Field(..., gt=0, description="Time-to-live in seconds")

    @property
    def is_expired(self) -> bool:
        """Check if cache entry has expired."""
        age = (datetime.now(UTC) - self.cached_at).total_seconds()
        return age > self.ttl_seconds

    @property
    def remaining_ttl(self) -> timedelta:
        """Calculate remaining time until expiration."""
        elapsed = (datetime.now(UTC) - self.cached_at).total_seconds()
        remaining = max(0, self.ttl_seconds - elapsed)
        return timedelta(seconds=remaining)


# ============================================================================
# Metrics Models (T010)
# ============================================================================

class BackendMetrics(BaseModel):
    """Metrics for a single backend."""

    backend: SearchBackendType
    queries_today: int = 0
    queries_this_month: int = 0
    cost_today: float = 0.0
    cost_this_month: float = 0.0
    cache_hits: int = 0
    cache_misses: int = 0
    errors: int = 0
    avg_latency_ms: float = 0.0


class SearchMetrics(BaseModel):
    """
    Aggregated search usage metrics.

    Used for monitoring and budget alerts.
    """

    total_queries_today: int = Field(
        default=0,
        ge=0,
        description="Total searches across all backends today",
    )
    total_queries_month: int = Field(
        default=0,
        ge=0,
        description="Total searches across all backends this month",
    )
    total_cost_today: float = Field(
        default=0.0,
        ge=0.0,
        description="Total cost in USD today",
    )
    total_cost_month: float = Field(
        default=0.0,
        ge=0.0,
        description="Total cost in USD this month",
    )
    cache_hit_rate: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Percentage of queries served from cache",
    )
    backends: list[BackendMetrics] = Field(
        default_factory=list,
        description="Per-backend breakdown",
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "total_queries_today": 150,
                "total_queries_month": 3200,
                "total_cost_today": 0.32,
                "total_cost_month": 6.85,
                "cache_hit_rate": 0.72,
                "backends": [
                    {
                        "backend": "brave",
                        "queries_today": 120,
                        "cost_today": 0.30,
                        "cache_hits": 85,
                        "cache_misses": 35,
                    }
                ],
            }
        }
    )
