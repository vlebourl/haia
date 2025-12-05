"""LLM module for HAIA.

Note: Feature 003 uses PydanticAI's native model handling.
Error classes kept for potential use in Phase 6 (Error Handling).
"""

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

__all__ = [
    # Error classes (kept for Phase 6 - Error Handling)
    "LLMError",
    "AuthenticationError",
    "RateLimitError",
    "TimeoutError",
    "ValidationError",
    "ServiceUnavailableError",
    "ResourceNotFoundError",
    "InvalidRequestError",
]
