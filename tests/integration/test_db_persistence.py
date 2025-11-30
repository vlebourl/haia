"""Integration tests for database persistence across sessions."""

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


class TestMessagePersistence:
    """Integration tests for message persistence."""

    async def test_messages_persist_across_sessions(
        self, async_session: async_sessionmaker[AsyncSession]
    ) -> None:
        """Test that messages persist and can be retrieved in a new session."""
        # Session 1: Create conversation and add messages
        async with async_session() as session:
            repo = ConversationRepository(session)
            conversation = await repo.create_conversation()
            await repo.add_message(conversation.id, "system", "You are a helpful assistant.")
            await repo.add_message(conversation.id, "user", "Hello!")
            await repo.add_message(conversation.id, "assistant", "Hi! How can I help you?")
            await session.commit()
            conv_id = conversation.id

        # Session 2: Retrieve conversation and verify messages
        async with async_session() as session:
            repo = ConversationRepository(session)
            conversation = await repo.get_conversation(conv_id)

            assert conversation is not None
            assert len(conversation.messages) == 3

            # Verify message content and order
            messages = conversation.messages
            assert messages[0].role == "system"
            assert messages[0].content == "You are a helpful assistant."
            assert messages[1].role == "user"
            assert messages[1].content == "Hello!"
            assert messages[2].role == "assistant"
            assert messages[2].content == "Hi! How can I help you?"

    async def test_messages_maintain_chronological_order(
        self, async_session: async_sessionmaker[AsyncSession]
    ) -> None:
        """Test that messages are retrieved in chronological order."""
        async with async_session() as session:
            repo = ConversationRepository(session)
            conversation = await repo.create_conversation()

            # Add messages with slight delays to ensure different timestamps
            for i in range(5):
                await repo.add_message(conversation.id, "user", f"Message {i + 1}")

            await session.commit()
            conv_id = conversation.id

        # Retrieve and verify order
        async with async_session() as session:
            repo = ConversationRepository(session)
            messages = await repo.get_all_messages(conv_id)

            assert len(messages) == 5
            for i in range(5):
                assert messages[i].content == f"Message {i + 1}"
                if i > 0:
                    # Timestamps should be in ascending order
                    assert messages[i].created_at >= messages[i - 1].created_at

    async def test_multiple_conversations_independent(
        self, async_session: async_sessionmaker[AsyncSession]
    ) -> None:
        """Test that multiple conversations store messages independently."""
        async with async_session() as session:
            repo = ConversationRepository(session)

            # Create two conversations
            conv1 = await repo.create_conversation()
            conv2 = await repo.create_conversation()

            # Add messages to each
            await repo.add_message(conv1.id, "user", "Conv1 Message 1")
            await repo.add_message(conv1.id, "assistant", "Conv1 Message 2")

            await repo.add_message(conv2.id, "user", "Conv2 Message 1")
            await repo.add_message(conv2.id, "assistant", "Conv2 Message 2")
            await repo.add_message(conv2.id, "user", "Conv2 Message 3")

            await session.commit()
            conv1_id = conv1.id
            conv2_id = conv2.id

        # Verify each conversation has correct messages
        async with async_session() as session:
            repo = ConversationRepository(session)

            conv1_messages = await repo.get_all_messages(conv1_id)
            conv2_messages = await repo.get_all_messages(conv2_id)

            assert len(conv1_messages) == 2
            assert all("Conv1" in msg.content for msg in conv1_messages)

            assert len(conv2_messages) == 3
            assert all("Conv2" in msg.content for msg in conv2_messages)

    async def test_empty_conversation_retrieval(
        self, async_session: async_sessionmaker[AsyncSession]
    ) -> None:
        """Test retrieving a conversation with no messages."""
        async with async_session() as session:
            repo = ConversationRepository(session)
            conversation = await repo.create_conversation()
            await session.commit()
            conv_id = conversation.id

        async with async_session() as session:
            repo = ConversationRepository(session)
            conversation = await repo.get_conversation(conv_id)

            assert conversation is not None
            assert len(conversation.messages) == 0

    async def test_large_message_content_persistence(
        self, async_session: async_sessionmaker[AsyncSession]
    ) -> None:
        """Test persisting and retrieving large message content."""
        large_content = "A" * 50000  # 50k characters

        async with async_session() as session:
            repo = ConversationRepository(session)
            conversation = await repo.create_conversation()
            await repo.add_message(conversation.id, "user", large_content)
            await session.commit()
            conv_id = conversation.id

        async with async_session() as session:
            repo = ConversationRepository(session)
            messages = await repo.get_all_messages(conv_id)

            assert len(messages) == 1
            assert messages[0].content == large_content
            assert len(messages[0].content) == 50000
