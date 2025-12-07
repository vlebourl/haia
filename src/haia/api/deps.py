"""FastAPI dependency injection for agent and correlation IDs."""

import logging
import uuid
from contextvars import ContextVar

from fastapi import Header
from pydantic_ai import Agent

from haia.memory.tracker import ConversationTracker

# Correlation ID context variable for request tracing
correlation_id_var: ContextVar[str] = ContextVar("correlation_id", default="unknown")

# Global agent instance (initialized at startup)
_agent: Agent | None = None

# Global conversation tracker instance (initialized at startup)
_conversation_tracker: ConversationTracker | None = None

# Logger
logger = logging.getLogger(__name__)


class CorrelationIdFilter(logging.Filter):
    """Logging filter to add correlation ID to all log records."""

    def filter(self, record):
        """Add correlation_id attribute to log record."""
        record.correlation_id = correlation_id_var.get()
        return True


async def get_correlation_id(x_correlation_id: str | None = Header(None)) -> str:
    """Get or generate correlation ID for request tracing.

    Args:
        x_correlation_id: Optional correlation ID from request header

    Returns:
        Correlation ID (from header or newly generated UUID)
    """
    cid = x_correlation_id or str(uuid.uuid4())
    correlation_id_var.set(cid)
    return cid


def get_agent() -> Agent:
    """FastAPI dependency for agent injection.

    Returns:
        PydanticAI agent instance

    Raises:
        RuntimeError: If agent not initialized (server startup failed)
    """
    if _agent is None:
        raise RuntimeError("Agent not initialized - server startup may have failed")
    return _agent


def set_agent(agent: Agent) -> None:
    """Set the global agent instance (called during startup).

    Args:
        agent: Configured PydanticAI agent
    """
    global _agent
    _agent = agent


def get_conversation_tracker() -> ConversationTracker:
    """FastAPI dependency for conversation tracker injection.

    Returns:
        ConversationTracker instance

    Raises:
        RuntimeError: If tracker not initialized (server startup failed)
    """
    if _conversation_tracker is None:
        raise RuntimeError(
            "ConversationTracker not initialized - server startup may have failed"
        )
    return _conversation_tracker


def set_conversation_tracker(tracker: ConversationTracker) -> None:
    """Set the global conversation tracker instance (called during startup).

    Args:
        tracker: Configured ConversationTracker
    """
    global _conversation_tracker
    _conversation_tracker = tracker
