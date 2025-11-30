"""Integration tests for conversation management."""

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


class TestConversationListing:
    """Integration tests for listing conversations."""

    async def test_list_conversations_sorted_by_activity(
        self, async_session: async_sessionmaker[AsyncSession]
    ) -> None:
        """Test that conversations are sorted by most recent activity."""
        async with async_session() as session:
            repo = ConversationRepository(session)

            # Create conversations and add messages at different times
            conv_a = await repo.create_conversation()
            conv_b = await repo.create_conversation()
            conv_c = await repo.create_conversation()

            # Add messages in specific order to set updated_at
            await repo.add_message(conv_a.id, "user", "First message to A")
            await repo.add_message(conv_b.id, "user", "First message to B")
            await repo.add_message(conv_c.id, "user", "First message to C")

            # Update conv_a again (should make it most recent)
            await repo.add_message(conv_a.id, "user", "Second message to A")

            await session.commit()

        # Retrieve conversations
        async with async_session() as session:
            repo = ConversationRepository(session)
            conversations = await repo.list_conversations()

            # Most recent should be first: conv_a, conv_c, conv_b
            assert len(conversations) == 3
            assert conversations[0].id == conv_a.id
            assert conversations[1].id == conv_c.id
            assert conversations[2].id == conv_b.id

    async def test_list_conversations_with_metadata(
        self, async_session: async_sessionmaker[AsyncSession]
    ) -> None:
        """Test that listed conversations include metadata."""
        async with async_session() as session:
            repo = ConversationRepository(session)

            conversation = await repo.create_conversation()
            await repo.add_message(conversation.id, "user", "Message 1")
            await repo.add_message(conversation.id, "assistant", "Message 2")
            await repo.add_message(conversation.id, "user", "Message 3")

            await session.commit()

        async with async_session() as session:
            repo = ConversationRepository(session)
            conversations = await repo.list_conversations()

            assert len(conversations) == 1
            conv = conversations[0]

            # Verify metadata
            assert conv.created_at is not None
            assert conv.updated_at is not None
            assert conv.updated_at >= conv.created_at
            assert len(conv.messages) == 3

    async def test_list_conversations_pagination_full_cycle(
        self, async_session: async_sessionmaker[AsyncSession]
    ) -> None:
        """Test paginating through all conversations."""
        # Create 25 conversations
        async with async_session() as session:
            repo = ConversationRepository(session)

            for i in range(25):
                conv = await repo.create_conversation()
                await repo.add_message(conv.id, "user", f"Message {i + 1}")

            await session.commit()

        # Retrieve in pages of 10
        all_conv_ids = set()

        for offset in [0, 10, 20]:
            async with async_session() as session:
                repo = ConversationRepository(session)
                page = await repo.list_conversations(limit=10, offset=offset)

                expected_count = 10 if offset < 20 else 5
                assert len(page) == expected_count

                # Track IDs
                for conv in page:
                    all_conv_ids.add(conv.id)

        # Verify we got all 25 unique conversations
        assert len(all_conv_ids) == 25


class TestConversationDeletion:
    """Integration tests for conversation deletion with CASCADE."""

    async def test_delete_conversation_cascades_all_messages(
        self, async_session: async_sessionmaker[AsyncSession]
    ) -> None:
        """Test that deleting conversation removes all messages via CASCADE."""
        from sqlalchemy import select

        from haia.db.models import Message

        # Create conversation with many messages
        async with async_session() as session:
            repo = ConversationRepository(session)
            conversation = await repo.create_conversation()

            for i in range(50):
                await repo.add_message(conversation.id, "user", f"Message {i + 1}")

            await session.commit()
            conv_id = conversation.id

        # Verify messages exist
        async with async_session() as session:
            result = await session.execute(select(Message).where(Message.conversation_id == conv_id))
            messages = list(result.scalars().all())
            assert len(messages) == 50

        # Delete conversation
        async with async_session() as session:
            repo = ConversationRepository(session)
            deleted = await repo.delete_conversation(conv_id)
            await session.commit()

            assert deleted is True

        # Verify all messages are deleted
        async with async_session() as session:
            result = await session.execute(select(Message).where(Message.conversation_id == conv_id))
            messages = list(result.scalars().all())
            assert len(messages) == 0

        # Verify conversation is deleted
        async with async_session() as session:
            repo = ConversationRepository(session)
            conv = await repo.get_conversation(conv_id)
            assert conv is None

    async def test_delete_one_conversation_preserves_others(
        self, async_session: async_sessionmaker[AsyncSession]
    ) -> None:
        """Test that deleting one conversation doesn't affect others."""
        # Create multiple conversations
        async with async_session() as session:
            repo = ConversationRepository(session)

            conv1 = await repo.create_conversation()
            conv2 = await repo.create_conversation()
            conv3 = await repo.create_conversation()

            await repo.add_message(conv1.id, "user", "Message in conv1")
            await repo.add_message(conv2.id, "user", "Message in conv2")
            await repo.add_message(conv3.id, "user", "Message in conv3")

            await session.commit()

            conv1_id = conv1.id
            conv2_id = conv2.id
            conv3_id = conv3.id

        # Delete conv2
        async with async_session() as session:
            repo = ConversationRepository(session)
            await repo.delete_conversation(conv2_id)
            await session.commit()

        # Verify conv1 and conv3 still exist
        async with async_session() as session:
            repo = ConversationRepository(session)

            conv1_retrieved = await repo.get_conversation(conv1_id)
            conv3_retrieved = await repo.get_conversation(conv3_id)

            assert conv1_retrieved is not None
            assert len(conv1_retrieved.messages) == 1

            assert conv3_retrieved is not None
            assert len(conv3_retrieved.messages) == 1

            # Verify conv2 is deleted
            conv2_retrieved = await repo.get_conversation(conv2_id)
            assert conv2_retrieved is None

    async def test_delete_and_recreate_conversation(
        self, async_session: async_sessionmaker[AsyncSession]
    ) -> None:
        """Test deleting a conversation and creating a new one."""
        # Create and delete conversation
        async with async_session() as session:
            repo = ConversationRepository(session)
            conversation = await repo.create_conversation()
            await repo.add_message(conversation.id, "user", "Message 1")
            await session.commit()
            conv_id = conversation.id

        async with async_session() as session:
            repo = ConversationRepository(session)
            await repo.delete_conversation(conv_id)
            await session.commit()

        # Create new conversation (should be independent of deleted one)
        async with async_session() as session:
            repo = ConversationRepository(session)
            new_conversation = await repo.create_conversation()
            await repo.add_message(new_conversation.id, "user", "New message")
            await session.commit()
            new_conv_id = new_conversation.id

        # Verify new conversation exists and has only its own message
        async with async_session() as session:
            repo = ConversationRepository(session)
            retrieved_conv = await repo.get_conversation(new_conv_id)

            assert retrieved_conv is not None
            assert len(retrieved_conv.messages) == 1
            assert retrieved_conv.messages[0].content == "New message"
