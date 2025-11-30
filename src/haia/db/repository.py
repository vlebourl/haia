"""Repository for conversation and message persistence.

This module provides the ConversationRepository class that encapsulates
all database operations for conversations and messages.
"""

import logging

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from haia.db.models import Conversation, Message

logger = logging.getLogger(__name__)


class ConversationRepository:
    """Repository for conversation and message persistence.

    Provides methods for creating conversations, adding messages,
    and retrieving conversation history with context window management.

    Args:
        session: AsyncSession for database operations

    Usage Examples:
        **Basic Conversation Creation:**

        ```python
        from haia.db import get_db, ConversationRepository

        async with async_session() as session:
            repo = ConversationRepository(session)

            # Create a new conversation
            conversation = await repo.create_conversation()
            print(f"Created conversation ID: {conversation.id}")

            await session.commit()
        ```

        **Adding Messages to a Conversation:**

        ```python
        async with async_session() as session:
            repo = ConversationRepository(session)

            # Add messages to existing conversation
            await repo.add_message(conversation_id, "system", "You are a helpful assistant.")
            await repo.add_message(conversation_id, "user", "Hello!")
            await repo.add_message(conversation_id, "assistant", "Hi! How can I help you?")

            await session.commit()
        ```

        **Retrieving Conversation with Full History:**

        ```python
        async with async_session() as session:
            repo = ConversationRepository(session)

            # Get conversation with all messages
            conversation = await repo.get_conversation(conversation_id)

            if conversation:
                print(f"Conversation {conversation.id} has {len(conversation.messages)} messages")
                for msg in conversation.messages:
                    print(f"{msg.role}: {msg.content}")
        ```

        **Context Window Management (20 Most Recent Messages):**

        ```python
        async with async_session() as session:
            repo = ConversationRepository(session)

            # Get context window for LLM (default: 20 most recent messages)
            context = await repo.get_context_messages(conversation_id)

            # Send to LLM
            llm_messages = [
                {"role": msg.role, "content": msg.content}
                for msg in context
            ]
        ```

        **Listing Conversations with Pagination:**

        ```python
        async with async_session() as session:
            repo = ConversationRepository(session)

            # List conversations (most recent first)
            conversations = await repo.list_conversations(limit=10, offset=0)

            for conv in conversations:
                msg_count = await repo.get_message_count(conv.id)
                print(f"Conversation {conv.id}: {msg_count} messages")
        ```

        **Deleting Conversations (Cascade):**

        ```python
        async with async_session() as session:
            repo = ConversationRepository(session)

            # Delete conversation and all its messages
            deleted = await repo.delete_conversation(conversation_id)

            if deleted:
                print("Conversation and all messages deleted")
                await session.commit()
        ```

        **FastAPI Integration:**

        ```python
        from fastapi import Depends
        from haia.db import get_db, ConversationRepository
        from sqlalchemy.ext.asyncio import AsyncSession

        @app.post("/conversations")
        async def create_conversation(db: AsyncSession = Depends(get_db)):
            repo = ConversationRepository(db)
            conversation = await repo.create_conversation()
            return {"id": conversation.id, "created_at": conversation.created_at}

        @app.post("/conversations/{conversation_id}/messages")
        async def add_message(
            conversation_id: int,
            role: str,
            content: str,
            db: AsyncSession = Depends(get_db),
        ):
            repo = ConversationRepository(db)
            message = await repo.add_message(conversation_id, role, content)
            return {"id": message.id, "role": message.role, "content": message.content}
        ```
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

    async def get_context_messages(
        self, conversation_id: int, limit: int = 20
    ) -> list[Message]:
        """Get the N most recent messages for LLM context window.

        Retrieves the most recent messages up to the specified limit, returning
        them in chronological order (oldest first) for LLM consumption. Uses
        efficient SQL query with composite index for optimal performance.

        Args:
            conversation_id: ID of conversation to retrieve messages from
            limit: Maximum number of messages to retrieve (default: 20)

        Returns:
            list[Message]: List of messages in chronological order (oldest first),
                limited to N most recent

        Raises:
            SQLAlchemyError: If database query fails

        Performance:
            O(log N + limit) where N is total messages in conversation
            Uses composite index on (conversation_id, created_at) for fast retrieval
        """
        # Query for most recent N messages using ORDER BY DESC + LIMIT
        # This uses the composite index (conversation_id, created_at) for efficiency
        stmt = (
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .order_by(Message.created_at.desc())  # Most recent first
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        messages = list(result.scalars().all())

        # Reverse to return chronological order (oldest first for LLM)
        messages.reverse()

        logger.debug(
            f"Retrieved {len(messages)} context messages for conversation {conversation_id} "
            f"(limit: {limit})"
        )

        return messages

    async def list_conversations(
        self, limit: int = 50, offset: int = 0
    ) -> list[Conversation]:
        """List all conversations ordered by last activity (most recent first).

        Args:
            limit: Maximum number of conversations to retrieve (default: 50)
            offset: Number of conversations to skip for pagination (default: 0)

        Returns:
            list[Conversation]: List of conversations ordered by updated_at DESC

        Raises:
            SQLAlchemyError: If database query fails

        Performance:
            O(log N + limit) where N is total conversations
            Uses index on updated_at for efficient sorting
        """
        stmt = (
            select(Conversation)
            .order_by(Conversation.updated_at.desc())  # Most recent first
            .limit(limit)
            .offset(offset)
        )
        result = await self.session.execute(stmt)
        conversations = list(result.scalars().all())

        logger.debug(f"Listed {len(conversations)} conversations (limit: {limit}, offset: {offset})")

        return conversations

    async def delete_conversation(self, conversation_id: int) -> bool:
        """Delete a conversation and all associated messages (CASCADE).

        Args:
            conversation_id: ID of conversation to delete

        Returns:
            bool: True if conversation existed and was deleted, False if not found

        Raises:
            SQLAlchemyError: If database delete fails

        Side Effects:
            - Deletes conversation row from database
            - Automatically deletes all messages via CASCADE constraint
        """
        stmt = delete(Conversation).where(Conversation.id == conversation_id)
        result = await self.session.execute(stmt)

        deleted = result.rowcount > 0

        if deleted:
            logger.info(f"Deleted conversation {conversation_id} with CASCADE to messages")
        else:
            logger.debug(f"Attempted to delete non-existent conversation {conversation_id}")

        return deleted

    async def get_message_count(self, conversation_id: int) -> int:
        """Get total number of messages in a conversation.

        Args:
            conversation_id: ID of conversation to count messages for

        Returns:
            int: Total number of messages (0 if conversation doesn't exist)

        Raises:
            SQLAlchemyError: If database query fails

        Performance:
            O(1) - SQLite COUNT(*) is optimized when using indexes
        """
        stmt = (
            select(func.count(Message.id))
            .where(Message.conversation_id == conversation_id)
        )
        result = await self.session.execute(stmt)
        count = result.scalar() or 0

        return count
