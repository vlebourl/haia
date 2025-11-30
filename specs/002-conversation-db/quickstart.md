# Quickstart: Conversation Database Persistence

**Feature**: Conversation Database Persistence
**Audience**: Developers integrating the database layer into HAIA
**Prerequisites**: Python 3.11+, SQLAlchemy 2.0+, aiosqlite

---

## Installation

Add dependencies to `pyproject.toml`:

```toml
[project]
dependencies = [
    "sqlalchemy[asyncio]>=2.0.0",
    "aiosqlite>=0.17.0",
    "alembic>=1.12.0",
]
```

Install with `uv`:

```bash
uv sync
```

---

## Quick Start (5 minutes)

### 1. Initialize Database Engine

```python
# src/haia/db/session.py
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine
from haia.config import settings

# Create async engine
engine: AsyncEngine = create_async_engine(
    settings.DATABASE_URL,  # "sqlite+aiosqlite:///./haia.db"
    echo=False,  # Set to True for SQL logging during development
    pool_size=5,
    max_overflow=10,
)

# Create session factory
async_session = async_sessionmaker(
    engine,
    expire_on_commit=False,  # Keep objects usable after commit
)
```

### 2. Initialize Database Schema

```python
# src/haia/db/session.py (continued)
from haia.db.models import Base

async def init_db() -> None:
    """Initialize database schema on first startup."""
    async with engine.begin() as conn:
        # Create all tables if they don't exist
        await conn.run_sync(Base.metadata.create_all)

# Run on application startup
import asyncio
asyncio.run(init_db())
```

### 3. Use Repository in FastAPI Endpoint

```python
# src/haia/db/session.py (dependency injection)
from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency for database sessions."""
    async with async_session() as session:
        try:
            yield session
            await session.commit()  # Auto-commit on success
        except Exception:
            await session.rollback()  # Rollback on error
            raise
        finally:
            await session.close()
```

```python
# src/haia/interfaces/api.py
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from haia.db.session import get_db
from haia.db.repository import ConversationRepository

router = APIRouter()

@router.post("/chat")
async def chat_endpoint(
    message: str,
    db: AsyncSession = Depends(get_db)
):
    """Handle chat message and persist to database."""
    repo = ConversationRepository(db)

    # Create new conversation (or retrieve existing one)
    conversation = await repo.create_conversation()

    # Add user message
    user_msg = await repo.add_message(
        conversation_id=conversation.id,
        role="user",
        content=message
    )

    # Get context for LLM (last 20 messages)
    context = await repo.get_context_messages(conversation.id, limit=20)

    # TODO: Call LLM with context and generate response
    # assistant_response = await llm.generate(context)

    # Add assistant response to conversation
    assistant_msg = await repo.add_message(
        conversation_id=conversation.id,
        role="assistant",
        content="Mock response"  # Replace with actual LLM response
    )

    return {"response": assistant_msg.content}
```

---

## Common Usage Patterns

### Pattern 1: Create Conversation and Add Messages

```python
from haia.db.repository import ConversationRepository
from haia.db.session import async_session

async def example_create_conversation():
    async with async_session() as session:
        repo = ConversationRepository(session)

        # Create new conversation
        conversation = await repo.create_conversation()
        print(f"Created conversation {conversation.id}")

        # Add system message
        await repo.add_message(
            conversation_id=conversation.id,
            role="system",
            content="You are a helpful homelab assistant."
        )

        # Add user message
        await repo.add_message(
            conversation_id=conversation.id,
            role="user",
            content="What is the status of my Proxmox cluster?"
        )

        # Session auto-commits when context exits
        await session.commit()
```

### Pattern 2: Retrieve Context Window for LLM

```python
async def get_llm_context(conversation_id: int) -> list[dict]:
    """Get formatted context for LLM API call."""
    async with async_session() as session:
        repo = ConversationRepository(session)

        # Get last 20 messages
        messages = await repo.get_context_messages(conversation_id, limit=20)

        # Format for LLM API (OpenAI-style)
        return [
            {"role": msg.role, "content": msg.content}
            for msg in messages
        ]
```

### Pattern 3: List All Conversations

```python
async def list_recent_conversations() -> list[dict]:
    """List all conversations sorted by recent activity."""
    async with async_session() as session:
        repo = ConversationRepository(session)

        conversations = await repo.list_conversations(limit=10)

        return [
            {
                "id": conv.id,
                "created_at": conv.created_at.isoformat(),
                "updated_at": conv.updated_at.isoformat(),
                "message_count": len(conv.messages),
            }
            for conv in conversations
        ]
```

### Pattern 4: Delete Old Conversations

```python
async def cleanup_old_conversations(days: int = 30):
    """Delete conversations older than N days."""
    from datetime import datetime, timedelta

    async with async_session() as session:
        repo = ConversationRepository(session)

        cutoff = datetime.utcnow() - timedelta(days=days)
        conversations = await repo.list_conversations(limit=1000)

        deleted_count = 0
        for conv in conversations:
            if conv.updated_at < cutoff:
                await repo.delete_conversation(conv.id)
                deleted_count += 1

        await session.commit()
        print(f"Deleted {deleted_count} old conversations")
```

### Pattern 5: Display Full Conversation History

```python
async def display_conversation(conversation_id: int):
    """Display all messages in a conversation (for debugging)."""
    async with async_session() as session:
        repo = ConversationRepository(session)

        messages = await repo.get_all_messages(conversation_id)

        for msg in messages:
            timestamp = msg.created_at.strftime("%Y-%m-%d %H:%M:%S")
            print(f"[{timestamp}] {msg.role}: {msg.content}")
```

---

## Database Migrations with Alembic

### Initial Setup

```bash
# Initialize Alembic (one-time setup)
alembic init src/haia/db/migrations
```

Edit `alembic.ini`:

```ini
# Point to database URL
sqlalchemy.url = sqlite+aiosqlite:///./haia.db
```

Edit `src/haia/db/migrations/env.py`:

```python
from haia.db.models import Base

# Set target metadata
target_metadata = Base.metadata
```

### Create Initial Migration

```bash
# Generate migration from models
alembic revision --autogenerate -m "Initial schema"

# Apply migration
alembic upgrade head
```

### Auto-Apply Migrations on Startup

```python
# src/haia/db/session.py
from alembic.config import Config
from alembic import command

async def run_migrations():
    """Apply pending database migrations on startup."""
    alembic_cfg = Config("alembic.ini")
    command.upgrade(alembic_cfg, "head")

# Call during application startup
await run_migrations()
```

---

## Configuration

### Environment Variables

```bash
# .env file
DATABASE_URL=sqlite+aiosqlite:///./haia.db
DATABASE_ECHO=false  # Set to true for SQL query logging
```

### Pydantic Settings

```python
# src/haia/config.py
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    DATABASE_URL: str = "sqlite+aiosqlite:///./haia.db"
    DATABASE_ECHO: bool = False

    class Config:
        env_file = ".env"

settings = Settings()
```

---

## Testing

### Unit Tests (Mock Database)

```python
# tests/unit/db/test_repository.py
import pytest
from unittest.mock import AsyncMock, MagicMock
from haia.db.repository import ConversationRepository
from haia.db.models import Conversation, Message

@pytest.mark.asyncio
async def test_create_conversation():
    # Mock session
    mock_session = AsyncMock()
    repo = ConversationRepository(mock_session)

    # Test
    conversation = await repo.create_conversation()

    # Verify
    mock_session.add.assert_called_once()
    assert isinstance(conversation, Conversation)
```

### Integration Tests (Real Database)

```python
# tests/integration/test_db_persistence.py
import pytest
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from haia.db.models import Base
from haia.db.repository import ConversationRepository

@pytest.fixture
async def db_session():
    """Create in-memory SQLite database for testing."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async_session = async_sessionmaker(engine, expire_on_commit=False)
    async with async_session() as session:
        yield session

@pytest.mark.asyncio
async def test_add_message_integration(db_session):
    repo = ConversationRepository(db_session)

    # Create conversation
    conversation = await repo.create_conversation()
    await db_session.commit()

    # Add message
    message = await repo.add_message(
        conversation_id=conversation.id,
        role="user",
        content="Test message"
    )
    await db_session.commit()

    # Verify
    assert message.id is not None
    assert message.content == "Test message"

    # Retrieve and verify
    messages = await repo.get_all_messages(conversation.id)
    assert len(messages) == 1
    assert messages[0].content == "Test message"
```

---

## Performance Tuning

### Enable Connection Pooling

```python
engine = create_async_engine(
    settings.DATABASE_URL,
    pool_size=10,  # Increase for high concurrency
    max_overflow=20,
    pool_pre_ping=True,  # Verify connections before use
)
```

### Enable Query Logging (Development)

```python
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=True,  # Log all SQL queries
)
```

### Optimize Context Window Query

The repository uses a composite index for efficient context window queries:

```sql
-- Automatically created by SQLAlchemy
CREATE INDEX ix_messages_conversation_created
ON messages (conversation_id, created_at);

-- Query plan (verify with EXPLAIN)
EXPLAIN QUERY PLAN
SELECT * FROM messages
WHERE conversation_id = 123
ORDER BY created_at DESC
LIMIT 20;

-- Should show: SEARCH messages USING INDEX ix_messages_conversation_created
```

---

## Troubleshooting

### Issue: "No such table: conversations"

**Cause**: Database schema not initialized

**Solution**: Run migrations or create tables manually:

```python
await init_db()  # Creates all tables
```

### Issue: "Database is locked"

**Cause**: Multiple processes trying to write simultaneously (SQLite limitation)

**Solution**: Use connection pooling with `pool_pre_ping=True` or migrate to PostgreSQL for production

### Issue: "asyncio.run() cannot be called from a running event loop"

**Cause**: Trying to run async code in already-running event loop

**Solution**: Use `await` instead of `asyncio.run()`:

```python
# Wrong
asyncio.run(init_db())

# Correct (in async context)
await init_db()
```

---

## Next Steps

1. **Implement Repository**: Follow the contract in `contracts/repository.json`
2. **Write Tests**: Cover all repository methods with unit and integration tests
3. **Integrate with Agent**: Pass conversation context to PydanticAI agent
4. **Add Logging**: Log all database operations for observability
5. **Production Hardening**: Add retry logic, connection pooling, monitoring

---

## References

- [SQLAlchemy 2.0 Async Tutorial](https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html)
- [FastAPI Dependencies](https://fastapi.tiangolo.com/tutorial/dependencies/)
- [Alembic Migrations](https://alembic.sqlalchemy.org/en/latest/tutorial.html)
- [aiosqlite Documentation](https://aiosqlite.omnilib.dev/en/stable/)
