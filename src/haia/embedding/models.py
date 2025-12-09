"""Pydantic models for embedding and retrieval workflows.

This module defines all data structures used for:
- Embedding generation requests/responses (Ollama API)
- Memory retrieval queries and results
- Relevance scoring
- Backfill progress tracking
- Error handling
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any, Literal

from pydantic import BaseModel, Field

from haia.extraction.models import ExtractedMemory

if TYPE_CHECKING:
    from haia.context.models import DeduplicationResult


# ============================================================================
# 1. Embedding Models
# ============================================================================


class EmbeddingRequest(BaseModel):
    """Request for embedding generation via Ollama."""

    model: str = Field(
        default="nomic-embed-text", description="Embedding model name"
    )
    input: str | list[str] = Field(
        ..., description="Text(s) to embed (single or batch)"
    )
    truncate: bool = Field(
        default=True, description="Truncate if exceeds context length"
    )
    dimensions: int = Field(default=768, description="Embedding dimensions")
    keep_alive: str = Field(default="5m", description="Model keep-alive duration")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "model": "nomic-embed-text",
                    "input": "User prefers Docker over Podman for homelab deployments",
                    "truncate": True,
                    "dimensions": 768,
                    "keep_alive": "5m",
                }
            ]
        }
    }


class EmbeddingResponse(BaseModel):
    """Response from Ollama embedding API."""

    model: str = Field(..., description="Model used for generation")
    embeddings: list[list[float]] = Field(
        ..., description="Generated embedding vectors"
    )
    total_duration: int | None = Field(
        None, description="Total time in nanoseconds"
    )
    load_duration: int | None = Field(
        None, description="Model load time in nanoseconds"
    )
    prompt_eval_count: int | None = Field(
        None, description="Number of tokens processed"
    )

    @property
    def latency_ms(self) -> float:
        """Get latency in milliseconds."""
        if self.total_duration:
            return self.total_duration / 1_000_000
        return 0.0

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "model": "nomic-embed-text",
                    "embeddings": [[0.010071, -0.001759, 0.050072]],
                    "total_duration": 14143917,
                    "load_duration": 1019500,
                    "prompt_eval_count": 8,
                }
            ]
        }
    }


class EmbeddingMetadata(BaseModel):
    """Metadata for embedding generation tracking."""

    memory_id: str
    model: str = "nomic-embed-text"
    model_version: str = "v1.5"
    dimensions: int = 768
    generated_at: datetime
    latency_ms: float
    success: bool
    error: str | None = None

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "memory_id": "mem_abc123",
                    "model": "nomic-embed-text",
                    "model_version": "v1.5",
                    "dimensions": 768,
                    "generated_at": "2025-12-08T10:30:00Z",
                    "latency_ms": 42.5,
                    "success": True,
                    "error": None,
                }
            ]
        }
    }


# ============================================================================
# 2. Retrieval Models
# ============================================================================


class RetrievalQuery(BaseModel):
    """Parameters for semantic memory retrieval."""

    query_text: str = Field(
        ..., min_length=1, description="Query text to search for"
    )
    query_embedding: list[float] | None = Field(
        None, description="Pre-computed query embedding (768-dim)"
    )

    top_k: int = Field(
        default=10, ge=1, le=100, description="Number of results to retrieve"
    )
    min_similarity: float = Field(
        default=0.65,
        ge=0.0,
        le=1.0,
        description="Minimum cosine similarity threshold",
    )
    min_confidence: float = Field(
        default=0.4,
        ge=0.0,
        le=1.0,
        description="Minimum extraction confidence threshold",
    )

    memory_types: list[str] | None = Field(
        None, description="Filter by memory types"
    )
    exclude_ids: list[str] | None = Field(
        None, description="Exclude specific memory IDs"
    )

    include_metadata: bool = Field(
        default=True, description="Include retrieval metadata in results"
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "query_text": "How should I deploy my services?",
                    "top_k": 10,
                    "min_similarity": 0.70,
                    "min_confidence": 0.50,
                    "memory_types": ["preference", "technical_context"],
                    "include_metadata": True,
                }
            ]
        }
    }


class RetrievalResult(BaseModel):
    """Memory retrieval result with relevance scoring."""

    memory: ExtractedMemory
    similarity_score: float = Field(
        ..., ge=0.0, le=1.0, description="Cosine similarity score"
    )
    relevance_score: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Combined relevance (similarity + confidence)",
    )
    rank: int = Field(..., ge=1, description="Result ranking (1 = most relevant)")

    # Optional metadata
    retrieved_at: datetime = Field(default_factory=datetime.utcnow)
    query_latency_ms: float | None = None

    # Context optimization metadata (Session 9)
    token_count: int | None = Field(
        None, ge=0, description="Estimated token count for this memory"
    )
    was_deduplicated: bool = Field(
        default=False, description="True if duplicates were removed from this result set"
    )
    budget_enforced: bool = Field(
        default=False, description="True if token budget limited results"
    )
    # Use Any temporarily to avoid circular import - will be AccessMetadata at runtime
    access_metadata: "Any" = Field(
        None, description="Access pattern metadata for re-ranking"
    )

    @property
    def is_high_confidence(self) -> bool:
        """Check if memory is high confidence (≥0.7)."""
        return self.memory.confidence >= 0.7

    @property
    def is_highly_relevant(self) -> bool:
        """Check if result is highly relevant (≥0.75)."""
        return self.relevance_score >= 0.75

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "memory": {
                        "memory_id": "mem_abc123",
                        "memory_type": "preference",
                        "content": "Prefers Docker over Kubernetes for homelab",
                        "confidence": 0.92,
                        "has_embedding": True,
                    },
                    "similarity_score": 0.85,
                    "relevance_score": 0.87,
                    "rank": 1,
                    "query_latency_ms": 23.4,
                }
            ]
        }
    }


class RetrievalResponse(BaseModel):
    """Complete retrieval response with results and metadata."""

    query: str
    results: list[RetrievalResult]
    total_results: int

    # Performance metrics
    total_latency_ms: float
    embedding_latency_ms: float
    search_latency_ms: float

    # Search metadata
    top_k: int
    min_similarity: float
    min_confidence: float

    # Filtering info
    memories_searched: int
    memories_matched: int
    memories_deduplicated: int = 0

    # Context optimization (Session 9)
    dedup_stats: "DeduplicationResult | None" = Field(
        None, description="Detailed deduplication statistics"
    )

    @property
    def has_results(self) -> bool:
        """Check if any results were found."""
        return len(self.results) > 0

    @property
    def top_result(self) -> RetrievalResult | None:
        """Get most relevant result."""
        return self.results[0] if self.results else None

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "query": "How should I deploy my services?",
                    "results": [
                        {"memory": {}, "similarity_score": 0.85, "rank": 1}
                    ],
                    "total_results": 3,
                    "total_latency_ms": 47.3,
                    "embedding_latency_ms": 22.1,
                    "search_latency_ms": 25.2,
                    "top_k": 10,
                    "min_similarity": 0.70,
                    "min_confidence": 0.50,
                    "memories_searched": 850,
                    "memories_matched": 15,
                    "memories_deduplicated": 2,
                }
            ]
        }
    }


# ============================================================================
# 3. Scoring Models
# ============================================================================


class RelevanceScore(BaseModel):
    """Detailed relevance score calculation."""

    similarity: float = Field(
        ..., ge=0.0, le=1.0, description="Cosine similarity score"
    )
    confidence: float = Field(
        ..., ge=0.0, le=1.0, description="Extraction confidence"
    )
    recency: float = Field(
        ..., ge=0.0, le=1.0, description="Recency decay factor"
    )
    type_weight: float = Field(
        ..., ge=0.0, le=2.0, description="Memory type priority weight"
    )

    # Scoring parameters
    similarity_weight: float = Field(default=0.65, description="α - similarity weight")
    confidence_weight: float = Field(
        default=0.35, description="β - confidence weight"
    )

    @property
    def final_score(self) -> float:
        """Calculate weighted final score."""
        base_score = (
            self.similarity * self.similarity_weight
            + self.confidence * self.confidence_weight
        )
        return min(1.0, base_score * self.type_weight)

    @property
    def score_breakdown(self) -> dict[str, float]:
        """Get contribution of each factor."""
        return {
            "similarity_contribution": self.similarity * self.similarity_weight,
            "confidence_contribution": self.confidence * self.confidence_weight,
            "type_multiplier": self.type_weight,
            "final_score": self.final_score,
        }


# ============================================================================
# 4. Backfill Models
# ============================================================================


class BackfillProgress(BaseModel):
    """Embedding backfill progress tracking."""

    progress_id: str
    status: Literal["pending", "running", "completed", "failed"]

    started_at: datetime
    completed_at: datetime | None = None

    total_nodes: int
    processed_nodes: int = 0
    failed_nodes: int = 0

    worker_count: int
    batch_size: int

    last_checkpoint_at: datetime | None = None
    last_processed_id: str | None = None

    error: str | None = None

    @property
    def percent_complete(self) -> float:
        """Calculate completion percentage."""
        if self.total_nodes == 0:
            return 0.0
        return (self.processed_nodes / self.total_nodes) * 100.0

    @property
    def success_rate(self) -> float:
        """Calculate success rate."""
        if self.processed_nodes == 0:
            return 0.0
        success = self.processed_nodes - self.failed_nodes
        return (success / self.processed_nodes) * 100.0

    @property
    def is_complete(self) -> bool:
        """Check if backfill is complete."""
        return self.status in ["completed", "failed"]


class BackfillRecord(BaseModel):
    """Single record for backfill processing."""

    node_id: str
    node_label: str
    content: str
    existing_embedding: list[float] | None = None

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "node_id": "fact_abc123",
                    "node_label": "Fact",
                    "content": "Uses Proxmox VE for virtualization",
                    "existing_embedding": None,
                }
            ]
        }
    }


class BackfillBatch(BaseModel):
    """Batch of records for backfill processing."""

    batch_id: str
    records: list[BackfillRecord]
    batch_size: int
    worker_id: int

    @property
    def record_count(self) -> int:
        """Get number of records in batch."""
        return len(self.records)


# ============================================================================
# 5. Error Models
# ============================================================================


class EmbeddingException(Exception):
    """Exception raised when embedding generation fails.

    This is a proper Python exception that can be caught and handled.
    Use this for raising errors in the embedding workflow.
    """

    def __init__(self, message: str, recoverable: bool = True):
        """Initialize embedding exception.

        Args:
            message: Error message
            recoverable: Whether this error can be retried
        """
        super().__init__(message)
        self.recoverable = recoverable


class EmbeddingError(BaseModel):
    """Error details for failed embedding generation (for structured logging).

    This is a Pydantic model for structured error data, not an exception.
    Use EmbeddingException for raising errors.
    """

    error_type: Literal[
        "connection_error", "model_error", "timeout", "validation_error", "unknown"
    ]
    error_message: str
    memory_id: str | None = None
    retry_count: int = 0
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    recoverable: bool = Field(..., description="Whether error is retryable")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "error_type": "connection_error",
                    "error_message": "Connection refused to http://localhost:11434",
                    "memory_id": "mem_abc123",
                    "retry_count": 2,
                    "recoverable": True,
                }
            ]
        }
    }
