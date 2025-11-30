"""Unit tests for Ollama client."""

import pytest
from httpx import Response

from haia.llm.errors import (
    InvalidRequestError,
    ResourceNotFoundError,
    ServiceUnavailableError,
    TimeoutError,
    ValidationError,
)
from haia.llm.models import Message
from haia.llm.providers.ollama import OllamaClient


class TestOllamaClient:
    """Tests for OllamaClient class."""

    @pytest.fixture
    def ollama_client(self):
        """Create OllamaClient for testing."""
        return OllamaClient(model="qwen2.5-coder:7b")

    @pytest.mark.asyncio
    async def test_successful_chat(self, ollama_client, mocker):
        """Test successful chat completion."""
        # Mock httpx response
        mock_response_data = {
            "model": "qwen2.5-coder:7b",
            "message": {
                "role": "assistant",
                "content": "Hello! How can I help you today?",
            },
            "done": True,
            "done_reason": "stop",
            "prompt_eval_count": 10,
            "eval_count": 8,
        }

        mock_response = mocker.Mock(spec=Response)
        mock_response.status_code = 200
        mock_response.json.return_value = mock_response_data

        mock_post = mocker.patch.object(
            ollama_client.client, "post", return_value=mock_response
        )

        # Call chat
        messages = [Message(role="user", content="Hello")]
        response = await ollama_client.chat(messages)

        # Verify request
        mock_post.assert_called_once()
        call_args = mock_post.call_args
        assert call_args[0][0] == "http://localhost:11434/api/chat"
        payload = call_args[1]["json"]
        assert payload["model"] == "qwen2.5-coder:7b"
        assert payload["stream"] is False
        assert len(payload["messages"]) == 1
        assert payload["messages"][0]["role"] == "user"

        # Verify response
        assert response.content == "Hello! How can I help you today?"
        assert response.model == "qwen2.5-coder:7b"
        assert response.usage.prompt_tokens == 10
        assert response.usage.completion_tokens == 8
        assert response.usage.total_tokens == 18
        assert response.finish_reason == "stop"

    @pytest.mark.asyncio
    async def test_chat_with_system_message(self, ollama_client, mocker):
        """Test chat with system message."""
        mock_response_data = {
            "model": "qwen2.5-coder:7b",
            "message": {"role": "assistant", "content": "Response"},
            "done": True,
            "prompt_eval_count": 15,
            "eval_count": 5,
        }

        mock_response = mocker.Mock(spec=Response)
        mock_response.status_code = 200
        mock_response.json.return_value = mock_response_data

        mock_post = mocker.patch.object(
            ollama_client.client, "post", return_value=mock_response
        )

        # Call chat with system message
        messages = [
            Message(role="system", content="You are a helpful assistant."),
            Message(role="user", content="Hello"),
        ]
        await ollama_client.chat(messages)

        # Verify system message is included in request
        payload = mock_post.call_args[1]["json"]
        assert len(payload["messages"]) == 2
        assert payload["messages"][0]["role"] == "system"
        assert payload["messages"][0]["content"] == "You are a helpful assistant."

    @pytest.mark.asyncio
    async def test_error_404_model_not_found(self, ollama_client, mocker):
        """Test 404 error for model not found."""
        mock_response = mocker.Mock(spec=Response)
        mock_response.status_code = 404
        mock_response.json.return_value = {"error": "model not found"}
        mock_response.text = "model not found"

        mocker.patch.object(ollama_client.client, "post", return_value=mock_response)

        messages = [Message(role="user", content="Hello")]

        with pytest.raises(ResourceNotFoundError) as exc_info:
            await ollama_client.chat(messages)

        error = exc_info.value
        assert error.provider == "ollama"
        assert "qwen2.5-coder:7b" in str(error)
        assert error.status_code == 404

    @pytest.mark.asyncio
    async def test_error_400_invalid_request(self, ollama_client, mocker):
        """Test 400 error for invalid request."""
        mock_response = mocker.Mock(spec=Response)
        mock_response.status_code = 400
        mock_response.json.return_value = {"error": "invalid request"}
        mock_response.text = "invalid request"

        mocker.patch.object(ollama_client.client, "post", return_value=mock_response)

        messages = [Message(role="user", content="Hello")]

        with pytest.raises(InvalidRequestError) as exc_info:
            await ollama_client.chat(messages)

        error = exc_info.value
        assert error.provider == "ollama"
        assert error.status_code == 400

    @pytest.mark.asyncio
    async def test_error_500_service_unavailable(self, ollama_client, mocker):
        """Test 500 error for service unavailable."""
        mock_response = mocker.Mock(spec=Response)
        mock_response.status_code = 500
        mock_response.json.return_value = {"error": "internal server error"}
        mock_response.text = "internal server error"

        mocker.patch.object(ollama_client.client, "post", return_value=mock_response)

        messages = [Message(role="user", content="Hello")]

        with pytest.raises(ServiceUnavailableError) as exc_info:
            await ollama_client.chat(messages)

        error = exc_info.value
        assert error.provider == "ollama"
        assert error.status_code == 500

    @pytest.mark.asyncio
    async def test_timeout_error(self, ollama_client, mocker):
        """Test timeout error."""
        import httpx

        mocker.patch.object(
            ollama_client.client,
            "post",
            side_effect=httpx.TimeoutException("Request timed out"),
        )

        messages = [Message(role="user", content="Hello")]

        with pytest.raises(TimeoutError) as exc_info:
            await ollama_client.chat(messages)

        error = exc_info.value
        assert error.provider == "ollama"
        assert "120.0" in str(error)  # Default timeout

    @pytest.mark.asyncio
    async def test_connection_error(self, ollama_client, mocker):
        """Test connection error."""
        import httpx

        mocker.patch.object(
            ollama_client.client,
            "post",
            side_effect=httpx.ConnectError("Connection refused"),
        )

        messages = [Message(role="user", content="Hello")]

        with pytest.raises(ServiceUnavailableError) as exc_info:
            await ollama_client.chat(messages)

        error = exc_info.value
        assert error.provider == "ollama"
        assert "localhost:11434" in str(error)

    @pytest.mark.asyncio
    async def test_malformed_json_response(self, ollama_client, mocker):
        """Test malformed JSON in response."""
        mock_response = mocker.Mock(spec=Response)
        mock_response.status_code = 200
        mock_response.json.return_value = {"message": {}}  # Missing content

        mocker.patch.object(ollama_client.client, "post", return_value=mock_response)

        messages = [Message(role="user", content="Hello")]

        with pytest.raises(ValidationError) as exc_info:
            await ollama_client.chat(messages)

        error = exc_info.value
        assert error.provider == "ollama"
        assert "Empty content" in str(error)

    @pytest.mark.asyncio
    async def test_response_mapping_minimal(self, ollama_client):
        """Test response mapping with minimal fields."""
        response_data = {
            "model": "qwen2.5-coder:7b",
            "message": {"content": "Test response"},
            "done": True,
            # Missing token counts - should default to 0
        }

        llm_response = ollama_client._map_response(response_data)

        assert llm_response.content == "Test response"
        assert llm_response.model == "qwen2.5-coder:7b"
        assert llm_response.usage.prompt_tokens == 0
        assert llm_response.usage.completion_tokens == 0
        assert llm_response.finish_reason == "stop"

    @pytest.mark.asyncio
    async def test_stream_chat_not_implemented(self, ollama_client):
        """Test that stream_chat raises NotImplementedError."""
        messages = [Message(role="user", content="Hello")]

        with pytest.raises(NotImplementedError, match="Streaming not implemented"):
            async for _ in ollama_client.stream_chat(messages):
                pass

    @pytest.mark.asyncio
    async def test_custom_base_url(self):
        """Test client with custom base URL."""
        client = OllamaClient(model="llama3.1:8b", base_url="http://192.168.1.100:11434")

        assert client.base_url == "http://192.168.1.100:11434"
        assert client.model == "llama3.1:8b"

    @pytest.mark.asyncio
    async def test_base_url_trailing_slash_removed(self):
        """Test that trailing slash is removed from base URL."""
        client = OllamaClient(
            model="qwen2.5-coder:7b", base_url="http://localhost:11434/"
        )

        assert client.base_url == "http://localhost:11434"

    @pytest.mark.asyncio
    async def test_context_manager(self, ollama_client):
        """Test async context manager support."""
        async with ollama_client as client:
            assert client is not None

        # Client should be closed after context exit
        assert ollama_client.client.is_closed
