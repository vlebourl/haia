# Data Model: Conversation Database Persistence

**Feature**: Conversation Database Persistence
**Date**: 2025-11-30
**Status**: Design Complete

## Overview

This document defines the SQLAlchemy models for conversation persistence using declarative base with Mapped[] type annotations for full type safety and async compatibility.

---

## Database Schema

### Entity Relationship Diagram

```
┌─────────────────────────┐
│   Conversation          │
├─────────────────────────┤
│ id: int (PK)            │
│ created_at: datetime    │
│ updated_at: datetime    │
└─────────────────────────┘
           │
           │ 1:N
           │
           ▼
┌─────────────────────────┐
│   Message               │
├─────────────────────────┤
│ id: int (PK)            │
│ conversation_id: int(FK)│
│ role: str               │
│ content: str            │
│ created_at: datetime    │
└─────────────────────────┘
```

---

## SQLAlchemy Models

### Base Configuration

```python
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncAttrs
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy import ForeignKey, String, Text, DateTime, Index


class Base(AsyncAttrs, DeclarativeBase):
    """Base class for all database models.

    Includes AsyncAttrs mixin for async relationship loading.
    """
    pass
```

### Conversation Model

```python
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
        default=datetime.utcnow,
        nullable=False,
        index=True  # Index for sorting by creation time
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
        index=True  # Index for sorting by last activity
    )

    # Relationships
    messages: Mapped[list["Message"]] = relationship(
        back_populates="conversation",
        cascade="all, delete-orphan",  # Delete messages when conversation deleted
        lazy="selectin"  # Eager load messages with conversation (async-safe)
    )

    def __repr__(self) -> str:
        return f"<Conversation(id={self.id}, created={self.created_at}, messages={len(self.messages)})>"
```

**Design Decisions**:
- `autoincrement=True`: Auto-generate sequential conversation IDs
- `DateTime(timezone=True)`: Store timestamps with timezone info (SQLite stores as UTC string)
- `default=datetime.utcnow`: Set timestamp on insert
- `onupdate=datetime.utcnow`: Auto-update `updated_at` on any message addition
- `cascade="all, delete-orphan"`: Automatically delete all messages when conversation deleted
- `lazy="selectin"`: Use SELECT IN loading for async compatibility (avoids lazy loading issues)
- Indexes on both timestamps for efficient sorting/filtering

### Message Model

```python
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
        index=True  # Index for fast filtering by conversation
    )

    # Message metadata
    role: Mapped[str] = mapped_column(
        String(20),
        nullable=False
    )

    content: Mapped[str] = mapped_column(
        Text,
        nullable=False
    )

    # Timestamp (UTC)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        nullable=False,
        index=True  # Index for sorting by time (context window queries)
    )

    # Relationships
    conversation: Mapped["Conversation"] = relationship(
        back_populates="messages"
    )

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
        preview = self.content[:50] + "..." if len(self.content) > 50 else self.content
        return f"<Message(id={self.id}, role={self.role}, content='{preview}')>"
```

**Design Decisions**:
- `String(20)`: Role is limited to system/user/assistant (20 chars max)
- `Text`: Content can be arbitrarily long (no length limit)
- `ForeignKey(..., ondelete="CASCADE")`: Delete messages when conversation deleted
- `composite index`: (conversation_id, created_at) enables fast context window queries
- Query pattern: `WHERE conversation_id = X ORDER BY created_at DESC LIMIT 20` uses index efficiently

---

## Validation Rules

### Role Validation

Valid message roles (enforced at application layer, not database):
- `"system"`: System instructions/prompts
- `"user"`: User input
- `"assistant"`: AI assistant responses

**Rationale**: SQLAlchemy doesn't support Enum validation with async well. Pydantic models handle validation before database insertion.

### Content Validation

- **Minimum length**: 1 character (empty messages rejected)
- **Maximum length**: No database limit (Text type), application may enforce reasonable limits
- **Encoding**: UTF-8 (SQLite stores as TEXT with UTF-8)

### Timestamp Validation

- All timestamps stored in UTC (application responsibility to convert)
- `created_at` is immutable (set once on insert)
- `updated_at` automatically updates on conversation message additions

---

## Indexes

### Primary Indexes

1. **conversations.id** (PRIMARY KEY): Auto-indexed
2. **messages.id** (PRIMARY KEY): Auto-indexed

### Secondary Indexes

1. **conversations.created_at**: For sorting conversations by creation time
2. **conversations.updated_at**: For sorting conversations by last activity
3. **messages.conversation_id**: For filtering messages by conversation
4. **messages.created_at**: For sorting messages chronologically

### Composite Indexes

1. **messages (conversation_id, created_at)**: For context window queries
   - Query pattern: `WHERE conversation_id = X ORDER BY created_at DESC LIMIT 20`
   - Performance: O(log N + 20) where N is total messages in conversation

---

## Performance Characteristics

### Query Performance

| Operation | Time Complexity | Typical Latency |
|-----------|----------------|-----------------|
| Create conversation | O(1) | < 5ms |
| Add message | O(1) | < 10ms |
| Get conversation by ID | O(1) | < 5ms |
| Get context messages (20 most recent) | O(log N + 20) | < 20ms (1000 messages) |
| Get all messages in conversation | O(N) | < 50ms (1000 messages) |

### Storage Estimates

- **Conversation**: ~50 bytes per row (fixed overhead)
- **Message**: ~100 bytes overhead + content length
- **Average message**: ~500 bytes (assuming ~400 chars of text)
- **1000 messages**: ~500KB
- **10,000 messages**: ~5MB

SQLite handles these sizes efficiently with proper indexing.

---

## Migration Strategy

### Initial Schema (Version 001)

**Migration file**: `migrations/versions/001_initial_schema.py`

```python
"""Initial schema for conversation persistence

Revision ID: 001
Revises:
Create Date: 2025-11-30
"""
from alembic import op
import sqlalchemy as sa

revision = '001'
down_revision = None
branch_labels = None
depends_on = None

def upgrade() -> None:
    # Create conversations table
    op.create_table(
        'conversations',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_conversations_created_at', 'conversations', ['created_at'])
    op.create_index('ix_conversations_updated_at', 'conversations', ['updated_at'])

    # Create messages table
    op.create_table(
        'messages',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('conversation_id', sa.Integer(), nullable=False),
        sa.Column('role', sa.String(20), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['conversation_id'], ['conversations.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_messages_conversation_id', 'messages', ['conversation_id'])
    op.create_index('ix_messages_created_at', 'messages', ['created_at'])
    op.create_index('ix_messages_conversation_created', 'messages', ['conversation_id', 'created_at'])

def downgrade() -> None:
    op.drop_table('messages')
    op.drop_table('conversations')
```

### Future Schema Changes

Future migrations may add:
- `user_id` column to Conversation (for multi-user support)
- `metadata` JSON column to Conversation (for custom tags/labels)
- `token_count` column to Message (for context window token tracking)
- `model` column to Message (track which model generated response)

---

## Type Safety

### Pydantic Models for Validation

```python
from pydantic import BaseModel, Field
from datetime import datetime

class MessageCreate(BaseModel):
    """Request model for creating a message."""
    role: Literal["system", "user", "assistant"]
    content: str = Field(min_length=1, max_length=100000)

class MessageResponse(BaseModel):
    """Response model for message data."""
    id: int
    conversation_id: int
    role: str
    content: str
    created_at: datetime

    model_config = {"from_attributes": True}  # Enable ORM mode

class ConversationResponse(BaseModel):
    """Response model for conversation data."""
    id: int
    created_at: datetime
    updated_at: datetime
    message_count: int  # Derived field

    model_config = {"from_attributes": True}
```

**Pattern**: SQLAlchemy models for database, Pydantic models for API validation and serialization.

---

## References

- [SQLAlchemy 2.0 Mapped Annotations](https://docs.sqlalchemy.org/en/20/orm/declarative_tables.html#mapped-column-derives-the-datatype-from-mapped)
- [SQLAlchemy Async ORM](https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html)
- [SQLite Indexes](https://www.sqlite.org/queryplanner.html)
- [Alembic Migrations](https://alembic.sqlalchemy.org/en/latest/tutorial.html)
