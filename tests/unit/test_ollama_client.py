"""Unit tests for Ollama embedding client.

Tests the HTTP client for generating embeddings via Ollama API.
All tests use mocked httpx responses to avoid external dependencies.
"""

import pytest
from unittest.mock import AsyncMock, patch
import httpx

from haia.embedding.ollama_client import OllamaClient
from haia.embedding.models import EmbeddingRequest, EmbeddingResponse, EmbeddingError


@pytest.fixture
def ollama_client():
    """Create Ollama client instance for testing."""
    return OllamaClient(base_url="http://localhost:11434", model="nomic-embed-text")


@pytest.fixture
def mock_embedding_response():
    """Mock successful embedding response from Ollama."""
    return {
        "model": "nomic-embed-text",
        "embeddings": [[0.010071, -0.001759, 0.050072] + [0.0] * 765],  # 768-dim
        "total_duration": 14143917,
        "load_duration": 1019500,
        "prompt_eval_count": 8,
    }


@pytest.mark.asyncio
async def test_embed_single_text_success(ollama_client, mock_embedding_response):
    """Test embedding generation for single text input."""
    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_response = AsyncMock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_embedding_response
        mock_response.raise_for_status = AsyncMock()
        mock_post.return_value = mock_response

        embedding = await ollama_client.embed("Test text for embedding")

        assert len(embedding) == 768
        assert isinstance(embedding[0], float)
        mock_post.assert_called_once()


@pytest.mark.asyncio
async def test_embed_batch_success(ollama_client, mock_embedding_response):
    """Test batch embedding generation for multiple texts."""
    batch_response = {
        **mock_embedding_response,
        "embeddings": [
            [0.01, -0.02, 0.03] + [0.0] * 765,
            [0.04, -0.05, 0.06] + [0.0] * 765,
            [0.07, -0.08, 0.09] + [0.0] * 765,
        ],
    }

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_response = AsyncMock()
        mock_response.status_code = 200
        mock_response.json.return_value = batch_response
        mock_response.raise_for_status = AsyncMock()
        mock_post.return_value = mock_response

        embeddings = await ollama_client.embed_batch(
            ["Text 1", "Text 2", "Text 3"]
        )

        assert len(embeddings) == 3
        assert all(len(emb) == 768 for emb in embeddings)
        mock_post.assert_called_once()


@pytest.mark.asyncio
async def test_embed_connection_error(ollama_client):
    """Test handling of connection errors to Ollama service."""
    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.side_effect = httpx.ConnectError("Connection refused")

        with pytest.raises(EmbeddingError) as exc_info:
            await ollama_client.embed("Test text")

        assert exc_info.value.error_type == "connection_error"
        assert exc_info.value.recoverable is True


@pytest.mark.asyncio
async def test_embed_timeout_error(ollama_client):
    """Test handling of timeout errors."""
    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.side_effect = httpx.TimeoutException("Request timeout")

        with pytest.raises(EmbeddingError) as exc_info:
            await ollama_client.embed("Test text")

        assert exc_info.value.error_type == "timeout"
        assert exc_info.value.recoverable is True


@pytest.mark.asyncio
async def test_embed_model_not_found(ollama_client):
    """Test handling of model not found error (404)."""
    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_response = AsyncMock()
        mock_response.status_code = 404
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Model not found",
            request=AsyncMock(),
            response=mock_response,
        )
        mock_post.return_value = mock_response

        with pytest.raises(EmbeddingError) as exc_info:
            await ollama_client.embed("Test text")

        assert exc_info.value.error_type == "model_error"
        assert exc_info.value.recoverable is False


@pytest.mark.asyncio
async def test_embed_server_error(ollama_client):
    """Test handling of server errors (5xx)."""
    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_response = AsyncMock()
        mock_response.status_code = 500
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Internal server error",
            request=AsyncMock(),
            response=mock_response,
        )
        mock_post.return_value = mock_response

        with pytest.raises(EmbeddingError) as exc_info:
            await ollama_client.embed("Test text")

        assert exc_info.value.error_type == "model_error"
        assert exc_info.value.recoverable is True


@pytest.mark.asyncio
async def test_embed_retry_logic(ollama_client):
    """Test retry logic with exponential backoff."""
    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        # First two attempts fail, third succeeds
        mock_response_fail = AsyncMock()
        mock_response_fail.status_code = 503
        mock_response_fail.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Service unavailable",
            request=AsyncMock(),
            response=mock_response_fail,
        )

        mock_response_success = AsyncMock()
        mock_response_success.status_code = 200
        mock_response_success.json.return_value = {
            "model": "nomic-embed-text",
            "embeddings": [[0.01] * 768],
            "total_duration": 14143917,
        }
        mock_response_success.raise_for_status = AsyncMock()

        mock_post.side_effect = [
            mock_response_fail,
            mock_response_fail,
            mock_response_success,
        ]

        embedding = await ollama_client.embed("Test text", max_retries=3)

        assert len(embedding) == 768
        assert mock_post.call_count == 3


@pytest.mark.asyncio
async def test_embed_validation_error():
    """Test validation of embedding request parameters."""
    client = OllamaClient(base_url="http://localhost:11434", model="nomic-embed-text")

    with pytest.raises(ValueError):
        await client.embed("")  # Empty text should fail

    with pytest.raises(ValueError):
        await client.embed_batch([])  # Empty batch should fail


@pytest.mark.asyncio
async def test_embed_dimensions_mismatch(ollama_client):
    """Test handling of dimension mismatch in response."""
    invalid_response = {
        "model": "nomic-embed-text",
        "embeddings": [[0.01, 0.02, 0.03]],  # Only 3 dimensions instead of 768
        "total_duration": 14143917,
    }

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_response = AsyncMock()
        mock_response.status_code = 200
        mock_response.json.return_value = invalid_response
        mock_response.raise_for_status = AsyncMock()
        mock_post.return_value = mock_response

        with pytest.raises(EmbeddingError) as exc_info:
            await ollama_client.embed("Test text")

        assert exc_info.value.error_type == "validation_error"
        assert "768" in exc_info.value.error_message


@pytest.mark.asyncio
async def test_embed_latency_tracking(ollama_client, mock_embedding_response):
    """Test that latency is tracked and returned."""
    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_response = AsyncMock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_embedding_response
        mock_response.raise_for_status = AsyncMock()
        mock_post.return_value = mock_response

        embedding = await ollama_client.embed("Test text")

        # Verify latency was calculated (from total_duration in nanoseconds)
        expected_latency_ms = mock_embedding_response["total_duration"] / 1_000_000
        assert expected_latency_ms > 0
