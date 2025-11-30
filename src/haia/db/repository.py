"""Repository for conversation and message persistence.

This module provides the ConversationRepository class that encapsulates
all database operations for conversations and messages.
"""

import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from haia.db.models import Conversation, Message

logger = logging.getLogger(__name__)


class ConversationRepository:
    """Repository for conversation and message persistence.

    Provides methods for creating conversations, adding messages,
    and retrieving conversation history with context window management.

    Args:
        session: AsyncSession for database operations
    """

    VALID_ROLES = {"system", "user", "assistant"}

    def __init__(self, session: AsyncSession) -> None:
        """Initialize repository with database session.

        Args:
            session: AsyncSession instance for database operations
        """
        self.session = session

    async def create_conversation(self) -> Conversation:
        """Create a new conversation and persist to database.

        Returns:
            Conversation: Newly created conversation with auto-generated ID and timestamps

        Raises:
            SQLAlchemyError: If database write fails
        """
        conversation = Conversation()
        self.session.add(conversation)
        await self.session.flush()  # Flush to get ID without committing
        logger.info(f"Created conversation with ID: {conversation.id}")
        return conversation

    async def get_conversation(self, conversation_id: int) -> Conversation | None:
        """Retrieve a conversation by ID with all messages eagerly loaded.

        Args:
            conversation_id: Unique identifier of the conversation

        Returns:
            Conversation | None: Conversation object with messages relationship loaded,
                or None if not found

        Raises:
            SQLAlchemyError: If database query fails
        """
        stmt = select(Conversation).where(Conversation.id == conversation_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def add_message(
        self, conversation_id: int, role: str, content: str
    ) -> Message:
        """Add a new message to an existing conversation.

        Updates the conversation's updated_at timestamp automatically.

        Args:
            conversation_id: ID of conversation to add message to
            role: Message role (system, user, or assistant)
            content: Message text content

        Returns:
            Message: Newly created message with auto-generated ID and timestamp

        Raises:
            ValueError: If conversation_id not found or invalid role
            SQLAlchemyError: If database write fails
        """
        # Validate role
        if role not in self.VALID_ROLES:
            raise ValueError(
                f"Invalid role: {role}. Must be one of: {', '.join(self.VALID_ROLES)}"
            )

        # Verify conversation exists
        conversation = await self.get_conversation(conversation_id)
        if conversation is None:
            raise ValueError(f"Conversation with ID {conversation_id} not found")

        # Create message
        message = Message(
            conversation_id=conversation_id,
            role=role,
            content=content,
        )
        self.session.add(message)
        await self.session.flush()  # Flush to get ID without committing

        # Update conversation's updated_at timestamp
        # This happens automatically via onupdate, but we need to mark the object as modified
        conversation.updated_at = message.created_at

        logger.info(
            f"Added message (ID: {message.id}, role: {role}) to conversation {conversation_id}"
        )
        return message

    async def get_all_messages(self, conversation_id: int) -> list[Message]:
        """Retrieve all messages in a conversation for display/debugging.

        Args:
            conversation_id: ID of conversation to retrieve messages from

        Returns:
            list[Message]: List of all messages in chronological order (oldest first)

        Raises:
            SQLAlchemyError: If database query fails
        """
        stmt = (
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .order_by(Message.created_at)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
