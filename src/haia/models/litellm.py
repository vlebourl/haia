"""LiteLLM-specific Pydantic models.

Session 16: LiteLLM Proxy Integration
Models for LiteLLM configuration, routing, and cost tracking.
"""

from pydantic import BaseModel, Field
from typing import Literal


class BudgetConfiguration(BaseModel):
    """Configuration for LiteLLM budget management."""

    enabled: bool = Field(default=True, description="Enable budget tracking")
    monthly_limit_usd: float = Field(default=50.0, description="Hard stop at this amount")
    alert_threshold_80: bool = Field(default=True, description="Alert at 80% of budget")
    alert_threshold_95: bool = Field(default=True, description="Alert at 95% of budget")
    alert_notification_channel: str = Field(
        default="telegram", description="Where to send alerts"
    )
    budget_reset_day: int = Field(
        default=1, ge=1, le=31, description="Day of month to reset (1-31)"
    )
    over_budget_behavior: Literal["ollama_only", "block_all", "queue_critical"] = Field(
        default="ollama_only",
        description="Behavior when over budget: ollama_only, block_all, queue_critical",
    )
    critical_features: list[str] = Field(
        default_factory=lambda: ["extraction", "relationships"],
        description="Features that always queue when over budget",
    )


class FallbackChainEntry(BaseModel):
    """Single entry in a fallback chain."""

    model_name: str = Field(description="Model identifier (e.g., 'chat-primary')")
    provider: str = Field(description="Provider name (e.g., 'gemini', 'anthropic')")
    priority: int = Field(description="Routing priority (1=first, 2=second, etc.)")
    max_retries: int = Field(default=3, description="Max attempts for this model")
    timeout_seconds: int = Field(
        default=30, description="Request timeout in seconds"
    )


class FallbackChain(BaseModel):
    """Ordered list of models to try for a specific feature."""

    feature: str = Field(description="HAIA feature (e.g., 'chat', 'extraction')")
    entries: list[FallbackChainEntry] = Field(
        description="Ordered by priority (lowest first)"
    )

    def get_primary(self) -> FallbackChainEntry:
        """Return highest priority (priority=1) entry."""
        return min(self.entries, key=lambda e: e.priority)

    def get_fallbacks(self) -> list[FallbackChainEntry]:
        """Return all entries except primary, sorted by priority."""
        return sorted(
            [e for e in self.entries if e.priority > 1], key=lambda e: e.priority
        )
