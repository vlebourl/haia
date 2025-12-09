"""Pydantic models for memory extraction.

This module defines all data structures used for conversation transcript input,
extraction output, and memory representation with full type safety and validation.
"""

import uuid
from datetime import datetime
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field, computed_field, field_validator


class MemoryCategory(str, Enum):
    """Primary memory categories (maps to memory_type field)."""

    PREFERENCE = "preference"
    PERSONAL_FACT = "personal_fact"
    TECHNICAL_CONTEXT = "technical_context"
    DECISION = "decision"
    CORRECTION = "correction"


class ConfidenceLevel(str, Enum):
    """Confidence level thresholds."""

    HIGH = "high"  # e0.7
    MEDIUM = "medium"  # 0.4-0.7
    LOW = "low"  # <0.4 (should not appear in results)

    @classmethod
    def from_score(cls, score: float) -> "ConfidenceLevel":
        """Convert numeric confidence to level."""
        if score >= 0.7:
            return cls.HIGH
        elif score >= 0.4:
            return cls.MEDIUM
        else:
            return cls.LOW


class Message(BaseModel):
    """Single message within a conversation."""

    content: str = Field(..., description="Message text content")
    timestamp: datetime = Field(..., description="When message was sent")
    speaker: Literal["user", "assistant"] = Field(
        ..., description="Who sent the message"
    )


class ConversationTranscript(BaseModel):
    """Complete conversation transcript for memory extraction."""

    conversation_id: str = Field(..., description="Unique conversation identifier")
    messages: list[Message] = Field(
        ..., min_length=1, description="All messages in chronological order"
    )
    start_time: datetime = Field(..., description="Conversation start timestamp")
    end_time: datetime = Field(..., description="Conversation end timestamp")
    message_count: int = Field(..., ge=1, description="Total number of messages")

    @property
    def duration_seconds(self) -> float:
        """Calculate conversation duration in seconds."""
        return (self.end_time - self.start_time).total_seconds()


class ExtractedMemory(BaseModel):
    """A single memory extracted from conversation transcript."""

    memory_id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        description="Unique memory identifier",
    )
    memory_type: Literal[
        "preference", "personal_fact", "technical_context", "decision", "correction"
    ] = Field(..., description="Primary category of memory")
    content: str = Field(
        ..., min_length=1, description="Natural language description of the memory"
    )
    confidence: float = Field(
        ..., ge=0.0, le=1.0, description="Confidence score (0.0-1.0)"
    )
    category: str | None = Field(
        None,
        description="Optional subcategory (e.g., 'infrastructure', 'tool_preference')",
    )
    source_conversation_id: str = Field(
        ..., description="ID of conversation this memory came from"
    )
    extraction_timestamp: datetime = Field(
        default_factory=datetime.utcnow, description="When extraction occurred"
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict, description="Additional context"
    )

    # Embedding fields (Session 8 - Memory Retrieval)
    embedding: list[float] | None = Field(
        None, description="768-dimensional embedding vector for semantic search"
    )
    has_embedding: bool = Field(
        False, description="True if embedding has been generated"
    )
    embedding_version: str | None = Field(
        None, description="Embedding model version (e.g., 'nomic-embed-text-v1')"
    )
    embedding_updated_at: datetime | None = Field(
        None, description="When embedding was last generated/updated"
    )

    @field_validator("confidence")
    @classmethod
    def validate_confidence_threshold(cls, v: float) -> float:
        """Ensure confidence meets 0.4 threshold (selective aggressive strategy)."""
        if v < 0.4:
            raise ValueError(
                f"Confidence {v} below 0.4 threshold - memory should be filtered"
            )
        return v

    @property
    def is_high_confidence(self) -> bool:
        """Check if confidence is high (e0.7)."""
        return self.confidence >= 0.7

    @property
    def is_medium_confidence(self) -> bool:
        """Check if confidence is medium (0.4-0.7)."""
        return 0.4 <= self.confidence < 0.7


class ExtractionResult(BaseModel):
    """Complete extraction result for a conversation."""

    conversation_id: str = Field(..., description="ID of conversation processed")
    memories: list[ExtractedMemory] = Field(
        default_factory=list, description="Extracted memories"
    )
    extraction_duration: float = Field(
        ..., ge=0.0, description="Processing time in seconds"
    )
    model_used: str = Field(
        ...,
        description="LLM model used for extraction (e.g., 'claude-haiku-4-5-20251001')",
    )
    extraction_timestamp: datetime = Field(
        default_factory=datetime.utcnow, description="When extraction completed"
    )
    error: str | None = Field(
        None, description="Error message if extraction failed"
    )

    @computed_field
    @property
    def memory_count(self) -> int:
        """Total number of memories extracted."""
        return len(self.memories)

    @computed_field
    @property
    def memory_types_distribution(self) -> dict[str, int]:
        """Count of memories by type."""
        distribution: dict[str, int] = {}
        for memory in self.memories:
            distribution[memory.memory_type] = (
                distribution.get(memory.memory_type, 0) + 1
            )
        return distribution

    @computed_field
    @property
    def average_confidence(self) -> float:
        """Average confidence across all memories."""
        if not self.memories:
            return 0.0
        return sum(m.confidence for m in self.memories) / len(self.memories)

    @computed_field
    @property
    def high_confidence_count(self) -> int:
        """Number of high-confidence memories (e0.7)."""
        return sum(1 for m in self.memories if m.is_high_confidence)

    @property
    def is_successful(self) -> bool:
        """Check if extraction succeeded."""
        return self.error is None
