"""
Pydantic models for memory consolidation lifecycle.

Defines data structures for memory tier management, priority scoring,
consolidation decisions, and reporting.

Session 14 (US6): Memory Consolidation Lifecycle
"""

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class MemoryTier(str, Enum):
    """
    Memory lifecycle tiers for consolidation (T097).

    Memories flow through tiers based on access patterns and priority:
    SHORT_TERM (new) → LONG_TERM (important) → ARCHIVED (low-priority)
    """

    SHORT_TERM = "short_term"
    LONG_TERM = "long_term"
    ARCHIVED = "archived"


class ConsolidationMetrics(BaseModel):
    """
    Metrics used to calculate memory consolidation priority (T098).

    Priority formula: 0.40 * access_freq + 0.30 * recency_score + 0.30 * confidence
    """

    priority_score: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Overall priority score (0.0-1.0) determining tier placement"
    )
    access_frequency: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Normalized access frequency (access_count / max_access)"
    )
    recency_score: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Recency score from decay function (1.0 = recent, 0.0 = old)"
    )
    confidence_score: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Memory extraction confidence (from original extraction)"
    )
    tier: MemoryTier = Field(
        ...,
        description="Current memory tier assignment"
    )
    last_accessed: datetime | None = Field(
        None,
        description="Timestamp of most recent access (None if never accessed)"
    )
    access_count: int = Field(
        default=0,
        ge=0,
        description="Number of times memory has been retrieved"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "priority_score": 0.75,
                "access_frequency": 0.80,
                "recency_score": 0.65,
                "confidence_score": 0.85,
                "tier": "long_term",
                "last_accessed": "2026-01-02T10:30:00Z",
                "access_count": 12
            }
        }


class ConsolidationDecision(BaseModel):
    """
    Decision to promote, archive, or keep a memory (T099).

    Includes reasoning for observability (P5: Observability).
    """

    memory_id: str = Field(
        ...,
        description="Unique memory identifier"
    )
    current_tier: MemoryTier = Field(
        ...,
        description="Current tier before consolidation"
    )
    recommended_tier: MemoryTier = Field(
        ...,
        description="Recommended tier after consolidation"
    )
    priority_score: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Calculated priority score that determined recommendation"
    )
    reasoning: str = Field(
        ...,
        description="Human-readable explanation of why this decision was made"
    )
    threshold: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Threshold used for decision (promotion: 0.7, archival: 0.2)"
    )
    metrics: ConsolidationMetrics | None = Field(
        None,
        description="Detailed metrics used in priority calculation"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "memory_id": "mem_abc123",
                "current_tier": "short_term",
                "recommended_tier": "long_term",
                "priority_score": 0.78,
                "reasoning": (
                    "High access frequency (12 retrievals) and recent usage "
                    "(last accessed 2 days ago) indicate important memory. "
                    "Priority 0.78 exceeds promotion threshold 0.7."
                ),
                "threshold": 0.7
            }
        }


class ConsolidationReport(BaseModel):
    """
    Summary report of consolidation job execution (T100).

    Tracks how many memories were processed, promoted, archived, or unchanged.
    """

    timestamp: datetime = Field(
        ...,
        description="When consolidation job ran"
    )
    processed_count: int = Field(
        ...,
        ge=0,
        description="Total memories evaluated during consolidation"
    )
    promoted_count: int = Field(
        ...,
        ge=0,
        description="Memories promoted from SHORT_TERM to LONG_TERM"
    )
    archived_count: int = Field(
        ...,
        ge=0,
        description="Memories archived from LONG_TERM to ARCHIVED"
    )
    unchanged_count: int = Field(
        ...,
        ge=0,
        description="Memories that remained in current tier"
    )
    decisions: list[ConsolidationDecision] = Field(
        default_factory=list,
        description="Detailed decision log for all tier changes"
    )
    execution_time_ms: float = Field(
        ...,
        ge=0.0,
        description="Total execution time in milliseconds"
    )

    @property
    def promotion_rate(self) -> float:
        """Calculate percentage of memories promoted."""
        if self.processed_count == 0:
            return 0.0
        return (self.promoted_count / self.processed_count) * 100

    @property
    def archival_rate(self) -> float:
        """Calculate percentage of memories archived."""
        if self.processed_count == 0:
            return 0.0
        return (self.archived_count / self.processed_count) * 100

    def summary(self) -> str:
        """Generate human-readable summary of consolidation run."""
        unchanged_pct = 100 - self.promotion_rate - self.archival_rate
        return (
            f"Consolidation Report ({self.timestamp.isoformat()}):\n"
            f"  Processed: {self.processed_count} memories\n"
            f"  Promoted:  {self.promoted_count} ({self.promotion_rate:.1f}%)\n"
            f"  Archived:  {self.archived_count} ({self.archival_rate:.1f}%)\n"
            f"  Unchanged: {self.unchanged_count} ({unchanged_pct:.1f}%)\n"
            f"  Execution: {self.execution_time_ms:.0f}ms"
        )

    class Config:
        json_schema_extra = {
            "example": {
                "timestamp": "2026-01-03T03:00:00Z",
                "processed_count": 100,
                "promoted_count": 28,
                "archived_count": 19,
                "unchanged_count": 53,
                "decisions": [],
                "execution_time_ms": 1250.5
            }
        }
