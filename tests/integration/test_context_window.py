"""Integration tests for context window management."""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from haia.db.models import Base
from haia.db.repository import ConversationRepository


@pytest.fixture
async def async_session() -> async_sessionmaker[AsyncSession]:
    """Create an in-memory SQLite database for testing."""
    from sqlalchemy import text

    engine = create_async_engine("sqlite+aiosqlite:///:memory:")

    async with engine.begin() as conn:
        # Enable foreign key constraints in SQLite
        await conn.execute(text("PRAGMA foreign_keys = ON"))
        await conn.run_sync(Base.metadata.create_all)

    session_maker = async_sessionmaker(engine, expire_on_commit=False)
    yield session_maker

    await engine.dispose()


class TestContextWindow20MessageLimit:
    """Integration tests for 20-message context window limit."""

    async def test_context_window_exactly_20_messages(
        self, async_session: async_sessionmaker[AsyncSession]
    ) -> None:
        """Test context window with exactly 20 messages."""
        async with async_session() as session:
            repo = ConversationRepository(session)
            conversation = await repo.create_conversation()

            # Add exactly 20 messages
            for i in range(20):
                await repo.add_message(conversation.id, "user", f"Message {i + 1}")

            await session.commit()
            conv_id = conversation.id

        # Retrieve context
        async with async_session() as session:
            repo = ConversationRepository(session)
            context = await repo.get_context_messages(conv_id)
            all_messages = await repo.get_all_messages(conv_id)

            # Should return all 20 messages
            assert len(context) == 20
            assert len(all_messages) == 20
            assert context[0].content == "Message 1"
            assert context[-1].content == "Message 20"

    async def test_context_window_more_than_20_messages(
        self, async_session: async_sessionmaker[AsyncSession]
    ) -> None:
        """Test that context window returns exactly 20 most recent messages when >20 exist."""
        async with async_session() as session:
            repo = ConversationRepository(session)
            conversation = await repo.create_conversation()

            # Add 30 messages
            for i in range(30):
                await repo.add_message(conversation.id, "user", f"Message {i + 1}")

            await session.commit()
            conv_id = conversation.id

        # Retrieve context and verify
        async with async_session() as session:
            repo = ConversationRepository(session)
            context = await repo.get_context_messages(conv_id)
            all_messages = await repo.get_all_messages(conv_id)

            # Context should have 20 most recent
            assert len(context) == 20
            # Database should have all 30
            assert len(all_messages) == 30

            # Context should be messages 11-30
            assert context[0].content == "Message 11"
            assert context[-1].content == "Message 30"

            # All messages should be 1-30
            assert all_messages[0].content == "Message 1"
            assert all_messages[-1].content == "Message 30"

    async def test_context_window_maintains_order_with_many_messages(
        self, async_session: async_sessionmaker[AsyncSession]
    ) -> None:
        """Test that context window maintains chronological order with many messages."""
        async with async_session() as session:
            repo = ConversationRepository(session)
            conversation = await repo.create_conversation()

            # Add 100 messages
            for i in range(100):
                await repo.add_message(
                    conversation.id, "user" if i % 2 == 0 else "assistant", f"Message {i + 1}"
                )

            await session.commit()
            conv_id = conversation.id

        # Retrieve context
        async with async_session() as session:
            repo = ConversationRepository(session)
            context = await repo.get_context_messages(conv_id)

            # Verify 20 most recent in chronological order
            assert len(context) == 20
            assert context[0].content == "Message 81"
            assert context[-1].content == "Message 100"

            # Verify timestamps are in order
            for i in range(len(context) - 1):
                assert context[i].created_at <= context[i + 1].created_at


class TestContextWindowUnder20Messages:
    """Integration tests for conversations with fewer than 20 messages."""

    async def test_context_window_with_1_message(
        self, async_session: async_sessionmaker[AsyncSession]
    ) -> None:
        """Test context window with only 1 message."""
        async with async_session() as session:
            repo = ConversationRepository(session)
            conversation = await repo.create_conversation()
            await repo.add_message(conversation.id, "user", "Single message")
            await session.commit()
            conv_id = conversation.id

        async with async_session() as session:
            repo = ConversationRepository(session)
            context = await repo.get_context_messages(conv_id)

            assert len(context) == 1
            assert context[0].content == "Single message"

    async def test_context_window_with_10_messages(
        self, async_session: async_sessionmaker[AsyncSession]
    ) -> None:
        """Test context window with 10 messages (under limit)."""
        async with async_session() as session:
            repo = ConversationRepository(session)
            conversation = await repo.create_conversation()

            for i in range(10):
                await repo.add_message(conversation.id, "user", f"Message {i + 1}")

            await session.commit()
            conv_id = conversation.id

        async with async_session() as session:
            repo = ConversationRepository(session)
            context = await repo.get_context_messages(conv_id)

            # Should return all 10 messages
            assert len(context) == 10
            assert context[0].content == "Message 1"
            assert context[-1].content == "Message 10"

    async def test_context_window_with_empty_conversation(
        self, async_session: async_sessionmaker[AsyncSession]
    ) -> None:
        """Test context window with no messages."""
        async with async_session() as session:
            repo = ConversationRepository(session)
            conversation = await repo.create_conversation()
            await session.commit()
            conv_id = conversation.id

        async with async_session() as session:
            repo = ConversationRepository(session)
            context = await repo.get_context_messages(conv_id)

            assert len(context) == 0
            assert context == []

    async def test_context_window_growing_conversation(
        self, async_session: async_sessionmaker[AsyncSession]
    ) -> None:
        """Test context window as conversation grows from 0 to 30+ messages."""
        async with async_session() as session:
            repo = ConversationRepository(session)
            conversation = await repo.create_conversation()
            await session.commit()
            conv_id = conversation.id

        # Add messages incrementally and verify context window
        for target_count in [5, 10, 15, 20, 25, 30]:
            async with async_session() as session:
                repo = ConversationRepository(session)
                current_messages = await repo.get_all_messages(conv_id)
                current_count = len(current_messages)

                # Add messages to reach target
                for i in range(current_count, target_count):
                    await repo.add_message(conv_id, "user", f"Message {i + 1}")

                await session.commit()

            # Verify context window size
            async with async_session() as session:
                repo = ConversationRepository(session)
                context = await repo.get_context_messages(conv_id)

                expected_size = min(target_count, 20)
                assert len(context) == expected_size

                # Verify we get the most recent messages
                if target_count <= 20:
                    assert context[0].content == "Message 1"
                else:
                    # Should start from message (target_count - 19)
                    assert context[0].content == f"Message {target_count - 19}"

                assert context[-1].content == f"Message {target_count}"
