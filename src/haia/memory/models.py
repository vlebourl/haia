"""Pydantic models for conversation boundary detection and transcript storage."""

from datetime import datetime
from enum import Enum
from typing import Literal, NamedTuple

from pydantic import BaseModel, Field


# T007: BoundaryTriggerReason enum
class BoundaryTriggerReason(str, Enum):
    """Reasons for conversation boundary detection.

    String enum for logging and debugging clarity.
    """

    IDLE_AND_MESSAGE_DROP = "idle_and_message_drop"
    """Idle time >10min AND message count dropped >50%"""

    IDLE_AND_HASH_CHANGE = "idle_and_hash_change"
    """Idle time >10min AND first message hash changed"""

    IDLE_AND_BOTH = "idle_and_both"
    """Idle time >10min AND both message drop + hash change"""


# T008: ChatMessage model
class ChatMessage(BaseModel):
    """A single message in a conversation.

    Compatible with OpenAI chat message format.
    """

    role: Literal["user", "assistant", "system"] = Field(
        ...,
        description="Message role (user/assistant/system)",
    )
    content: str = Field(
        ...,
        description="Message text content",
    )
    timestamp: datetime = Field(
        ...,
        description="When this message was sent/received (UTC)",
    )

    class Config:
        frozen = True  # Immutable once created
        extra = "forbid"


# T009: ConversationMetadata model
class ConversationMetadata(BaseModel):
    """Metadata for tracking conversation state across requests.

    This model stores the minimal information needed to detect conversation
    boundaries using the hybrid heuristic (idle time + message history change).
    """

    conversation_id: str = Field(
        ...,
        description="Unique identifier for the conversation",
    )
    last_seen: datetime = Field(
        ...,
        description="Timestamp of the last request in this conversation (UTC)",
    )
    message_count: int = Field(
        ...,
        ge=1,
        description="Number of messages in the last request",
    )
    first_message_hash: str = Field(
        ...,
        description="SHA-256 hash of the first message content for change detection",
    )
    start_time: datetime = Field(
        ...,
        description="Timestamp when this conversation was first seen (UTC)",
    )

    class Config:
        """Pydantic config for strict mode compliance."""

        frozen = False  # Mutable for updates
        extra = "forbid"  # Reject unknown fields


# T010: ConversationTranscript model
class ConversationTranscript(BaseModel):
    """Complete conversation transcript captured at boundary detection.

    Persisted to filesystem for later memory extraction.
    """

    conversation_id: str = Field(
        ...,
        description="Unique identifier for the conversation",
    )
    start_time: datetime = Field(
        ...,
        description="When the conversation started (UTC)",
    )
    end_time: datetime = Field(
        ...,
        description="When the conversation ended (UTC)",
    )
    message_count: int = Field(
        ...,
        ge=1,
        description="Total number of messages in the conversation",
    )
    trigger_reason: BoundaryTriggerReason = Field(
        ...,
        description="Why the boundary was detected",
    )
    messages: list[ChatMessage] = Field(
        ...,
        min_length=1,
        description="Complete ordered list of messages",
    )
    metadata: dict[str, str] = Field(
        default_factory=dict,
        description="Additional metadata (IP, user agent, etc.)",
    )

    class Config:
        frozen = True  # Immutable once created
        extra = "forbid"

    @property
    def duration_seconds(self) -> float:
        """Calculate conversation duration in seconds."""
        return (self.end_time - self.start_time).total_seconds()

    @property
    def filename(self) -> str:
        """Generate filesystem-safe filename for this transcript."""
        timestamp = self.end_time.strftime("%Y%m%d_%H%M%S")
        # Truncate conv_id to 8 chars for readability
        short_id = self.conversation_id[:8]
        return f"{short_id}_{timestamp}.json"


# T011: BoundaryDetectionEvent model
class BoundaryDetectionEvent(BaseModel):
    """Event logged when a conversation boundary is detected.

    Used for observability, debugging, and false positive analysis.
    """

    timestamp: datetime = Field(
        ...,
        description="When the boundary was detected (UTC)",
    )
    conversation_id: str = Field(
        ...,
        description="ID of the conversation that ended",
    )
    idle_duration_seconds: float = Field(
        ...,
        ge=0,
        description="Time since last request (seconds)",
    )
    previous_message_count: int = Field(
        ...,
        ge=1,
        description="Message count in the previous request",
    )
    current_message_count: int = Field(
        ...,
        ge=1,
        description="Message count in the current request",
    )
    message_count_drop_percent: float = Field(
        ...,
        ge=0,
        le=100,
        description="Percentage drop in message count",
    )
    previous_first_hash: str = Field(
        ...,
        description="SHA-256 hash of first message in previous request",
    )
    current_first_hash: str = Field(
        ...,
        description="SHA-256 hash of first message in current request",
    )
    hash_changed: bool = Field(
        ...,
        description="Whether the first message hash changed",
    )
    trigger_reason: BoundaryTriggerReason = Field(
        ...,
        description="Why the boundary was detected",
    )
    transcript_filename: str = Field(
        ...,
        description="Filename of the stored transcript",
    )

    class Config:
        frozen = True
        extra = "forbid"

    def to_log_dict(self) -> dict[str, str | float | bool]:
        """Convert to dictionary for structured logging."""
        return {
            "event_type": "conversation_boundary_detected",
            "timestamp": self.timestamp.isoformat(),
            "conversation_id": self.conversation_id,
            "idle_duration_seconds": self.idle_duration_seconds,
            "previous_message_count": self.previous_message_count,
            "current_message_count": self.current_message_count,
            "message_count_drop_percent": self.message_count_drop_percent,
            "hash_changed": self.hash_changed,
            "trigger_reason": self.trigger_reason.value,
            "transcript_filename": self.transcript_filename,
        }


# T012: BoundaryDetectionResult named tuple
class BoundaryDetectionResult(NamedTuple):
    """Result of boundary detection heuristic.

    Used internally by ConversationTracker.
    """

    detected: bool
    """Whether a boundary was detected"""

    reason: BoundaryTriggerReason | None
    """Why the boundary was detected (None if not detected)"""

    idle_duration_seconds: float
    """Calculated idle time"""

    message_count_drop_percent: float
    """Calculated message count drop percentage"""

    hash_changed: bool
    """Whether first message hash changed"""
