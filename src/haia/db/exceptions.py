"""Custom exceptions for database operations.

This module defines domain-specific exceptions for conversation database operations,
providing better error handling and more informative error messages.
"""


class DatabaseError(Exception):
    """Base exception for all database-related errors.

    All custom database exceptions inherit from this base class.
    Allows for catching all database errors with a single except clause.
    """

    pass


class ConversationNotFoundError(DatabaseError):
    """Raised when a requested conversation does not exist.

    Attributes:
        conversation_id: ID of the conversation that was not found
    """

    def __init__(self, conversation_id: int) -> None:
        """Initialize exception with conversation ID.

        Args:
            conversation_id: ID of the missing conversation
        """
        self.conversation_id = conversation_id
        super().__init__(f"Conversation with ID {conversation_id} not found")


class MessageNotFoundError(DatabaseError):
    """Raised when a requested message does not exist.

    Attributes:
        message_id: ID of the message that was not found
    """

    def __init__(self, message_id: int) -> None:
        """Initialize exception with message ID.

        Args:
            message_id: ID of the missing message
        """
        self.message_id = message_id
        super().__init__(f"Message with ID {message_id} not found")


class InvalidRoleError(DatabaseError):
    """Raised when an invalid message role is provided.

    Valid roles are: 'system', 'user', 'assistant'.

    Attributes:
        role: The invalid role that was provided
        valid_roles: Set of valid role values
    """

    def __init__(self, role: str, valid_roles: set[str] | None = None) -> None:
        """Initialize exception with role information.

        Args:
            role: The invalid role that was provided
            valid_roles: Optional set of valid roles (default: system, user, assistant)
        """
        self.role = role
        self.valid_roles = valid_roles or {"system", "user", "assistant"}
        valid_str = ", ".join(sorted(self.valid_roles))
        super().__init__(f"Invalid role '{role}'. Valid roles: {valid_str}")


class EmptyContentError(DatabaseError):
    """Raised when attempting to create a message with empty content.

    Message content must be at least 1 character long.
    """

    def __init__(self) -> None:
        """Initialize exception."""
        super().__init__("Message content cannot be empty")


class DatabaseConnectionError(DatabaseError):
    """Raised when database connection fails.

    Typically indicates configuration issues or database server unavailability.

    Attributes:
        original_error: The underlying exception that caused the connection failure
    """

    def __init__(self, original_error: Exception) -> None:
        """Initialize exception with underlying error.

        Args:
            original_error: The exception that caused the connection failure
        """
        self.original_error = original_error
        super().__init__(f"Database connection failed: {str(original_error)}")


class DatabaseIntegrityError(DatabaseError):
    """Raised when a database integrity constraint is violated.

    Examples:
        - Foreign key constraint violation
        - Unique constraint violation
        - Check constraint violation

    Attributes:
        original_error: The underlying SQLAlchemy IntegrityError
    """

    def __init__(self, original_error: Exception) -> None:
        """Initialize exception with underlying error.

        Args:
            original_error: The SQLAlchemy IntegrityError
        """
        self.original_error = original_error
        super().__init__(f"Database integrity constraint violated: {str(original_error)}")


class ConcurrentModificationError(DatabaseError):
    """Raised when a concurrent modification conflict is detected.

    Occurs when two or more processes attempt to modify the same data simultaneously.

    Attributes:
        entity_type: Type of entity that was modified (e.g., "Conversation", "Message")
        entity_id: ID of the entity that was modified
    """

    def __init__(self, entity_type: str, entity_id: int) -> None:
        """Initialize exception with entity information.

        Args:
            entity_type: Type of entity (e.g., "Conversation", "Message")
            entity_id: ID of the entity
        """
        self.entity_type = entity_type
        self.entity_id = entity_id
        super().__init__(
            f"Concurrent modification detected for {entity_type} with ID {entity_id}. "
            "Please retry the operation."
        )
