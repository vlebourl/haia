"""
Search metrics API endpoint.

Provides GET /search/metrics endpoint for monitoring search usage and costs.
"""

from fastapi import APIRouter, Depends
from typing import Annotated

from haia.services.search.metrics import SearchMetricsService
from haia.tools.search import get_search_selector

router = APIRouter(prefix="/search", tags=["search"])


def get_metrics_service() -> SearchMetricsService:
    """
    Dependency to get metrics service from search selector.

    Returns:
        SearchMetricsService instance
    """
    selector = get_search_selector()
    return selector.metrics


@router.get("/metrics")
async def get_search_metrics(
    metrics: Annotated[SearchMetricsService, Depends(get_metrics_service)],
) -> dict:
    """
    Get search metrics and cost tracking data (T075).

    Returns daily and monthly query counts, costs, cache hit rates,
    and budget status.

    **Response includes:**
    - Daily metrics (today's usage)
    - Monthly metrics (current month's usage)
    - Budget status (daily and monthly)
    - Budget alerts (if any thresholds exceeded)

    **Example response:**
    ```json
    {
      "daily": {
        "date": "2026-01-03",
        "total_queries": 42,
        "total_cost_usd": 0.21,
        "cache_hit_rate": 0.65,
        "backends": {
          "brave": {
            "queries": 25,
            "cache_hits": 18,
            "cache_misses": 7,
            "errors": 0,
            "cost_usd": 0.125,
            "cache_hit_rate": 0.72
          },
          "duckduckgo": {
            "queries": 17,
            "cache_hits": 9,
            "cache_misses": 8,
            "errors": 0,
            "cost_usd": 0.0,
            "cache_hit_rate": 0.53
          }
        }
      },
      "monthly": {
        "month": "2026-01",
        "total_queries": 580,
        "total_cost_usd": 2.85,
        "days_tracked": 3
      },
      "budgets": {
        "daily": {
          "limit_usd": 1.0,
          "used_usd": 0.21,
          "remaining_usd": 0.79,
          "percent_used": 21.0
        },
        "monthly": {
          "limit_usd": 10.0,
          "used_usd": 2.85,
          "remaining_usd": 7.15,
          "percent_used": 28.5
        }
      },
      "alerts": []
    }
    ```

    Returns:
        Metrics summary with daily, monthly, and budget data
    """
    return metrics.get_summary()
