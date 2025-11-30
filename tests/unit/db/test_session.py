"""Unit tests for database session management."""

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from haia.db.models import Base
from haia.db.session import get_db, init_db


@pytest.fixture
async def async_session() -> async_sessionmaker[AsyncSession]:
    """Create an in-memory SQLite database for testing."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")

    async with engine.begin() as conn:
        # Enable foreign key constraints in SQLite
        await conn.execute(text("PRAGMA foreign_keys = ON"))
        await conn.run_sync(Base.metadata.create_all)

    session_maker = async_sessionmaker(engine, expire_on_commit=False)
    yield session_maker

    await engine.dispose()


class TestGetDbDependency:
    """Tests for get_db FastAPI dependency function."""

    async def test_get_db_yields_session(self) -> None:
        """Test that get_db yields an AsyncSession."""
        generator = get_db()
        session = await anext(generator)

        assert isinstance(session, AsyncSession)

        # Cleanup
        try:
            await generator.aclose()
        except StopAsyncIteration:
            pass

    async def test_get_db_commits_on_success(
        self, async_session: async_sessionmaker[AsyncSession]
    ) -> None:
        """Test that get_db automatically commits on success."""
        from haia.db.models import Conversation

        # Override the global async_session for this test
        import haia.db.session

        original_session = haia.db.session.async_session
        haia.db.session.async_session = async_session

        try:
            # Use get_db to create a conversation (proper async context manager usage)
            async for session in get_db():
                conversation = Conversation()
                session.add(conversation)
                # Exit the async for loop, which should trigger commit

            # Verify data was committed
            async with async_session() as new_session:
                from sqlalchemy import select

                result = await new_session.execute(select(Conversation))
                conversations = list(result.scalars().all())
                assert len(conversations) == 1

        finally:
            # Restore original session
            haia.db.session.async_session = original_session

    async def test_get_db_rolls_back_on_error(
        self, async_session: async_sessionmaker[AsyncSession]
    ) -> None:
        """Test that get_db rolls back on error."""
        from haia.db.models import Conversation

        import haia.db.session

        original_session = haia.db.session.async_session
        haia.db.session.async_session = async_session

        try:
            generator = get_db()
            session = await anext(generator)

            conversation = Conversation()
            session.add(conversation)

            # Simulate an error by raising exception
            try:
                await generator.athrow(ValueError("Test error"))
            except ValueError:
                pass

            # Verify data was NOT committed
            async with async_session() as new_session:
                from sqlalchemy import select

                result = await new_session.execute(select(Conversation))
                conversations = list(result.scalars().all())
                assert len(conversations) == 0

        finally:
            haia.db.session.async_session = original_session


class TestInitDb:
    """Tests for database initialization function."""

    async def test_init_db_creates_schema(self) -> None:
        """Test that init_db creates all tables."""
        import haia.db.session

        # Create a new in-memory engine for this test
        test_engine = create_async_engine("sqlite+aiosqlite:///:memory:")

        # Replace the global engine temporarily
        original_engine = haia.db.session.engine
        haia.db.session.engine = test_engine

        try:
            # Run init_db
            await init_db()

            # Verify tables were created
            async with test_engine.begin() as conn:
                # Check that conversations table exists
                result = await conn.execute(
                    text("SELECT name FROM sqlite_master WHERE type='table' AND name='conversations'")
                )
                tables = list(result.scalars())
                assert "conversations" in tables

                # Check that messages table exists
                result = await conn.execute(
                    text("SELECT name FROM sqlite_master WHERE type='table' AND name='messages'")
                )
                tables = list(result.scalars())
                assert "messages" in tables

        finally:
            # Restore original engine
            haia.db.session.engine = original_engine
            await test_engine.dispose()

    async def test_init_db_idempotent(self) -> None:
        """Test that init_db can be called multiple times safely."""
        import haia.db.session

        test_engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        original_engine = haia.db.session.engine
        haia.db.session.engine = test_engine

        try:
            # Call init_db twice
            await init_db()
            await init_db()  # Should not raise error

            # Verify tables still exist
            async with test_engine.begin() as conn:
                result = await conn.execute(
                    text("SELECT name FROM sqlite_master WHERE type='table'")
                )
                tables = list(result.scalars())
                assert "conversations" in tables
                assert "messages" in tables

        finally:
            haia.db.session.engine = original_engine
            await test_engine.dispose()


class TestSessionLifecycle:
    """Tests for complete session lifecycle."""

    async def test_session_isolation(
        self, async_session: async_sessionmaker[AsyncSession]
    ) -> None:
        """Test that separate sessions are isolated."""
        from haia.db.models import Conversation

        # Session 1: Create conversation (no commit)
        async with async_session() as session1:
            conversation = Conversation()
            session1.add(conversation)
            # Don't commit

        # Session 2: Should not see uncommitted data
        async with async_session() as session2:
            from sqlalchemy import select

            result = await session2.execute(select(Conversation))
            conversations = list(result.scalars().all())
            assert len(conversations) == 0

    async def test_session_commit_visible_to_new_session(
        self, async_session: async_sessionmaker[AsyncSession]
    ) -> None:
        """Test that committed data is visible to new sessions."""
        from haia.db.models import Conversation

        # Session 1: Create and commit conversation
        async with async_session() as session1:
            conversation = Conversation()
            session1.add(conversation)
            await session1.commit()
            conv_id = conversation.id

        # Session 2: Should see committed data
        async with async_session() as session2:
            from sqlalchemy import select

            result = await session2.execute(select(Conversation).where(Conversation.id == conv_id))
            retrieved_conv = result.scalar_one_or_none()
            assert retrieved_conv is not None
            assert retrieved_conv.id == conv_id

    async def test_session_expire_on_commit_false(
        self, async_session: async_sessionmaker[AsyncSession]
    ) -> None:
        """Test that expire_on_commit=False keeps objects usable after commit."""
        from haia.db.models import Conversation

        async with async_session() as session:
            conversation = Conversation()
            session.add(conversation)
            await session.commit()

            # Object should still be usable after commit
            assert conversation.id is not None
            assert conversation.created_at is not None
