"""Database layer for conversation persistence.

This package provides database models, repository, and session management
for storing and retrieving conversation history.
"""

from haia.db.exceptions import (
    ConcurrentModificationError,
    ConversationNotFoundError,
    DatabaseConnectionError,
    DatabaseError,
    DatabaseIntegrityError,
    EmptyContentError,
    InvalidRoleError,
    MessageNotFoundError,
)
from haia.db.models import (
    Base,
    ConversationResponse,
    MessageCreate,
    MessageResponse,
)
from haia.db.repository import ConversationRepository
from haia.db.session import apply_migrations, close_db, get_db, init_db

__all__ = [
    "Base",
    "ConcurrentModificationError",
    "ConversationNotFoundError",
    "ConversationRepository",
    "ConversationResponse",
    "DatabaseConnectionError",
    "DatabaseError",
    "DatabaseIntegrityError",
    "EmptyContentError",
    "InvalidRoleError",
    "MessageCreate",
    "MessageNotFoundError",
    "MessageResponse",
    "apply_migrations",
    "close_db",
    "get_db",
    "init_db",
]
