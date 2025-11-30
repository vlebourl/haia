"""Unit tests for error classes."""

from haia.llm.errors import (
    AuthenticationError,
    InvalidRequestError,
    LLMError,
    RateLimitError,
    ResourceNotFoundError,
    ServiceUnavailableError,
    TimeoutError,
    ValidationError,
    correlation_id_var,
)


class TestLLMError:
    """Tests for LLMError base class."""

    def test_basic_error(self) -> None:
        """Test creating basic error."""
        error = LLMError("Test error")
        assert error.message == "Test error"
        assert error.provider is None
        assert error.original_error is None
        assert error.correlation_id is not None  # Auto-generated
        assert len(error.extra_context) == 0

    def test_error_with_provider(self) -> None:
        """Test error with provider information."""
        error = LLMError("Test error", provider="anthropic")
        assert error.provider == "anthropic"
        assert "anthropic" in str(error)

    def test_error_with_correlation_id(self) -> None:
        """Test error with explicit correlation ID."""
        error = LLMError("Test error", correlation_id="test-123")
        assert error.correlation_id == "test-123"
        assert "test-123" in str(error)

    def test_error_with_original_error(self) -> None:
        """Test error wrapping original exception."""
        original = ValueError("Original error")
        error = LLMError("Wrapped error", original_error=original)
        assert error.original_error == original

    def test_error_with_extra_context(self) -> None:
        """Test error with additional context."""
        error = LLMError("Test error", status_code=500, endpoint="/api/chat")
        assert error.extra_context["status_code"] == 500
        assert error.extra_context["endpoint"] == "/api/chat"

    def test_to_dict(self) -> None:
        """Test conversion to dictionary."""
        error = LLMError(
            "Test error",
            provider="anthropic",
            correlation_id="test-123",
            status_code=500,
        )
        error_dict = error.to_dict()

        assert error_dict["error_type"] == "LLMError"
        assert error_dict["message"] == "Test error"
        assert error_dict["provider"] == "anthropic"
        assert error_dict["correlation_id"] == "test-123"
        assert error_dict["extra_context"]["status_code"] == 500

    def test_correlation_id_from_context(self) -> None:
        """Test correlation ID is read from context variable."""
        # Set correlation ID in context
        token = correlation_id_var.set("context-123")
        try:
            error = LLMError("Test error")
            assert error.correlation_id == "context-123"
        finally:
            correlation_id_var.reset(token)

    def test_auto_generated_correlation_id(self) -> None:
        """Test correlation ID is auto-generated if not provided."""
        error = LLMError("Test error")
        assert error.correlation_id is not None
        assert len(error.correlation_id) > 0
        # Should be a valid UUID format (36 characters with dashes)
        assert len(error.correlation_id) == 36


class TestSpecificErrors:
    """Tests for specific error types."""

    def test_authentication_error(self) -> None:
        """Test AuthenticationError."""
        error = AuthenticationError("Invalid API key", provider="anthropic")
        assert isinstance(error, LLMError)
        assert error.message == "Invalid API key"

    def test_rate_limit_error(self) -> None:
        """Test RateLimitError."""
        error = RateLimitError("Rate limit exceeded", provider="anthropic")
        assert isinstance(error, LLMError)
        assert error.message == "Rate limit exceeded"

    def test_timeout_error(self) -> None:
        """Test TimeoutError."""
        error = TimeoutError("Request timed out", provider="anthropic")
        assert isinstance(error, LLMError)
        assert error.message == "Request timed out"

    def test_validation_error(self) -> None:
        """Test ValidationError."""
        error = ValidationError("Invalid response format", provider="anthropic")
        assert isinstance(error, LLMError)
        assert error.message == "Invalid response format"

    def test_service_unavailable_error(self) -> None:
        """Test ServiceUnavailableError."""
        error = ServiceUnavailableError("Service unavailable", provider="anthropic")
        assert isinstance(error, LLMError)
        assert error.message == "Service unavailable"

    def test_resource_not_found_error(self) -> None:
        """Test ResourceNotFoundError."""
        error = ResourceNotFoundError("Model not found", provider="ollama")
        assert isinstance(error, LLMError)
        assert error.message == "Model not found"

    def test_invalid_request_error(self) -> None:
        """Test InvalidRequestError."""
        error = InvalidRequestError("Invalid parameters", provider="anthropic")
        assert isinstance(error, LLMError)
        assert error.message == "Invalid parameters"

    def test_error_inheritance(self) -> None:
        """Test all specific errors inherit from LLMError."""
        errors = [
            AuthenticationError("test"),
            RateLimitError("test"),
            TimeoutError("test"),
            ValidationError("test"),
            ServiceUnavailableError("test"),
            ResourceNotFoundError("test"),
            InvalidRequestError("test"),
        ]
        for error in errors:
            assert isinstance(error, LLMError)
            assert isinstance(error, Exception)
