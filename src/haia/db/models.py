"""Database models for conversation persistence.

This module defines SQLAlchemy models for storing conversations and messages
using async-compatible patterns with Mapped[] type annotations.
"""

from datetime import datetime, timezone

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
