"""
Unit tests for search metrics and cost tracking (T080-T081).
"""

import pytest
import tempfile
from pathlib import Path
from unittest.mock import patch
from datetime import datetime, UTC

from haia.services.search.metrics import (
    SearchMetricsService,
    BackendMetrics,
    BudgetAlertLevel,
)
from haia.models.search import SearchBackendType


@pytest.fixture
def temp_metrics_file():
    """Create temporary metrics file for testing."""
    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".json") as f:
        yield Path(f.name)
    Path(f.name).unlink(missing_ok=True)


@pytest.fixture
def metrics_service(temp_metrics_file):
    """Create metrics service with temporary storage."""
    with patch("haia.services.search.metrics.search_backend_settings") as mock_settings:
        mock_settings.search_daily_budget_usd = 1.0
        mock_settings.search_monthly_budget_usd = 10.0
        return SearchMetricsService(storage_path=temp_metrics_file)


class TestBackendMetrics:
    """Test suite for BackendMetrics model."""

    def test_cache_hit_rate_calculation(self):
        """Test cache hit rate calculation."""
        metrics = BackendMetrics(
            backend=SearchBackendType.BRAVE,
            cache_hits=70,
            cache_misses=30,
        )

        assert metrics.cache_hit_rate == 0.7

    def test_cache_hit_rate_zero_queries(self):
        """Test cache hit rate with no queries."""
        metrics = BackendMetrics(backend=SearchBackendType.BRAVE)
        assert metrics.cache_hit_rate == 0.0


class TestSearchMetricsService:
    """Test suite for SearchMetricsService (T080-T081)."""

    def test_initialization(self, metrics_service):
        """Test service initialization."""
        assert metrics_service.current_daily.date == datetime.now(UTC).strftime("%Y-%m-%d")
        assert metrics_service.current_monthly.month == datetime.now(UTC).strftime("%Y-%m")
        assert metrics_service.current_daily.total_queries == 0
        assert metrics_service.current_daily.total_cost_usd == 0.0

    def test_record_query_increments_counter(self, metrics_service):
        """Test recording query increments counters (T080)."""
        metrics_service.record_query(SearchBackendType.BRAVE, from_cache=False)

        assert metrics_service.current_daily.total_queries == 1
        assert SearchBackendType.BRAVE.value in metrics_service.current_daily.backends
        backend_metrics = metrics_service.current_daily.backends[SearchBackendType.BRAVE.value]
        assert backend_metrics.query_count == 1
        assert backend_metrics.cache_misses == 1

    def test_record_cache_hit(self, metrics_service):
        """Test recording cache hit doesn't increment query count (T080)."""
        metrics_service.record_query(SearchBackendType.BRAVE, from_cache=True)

        assert metrics_service.current_daily.total_queries == 0  # Cache hits don't count
        backend_metrics = metrics_service.current_daily.backends[SearchBackendType.BRAVE.value]
        assert backend_metrics.cache_hits == 1
        assert backend_metrics.query_count == 0

    def test_record_error(self, metrics_service):
        """Test recording error increments error counter (T080)."""
        metrics_service.record_query(SearchBackendType.BRAVE, from_cache=False, error=True)

        backend_metrics = metrics_service.current_daily.backends[SearchBackendType.BRAVE.value]
        assert backend_metrics.error_count == 1
        assert backend_metrics.total_cost_usd == 0.0  # Errors don't cost money

    def test_cost_calculation_brave(self, metrics_service):
        """Test cost calculation for Brave backend ($5 per 1000) (T080)."""
        # Brave: $5 per 1000 queries = $0.005 per query
        metrics_service.record_query(SearchBackendType.BRAVE, from_cache=False)

        backend_metrics = metrics_service.current_daily.backends[SearchBackendType.BRAVE.value]
        assert backend_metrics.total_cost_usd == pytest.approx(0.005, rel=1e-6)

    def test_cost_calculation_duckduckgo(self, metrics_service):
        """Test cost calculation for DuckDuckGo (free) (T080)."""
        metrics_service.record_query(SearchBackendType.DUCKDUCKGO, from_cache=False)

        backend_metrics = metrics_service.current_daily.backends[SearchBackendType.DUCKDUCKGO.value]
        assert backend_metrics.total_cost_usd == 0.0

    def test_cost_calculation_tavily(self, metrics_service):
        """Test cost calculation for Tavily ($1 per 1000) (T080)."""
        # Tavily: $1 per 1000 queries = $0.001 per query
        metrics_service.record_query(SearchBackendType.TAVILY, from_cache=False)

        backend_metrics = metrics_service.current_daily.backends[SearchBackendType.TAVILY.value]
        assert backend_metrics.total_cost_usd == pytest.approx(0.001, rel=1e-6)

    def test_cost_calculation_google_cse(self, metrics_service):
        """Test cost calculation for Google CSE ($5 per 1000) (T080)."""
        # Google CSE: $5 per 1000 queries = $0.005 per query
        metrics_service.record_query(SearchBackendType.GOOGLE_CSE, from_cache=False)

        backend_metrics = metrics_service.current_daily.backends[SearchBackendType.GOOGLE_CSE.value]
        assert backend_metrics.total_cost_usd == pytest.approx(0.005, rel=1e-6)

    def test_daily_budget_warning_at_80_percent(self, metrics_service):
        """Test budget warning alert at 80% threshold (T081)."""
        # Daily budget: $1.00, so 80% = $0.80
        # Brave: $0.005 per query, so need 160 queries to reach 80%
        for _ in range(160):
            metrics_service.record_query(SearchBackendType.BRAVE, from_cache=False)

        summary = metrics_service.get_summary()

        # Should have at least one warning alert
        assert len(summary["alerts"]) > 0
        assert any(alert["level"] == "warning" and alert["period"] == "daily" for alert in summary["alerts"])

        # Verify percent
        assert summary["budgets"]["daily"]["percent_used"] >= 80.0

    def test_daily_budget_critical_at_95_percent(self, metrics_service):
        """Test budget critical alert at 95% threshold (T081)."""
        # Daily budget: $1.00, so 95% = $0.95
        # Brave: $0.005 per query, so need 190 queries to reach 95%
        for _ in range(190):
            metrics_service.record_query(SearchBackendType.BRAVE, from_cache=False)

        summary = metrics_service.get_summary()

        # Should have critical alert
        assert any(alert["level"] == "critical" and alert["period"] == "daily" for alert in summary["alerts"])

        # Verify percent
        assert summary["budgets"]["daily"]["percent_used"] >= 95.0

    def test_monthly_budget_warning(self, metrics_service):
        """Test monthly budget warning alert (T081)."""
        # Monthly budget: $10.00, so 80% = $8.00
        # Brave: $0.005 per query, so need 1600 queries
        for _ in range(1600):
            metrics_service.record_query(SearchBackendType.BRAVE, from_cache=False)

        summary = metrics_service.get_summary()

        # Should have monthly warning
        assert any(alert["level"] == "warning" and alert["period"] == "monthly" for alert in summary["alerts"])

    def test_no_alerts_under_threshold(self, metrics_service):
        """Test no alerts when under 80% threshold (T081)."""
        # Record just a few queries (well under 80%)
        for _ in range(10):
            metrics_service.record_query(SearchBackendType.BRAVE, from_cache=False)

        summary = metrics_service.get_summary()

        # Should have no alerts
        assert len(summary["alerts"]) == 0

    def test_get_summary_structure(self, metrics_service):
        """Test get_summary returns complete structure (T080)."""
        metrics_service.record_query(SearchBackendType.BRAVE, from_cache=False)
        metrics_service.record_query(SearchBackendType.BRAVE, from_cache=True)
        metrics_service.record_query(SearchBackendType.DUCKDUCKGO, from_cache=False)

        summary = metrics_service.get_summary()

        # Verify structure
        assert "daily" in summary
        assert "monthly" in summary
        assert "budgets" in summary
        assert "alerts" in summary

        # Verify daily data
        assert summary["daily"]["total_queries"] == 2  # Cache hits don't count
        assert "backends" in summary["daily"]
        assert "brave" in summary["daily"]["backends"]
        assert "duckduckgo" in summary["daily"]["backends"]

        # Verify budget data
        assert "daily" in summary["budgets"]
        assert "monthly" in summary["budgets"]
        assert "limit_usd" in summary["budgets"]["daily"]
        assert "used_usd" in summary["budgets"]["daily"]
        assert "remaining_usd" in summary["budgets"]["daily"]
        assert "percent_used" in summary["budgets"]["daily"]

    def test_cache_hit_rate_in_summary(self, metrics_service):
        """Test cache hit rate calculation in summary (T080)."""
        # 7 hits, 3 misses = 70% hit rate
        for _ in range(7):
            metrics_service.record_query(SearchBackendType.BRAVE, from_cache=True)
        for _ in range(3):
            metrics_service.record_query(SearchBackendType.BRAVE, from_cache=False)

        summary = metrics_service.get_summary()

        brave_metrics = summary["daily"]["backends"]["brave"]
        assert brave_metrics["cache_hit_rate"] == pytest.approx(0.7, rel=1e-2)

    def test_monthly_aggregation(self, metrics_service):
        """Test monthly metrics aggregate daily totals (T080)."""
        # Record queries
        for _ in range(50):
            metrics_service.record_query(SearchBackendType.BRAVE, from_cache=False)

        # Verify monthly total includes daily
        assert metrics_service.current_monthly.total_queries >= 50
        assert metrics_service.current_monthly.total_cost_usd >= 0.25  # 50 * 0.005
