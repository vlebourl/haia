"""
Base interface and utilities for search backends.

Provides abstract base class for backend implementations and common utilities
for query normalization, domain extraction, and content type detection.
"""

import re
from abc import ABC, abstractmethod
from urllib.parse import urlparse

from haia.models.search import ContentType, SearchRequest, SearchResponse


# ============================================================================
# Abstract Base Interface (T011)
# ============================================================================

class BaseSearchBackend(ABC):
    """
    Abstract base class for search backend implementations.

    All search backends (Brave, DuckDuckGo, Google CSE, Tavily) must implement
    this interface to ensure consistent behavior and enable automatic failover.
    """

    @abstractmethod
    async def search(self, request: SearchRequest) -> SearchResponse:
        """
        Execute search query and return normalized results.

        Args:
            request: Search request with query and optional filters

        Returns:
            SearchResponse with normalized results

        Raises:
            RateLimitError: When backend rate limit is exceeded
            BackendError: When backend returns an error
            NetworkError: When network connection fails
        """
        pass

    @abstractmethod
    async def health_check(self) -> bool:
        """
        Check if backend is healthy and available.

        Returns:
            True if backend is operational, False otherwise
        """
        pass

    @property
    @abstractmethod
    def backend_type(self) -> str:
        """Return backend identifier (e.g., 'brave', 'duckduckgo')."""
        pass


# ============================================================================
# Utility Functions (T013-T015)
# ============================================================================

def normalize_query(query: str) -> str:
    """
    Normalize search query for consistent caching and comparison.

    Normalization steps:
    1. Convert to lowercase
    2. Strip leading/trailing whitespace
    3. Replace multiple spaces with single space
    4. Remove special characters (keep alphanumeric, spaces, hyphens)

    Args:
        query: Raw search query string

    Returns:
        Normalized query string

    Example:
        >>> normalize_query("  Latest   Proxmox-VE Version?? ")
        'latest proxmox-ve version'
    """
    # Convert to lowercase and strip whitespace
    normalized = query.lower().strip()

    # Replace multiple spaces with single space
    normalized = re.sub(r"\s+", " ", normalized)

    # Remove special characters except alphanumeric, spaces, and hyphens
    normalized = re.sub(r"[^a-z0-9\s\-]", "", normalized)

    return normalized


def extract_domain(url: str) -> str:
    """
    Extract domain name from URL.

    Args:
        url: Full URL string

    Returns:
        Domain name (e.g., 'proxmox.com')

    Example:
        >>> extract_domain("https://www.proxmox.com/en/news/article")
        'proxmox.com'
        >>> extract_domain("http://docs.python.org/3/library/")
        'docs.python.org'
    """
    try:
        parsed = urlparse(url)
        domain = parsed.netloc

        # Remove 'www.' prefix if present
        if domain.startswith("www."):
            domain = domain[4:]

        return domain
    except Exception:
        # If parsing fails, return empty string
        return ""


def detect_content_type(url: str, title: str = "") -> ContentType:
    """
    Detect content type based on URL patterns and title keywords.

    Detection rules:
    - DOCUMENTATION: docs.*, /documentation/, /manual/, /guide/
    - CODE: github.com, gitlab.com, /blob/, /src/
    - FORUM: forum.*, reddit.com, stackoverflow.com
    - VIDEO: youtube.com, vimeo.com, .mp4, .webm
    - BLOG: blog.*, /blog/, medium.com
    - NEWS: /news/, /press-release/, /announcement/
    - UNKNOWN: Default if no pattern matches

    Args:
        url: Full URL string
        title: Optional title for additional context

    Returns:
        ContentType enum value

    Example:
        >>> detect_content_type("https://docs.python.org/3/library/")
        ContentType.DOCUMENTATION
        >>> detect_content_type("https://github.com/anthropics/claude-code")
        ContentType.CODE
    """
    url_lower = url.lower()
    title_lower = title.lower()

    # Documentation patterns
    if any(
        pattern in url_lower
        for pattern in [
            "docs.",
            "/docs/",
            "/documentation/",
            "/manual/",
            "/guide/",
            "/reference/",
            "/api/",
        ]
    ):
        return ContentType.DOCUMENTATION

    # Code repository patterns
    if any(
        pattern in url_lower
        for pattern in [
            "github.com",
            "gitlab.com",
            "bitbucket.org",
            "/blob/",
            "/src/",
            "/tree/",
        ]
    ):
        return ContentType.CODE

    # Forum patterns
    if any(
        pattern in url_lower
        for pattern in [
            "forum.",
            "/forum/",
            "reddit.com",
            "stackoverflow.com",
            "stackexchange.com",
        ]
    ):
        return ContentType.FORUM

    # Video patterns
    if any(
        pattern in url_lower
        for pattern in [
            "youtube.com",
            "youtu.be",
            "vimeo.com",
            ".mp4",
            ".webm",
            "/watch",
            "/video/",
        ]
    ):
        return ContentType.VIDEO

    # Blog patterns
    if any(
        pattern in url_lower
        for pattern in [
            "blog.",
            "/blog/",
            "medium.com",
            "dev.to",
            "/article/",
            "/post/",
        ]
    ):
        return ContentType.BLOG

    # News patterns
    if any(
        pattern in url_lower
        for pattern in [
            "/news/",
            "/press-release/",
            "/announcement/",
            "news.",
        ]
    ):
        return ContentType.NEWS

    # Check title for additional hints
    if "documentation" in title_lower or "docs" in title_lower:
        return ContentType.DOCUMENTATION

    # Default to unknown
    return ContentType.UNKNOWN


# ============================================================================
# Custom Exceptions
# ============================================================================

class SearchError(Exception):
    """Base exception for search-related errors."""

    pass


class RateLimitError(SearchError):
    """Raised when backend rate limit is exceeded."""

    def __init__(self, backend: str, retry_after: int | None = None):
        self.backend = backend
        self.retry_after = retry_after
        message = f"Rate limit exceeded for {backend}"
        if retry_after:
            message += f". Retry after {retry_after} seconds"
        super().__init__(message)


class BackendError(SearchError):
    """Raised when backend returns an error response."""

    def __init__(self, backend: str, status_code: int | None = None, message: str = ""):
        self.backend = backend
        self.status_code = status_code
        error_message = f"Backend error for {backend}"
        if status_code:
            error_message += f" (HTTP {status_code})"
        if message:
            error_message += f": {message}"
        super().__init__(error_message)


class NetworkError(SearchError):
    """Raised when network connection fails."""

    def __init__(self, backend: str, original_error: Exception):
        self.backend = backend
        self.original_error = original_error
        super().__init__(f"Network error for {backend}: {original_error}")


class AuthenticationError(SearchError):
    """
    Raised when API authentication fails (T086).

    Common causes:
    - Invalid API key
    - Expired API key
    - Missing API credentials
    - Insufficient API permissions
    """

    def __init__(self, backend: str, message: str = "Authentication failed"):
        self.backend = backend
        super().__init__(f"Authentication error for {backend}: {message}")


class QuotaExceededError(RateLimitError):
    """
    Raised when API quota is exceeded (daily/monthly limits).

    Different from rate limiting (requests/second), quota limits are
    typically daily or monthly usage caps.
    """

    def __init__(
        self,
        backend: str,
        quota_type: str = "daily",
        reset_time: str | None = None,
        retry_after: int | None = None,
    ):
        self.quota_type = quota_type
        self.reset_time = reset_time
        # Call parent RateLimitError.__init__ to properly set backend and retry_after
        super().__init__(backend, retry_after)
        # Override message to include quota details
        message = f"{quota_type.capitalize()} quota exceeded for {backend}"
        if reset_time:
            message += f". Resets at {reset_time}"
        self.args = (message,)
