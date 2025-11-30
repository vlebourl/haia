# Research: Conversation Database Persistence

**Feature**: Conversation Database Persistence
**Date**: 2025-11-30
**Status**: Complete

## Overview

This document consolidates research findings for implementing persistent conversation storage using SQLite with async SQLAlchemy, including context window management, migrations, and repository patterns.

---

## Decision 1: SQLAlchemy 2.0 Async Patterns

**Decision**: Use SQLAlchemy 2.0+ with async/await and Mapped[] type annotations

**Rationale**:
- SQLAlchemy 2.0 provides first-class async support with AsyncEngine and AsyncSession
- Mapped[] annotations enable full type safety compatible with mypy strict mode
- Declarative models reduce boilerplate compared to manual table definitions
- async_sessionmaker provides proper async context manager support
- aiosqlite driver integrates seamlessly with AsyncEngine

**Implementation Pattern**:

```python
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

# Base class for all models
class Base(DeclarativeBase):
    pass

# Model definition with Mapped[] annotations
class Conversation(Base):
    __tablename__ = "conversations"

    id: Mapped[int] = mapped_column(primary_key=True)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationship with type annotation
    messages: Mapped[list["Message"]] = relationship(back_populates="conversation")

# Async engine and session factory
engine = create_async_engine("sqlite+aiosqlite:///./haia.db", echo=False)
async_session = async_sessionmaker(engine, expire_on_commit=False)

# Usage in repository
async with async_session() as session:
    result = await session.execute(select(Conversation).where(Conversation.id == conv_id))
    conversation = result.scalar_one_or_none()
```

**Key Benefits**:
- Full async support without blocking event loop
- Type-safe models with IDE autocomplete
- Automatic session management via async context managers
- Connection pooling built-in
- Compatible with FastAPI dependency injection

**Alternatives Considered**:
- Sync SQLAlchemy with thread pool: Rejected - adds complexity, doesn't align with async-first principle
- Raw SQL with aiosqlite: Rejected - too much boilerplate, no type safety, error-prone
- SQLModel: Rejected - less mature than SQLAlchemy 2.0 for async

---

## Decision 2: Repository Pattern for Data Access

**Decision**: Implement repository class to encapsulate all database operations

**Rationale**:
- Separates data access logic from business logic
- Makes testing easier (mock repository instead of database)
- Provides clean API for consumers (chat API, agent)
- Centralizes context window logic in one place
- Enables future optimization without changing callers

**Repository Interface**:

```python
class ConversationRepository:
    """Repository for conversation and message persistence."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_conversation(self) -> Conversation:
        """Create new conversation."""

    async def get_conversation(self, conversation_id: int) -> Conversation | None:
        """Retrieve conversation by ID."""

    async def add_message(
        self, conversation_id: int, role: str, content: str
    ) -> Message:
        """Add message to conversation and update context window."""

    async def get_context_messages(
        self, conversation_id: int, limit: int = 20
    ) -> list[Message]:
        """Get most recent N messages for LLM context."""

    async def get_all_messages(self, conversation_id: int) -> list[Message]:
        """Get all messages in conversation (for display)."""
```

**Pattern Benefits**:
- Single responsibility: repository only handles data access
- Dependency injection: pass session to repository
- Testable: mock repository methods in unit tests
- Centralized logic: context window management in one place

**Alternatives Considered**:
- Active Record pattern (models with save/find methods): Rejected - mixes concerns, harder to test
- Direct SQLAlchemy queries in API layer: Rejected - violates separation of concerns
- DAO pattern with interfaces: Rejected - over-engineered for single database

---

## Decision 3: Context Window Management Strategy

**Decision**: Use SQL LIMIT with ORDER BY for efficient context window queries

**Rationale**:
- Database-level sorting and limiting is fast (< 100ms for 1000+ messages)
- No need to load all messages into memory
- SQLite handles ORDER BY + LIMIT efficiently with proper indexes
- Repository method encapsulates complexity

**Implementation Approach**:

```python
async def get_context_messages(
    self, conversation_id: int, limit: int = 20
) -> list[Message]:
    """Get most recent N messages for LLM context."""
    stmt = (
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.created_at.desc())  # Most recent first
        .limit(limit)
    )
    result = await self.session.execute(stmt)
    messages = list(result.scalars().all())

    # Reverse to get chronological order (oldest first for LLM)
    return messages[::-1]
```

**Index Strategy**:
```python
# In Message model
class Message(Base):
    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(primary_key=True)
    conversation_id: Mapped[int] = mapped_column(
        ForeignKey("conversations.id"), index=True  # Index for fast filtering
    )
    created_at: Mapped[datetime] = mapped_column(
        default=datetime.utcnow, index=True  # Index for fast sorting
    )
```

**Query Performance**:
- Composite index on (conversation_id, created_at) for optimal performance
- EXPLAIN QUERY PLAN shows index usage
- Retrieval time: O(log N + 20) where N is total messages

**Alternatives Considered**:
- Boolean flag `in_context_window` on Message: Rejected - requires updating flags on every new message (expensive)
- Application-level filtering after loading all messages: Rejected - wasteful for large conversations
- Separate context_messages table: Rejected - adds complexity, denormalization issues

---

## Decision 4: Alembic for Database Migrations

**Decision**: Use Alembic for schema versioning and migrations

**Rationale**:
- Industry standard for SQLAlchemy migrations
- Auto-generates migrations from model changes
- Tracks schema version in database (alembic_version table)
- Supports upgrade/downgrade operations
- Can auto-apply migrations on startup

**Migration Setup**:

1. Initialize Alembic in project:
```bash
alembic init src/haia/db/migrations
```

2. Configure `alembic.ini` with async engine:
```ini
sqlalchemy.url = sqlite+aiosqlite:///./haia.db
```

3. Update `env.py` for async migrations:
```python
from sqlalchemy.ext.asyncio import create_async_engine
from haia.db.models import Base

config = context.config
target_metadata = Base.metadata

async def run_migrations_online():
    connectable = create_async_engine(config.get_main_option("sqlalchemy.url"))
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
```

4. Auto-apply on startup (in `session.py`):
```python
async def init_db():
    """Initialize database and run migrations."""
    from alembic.config import Config
    from alembic import command

    alembic_cfg = Config("alembic.ini")
    command.upgrade(alembic_cfg, "head")  # Apply all pending migrations
```

**Migration Workflow**:
1. Modify models (add field, new table, etc.)
2. Generate migration: `alembic revision --autogenerate -m "description"`
3. Review auto-generated migration file
4. Apply: `alembic upgrade head` (or auto-apply on startup)

**Alternatives Considered**:
- Manual SQL migration scripts: Rejected - error-prone, no version tracking
- SQLAlchemy's create_all(): Rejected - doesn't handle schema changes, only creates missing tables
- No migrations (recreate database each time): Rejected - data loss on upgrades

---

## Decision 5: Database Session Management

**Decision**: Use FastAPI dependency injection for session lifecycle

**Rationale**:
- FastAPI's `Depends()` provides clean dependency injection
- Async context manager ensures session cleanup
- Connection pooling handled by AsyncEngine
- Easy to override for testing (provide mock session)

**Implementation Pattern**:

```python
# In session.py
from sqlalchemy.ext.asyncio import AsyncSession

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency for database sessions."""
    async with async_session() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()

# In API endpoint
from fastapi import Depends

@app.post("/chat")
async def chat(
    message: str,
    db: AsyncSession = Depends(get_db)
):
    repo = ConversationRepository(db)
    await repo.add_message(conv_id, "user", message)
```

**Session Lifecycle**:
1. Request arrives at FastAPI endpoint
2. `Depends(get_db)` creates new AsyncSession
3. Repository uses session for queries
4. On success: session commits automatically
5. On error: session rolls back
6. Session closes in finally block

**Connection Pooling**:
```python
engine = create_async_engine(
    "sqlite+aiosqlite:///./haia.db",
    pool_size=5,  # Max 5 concurrent connections
    max_overflow=10,  # Allow 10 additional connections under load
    echo=False,  # Set True for SQL logging during development
)
```

**Alternatives Considered**:
- Manual session management in each endpoint: Rejected - repetitive, error-prone
- Global session object: Rejected - not safe for concurrent requests
- Session per repository instance: Rejected - harder to control lifecycle

---

## Best Practices Applied

1. **Async-First**: All database operations use async/await
2. **Type Safety**: Mapped[] annotations for full type checking
3. **Separation of Concerns**: Repository pattern isolates data access
4. **Performance**: Indexed queries, connection pooling
5. **Maintainability**: Alembic migrations for schema versioning
6. **Testability**: Dependency injection enables easy mocking
7. **Error Handling**: Graceful rollback on exceptions

---

## Implementation Checklist

- [x] Research SQLAlchemy 2.0 async patterns ✅
- [x] Design repository interface ✅
- [x] Plan context window query strategy ✅
- [x] Configure Alembic migrations ✅
- [x] Design session management pattern ✅
- [ ] Implement SQLAlchemy models (data-model.md)
- [ ] Implement repository class
- [ ] Configure Alembic for async
- [ ] Write unit tests for repository
- [ ] Write integration tests with real database
- [ ] Add logging and observability

---

## References

- [SQLAlchemy 2.0 Async Documentation](https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html)
- [Alembic Tutorial](https://alembic.sqlalchemy.org/en/latest/tutorial.html)
- [FastAPI Dependency Injection](https://fastapi.tiangolo.com/tutorial/dependencies/)
- [SQLAlchemy Performance Best Practices](https://docs.sqlalchemy.org/en/20/faq/performance.html)
