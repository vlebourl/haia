"""Unit tests for database models."""

from datetime import datetime

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from haia.db.models import Base


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


class TestConversationModel:
    """Tests for Conversation model."""

    async def test_conversation_creation(self, async_session: async_sessionmaker[AsyncSession]) -> None:
        """Test creating a conversation with auto-generated fields."""
        from haia.db.models import Conversation

        async with async_session() as session:
            conversation = Conversation()
            session.add(conversation)
            await session.commit()
            await session.refresh(conversation)

            assert conversation.id is not None
            assert isinstance(conversation.created_at, datetime)
            assert isinstance(conversation.updated_at, datetime)

    async def test_conversation_timestamps(self, async_session: async_sessionmaker[AsyncSession]) -> None:
        """Test that conversation timestamps are set correctly."""
        from haia.db.models import Conversation

        async with async_session() as session:
            conversation = Conversation()
            session.add(conversation)
            await session.commit()
            await session.refresh(conversation)

            # created_at and updated_at should be close to now
            assert conversation.created_at is not None
            assert conversation.updated_at is not None
            # They should be close to each other (within 1 second)
            time_diff = abs((conversation.updated_at - conversation.created_at).total_seconds())
            assert time_diff < 1.0, f"Timestamps differ by {time_diff} seconds"


class TestMessageModel:
    """Tests for Message model."""

    async def test_message_creation(self, async_session: async_sessionmaker[AsyncSession]) -> None:
        """Test creating a message with required fields."""
        from haia.db.models import Conversation, Message

        async with async_session() as session:
            # Create conversation first
            conversation = Conversation()
            session.add(conversation)
            await session.commit()
            await session.refresh(conversation)

            # Create message
            message = Message(
                conversation_id=conversation.id,
                role="user",
                content="Test message",
            )
            session.add(message)
            await session.commit()
            await session.refresh(message)

            assert message.id is not None
            assert message.conversation_id == conversation.id
            assert message.role == "user"
            assert message.content == "Test message"
            assert isinstance(message.created_at, datetime)

    async def test_message_role_values(self, async_session: async_sessionmaker[AsyncSession]) -> None:
        """Test message with different role values."""
        from haia.db.models import Conversation, Message

        roles = ["system", "user", "assistant"]

        async with async_session() as session:
            conversation = Conversation()
            session.add(conversation)
            await session.commit()
            await session.refresh(conversation)

            for role in roles:
                message = Message(
                    conversation_id=conversation.id,
                    role=role,
                    content=f"Message with role {role}",
                )
                session.add(message)

            await session.commit()

            # Verify all roles were saved
            from sqlalchemy import select

            result = await session.execute(select(Message))
            messages = list(result.scalars().all())

            assert len(messages) == 3
            saved_roles = {msg.role for msg in messages}
            assert saved_roles == set(roles)

    async def test_message_long_content(self, async_session: async_sessionmaker[AsyncSession]) -> None:
        """Test message with long content."""
        from haia.db.models import Conversation, Message

        long_content = "A" * 10000  # 10k characters

        async with async_session() as session:
            conversation = Conversation()
            session.add(conversation)
            await session.commit()
            await session.refresh(conversation)

            message = Message(
                conversation_id=conversation.id,
                role="user",
                content=long_content,
            )
            session.add(message)
            await session.commit()
            await session.refresh(message)

            assert message.content == long_content
            assert len(message.content) == 10000
