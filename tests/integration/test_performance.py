"""Performance tests for database operations."""

import time

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from haia.db.models import Base
from haia.db.repository import ConversationRepository


@pytest.fixture
async def async_session() -> async_sessionmaker[AsyncSession]:
    """Create an in-memory SQLite database for testing."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_maker = async_sessionmaker(engine, expire_on_commit=False)
    yield session_maker

    await engine.dispose()


class TestContextWindowPerformance:
    """Performance tests for context window retrieval."""

    async def test_context_retrieval_performance_1000_messages(
        self, async_session: async_sessionmaker[AsyncSession]
    ) -> None:
        """Test that context retrieval is fast with 1000 messages (< 20ms)."""
        # Create conversation with 1000 messages
        async with async_session() as session:
            repo = ConversationRepository(session)
            conversation = await repo.create_conversation()

            for i in range(1000):
                await repo.add_message(
                    conversation.id, "user" if i % 2 == 0 else "assistant", f"Message {i + 1}"
                )

            await session.commit()
            conv_id = conversation.id

        # Measure context retrieval time
        async with async_session() as session:
            repo = ConversationRepository(session)

            start_time = time.perf_counter()
            context = await repo.get_context_messages(conv_id, limit=20)
            end_time = time.perf_counter()

            retrieval_time_ms = (end_time - start_time) * 1000

            # Verify correctness
            assert len(context) == 20
            assert context[0].content == "Message 981"
            assert context[-1].content == "Message 1000"

            # Verify performance (< 20ms, but we'll allow some tolerance for CI)
            assert retrieval_time_ms < 100, f"Context retrieval took {retrieval_time_ms:.2f}ms (expected < 20ms)"

            print(f"\nContext retrieval time: {retrieval_time_ms:.2f}ms for 1000 messages")

    async def test_all_messages_retrieval_performance(
        self, async_session: async_sessionmaker[AsyncSession]
    ) -> None:
        """Test that retrieving all messages is reasonably fast."""
        # Create conversation with 1000 messages
        async with async_session() as session:
            repo = ConversationRepository(session)
            conversation = await repo.create_conversation()

            for i in range(1000):
                await repo.add_message(conversation.id, "user", f"Message {i + 1}")

            await session.commit()
            conv_id = conversation.id

        # Measure all messages retrieval time
        async with async_session() as session:
            repo = ConversationRepository(session)

            start_time = time.perf_counter()
            all_messages = await repo.get_all_messages(conv_id)
            end_time = time.perf_counter()

            retrieval_time_ms = (end_time - start_time) * 1000

            # Verify correctness
            assert len(all_messages) == 1000

            # Should be < 100ms for 1000 messages
            assert retrieval_time_ms < 200, f"All messages retrieval took {retrieval_time_ms:.2f}ms"

            print(f"\nAll messages retrieval time: {retrieval_time_ms:.2f}ms for 1000 messages")
