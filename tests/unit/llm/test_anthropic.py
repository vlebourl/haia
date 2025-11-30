"""Unit tests for AnthropicClient."""

from unittest.mock import AsyncMock, Mock, patch

import anthropic
import pytest

from haia.llm.errors import (
    AuthenticationError,
    InvalidRequestError,
    RateLimitError,
    ResourceNotFoundError,
    ServiceUnavailableError,
    TimeoutError,
    ValidationError,
)
from haia.llm.models import Message
from haia.llm.providers.anthropic import AnthropicClient


class TestAnthropicClient:
    """Tests for AnthropicClient."""

    @pytest.fixture
    def client(self) -> AnthropicClient:
        """Create test client."""
        return AnthropicClient(
            api_key="test-api-key", model="claude-haiku-4-5-20251001", timeout=30.0
        )

    @pytest.fixture
    def mock_anthropic_response(self) -> Mock:
        """Create mock Anthropic API response."""
        response = Mock()
        response.content = [Mock(text="Test response from Claude")]
        response.model = "claude-haiku-4-5-20251001"
        response.usage = Mock(input_tokens=10, output_tokens=5)
        response.stop_reason = "stop"
        return response

    @pytest.mark.asyncio
    async def test_chat_success(
        self, client: AnthropicClient, mock_anthropic_response: Mock
    ) -> None:
        """Test successful chat completion."""
        with patch.object(
            client.client.messages, "create", new_callable=AsyncMock
        ) as mock_create:
            mock_create.return_value = mock_anthropic_response

            messages = [Message(role="user", content="Hello")]
            response = await client.chat(messages=messages)

            assert response.content == "Test response from Claude"
            assert response.model == "claude-haiku-4-5-20251001"
            assert response.usage.prompt_tokens == 10
            assert response.usage.completion_tokens == 5
            assert response.usage.total_tokens == 15
            assert response.finish_reason == "stop"

            # Verify API was called correctly
            mock_create.assert_called_once()
            call_args = mock_create.call_args
            assert call_args.kwargs["model"] == "claude-haiku-4-5-20251001"
            assert call_args.kwargs["max_tokens"] == 1024
            assert call_args.kwargs["temperature"] == 0.7
            assert len(call_args.kwargs["messages"]) == 1

    @pytest.mark.asyncio
    async def test_chat_with_system_prompt(
        self, client: AnthropicClient, mock_anthropic_response: Mock
    ) -> None:
        """Test chat with system prompt (handled as top-level parameter)."""
        with patch.object(
            client.client.messages, "create", new_callable=AsyncMock
        ) as mock_create:
            mock_create.return_value = mock_anthropic_response

            messages = [
                Message(role="system", content="You are a helpful assistant."),
                Message(role="user", content="Hello"),
            ]
            await client.chat(messages=messages)

            # System message should be passed as top-level 'system' parameter
            call_args = mock_create.call_args
            assert call_args.kwargs["system"] == "You are a helpful assistant."
            # Only user message should be in messages list
            assert len(call_args.kwargs["messages"]) == 1
            assert call_args.kwargs["messages"][0]["role"] == "user"

    @pytest.mark.asyncio
    async def test_chat_with_custom_parameters(
        self, client: AnthropicClient, mock_anthropic_response: Mock
    ) -> None:
        """Test chat with custom temperature and max_tokens."""
        with patch.object(
            client.client.messages, "create", new_callable=AsyncMock
        ) as mock_create:
            mock_create.return_value = mock_anthropic_response

            messages = [Message(role="user", content="Hello")]
            await client.chat(messages=messages, temperature=0.5, max_tokens=2048)

            call_args = mock_create.call_args
            assert call_args.kwargs["temperature"] == 0.5
            assert call_args.kwargs["max_tokens"] == 2048

    @pytest.mark.asyncio
    async def test_chat_authentication_error(self, client: AnthropicClient) -> None:
        """Test authentication error handling."""
        with patch.object(
            client.client.messages, "create", new_callable=AsyncMock
        ) as mock_create:
            mock_create.side_effect = anthropic.APIStatusError(
                message="Invalid API key",
                response=Mock(status_code=401),
                body=None,
            )

            messages = [Message(role="user", content="Hello")]

            with pytest.raises(AuthenticationError) as exc_info:
                await client.chat(messages=messages)

            assert "authentication failed" in str(exc_info.value).lower()
            assert exc_info.value.provider == "anthropic"

    @pytest.mark.asyncio
    async def test_chat_rate_limit_error(self, client: AnthropicClient) -> None:
        """Test rate limit error handling."""
        with patch.object(
            client.client.messages, "create", new_callable=AsyncMock
        ) as mock_create:
            mock_create.side_effect = anthropic.APIStatusError(
                message="Rate limit exceeded",
                response=Mock(status_code=429),
                body=None,
            )

            messages = [Message(role="user", content="Hello")]

            with pytest.raises(RateLimitError) as exc_info:
                await client.chat(messages=messages)

            assert "rate limit" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_chat_timeout_error(self, client: AnthropicClient) -> None:
        """Test timeout error handling."""
        with patch.object(
            client.client.messages, "create", new_callable=AsyncMock
        ) as mock_create:
            mock_create.side_effect = anthropic.APITimeoutError(request=Mock())

            messages = [Message(role="user", content="Hello")]

            with pytest.raises(TimeoutError) as exc_info:
                await client.chat(messages=messages)

            assert "timed out" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_chat_service_unavailable_error(
        self, client: AnthropicClient
    ) -> None:
        """Test service unavailable error handling."""
        with patch.object(
            client.client.messages, "create", new_callable=AsyncMock
        ) as mock_create:
            mock_create.side_effect = anthropic.APIStatusError(
                message="Service unavailable",
                response=Mock(status_code=503),
                body=None,
            )

            messages = [Message(role="user", content="Hello")]

            with pytest.raises(ServiceUnavailableError) as exc_info:
                await client.chat(messages=messages)

            assert "unavailable" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_chat_resource_not_found_error(
        self, client: AnthropicClient
    ) -> None:
        """Test resource not found error handling."""
        with patch.object(
            client.client.messages, "create", new_callable=AsyncMock
        ) as mock_create:
            mock_create.side_effect = anthropic.APIStatusError(
                message="Model not found",
                response=Mock(status_code=404),
                body=None,
            )

            messages = [Message(role="user", content="Hello")]

            with pytest.raises(ResourceNotFoundError) as exc_info:
                await client.chat(messages=messages)

            assert "not found" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_chat_invalid_request_error(self, client: AnthropicClient) -> None:
        """Test invalid request error handling."""
        with patch.object(
            client.client.messages, "create", new_callable=AsyncMock
        ) as mock_create:
            mock_create.side_effect = anthropic.APIStatusError(
                message="Invalid request",
                response=Mock(status_code=400),
                body=None,
            )

            messages = [Message(role="user", content="Hello")]

            with pytest.raises(InvalidRequestError) as exc_info:
                await client.chat(messages=messages)

            assert "invalid" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_chat_validation_error_empty_content(
        self, client: AnthropicClient
    ) -> None:
        """Test validation error when response has empty content."""
        with patch.object(
            client.client.messages, "create", new_callable=AsyncMock
        ) as mock_create:
            # Mock response with empty content list
            mock_response = Mock()
            mock_response.content = []
            mock_create.return_value = mock_response

            messages = [Message(role="user", content="Hello")]

            with pytest.raises(ValidationError) as exc_info:
                await client.chat(messages=messages)

            assert "parse" in str(exc_info.value).lower() or "empty" in str(
                exc_info.value
            ).lower()

    @pytest.mark.asyncio
    async def test_stream_chat_not_implemented(self, client: AnthropicClient) -> None:
        """Test that stream_chat raises NotImplementedError in MVP."""
        messages = [Message(role="user", content="Hello")]

        with pytest.raises(NotImplementedError) as exc_info:
            async for _ in client.stream_chat(messages=messages):
                pass

        assert "not implemented" in str(exc_info.value).lower()
