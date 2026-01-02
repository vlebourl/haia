"""
Pydantic models for hybrid retrieval system (Session 13).

These models support combining vector search, BM25 keyword matching,
and graph traversal using Reciprocal Rank Fusion.
"""

from datetime import datetime
from pydantic import BaseModel, Field, field_validator


class RetrievedMemory(BaseModel):
    """Base model for a retrieved memory (used by all retrieval methods)."""

    memory_id: str = Field(..., min_length=1, description="Unique memory identifier")
    content: str = Field(..., min_length=1, description="Memory content")
    type: str = Field(..., min_length=1, description="Memory type/category")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Extraction confidence")
    valid_from: datetime = Field(..., description="Temporal validity start")
    valid_until: datetime | None = Field(None, description="Temporal validity end")


class HybridRetrievalRequest(BaseModel):
    """Configuration for hybrid retrieval operation."""

    query: str = Field(..., min_length=1, description="Query text")
    enabled_methods: set[str] = Field(
        default={"vector", "bm25", "graph"},
        description="Enabled retrieval methods",
    )
    top_k: int = Field(default=10, ge=1, le=100, description="Number of results")
    graph_depth: int = Field(
        default=2, ge=1, le=3, description="Graph traversal depth"
    )
    rrf_k: int = Field(default=60, ge=1, description="RRF constant parameter")

    @field_validator("enabled_methods")
    @classmethod
    def validate_methods(cls, v: set[str]) -> set[str]:
        """Validate enabled methods."""
        valid_methods = {"vector", "bm25", "graph"}
        if not v.issubset(valid_methods):
            raise ValueError(f"Invalid methods: {v - valid_methods}")
        if len(v) == 0:
            raise ValueError("At least one method must be enabled")
        return v


class MethodResult(BaseModel):
    """Results from a single retrieval method."""

    method: str = Field(..., description="Method identifier")
    memories: list[RetrievedMemory] = Field(default_factory=list)
    scores: dict[str, float] = Field(default_factory=dict)
    error: str | None = Field(default=None, description="Error message if failed")

    @field_validator("method")
    @classmethod
    def validate_method(cls, v: str) -> str:
        """Validate method name."""
        valid_methods = {"vector", "bm25", "graph"}
        if v not in valid_methods:
            raise ValueError(f"Invalid method: {v}")
        return v


class RRFScore(BaseModel):
    """RRF score with source attribution."""

    memory_id: str
    rrf_score: float = Field(..., ge=0.0)
    method_contributions: dict[str, tuple[int, float]] = Field(default_factory=dict)
    source_methods: list[str] = Field(default_factory=list)

    @field_validator("source_methods")
    @classmethod
    def validate_sources(cls, v: list[str], info) -> list[str]:
        """Validate source methods match contributions."""
        contributions = info.data.get("method_contributions", {})
        if set(v) != set(contributions.keys()):
            raise ValueError("source_methods must match method_contributions keys")
        return v


class RetrievalResult(RetrievedMemory):
    """Final retrieval result with RRF metadata."""

    rrf_score: float = Field(..., ge=0.0)
    source_attribution: list[str] = Field(..., min_length=1)
    method_ranks: dict[str, int] = Field(default_factory=dict)

    @field_validator("method_ranks")
    @classmethod
    def validate_ranks(cls, v: dict[str, int], info) -> dict[str, int]:
        """Validate method ranks match source attribution."""
        sources = info.data.get("source_attribution", [])
        if set(v.keys()) != set(sources):
            raise ValueError("method_ranks must match source_attribution")
        return v


class GraphTraversalConfig(BaseModel):
    """Configuration for graph traversal."""

    relationship_types: list[str] = Field(
        default=["RELATED_TO", "DEPENDS_ON", "SUPERSEDES"], min_length=1
    )
    max_depth: int = Field(default=2, ge=1, le=3)
    use_apoc: bool = Field(default=True)
    cycle_detection: bool = Field(default=True)
