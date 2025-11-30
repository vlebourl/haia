"""Unit tests for factory function."""

import pytest
from pydantic import Field
from pydantic_settings import BaseSettings

from haia.llm.factory import create_client
from haia.llm.providers.anthropic import AnthropicClient
from haia.llm.providers.ollama import OllamaClient


class MockSettings(BaseSettings):
    """Mock settings for testing."""

    haia_model: str = Field(..., description="Model selection")
    anthropic_api_key: str | None = None
    ollama_base_url: str | None = None
    llm_timeout: float = 30.0


class TestCreateClient:
    """Tests for create_client factory function."""

    def test_create_anthropic_client(self) -> None:
        """Test creating Anthropic client."""
        config = MockSettings(
            haia_model="anthropic:claude-haiku-4-5-20251001",
            anthropic_api_key="test-key",
        )

        client = create_client(config)

        assert isinstance(client, AnthropicClient)
        assert client.model == "claude-haiku-4-5-20251001"
        assert client.timeout == 30.0

    def test_create_client_with_custom_timeout(self) -> None:
        """Test creating client with custom timeout."""
        config = MockSettings(
            haia_model="anthropic:claude-haiku-4-5-20251001",
            anthropic_api_key="test-key",
            llm_timeout=60.0,
        )

        client = create_client(config)

        assert client.timeout == 60.0

    def test_invalid_model_format_no_colon(self) -> None:
        """Test error when model format has no colon."""
        config = MockSettings(
            haia_model="invalid-format",
            anthropic_api_key="test-key",
        )

        with pytest.raises(ValueError) as exc_info:
            create_client(config)

        assert "invalid" in str(exc_info.value).lower()
        assert "provider:model" in str(exc_info.value).lower()

    def test_invalid_model_format_empty_provider(self) -> None:
        """Test error when provider is empty."""
        config = MockSettings(
            haia_model=":model",
            anthropic_api_key="test-key",
        )

        with pytest.raises(ValueError) as exc_info:
            create_client(config)

        assert "invalid" in str(exc_info.value).lower() or "non-empty" in str(exc_info.value).lower()

    def test_invalid_model_format_empty_model(self) -> None:
        """Test error when model is empty."""
        config = MockSettings(
            haia_model="anthropic:",
            anthropic_api_key="test-key",
        )

        with pytest.raises(ValueError) as exc_info:
            create_client(config)

        assert "invalid" in str(exc_info.value).lower() or "non-empty" in str(exc_info.value).lower()

    def test_anthropic_missing_api_key(self) -> None:
        """Test error when Anthropic API key is missing."""
        config = MockSettings(
            haia_model="anthropic:claude-haiku-4-5-20251001",
        )

        with pytest.raises(ValueError) as exc_info:
            create_client(config)

        assert "anthropic_api_key" in str(exc_info.value).lower() or "configuration" in str(exc_info.value).lower()

    def test_anthropic_empty_api_key(self) -> None:
        """Test error when Anthropic API key is empty."""
        config = MockSettings(
            haia_model="anthropic:claude-haiku-4-5-20251001",
            anthropic_api_key="",
        )

        with pytest.raises(ValueError) as exc_info:
            create_client(config)

        assert "empty" in str(exc_info.value).lower()

    def test_unsupported_provider(self) -> None:
        """Test error when provider is not supported."""
        config = MockSettings(
            haia_model="unknown:model",
            anthropic_api_key="test-key",
        )

        with pytest.raises(ValueError) as exc_info:
            create_client(config)

        assert "unsupported" in str(exc_info.value).lower()
        assert "unknown" in str(exc_info.value).lower()

    def test_create_ollama_client(self) -> None:
        """Test creating Ollama client."""
        config = MockSettings(
            haia_model="ollama:qwen2.5-coder:7b",
        )

        client = create_client(config)

        assert isinstance(client, OllamaClient)
        assert client.model == "qwen2.5-coder:7b"
        assert client.base_url == "http://localhost:11434"
        assert client.timeout == 120.0  # Ollama defaults to 120s

    def test_create_ollama_client_custom_base_url(self) -> None:
        """Test creating Ollama client with custom base URL."""
        config = MockSettings(
            haia_model="ollama:llama3.1:8b",
            ollama_base_url="http://192.168.1.100:11434",
        )

        client = create_client(config)

        assert isinstance(client, OllamaClient)
        assert client.model == "llama3.1:8b"
        assert client.base_url == "http://192.168.1.100:11434"

    def test_create_ollama_client_custom_timeout(self) -> None:
        """Test creating Ollama client with custom timeout."""
        config = MockSettings(
            haia_model="ollama:qwen2.5-coder:7b",
            llm_timeout=60.0,
        )

        client = create_client(config)

        assert client.timeout == 60.0

    def test_openai_not_implemented(self) -> None:
        """Test that OpenAI provider raises NotImplementedError."""
        config = MockSettings(
            haia_model="openai:gpt-4",
            anthropic_api_key="test-key",
        )

        with pytest.raises(NotImplementedError) as exc_info:
            create_client(config)

        assert "openai" in str(exc_info.value).lower()

    def test_gemini_not_implemented(self) -> None:
        """Test that Gemini provider raises NotImplementedError."""
        config = MockSettings(
            haia_model="gemini:gemini-pro",
            anthropic_api_key="test-key",
        )

        with pytest.raises(NotImplementedError) as exc_info:
            create_client(config)

        assert "gemini" in str(exc_info.value).lower()

    def test_config_missing_haia_model(self) -> None:
        """Test error when config doesn't have haia_model attribute."""

        class InvalidConfig:
            """Config without haia_model."""

            pass

        with pytest.raises(ValueError) as exc_info:
            create_client(InvalidConfig())  # type: ignore

        assert "missing" in str(exc_info.value).lower()
        assert "haia_model" in str(exc_info.value).lower()
