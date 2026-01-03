"""
Web search tool for HAIA agent.

Provides PydanticAI @agent.tool function for web search with automatic
intent detection and result formatting.
"""

import logging
import re

from pydantic_ai import RunContext

from haia.config import search_backend_settings
from haia.models.search import SearchRequest
from haia.services.search.cache import SearchCacheService
from haia.services.search.selector import SearchBackendSelector

logger = logging.getLogger(__name__)


# Global selector instance (initialized on first use)
_selector: SearchBackendSelector | None = None


def get_search_selector() -> SearchBackendSelector:
    """
    Get or create global search backend selector.

    Returns:
        SearchBackendSelector instance
    """
    global _selector
    if _selector is None:
        cache = SearchCacheService()
        _selector = SearchBackendSelector(cache=cache)
        logger.info("Search selector initialized")
    return _selector


def should_trigger_search(query: str) -> bool:
    """
    Determine if web search should be automatically triggered.

    Trigger patterns:
    - Explicit: "search the web", "google", "look up online"
    - Version queries: "latest version", "current version", "newest release"
    - Time-sensitive: "recent", "today", "this week", "2026"
    - Error codes: "error [code]", "errno", specific error patterns
    - Documentation: "documentation for", "how to configure", "setup guide"

    Exclusion patterns (skip search):
    - Conceptual questions: "what is", "explain", "why does"
    - Historical: "history of", "who invented"
    - Explicit: "don't search", "answer without searching"

    Args:
        query: User's question or request

    Returns:
        True if search should be triggered, False otherwise
    """
    query_lower = query.lower()

    # Exclusion patterns (high priority - skip search)
    exclusion_patterns = [
        r"(don't|do not|without)\s+(search|searching|google|looking up)",
        r"^(what is|explain|why does|why do|how does)",
        r"(history of|who invented|who created|who discovered)",
    ]

    for pattern in exclusion_patterns:
        if re.search(pattern, query_lower):
            logger.debug(f"Query matches exclusion pattern '{pattern}', skipping search")
            return False

    # Trigger patterns
    trigger_patterns = [
        # Explicit search requests
        r"(search|google|look up|find)\s+(the web|online|internet)",
        r"(search for|google for)",
        # Version and release queries
        r"(latest|newest|current|most recent)\s+(version|release)",
        r"(what is|what's)\s+the\s+(latest|newest|current|recent)\s+(version|release)",
        # Time-sensitive queries
        r"(recent|today|this week|this month|2026|2025)",
        r"(new|updated|announced)\s+(in|this year)",
        # Error and troubleshooting
        r"(error|errno|exception|failed|failure)\s+[a-z0-9\-_]+",
        r"(fix|solve|troubleshoot|debug)\s+.*\s+(error|issue|problem)",
        # Documentation queries
        r"(documentation|docs|guide|tutorial|manual)\s+(for|on)",
        r"(how to|how do I)\s+(configure|setup|install|deploy)",
        # Release notes and changelogs
        r"(release notes|changelog|what's new|new features)",
        # Specific version numbers
        r"\d+\.\d+(\.\d+)?",  # Version numbers like 8.1 or 8.1.2
    ]

    for pattern in trigger_patterns:
        if re.search(pattern, query_lower):
            logger.debug(f"Query matches trigger pattern '{pattern}', enabling search")
            return True

    # Default: don't trigger for general questions
    return False


def is_documentation_query(query: str) -> bool:
    """
    Detect if query is specifically asking for documentation.

    Documentation query patterns (US2 - T054):
    - "documentation for X"
    - "X documentation"
    - "docs for X"
    - "X manual"
    - "guide for X"
    - "how to configure X"
    - "X setup guide"

    Args:
        query: User's question or request

    Returns:
        True if query is asking for documentation, False otherwise
    """
    query_lower = query.lower()

    doc_patterns = [
        r"\b(documentation|docs|manual|guide|tutorial)\s+(for|on|about)\b",
        r"\b(official|proxmox|docker|kubernetes|home assistant)\s+(documentation|docs|guide)\b",
        r"\b(how to|how do I)\s+(configure|setup|install|use|deploy|integrate)\b",
        r"\b(setup|installation|configuration|deployment)\s+(guide|tutorial|manual|docs)\b",
        r"\b(read the docs|rtfd|official docs)\b",
        r"\b(user guide|admin guide|reference manual)\b",
    ]

    for pattern in doc_patterns:
        if re.search(pattern, query_lower):
            logger.debug(f"Query matches documentation pattern '{pattern}'")
            return True

    return False


async def web_search(
    ctx: RunContext,
    query: str,
    max_results: int = 10,
) -> str:
    """
    Search the web for current information, documentation, and troubleshooting.

    This tool enables HAIA to access up-to-date information beyond its training
    data cutoff. Automatically searches multiple backends (Brave Search, DuckDuckGo)
    with failover and caching for cost optimization.

    Use this tool when the user asks about:
    - Latest versions or releases
    - Recent documentation or updates
    - Current troubleshooting solutions
    - Time-sensitive information (today, this week, 2026)
    - Error codes and specific technical issues

    Do NOT use for:
    - General conceptual questions (what is, explain, why)
    - Historical information (history of, who invented)
    - When user explicitly says "don't search" or "without searching"

    Args:
        ctx: PydanticAI run context
        query: Search query (user's question or specific search terms)
        max_results: Maximum number of results to fetch (default: 10)

    Returns:
        Formatted search results as markdown for LLM context
    """
    if not search_backend_settings.search_enabled:
        logger.warning("Web search is disabled in configuration")
        return "Web search is currently disabled. Please enable SEARCH_ENABLED in configuration."

    logger.info(f"Web search triggered: '{query}'")

    try:
        # Detect if this is a documentation query (US2 - T054-T055)
        is_doc_query = is_documentation_query(query)

        # Apply domain filters for documentation queries
        allowed_domains = []
        if is_doc_query:
            # Whitelist official documentation domains for better results
            allowed_domains = [
                "docs.python.org",
                "pve.proxmox.com",
                "proxmox.com",
                "home-assistant.io",
                "docs.docker.com",
                "kubernetes.io",
                "docs.ceph.com",
                "wiki.archlinux.org",
                "docs.ansible.com",
                "grafana.com",
                "prometheus.io",
                "github.com",  # GitHub documentation pages
            ]
            logger.info(f"Documentation query detected, applying domain whitelist ({len(allowed_domains)} domains)")

        # Create search request
        request = SearchRequest(
            query=query,
            max_results=min(max_results, search_backend_settings.search_default_max_results),
            use_cache=True,
            allowed_domains=allowed_domains,
        )

        # Execute search
        selector = get_search_selector()
        response = await selector.search(request)

        # Format results for LLM
        formatted = response.format_for_llm()

        # Add metadata footer
        footer = f"\n\n---\n**Search completed**: {len(response.results)} results from {response.backend_used.value}"
        if response.from_cache:
            footer += " (cached)"
        footer += f" in {response.execution_time_ms:.0f}ms"

        return formatted + footer

    except Exception as e:
        logger.error(f"Web search failed: {e}", exc_info=True)
        return f"Web search failed: {e}. Answering based on my training data (may be outdated)."
