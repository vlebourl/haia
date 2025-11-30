"""Error classes for LLM abstraction layer."""

import contextvars
import uuid
from typing import Any

# Correlation ID context variable for async-safe tracking
correlation_id_var: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "correlation_id", default=None
)


def _get_correlation_id() -> str:
    """Get current correlation ID or generate new one."""
    corr_id = correlation_id_var.get()
    return corr_id if corr_id is not None else str(uuid.uuid4())


class LLMError(Exception):
    """Base exception for LLM abstraction layer errors."""

    def __init__(
        self,
        message: str,
        *,
        correlation_id: str | None = None,
        provider: str | None = None,
        original_error: Exception | None = None,
        **extra_context: Any,
    ):
        super().__init__(message)
        self.message = message
        self.correlation_id = correlation_id or _get_correlation_id()
        self.provider = provider
        self.original_error = original_error
        self.extra_context = extra_context

    @property
    def status_code(self) -> int | None:
        """HTTP status code if applicable."""
        return self.extra_context.get("status_code")

    def __str__(self) -> str:
        parts = [self.message]
        if self.provider:
            parts.append(f"[provider={self.provider}]")
        if self.correlation_id:
            parts.append(f"[correlation_id={self.correlation_id}]")
        return " ".join(parts)

    def to_dict(self) -> dict[str, Any]:
        """Convert error to dictionary for logging/API responses."""
        return {
            "error_type": self.__class__.__name__,
            "message": self.message,
            "provider": self.provider,
            "correlation_id": self.correlation_id,
            "extra_context": self.extra_context,
        }


class AuthenticationError(LLMError):
    """API authentication failed (401, 403)."""

    pass


class RateLimitError(LLMError):
    """API rate limit exceeded (429)."""

    pass


class TimeoutError(LLMError):
    """API request timed out."""

    pass


class ValidationError(LLMError):
    """Response validation failed (malformed data)."""

    pass


class ServiceUnavailableError(LLMError):
    """Provider service unavailable (500, 502, 503)."""

    pass


class ResourceNotFoundError(LLMError):
    """Requested resource not found (404)."""

    pass


class InvalidRequestError(LLMError):
    """Invalid request parameters (400)."""

    pass
