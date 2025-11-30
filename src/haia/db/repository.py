"""Repository for conversation and message persistence.

This module provides the ConversationRepository class that encapsulates
all database operations for conversations and messages.
"""

from sqlalchemy.ext.asyncio import AsyncSession


class ConversationRepository:
    """Repository for conversation and message persistence.

    Provides methods for creating conversations, adding messages,
    and retrieving conversation history with context window management.

    Args:
        session: AsyncSession for database operations
    """

    def __init__(self, session: AsyncSession) -> None:
        """Initialize repository with database session.

        Args:
            session: AsyncSession instance for database operations
        """
        self.session = session
