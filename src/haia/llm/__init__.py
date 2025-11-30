"""LLM abstraction layer - model-agnostic interface for chat completion."""

from haia.llm.client import LLMClient
from haia.llm.errors import (
    AuthenticationError,
    InvalidRequestError,
    LLMError,
    RateLimitError,
    ResourceNotFoundError,
    ServiceUnavailableError,
    TimeoutError,
    ValidationError,
)
from haia.llm.factory import create_client
from haia.llm.models import LLMResponse, LLMResponseChunk, Message, TokenUsage

__all__ = [
    # Client interface
    "LLMClient",
    "create_client",
    # Data models
    "Message",
    "TokenUsage",
    "LLMResponse",
    "LLMResponseChunk",
    # Errors
    "LLMError",
    "AuthenticationError",
    "RateLimitError",
    "TimeoutError",
    "ValidationError",
    "ServiceUnavailableError",
    "ResourceNotFoundError",
    "InvalidRequestError",
]
