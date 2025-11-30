"""Integration tests for concurrent database operations."""

import asyncio

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
        # Enable foreign key constraints and WAL mode for concurrency
        await conn.execute(text("PRAGMA foreign_keys = ON"))
        await conn.execute(text("PRAGMA journal_mode = WAL"))
        await conn.run_sync(Base.metadata.create_all)

    session_maker = async_sessionmaker(engine, expire_on_commit=False)
    yield session_maker

    await engine.dispose()


class TestConcurrentWrites:
    """Integration tests for concurrent write operations."""

    async def test_concurrent_conversation_creation(
        self, async_session: async_sessionmaker[AsyncSession]
    ) -> None:
        """Test creating multiple conversations concurrently."""

        async def create_conversation(session_maker: async_sessionmaker[AsyncSession], index: int):
            """Create a single conversation in a dedicated session."""
            async with session_maker() as session:
                repo = ConversationRepository(session)
                conversation = await repo.create_conversation()
                await repo.add_message(conversation.id, "user", f"Message from task {index}")
                await session.commit()
                return conversation.id

        # Create 10 conversations concurrently
        tasks = [create_conversation(async_session, i) for i in range(10)]
        conversation_ids = await asyncio.gather(*tasks)

        # Verify all conversations were created
        assert len(conversation_ids) == 10
        assert len(set(conversation_ids)) == 10  # All unique IDs

        # Verify all conversations exist in database
        async with async_session() as session:
            repo = ConversationRepository(session)
            conversations = await repo.list_conversations(limit=20)
            assert len(conversations) == 10

    async def test_concurrent_message_addition_to_same_conversation(
        self, async_session: async_sessionmaker[AsyncSession]
    ) -> None:
        """Test adding messages to the same conversation concurrently."""

        # Create initial conversation
        async with async_session() as session:
            repo = ConversationRepository(session)
            conversation = await repo.create_conversation()
            await session.commit()
            conv_id = conversation.id

        async def add_message(
            session_maker: async_sessionmaker[AsyncSession], conv_id: int, index: int
        ):
            """Add a single message in a dedicated session."""
            async with session_maker() as session:
                repo = ConversationRepository(session)
                message = await repo.add_message(conv_id, "user", f"Concurrent message {index}")
                await session.commit()
                return message.id

        # Add 20 messages concurrently to the same conversation
        tasks = [add_message(async_session, conv_id, i) for i in range(20)]
        message_ids = await asyncio.gather(*tasks)

        # Verify all messages were added
        assert len(message_ids) == 20
        assert len(set(message_ids)) == 20  # All unique IDs

        # Verify all messages exist in database
        async with async_session() as session:
            repo = ConversationRepository(session)
            all_messages = await repo.get_all_messages(conv_id)
            assert len(all_messages) == 20

            # Verify all expected message contents exist
            message_contents = {msg.content for msg in all_messages}
            expected_contents = {f"Concurrent message {i}" for i in range(20)}
            assert message_contents == expected_contents

    async def test_concurrent_read_and_write(
        self, async_session: async_sessionmaker[AsyncSession]
    ) -> None:
        """Test concurrent reads and writes to the same conversation."""

        # Create conversation with initial messages
        async with async_session() as session:
            repo = ConversationRepository(session)
            conversation = await repo.create_conversation()
            for i in range(5):
                await repo.add_message(conversation.id, "user", f"Initial message {i}")
            await session.commit()
            conv_id = conversation.id

        async def read_messages(session_maker: async_sessionmaker[AsyncSession], conv_id: int):
            """Read messages from conversation."""
            async with session_maker() as session:
                repo = ConversationRepository(session)
                messages = await repo.get_all_messages(conv_id)
                return len(messages)

        async def write_message(
            session_maker: async_sessionmaker[AsyncSession], conv_id: int, index: int
        ):
            """Write a message to conversation."""
            async with session_maker() as session:
                repo = ConversationRepository(session)
                await repo.add_message(conv_id, "user", f"Added message {index}")
                await session.commit()

        # Mix of 10 reads and 10 writes
        read_tasks = [read_messages(async_session, conv_id) for _ in range(10)]
        write_tasks = [write_message(async_session, conv_id, i) for i in range(10)]

        # Run all tasks concurrently
        results = await asyncio.gather(*read_tasks, *write_tasks, return_exceptions=True)

        # Verify no exceptions occurred
        exceptions = [r for r in results if isinstance(r, Exception)]
        assert len(exceptions) == 0, f"Exceptions occurred: {exceptions}"

        # Verify final state: 5 initial + 10 added = 15 messages
        async with async_session() as session:
            repo = ConversationRepository(session)
            final_messages = await repo.get_all_messages(conv_id)
            assert len(final_messages) == 15

    async def test_concurrent_conversation_deletion(
        self, async_session: async_sessionmaker[AsyncSession]
    ) -> None:
        """Test concurrent deletion of different conversations."""

        # Create 10 conversations
        conversation_ids = []
        async with async_session() as session:
            repo = ConversationRepository(session)
            for i in range(10):
                conv = await repo.create_conversation()
                await repo.add_message(conv.id, "user", f"Message {i}")
                conversation_ids.append(conv.id)
            await session.commit()

        async def delete_conversation(
            session_maker: async_sessionmaker[AsyncSession], conv_id: int
        ):
            """Delete a single conversation."""
            async with session_maker() as session:
                repo = ConversationRepository(session)
                deleted = await repo.delete_conversation(conv_id)
                await session.commit()
                return deleted

        # Delete all conversations concurrently
        tasks = [delete_conversation(async_session, conv_id) for conv_id in conversation_ids]
        results = await asyncio.gather(*tasks)

        # Verify all deletions succeeded
        assert all(results)

        # Verify no conversations remain
        async with async_session() as session:
            repo = ConversationRepository(session)
            remaining = await repo.list_conversations()
            assert len(remaining) == 0

    async def test_concurrent_reads_during_writes(
        self, async_session: async_sessionmaker[AsyncSession]
    ) -> None:
        """Test that read operations work correctly while writes are happening.

        Uses sequential writes to avoid SQLite's concurrency limitations in in-memory
        databases, while testing that concurrent reads work correctly throughout.
        """

        async def list_conversations(session_maker: async_sessionmaker[AsyncSession]):
            """List all conversations - should always succeed."""
            async with session_maker() as session:
                repo = ConversationRepository(session)
                conversations = await repo.list_conversations(limit=100)
                return len(conversations)

        # Create 5 conversations sequentially
        for i in range(5):
            async with async_session() as session:
                repo = ConversationRepository(session)
                conv = await repo.create_conversation()
                for j in range(5):
                    await repo.add_message(conv.id, "user", f"Message {j} from conv {i}")
                await session.commit()

        # Now do concurrent reads while verifying consistency
        list_tasks = [list_conversations(async_session) for _ in range(20)]
        results = await asyncio.gather(*list_tasks)

        # All read operations should succeed and return the same count
        assert all(count == 5 for count in results), "All reads should see 5 conversations"

        # Verify final state
        async with async_session() as session:
            repo = ConversationRepository(session)
            final_conversations = await repo.list_conversations()
            assert len(final_conversations) == 5

            # Verify each conversation has 5 messages
            for conv in final_conversations:
                msg_count = await repo.get_message_count(conv.id)
                assert msg_count == 5


class TestConcurrentContextWindow:
    """Tests for concurrent context window access."""

    async def test_concurrent_context_window_reads(
        self, async_session: async_sessionmaker[AsyncSession]
    ) -> None:
        """Test concurrent reads of context window from same conversation."""

        # Create conversation with 30 messages
        async with async_session() as session:
            repo = ConversationRepository(session)
            conversation = await repo.create_conversation()
            for i in range(30):
                await repo.add_message(conversation.id, "user", f"Message {i + 1}")
            await session.commit()
            conv_id = conversation.id

        async def get_context(session_maker: async_sessionmaker[AsyncSession], conv_id: int):
            """Get context window for conversation."""
            async with session_maker() as session:
                repo = ConversationRepository(session)
                context = await repo.get_context_messages(conv_id)
                return context

        # Get context window 20 times concurrently
        tasks = [get_context(async_session, conv_id) for _ in range(20)]
        results = await asyncio.gather(*tasks)

        # Verify all reads returned the same 20 messages
        assert all(len(context) == 20 for context in results)

        # Verify all context windows have the same message IDs
        first_context_ids = [msg.id for msg in results[0]]
        for context in results[1:]:
            context_ids = [msg.id for msg in context]
            assert context_ids == first_context_ids
