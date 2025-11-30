"""Unit tests for ConversationRepository."""

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from haia.db.models import Base
from haia.db.repository import ConversationRepository


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


class TestCreateConversation:
    """Tests for create_conversation method."""

    async def test_create_conversation_returns_conversation(
        self, async_session: async_sessionmaker[AsyncSession]
    ) -> None:
        """Test that create_conversation returns a Conversation object."""
        from haia.db.models import Conversation

        async with async_session() as session:
            repo = ConversationRepository(session)
            conversation = await repo.create_conversation()

            assert isinstance(conversation, Conversation)
            assert conversation.id is not None

    async def test_create_conversation_persists_to_database(
        self, async_session: async_sessionmaker[AsyncSession]
    ) -> None:
        """Test that created conversation is persisted to database."""
        from sqlalchemy import select

        from haia.db.models import Conversation

        async with async_session() as session:
            repo = ConversationRepository(session)
            conversation = await repo.create_conversation()
            conv_id = conversation.id
            await session.commit()

        # Verify in new session
        async with async_session() as session:
            result = await session.execute(select(Conversation).where(Conversation.id == conv_id))
            saved_conversation = result.scalar_one_or_none()

            assert saved_conversation is not None
            assert saved_conversation.id == conv_id


class TestAddMessage:
    """Tests for add_message method."""

    async def test_add_message_returns_message(
        self, async_session: async_sessionmaker[AsyncSession]
    ) -> None:
        """Test that add_message returns a Message object."""
        from haia.db.models import Message

        async with async_session() as session:
            repo = ConversationRepository(session)
            conversation = await repo.create_conversation()
            await session.commit()

            message = await repo.add_message(
                conversation_id=conversation.id,
                role="user",
                content="Test message",
            )

            assert isinstance(message, Message)
            assert message.id is not None
            assert message.content == "Test message"

    async def test_add_message_persists_to_database(
        self, async_session: async_sessionmaker[AsyncSession]
    ) -> None:
        """Test that added message is persisted to database."""
        from sqlalchemy import select

        from haia.db.models import Message

        async with async_session() as session:
            repo = ConversationRepository(session)
            conversation = await repo.create_conversation()
            await session.commit()

            message = await repo.add_message(
                conversation_id=conversation.id,
                role="user",
                content="Test message",
            )
            msg_id = message.id
            await session.commit()

        # Verify in new session
        async with async_session() as session:
            result = await session.execute(select(Message).where(Message.id == msg_id))
            saved_message = result.scalar_one_or_none()

            assert saved_message is not None
            assert saved_message.content == "Test message"
            assert saved_message.role == "user"

    async def test_add_multiple_messages(
        self, async_session: async_sessionmaker[AsyncSession]
    ) -> None:
        """Test adding multiple messages to a conversation."""
        async with async_session() as session:
            repo = ConversationRepository(session)
            conversation = await repo.create_conversation()
            await session.commit()

            # Add multiple messages
            msg1 = await repo.add_message(conversation.id, "user", "First message")
            msg2 = await repo.add_message(conversation.id, "assistant", "Second message")
            msg3 = await repo.add_message(conversation.id, "user", "Third message")
            await session.commit()

            assert msg1.id is not None
            assert msg2.id is not None
            assert msg3.id is not None
            # IDs should be different
            assert msg1.id != msg2.id != msg3.id


class TestGetConversation:
    """Tests for get_conversation method."""

    async def test_get_conversation_returns_conversation(
        self, async_session: async_sessionmaker[AsyncSession]
    ) -> None:
        """Test that get_conversation returns the correct conversation."""
        async with async_session() as session:
            repo = ConversationRepository(session)
            conversation = await repo.create_conversation()
            await session.commit()
            conv_id = conversation.id

        async with async_session() as session:
            repo = ConversationRepository(session)
            retrieved = await repo.get_conversation(conv_id)

            assert retrieved is not None
            assert retrieved.id == conv_id

    async def test_get_conversation_returns_none_for_missing(
        self, async_session: async_sessionmaker[AsyncSession]
    ) -> None:
        """Test that get_conversation returns None for non-existent conversation."""
        async with async_session() as session:
            repo = ConversationRepository(session)
            retrieved = await repo.get_conversation(999999)

            assert retrieved is None

    async def test_get_conversation_with_messages(
        self, async_session: async_sessionmaker[AsyncSession]
    ) -> None:
        """Test that get_conversation loads messages."""
        async with async_session() as session:
            repo = ConversationRepository(session)
            conversation = await repo.create_conversation()
            await repo.add_message(conversation.id, "user", "Message 1")
            await repo.add_message(conversation.id, "assistant", "Message 2")
            await session.commit()
            conv_id = conversation.id

        async with async_session() as session:
            repo = ConversationRepository(session)
            retrieved = await repo.get_conversation(conv_id)

            assert retrieved is not None
            assert len(retrieved.messages) == 2


class TestListConversations:
    """Tests for list_conversations method."""

    async def test_list_conversations_empty(
        self, async_session: async_sessionmaker[AsyncSession]
    ) -> None:
        """Test listing conversations when none exist."""
        async with async_session() as session:
            repo = ConversationRepository(session)
            conversations = await repo.list_conversations()

            assert conversations == []

    async def test_list_conversations_sorted_by_updated_at(
        self, async_session: async_sessionmaker[AsyncSession]
    ) -> None:
        """Test that conversations are sorted by updated_at DESC (most recent first)."""
        async with async_session() as session:
            repo = ConversationRepository(session)

            # Create 3 conversations
            conv1 = await repo.create_conversation()
            conv2 = await repo.create_conversation()
            conv3 = await repo.create_conversation()

            # Add messages to conversations in different order
            await repo.add_message(conv1.id, "user", "Message to conv1")
            await repo.add_message(conv3.id, "user", "Message to conv3")
            await repo.add_message(conv2.id, "user", "Message to conv2")

            await session.commit()

        async with async_session() as session:
            repo = ConversationRepository(session)
            conversations = await repo.list_conversations()

            # Should be sorted by updated_at DESC: conv2, conv3, conv1
            assert len(conversations) == 3
            assert conversations[0].id == conv2.id
            assert conversations[1].id == conv3.id
            assert conversations[2].id == conv1.id

    async def test_list_conversations_with_pagination(
        self, async_session: async_sessionmaker[AsyncSession]
    ) -> None:
        """Test pagination with limit and offset."""
        async with async_session() as session:
            repo = ConversationRepository(session)

            # Create 10 conversations
            for _ in range(10):
                await repo.create_conversation()

            await session.commit()

        async with async_session() as session:
            repo = ConversationRepository(session)

            # Get first 5
            page1 = await repo.list_conversations(limit=5, offset=0)
            assert len(page1) == 5

            # Get next 5
            page2 = await repo.list_conversations(limit=5, offset=5)
            assert len(page2) == 5

            # Verify no overlap
            page1_ids = {conv.id for conv in page1}
            page2_ids = {conv.id for conv in page2}
            assert page1_ids.isdisjoint(page2_ids)


class TestDeleteConversation:
    """Tests for delete_conversation method."""

    async def test_delete_conversation_returns_true_when_exists(
        self, async_session: async_sessionmaker[AsyncSession]
    ) -> None:
        """Test that delete_conversation returns True when conversation exists."""
        async with async_session() as session:
            repo = ConversationRepository(session)
            conversation = await repo.create_conversation()
            await session.commit()
            conv_id = conversation.id

        async with async_session() as session:
            repo = ConversationRepository(session)
            deleted = await repo.delete_conversation(conv_id)
            await session.commit()

            assert deleted is True

    async def test_delete_conversation_returns_false_when_not_exists(
        self, async_session: async_sessionmaker[AsyncSession]
    ) -> None:
        """Test that delete_conversation returns False when conversation doesn't exist."""
        async with async_session() as session:
            repo = ConversationRepository(session)
            deleted = await repo.delete_conversation(999999)
            await session.commit()

            assert deleted is False

    async def test_delete_conversation_cascades_to_messages(
        self, async_session: async_sessionmaker[AsyncSession]
    ) -> None:
        """Test that deleting conversation also deletes all messages (CASCADE)."""
        from sqlalchemy import select

        from haia.db.models import Message

        async with async_session() as session:
            repo = ConversationRepository(session)
            conversation = await repo.create_conversation()
            await repo.add_message(conversation.id, "user", "Message 1")
            await repo.add_message(conversation.id, "user", "Message 2")
            await session.commit()
            conv_id = conversation.id

        # Verify messages exist
        async with async_session() as session:
            result = await session.execute(select(Message).where(Message.conversation_id == conv_id))
            messages = list(result.scalars().all())
            assert len(messages) == 2

        # Delete conversation
        async with async_session() as session:
            repo = ConversationRepository(session)
            await repo.delete_conversation(conv_id)
            await session.commit()

        # Verify messages are also deleted
        async with async_session() as session:
            result = await session.execute(select(Message).where(Message.conversation_id == conv_id))
            messages = list(result.scalars().all())
            assert len(messages) == 0


class TestGetMessageCount:
    """Tests for get_message_count method."""

    async def test_get_message_count_empty_conversation(
        self, async_session: async_sessionmaker[AsyncSession]
    ) -> None:
        """Test message count for empty conversation."""
        async with async_session() as session:
            repo = ConversationRepository(session)
            conversation = await repo.create_conversation()
            await session.commit()

            count = await repo.get_message_count(conversation.id)
            assert count == 0

    async def test_get_message_count_with_messages(
        self, async_session: async_sessionmaker[AsyncSession]
    ) -> None:
        """Test message count with multiple messages."""
        async with async_session() as session:
            repo = ConversationRepository(session)
            conversation = await repo.create_conversation()

            for i in range(25):
                await repo.add_message(conversation.id, "user", f"Message {i + 1}")

            await session.commit()

            count = await repo.get_message_count(conversation.id)
            assert count == 25

    async def test_get_message_count_nonexistent_conversation(
        self, async_session: async_sessionmaker[AsyncSession]
    ) -> None:
        """Test message count for non-existent conversation returns 0."""
        async with async_session() as session:
            repo = ConversationRepository(session)
            count = await repo.get_message_count(999999)
            assert count == 0


class TestGetContextMessages:
    """Tests for get_context_messages method."""

    async def test_get_context_messages_with_limit(
        self, async_session: async_sessionmaker[AsyncSession]
    ) -> None:
        """Test that get_context_messages respects the limit parameter."""
        async with async_session() as session:
            repo = ConversationRepository(session)
            conversation = await repo.create_conversation()

            # Add 30 messages
            for i in range(30):
                await repo.add_message(conversation.id, "user", f"Message {i + 1}")

            await session.commit()
            conv_id = conversation.id

        async with async_session() as session:
            repo = ConversationRepository(session)
            # Get context with default limit (20)
            context = await repo.get_context_messages(conv_id)

            assert len(context) == 20
            # Should be messages 11-30 (most recent 20)
            assert context[0].content == "Message 11"
            assert context[-1].content == "Message 30"

    async def test_get_context_messages_chronological_order(
        self, async_session: async_sessionmaker[AsyncSession]
    ) -> None:
        """Test that context messages are returned in chronological order (oldest first)."""
        async with async_session() as session:
            repo = ConversationRepository(session)
            conversation = await repo.create_conversation()

            for i in range(25):
                await repo.add_message(conversation.id, "user", f"Message {i + 1}")

            await session.commit()
            conv_id = conversation.id

        async with async_session() as session:
            repo = ConversationRepository(session)
            context = await repo.get_context_messages(conv_id, limit=20)

            # Verify chronological order
            for i in range(len(context) - 1):
                assert context[i].created_at <= context[i + 1].created_at

    async def test_get_context_messages_under_limit(
        self, async_session: async_sessionmaker[AsyncSession]
    ) -> None:
        """Test that get_context_messages returns all messages if under limit."""
        async with async_session() as session:
            repo = ConversationRepository(session)
            conversation = await repo.create_conversation()

            # Add only 10 messages
            for i in range(10):
                await repo.add_message(conversation.id, "user", f"Message {i + 1}")

            await session.commit()
            conv_id = conversation.id

        async with async_session() as session:
            repo = ConversationRepository(session)
            context = await repo.get_context_messages(conv_id, limit=20)

            # Should return all 10 messages
            assert len(context) == 10
            assert context[0].content == "Message 1"
            assert context[-1].content == "Message 10"

    async def test_get_context_messages_custom_limit(
        self, async_session: async_sessionmaker[AsyncSession]
    ) -> None:
        """Test get_context_messages with custom limit parameter."""
        async with async_session() as session:
            repo = ConversationRepository(session)
            conversation = await repo.create_conversation()

            for i in range(50):
                await repo.add_message(conversation.id, "user", f"Message {i + 1}")

            await session.commit()
            conv_id = conversation.id

        async with async_session() as session:
            repo = ConversationRepository(session)
            # Use custom limit of 10
            context = await repo.get_context_messages(conv_id, limit=10)

            assert len(context) == 10
            # Should be messages 41-50 (most recent 10)
            assert context[0].content == "Message 41"
            assert context[-1].content == "Message 50"
