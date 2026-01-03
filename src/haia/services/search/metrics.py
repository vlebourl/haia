"""
Search metrics and cost tracking service.

Tracks query counts, costs, and provides budget alerts for multi-backend search.
"""

import json
import logging
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from haia.config import search_backend_settings
from haia.models.search import SearchBackendType

logger = logging.getLogger(__name__)


# Backend cost configuration (USD per 1000 queries)
BACKEND_COSTS = {
    SearchBackendType.BRAVE: 5.0,  # $5 per 1000 queries
    SearchBackendType.DUCKDUCKGO: 0.0,  # Free
    SearchBackendType.TAVILY: 1.0,  # $1 per 1000 queries (AI-optimized tier)
    SearchBackendType.GOOGLE_CSE: 5.0,  # $5 per 1000 queries (beyond free 100/day)
}


class BudgetAlertLevel(str, Enum):
    """Budget alert severity levels."""

    OK = "ok"
    WARNING = "warning"  # 80% threshold
    CRITICAL = "critical"  # 95% threshold


class BackendMetrics(BaseModel):
    """Metrics for a single backend."""

    backend: SearchBackendType = Field(..., description="Backend identifier")
    query_count: int = Field(default=0, description="Total queries made")
    cache_hits: int = Field(default=0, description="Cache hits")
    cache_misses: int = Field(default=0, description="Cache misses")
    error_count: int = Field(default=0, description="Failed queries")
    total_cost_usd: float = Field(default=0.0, description="Total cost in USD")

    @property
    def cache_hit_rate(self) -> float:
        """Calculate cache hit rate (0.0-1.0)."""
        total = self.cache_hits + self.cache_misses
        return self.cache_hits / total if total > 0 else 0.0


class DailyMetrics(BaseModel):
    """Daily aggregated metrics."""

    date: str = Field(..., description="Date in YYYY-MM-DD format")
    total_queries: int = Field(default=0, description="Total queries across all backends")
    total_cost_usd: float = Field(default=0.0, description="Total cost in USD")
    backends: dict[str, BackendMetrics] = Field(
        default_factory=dict,
        description="Per-backend metrics",
    )


class MonthlyMetrics(BaseModel):
    """Monthly aggregated metrics."""

    month: str = Field(..., description="Month in YYYY-MM format")
    total_queries: int = Field(default=0, description="Total queries across all backends")
    total_cost_usd: float = Field(default=0.0, description="Total cost in USD")
    daily_breakdown: list[DailyMetrics] = Field(
        default_factory=list,
        description="Daily metrics within the month",
    )


class BudgetAlert(BaseModel):
    """Budget alert notification."""

    level: BudgetAlertLevel = Field(..., description="Alert severity")
    period: str = Field(..., description="Period (daily or monthly)")
    current_cost: float = Field(..., description="Current cost in USD")
    budget_limit: float = Field(..., description="Budget limit in USD")
    percent_used: float = Field(..., description="Percentage of budget used")
    message: str = Field(..., description="Human-readable alert message")


class SearchMetricsService:
    """
    Search metrics tracking and cost management service (T069-T073).

    Features:
    - Per-backend query counting
    - Daily and monthly aggregation
    - Cost calculation based on backend pricing
    - Budget alerts at 80% (warning) and 95% (critical)
    - Cache hit/miss tracking
    - Persistent storage (JSON file)
    """

    def __init__(self, storage_path: Path | None = None):
        """
        Initialize metrics service.

        Args:
            storage_path: Path to metrics storage file (default: ~/.haia/search_metrics.json)
        """
        if storage_path is None:
            storage_path = Path.home() / ".haia" / "search_metrics.json"

        self.storage_path = storage_path
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)

        # Load existing metrics
        self.current_daily: DailyMetrics = self._load_or_create_daily()
        self.current_monthly: MonthlyMetrics = self._load_or_create_monthly()

        logger.info(f"SearchMetricsService initialized (storage: {self.storage_path})")

    def _load_or_create_daily(self) -> DailyMetrics:
        """Load or create daily metrics for today."""
        today = datetime.now(UTC).strftime("%Y-%m-%d")

        if self.storage_path.exists():
            try:
                with open(self.storage_path) as f:
                    data = json.load(f)

                # Check if we have data for today
                daily_data = data.get("daily", {})
                if daily_data.get("date") == today:
                    # Reconstruct BackendMetrics
                    backends = {}
                    for backend_name, backend_dict in daily_data.get("backends", {}).items():
                        backends[backend_name] = BackendMetrics(**backend_dict)

                    return DailyMetrics(
                        date=daily_data["date"],
                        total_queries=daily_data.get("total_queries", 0),
                        total_cost_usd=daily_data.get("total_cost_usd", 0.0),
                        backends=backends,
                    )
            except Exception as e:
                logger.warning(f"Failed to load daily metrics: {e}")

        # Create new daily metrics
        return DailyMetrics(date=today, backends={})

    def _load_or_create_monthly(self) -> MonthlyMetrics:
        """Load or create monthly metrics for current month."""
        this_month = datetime.now(UTC).strftime("%Y-%m")

        if self.storage_path.exists():
            try:
                with open(self.storage_path) as f:
                    data = json.load(f)

                monthly_data = data.get("monthly", {})
                if monthly_data.get("month") == this_month:
                    return MonthlyMetrics(**monthly_data)
            except Exception as e:
                logger.warning(f"Failed to load monthly metrics: {e}")

        # Create new monthly metrics
        return MonthlyMetrics(month=this_month)

    def _save_metrics(self):
        """Persist metrics to storage."""
        try:
            data = {
                "daily": self.current_daily.model_dump(),
                "monthly": self.current_monthly.model_dump(),
                "last_updated": datetime.now(UTC).isoformat(),
            }

            with open(self.storage_path, "w") as f:
                json.dump(data, f, indent=2)

        except Exception as e:
            logger.error(f"Failed to save metrics: {e}")

    def record_query(
        self,
        backend: SearchBackendType,
        from_cache: bool = False,
        error: bool = False,
    ):
        """
        Record a search query (T069-T070).

        Args:
            backend: Backend that handled the query
            from_cache: Whether result came from cache
            error: Whether query failed
        """
        # Check if we need to roll over to new day/month
        today = datetime.now(UTC).strftime("%Y-%m-%d")
        this_month = datetime.now(UTC).strftime("%Y-%m")

        if self.current_daily.date != today:
            # Archive current day to monthly, start new day
            self.current_monthly.daily_breakdown.append(self.current_daily)
            self.current_daily = DailyMetrics(date=today, backends={})

        if self.current_monthly.month != this_month:
            # Start new month (could archive old month if needed)
            self.current_monthly = MonthlyMetrics(month=this_month)

        # Get or create backend metrics
        backend_name = backend.value
        if backend_name not in self.current_daily.backends:
            self.current_daily.backends[backend_name] = BackendMetrics(backend=backend)

        metrics = self.current_daily.backends[backend_name]

        # Update counters
        if from_cache:
            metrics.cache_hits += 1
        else:
            metrics.cache_misses += 1
            metrics.query_count += 1

        if error:
            metrics.error_count += 1

        # Calculate cost (T071)
        cost_per_query = BACKEND_COSTS.get(backend, 0.0) / 1000.0
        query_cost = cost_per_query if not from_cache and not error else 0.0
        metrics.total_cost_usd += query_cost

        # Update daily totals
        if not from_cache:
            self.current_daily.total_queries += 1
        self.current_daily.total_cost_usd = sum(
            m.total_cost_usd for m in self.current_daily.backends.values()
        )

        # Update monthly totals
        self.current_monthly.total_queries = sum(
            day.total_queries for day in self.current_monthly.daily_breakdown
        ) + self.current_daily.total_queries

        self.current_monthly.total_cost_usd = sum(
            day.total_cost_usd for day in self.current_monthly.daily_breakdown
        ) + self.current_daily.total_cost_usd

        # Save to disk
        self._save_metrics()

        # Check budget alerts (T072)
        self._check_budget_alerts()

    def _check_budget_alerts(self):
        """
        Check if budget thresholds have been exceeded (T072).

        Alerts at 80% (warning) and 95% (critical) of daily/monthly budgets.
        """
        alerts = []

        # Daily budget check
        daily_budget = search_backend_settings.search_daily_budget_usd
        daily_percent = (self.current_daily.total_cost_usd / daily_budget * 100) if daily_budget > 0 else 0

        if daily_percent >= 95:
            alerts.append(
                BudgetAlert(
                    level=BudgetAlertLevel.CRITICAL,
                    period="daily",
                    current_cost=self.current_daily.total_cost_usd,
                    budget_limit=daily_budget,
                    percent_used=daily_percent,
                    message=f"CRITICAL: Daily search budget at {daily_percent:.1f}% "
                    f"(${self.current_daily.total_cost_usd:.2f} / ${daily_budget:.2f})",
                )
            )
        elif daily_percent >= 80:
            alerts.append(
                BudgetAlert(
                    level=BudgetAlertLevel.WARNING,
                    period="daily",
                    current_cost=self.current_daily.total_cost_usd,
                    budget_limit=daily_budget,
                    percent_used=daily_percent,
                    message=f"WARNING: Daily search budget at {daily_percent:.1f}% "
                    f"(${self.current_daily.total_cost_usd:.2f} / ${daily_budget:.2f})",
                )
            )

        # Monthly budget check
        monthly_budget = search_backend_settings.search_monthly_budget_usd
        monthly_percent = (
            (self.current_monthly.total_cost_usd / monthly_budget * 100) if monthly_budget > 0 else 0
        )

        if monthly_percent >= 95:
            alerts.append(
                BudgetAlert(
                    level=BudgetAlertLevel.CRITICAL,
                    period="monthly",
                    current_cost=self.current_monthly.total_cost_usd,
                    budget_limit=monthly_budget,
                    percent_used=monthly_percent,
                    message=f"CRITICAL: Monthly search budget at {monthly_percent:.1f}% "
                    f"(${self.current_monthly.total_cost_usd:.2f} / ${monthly_budget:.2f})",
                )
            )
        elif monthly_percent >= 80:
            alerts.append(
                BudgetAlert(
                    level=BudgetAlertLevel.WARNING,
                    period="monthly",
                    current_cost=self.current_monthly.total_cost_usd,
                    budget_limit=monthly_budget,
                    percent_used=monthly_percent,
                    message=f"WARNING: Monthly search budget at {monthly_percent:.1f}% "
                    f"(${self.current_monthly.total_cost_usd:.2f} / ${monthly_budget:.2f})",
                )
            )

        # Log alerts
        for alert in alerts:
            if alert.level == BudgetAlertLevel.CRITICAL:
                logger.error(alert.message)
            elif alert.level == BudgetAlertLevel.WARNING:
                logger.warning(alert.message)

        return alerts

    def get_daily_metrics(self) -> DailyMetrics:
        """Get current daily metrics."""
        return self.current_daily

    def get_monthly_metrics(self) -> MonthlyMetrics:
        """Get current monthly metrics."""
        return self.current_monthly

    def get_summary(self) -> dict[str, Any]:
        """
        Get metrics summary for API responses.

        Returns:
            Dictionary with daily and monthly summaries
        """
        # Calculate overall cache hit rate
        total_cache_hits = sum(m.cache_hits for m in self.current_daily.backends.values())
        total_cache_misses = sum(m.cache_misses for m in self.current_daily.backends.values())
        total_cache_ops = total_cache_hits + total_cache_misses
        overall_cache_hit_rate = total_cache_hits / total_cache_ops if total_cache_ops > 0 else 0.0

        # Get budget alerts
        alerts = self._check_budget_alerts()

        return {
            "daily": {
                "date": self.current_daily.date,
                "total_queries": self.current_daily.total_queries,
                "total_cost_usd": round(self.current_daily.total_cost_usd, 4),
                "cache_hit_rate": round(overall_cache_hit_rate, 2),
                "backends": {
                    name: {
                        "queries": metrics.query_count,
                        "cache_hits": metrics.cache_hits,
                        "cache_misses": metrics.cache_misses,
                        "errors": metrics.error_count,
                        "cost_usd": round(metrics.total_cost_usd, 4),
                        "cache_hit_rate": round(metrics.cache_hit_rate, 2),
                    }
                    for name, metrics in self.current_daily.backends.items()
                },
            },
            "monthly": {
                "month": self.current_monthly.month,
                "total_queries": self.current_monthly.total_queries,
                "total_cost_usd": round(self.current_monthly.total_cost_usd, 4),
                "days_tracked": len(self.current_monthly.daily_breakdown) + 1,  # +1 for current day
            },
            "budgets": {
                "daily": {
                    "limit_usd": search_backend_settings.search_daily_budget_usd,
                    "used_usd": round(self.current_daily.total_cost_usd, 4),
                    "remaining_usd": round(
                        search_backend_settings.search_daily_budget_usd - self.current_daily.total_cost_usd,
                        4,
                    ),
                    "percent_used": round(
                        (self.current_daily.total_cost_usd / search_backend_settings.search_daily_budget_usd * 100)
                        if search_backend_settings.search_daily_budget_usd > 0
                        else 0,
                        1,
                    ),
                },
                "monthly": {
                    "limit_usd": search_backend_settings.search_monthly_budget_usd,
                    "used_usd": round(self.current_monthly.total_cost_usd, 4),
                    "remaining_usd": round(
                        search_backend_settings.search_monthly_budget_usd - self.current_monthly.total_cost_usd,
                        4,
                    ),
                    "percent_used": round(
                        (self.current_monthly.total_cost_usd / search_backend_settings.search_monthly_budget_usd * 100)
                        if search_backend_settings.search_monthly_budget_usd > 0
                        else 0,
                        1,
                    ),
                },
            },
            "alerts": [alert.model_dump() for alert in alerts],
        }
