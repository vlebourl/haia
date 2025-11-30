"""Database models for conversation persistence.

This module defines SQLAlchemy models for storing conversations and messages
using async-compatible patterns with Mapped[] type annotations.
"""

from datetime import datetime, timezone

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import DateTime, ForeignKey, Index, String, Text
from sqlalchemy.ext.asyncio import AsyncAttrs
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(AsyncAttrs, DeclarativeBase):
    """Base class for all database models.

    Includes AsyncAttrs mixin for async relationship loading.
    All models should inherit from this base class.
    """

    pass


class Conversation(Base):
    """Represents a conversation thread containing multiple messages.

    A conversation is a collection of messages exchanged between the user
    and the AI assistant. Each conversation maintains its own context window
    for LLM processing.

    Attributes:
        id: Unique identifier for the conversation
        created_at: Timestamp when conversation was created
        updated_at: Timestamp of last message added
        messages: Related Message objects (lazy-loaded relationship)
    """

    __tablename__ = "conversations"

    # Primary key
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    # Timestamps (UTC)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
        index=True,  # Index for sorting by creation time
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
        index=True,  # Index for sorting by last activity
    )

    # Relationships
    messages: Mapped[list["Message"]] = relationship(
        back_populates="conversation",
        cascade="all, delete-orphan",  # Delete messages when conversation deleted
        lazy="selectin",  # Eager load messages with conversation (async-safe)
        order_by="Message.created_at",  # Order messages chronologically
    )

    def __repr__(self) -> str:
        """String representation of conversation."""
        return f"<Conversation(id={self.id}, created={self.created_at}, messages={len(self.messages)})>"


class Message(Base):
    """Represents a single message in a conversation.

    Messages are ordered chronologically within a conversation. The most recent
    20 messages form the "context window" sent to the LLM.

    Attributes:
        id: Unique identifier for the message
        conversation_id: Foreign key to parent conversation
        role: Message role (system, user, assistant)
        content: Message text content
        created_at: Timestamp when message was created
        conversation: Related Conversation object (lazy-loaded)
    """

    __tablename__ = "messages"

    # Primary key
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    # Foreign key to conversation
    conversation_id: Mapped[int] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,  # Index for fast filtering by conversation
    )

    # Message metadata
    role: Mapped[str] = mapped_column(String(20), nullable=False)

    content: Mapped[str] = mapped_column(Text, nullable=False)

    # Timestamp (UTC)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
        index=True,  # Index for sorting by time (context window queries)
    )

    # Relationships
    conversation: Mapped["Conversation"] = relationship(back_populates="messages")

    # Composite index for efficient context window queries
    __table_args__ = (
        Index(
            "ix_messages_conversation_created",
            "conversation_id",
            "created_at",
            # Speeds up: WHERE conversation_id = X ORDER BY created_at DESC LIMIT 20
        ),
    )

    def __repr__(self) -> str:
        """String representation of message."""
        preview = self.content[:50] + "..." if len(self.content) > 50 else self.content
        return f"<Message(id={self.id}, role={self.role}, content='{preview}')>"


# ============================================================================
# Pydantic Models (API Contracts)
# ============================================================================


class MessageCreate(BaseModel):
    """Request schema for creating a new message.

    Used when adding messages to a conversation via API endpoints.

    Attributes:
        role: Message role (system, user, or assistant)
        content: Message text content

    Example:
        ```python
        message_data = MessageCreate(
            role="user",
            content="What is the weather like today?"
        )
        ```
    """

    role: str = Field(
        ...,
        description="Message role: 'system', 'user', or 'assistant'",
        pattern="^(system|user|assistant)$",
    )
    content: str = Field(
        ...,
        min_length=1,
        description="Message text content (non-empty)",
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "role": "user",
                "content": "What is the weather like today?",
            }
        }
    )


class MessageResponse(BaseModel):
    """Response schema for message data.

    Returned when retrieving messages from conversations.

    Attributes:
        id: Unique message identifier
        role: Message role (system, user, or assistant)
        content: Message text content
        created_at: Timestamp when message was created (UTC)

    Example:
        ```python
        {
            "id": 42,
            "role": "user",
            "content": "What is the weather like today?",
            "created_at": "2025-01-15T10:30:00Z"
        }
        ```
    """

    id: int = Field(..., description="Unique message identifier")
    role: str = Field(..., description="Message role (system/user/assistant)")
    content: str = Field(..., description="Message text content")
    created_at: datetime = Field(..., description="Timestamp when message was created (UTC)")

    model_config = ConfigDict(
        from_attributes=True,  # Enable ORM mode for SQLAlchemy model conversion
        json_schema_extra={
            "example": {
                "id": 42,
                "role": "user",
                "content": "What is the weather like today?",
                "created_at": "2025-01-15T10:30:00Z",
            }
        },
    )


class ConversationResponse(BaseModel):
    """Response schema for conversation data with metadata.

    Returned when retrieving or listing conversations.

    Attributes:
        id: Unique conversation identifier
        created_at: Timestamp when conversation was created (UTC)
        updated_at: Timestamp of last message added (UTC)
        message_count: Total number of messages in conversation
        messages: List of messages (optional, only included when fetching full conversation)

    Example:
        ```python
        {
            "id": 1,
            "created_at": "2025-01-15T10:00:00Z",
            "updated_at": "2025-01-15T10:30:00Z",
            "message_count": 5,
            "messages": [...]  # Only when fetching full conversation
        }
        ```
    """

    id: int = Field(..., description="Unique conversation identifier")
    created_at: datetime = Field(..., description="Timestamp when conversation was created (UTC)")
    updated_at: datetime = Field(..., description="Timestamp of last message added (UTC)")
    message_count: int = Field(0, description="Total number of messages in conversation")
    messages: list[MessageResponse] = Field(
        default_factory=list,
        description="List of messages (only included when fetching full conversation)",
    )

    model_config = ConfigDict(
        from_attributes=True,  # Enable ORM mode for SQLAlchemy model conversion
        json_schema_extra={
            "example": {
                "id": 1,
                "created_at": "2025-01-15T10:00:00Z",
                "updated_at": "2025-01-15T10:30:00Z",
                "message_count": 5,
                "messages": [],
            }
        },
    )
