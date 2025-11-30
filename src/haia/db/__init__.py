"""Database layer for conversation persistence.

This package provides database models, repository, and session management
for storing and retrieving conversation history.
"""

from haia.db.models import Base
from haia.db.repository import ConversationRepository
from haia.db.session import get_db

__all__ = ["Base", "ConversationRepository", "get_db"]
