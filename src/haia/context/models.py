"""Pydantic models for context optimization.

This module defines type-safe models for:
- Memory deduplication results
- Multi-factor relevance scoring
- Access pattern tracking
- Token budget management
"""

from __future__ import annotations

import math
from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, Field, computed_field, field_validator

if TYPE_CHECKING:
    from haia.embedding.models import RetrievalResult


# ============================================================================
# 1. TruncationStrategy Enum
# ============================================================================


class TruncationStrategy(str, Enum):
    """Strategy for handling token budget overflow."""

    HARD_CUTOFF = "hard_cutoff"  # Stop including memories when budget reached
    TRUNCATE = "truncate"  # Truncate individual memories to fit budget


# ============================================================================
# 2. ScoreWeights Model
# ============================================================================


class ScoreWeights(BaseModel):
    """Weights for multi-factor relevance scoring.

    All weights must sum to 1.0 (±0.01 tolerance) for normalized scoring.
    """

    similarity_weight: float = Field(
        default=0.40, ge=0.0, le=1.0, description="Weight for vector similarity"
    )
    confidence_weight: float = Field(
        default=0.25, ge=0.0, le=1.0, description="Weight for extraction confidence"
    )
    recency_weight: float = Field(
        default=0.20, ge=0.0, le=1.0, description="Weight for recency score"
    )
    frequency_weight: float = Field(
        default=0.15, ge=0.0, le=1.0, description="Weight for frequency score"
    )

    @field_validator("frequency_weight")
    @classmethod
    def validate_weights_sum(cls, v: float, info) -> float:
        """Ensure weights sum to 1.0 (±0.01 tolerance)."""
        # Get all weights
        similarity = info.data.get("similarity_weight", 0.40)
        confidence = info.data.get("confidence_weight", 0.25)
        recency = info.data.get("recency_weight", 0.20)
        frequency = v

        total = similarity + confidence + recency + frequency
        if not (0.99 <= total <= 1.01):
            raise ValueError(
                f"Weights must sum to 1.0 (±0.01), got {total:.3f}. "
                f"Weights: similarity={similarity}, confidence={confidence}, "
                f"recency={recency}, frequency={frequency}"
            )
        return v


# ============================================================================
# 3. RelevanceScore Model
# ============================================================================


class RelevanceScore(BaseModel):
    """Multi-factor relevance score for memory ranking.

    Combines vector similarity, extraction confidence, recency, and frequency
    using configurable weights.
    """

    similarity_score: float = Field(..., ge=0.0, le=1.0, description="Vector similarity")
    confidence_score: float = Field(
        ..., ge=0.0, le=1.0, description="Extraction confidence"
    )
    recency_score: float = Field(..., ge=0.0, le=1.0, description="Recency decay")
    frequency_score: float = Field(
        ..., ge=0.0, le=1.0, description="Log-normalized access count"
    )
    weights: ScoreWeights = Field(
        default_factory=ScoreWeights, description="Scoring weights"
    )

    @computed_field
    @property
    def composite_score(self) -> float:
        """Weighted sum of all factor scores."""
        return (
            self.weights.similarity_weight * self.similarity_score
            + self.weights.confidence_weight * self.confidence_score
            + self.weights.recency_weight * self.recency_score
            + self.weights.frequency_weight * self.frequency_score
        )

    def __lt__(self, other: RelevanceScore) -> bool:
        """Enable sorting by composite score."""
        return self.composite_score < other.composite_score

    def __gt__(self, other: RelevanceScore) -> bool:
        """Enable sorting by composite score."""
        return self.composite_score > other.composite_score


# ============================================================================
# 4. AccessMetadata Model
# ============================================================================


class AccessMetadata(BaseModel):
    """Tracks memory access patterns for usage-based ranking.

    Stores when and how often a memory has been accessed to support
    recency and frequency scoring in relevance re-ranking.
    """

    memory_id: str = Field(..., min_length=1, description="Unique memory identifier")
    last_accessed: datetime | None = Field(
        default=None, description="Most recent access timestamp (UTC)"
    )
    access_count: int = Field(default=0, ge=0, description="Total access count")
    first_accessed: datetime | None = Field(
        default=None, description="First access timestamp (UTC)"
    )
    access_history: list[datetime] = Field(
        default_factory=list, max_length=10, description="Recent access timestamps"
    )

    @field_validator("access_count")
    @classmethod
    def validate_access_consistency(cls, v: int, info) -> int:
        """If access_count > 0, last_accessed must be set."""
        if v > 0 and info.data.get("last_accessed") is None:
            raise ValueError("last_accessed required when access_count > 0")
        return v

    @field_validator("access_history")
    @classmethod
    def validate_history_sorted(cls, v: list[datetime]) -> list[datetime]:
        """Ensure access_history is sorted descending (newest first)."""
        if len(v) > 1:
            sorted_v = sorted(v, reverse=True)
            if v != sorted_v:
                raise ValueError("access_history must be sorted descending (newest first)")
        return v

    def record_access(self, accessed_at: datetime) -> None:
        """Record a new access event (mutates in place).

        Args:
            accessed_at: Timestamp of access (UTC timezone)
        """
        self.last_accessed = accessed_at
        self.access_count += 1
        if self.first_accessed is None:
            self.first_accessed = accessed_at
        # Update history (keep last 10)
        self.access_history.insert(0, accessed_at)
        self.access_history = self.access_history[:10]


# ============================================================================
# 5. TokenBudget Model
# ============================================================================


class TokenBudget(BaseModel):
    """Configuration for token budget management.

    Defines maximum tokens allowed for memory context and how to handle
    overflow situations.
    """

    max_tokens: int | None = Field(
        default=None,
        gt=0,
        description="Max tokens for memory context (None = unlimited)",
    )
    truncation_strategy: TruncationStrategy = Field(
        default=TruncationStrategy.HARD_CUTOFF,
        description="How to handle budget overflow",
    )
    reserve_tokens: int = Field(
        default=500, ge=0, description="Tokens reserved for user message + system"
    )
    include_metadata: bool = Field(
        default=False, description="Include metadata in token count"
    )

    @computed_field
    @property
    def is_unlimited(self) -> bool:
        """True if no budget constraint."""
        return self.max_tokens is None

    @computed_field
    @property
    def effective_budget(self) -> int | None:
        """Effective budget after reserve tokens."""
        if self.max_tokens is None:
            return None
        return max(0, self.max_tokens - self.reserve_tokens)


# ============================================================================
# 6. DeduplicationResult Model
# ============================================================================


class DeduplicationResult(BaseModel):
    """Result of memory deduplication with metadata.

    Contains the unique memories after deduplication and statistics about
    what was removed and why.
    """

    unique_memories: list[RetrievalResult] = Field(
        ..., min_length=1, description="Memories retained after deduplication"
    )
    duplicate_count: int = Field(default=0, ge=0, description="Exact duplicates removed")
    similar_count: int = Field(
        default=0, ge=0, description="Semantically similar removed"
    )
    superseded_count: int = Field(
        default=0, ge=0, description="Superseded by corrections"
    )
    dedup_metadata: dict[str, Any] = Field(
        default_factory=dict, description="Metadata for observability"
    )

    @computed_field
    @property
    def total_removed(self) -> int:
        """Total number of memories removed during deduplication."""
        return self.duplicate_count + self.similar_count + self.superseded_count

    @computed_field
    @property
    def dedup_ratio(self) -> float:
        """Ratio of memories removed (0.0-1.0)."""
        total_input = len(self.unique_memories) + self.total_removed
        return self.total_removed / total_input if total_input > 0 else 0.0
