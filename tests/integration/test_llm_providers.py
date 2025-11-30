"""Integration tests for LLM providers (requires API keys)."""

import os

import pytest

from haia.llm import Message, create_client
from haia.llm.errors import AuthenticationError
from pydantic import Field
from pydantic_settings import BaseSettings


class IntegrationTestSettings(BaseSettings):
    """Settings for integration tests."""

    haia_model: str = Field(..., description="Model selection")
    anthropic_api_key: str | None = None
    ollama_base_url: str | None = None
    llm_timeout: float = 30.0


@pytest.mark.integration
@pytest.mark.skipif(
    not os.getenv("ANTHROPIC_API_KEY"),
    reason="ANTHROPIC_API_KEY not set - skipping integration test",
)
@pytest.mark.asyncio
async def test_anthropic_real_api_call() -> None:
    """Test real API call to Anthropic Claude (requires ANTHROPIC_API_KEY)."""
    # Load settings from environment
    config = IntegrationTestSettings(
        haia_model="anthropic:claude-haiku-4-5-20251001",
        anthropic_api_key=os.getenv("ANTHROPIC_API_KEY"),
    )

    client = create_client(config)

    # Send test message
    messages = [Message(role="user", content="Hello! Please respond with just 'Hi'")]

    response = await client.chat(messages=messages, max_tokens=10)

    # Verify response
    assert response.content is not None
    assert len(response.content) > 0
    assert response.model == "claude-haiku-4-5-20251001"
    assert response.usage.prompt_tokens > 0
    assert response.usage.completion_tokens > 0
    assert response.usage.total_tokens > 0
    assert response.finish_reason in ("stop", "end_turn")


@pytest.mark.integration
@pytest.mark.asyncio
async def test_anthropic_invalid_api_key() -> None:
    """Test authentication error with invalid API key."""
    config = IntegrationTestSettings(
        haia_model="anthropic:claude-haiku-4-5-20251001",
        anthropic_api_key="invalid-key",
    )

    client = create_client(config)

    messages = [Message(role="user", content="Hello")]

    with pytest.raises(AuthenticationError):
        await client.chat(messages=messages)


@pytest.mark.integration
@pytest.mark.skipif(
    not os.getenv("ANTHROPIC_API_KEY"),
    reason="ANTHROPIC_API_KEY not set - skipping integration test",
)
@pytest.mark.asyncio
async def test_anthropic_with_system_prompt() -> None:
    """Test Anthropic with system prompt."""
    config = IntegrationTestSettings(
        haia_model="anthropic:claude-haiku-4-5-20251001",
        anthropic_api_key=os.getenv("ANTHROPIC_API_KEY"),
    )

    client = create_client(config)

    # Send test message with system prompt
    messages = [
        Message(
            role="system",
            content="You are a concise assistant. Respond with exactly one word.",
        ),
        Message(role="user", content="Say hello"),
    ]

    response = await client.chat(messages=messages, max_tokens=10)

    # Verify response
    assert response.content is not None
    assert len(response.content) > 0
    # Response should be very short since we asked for one word
    assert len(response.content.split()) <= 3


def _is_ollama_available() -> bool:
    """Check if Ollama is running locally."""
    import httpx

    try:
        response = httpx.get("http://localhost:11434/api/tags", timeout=2.0)
        return response.status_code == 200
    except Exception:
        return False


@pytest.mark.integration
@pytest.mark.skipif(
    not _is_ollama_available(),
    reason="Ollama not running on localhost:11434 - skipping integration test",
)
@pytest.mark.asyncio
async def test_ollama_real_api_call() -> None:
    """Test real API call to Ollama (requires local Ollama instance)."""
    config = IntegrationTestSettings(
        haia_model="ollama:qwen2.5-coder:7b",
    )

    client = create_client(config)

    # Send test message
    messages = [Message(role="user", content="Hello! Please respond with just 'Hi'")]

    response = await client.chat(messages=messages, max_tokens=10)

    # Verify response
    assert response.content is not None
    assert len(response.content) > 0
    assert "qwen2.5-coder" in response.model.lower()
    assert response.usage.prompt_tokens >= 0  # Ollama may return 0 if not counting
    assert response.usage.completion_tokens >= 0
    assert response.finish_reason in ("stop", "end_turn", None)


@pytest.mark.integration
@pytest.mark.skipif(
    not _is_ollama_available(),
    reason="Ollama not running - skipping integration test",
)
@pytest.mark.asyncio
async def test_ollama_with_system_message() -> None:
    """Test Ollama with system message."""
    config = IntegrationTestSettings(
        haia_model="ollama:qwen2.5-coder:7b",
    )

    client = create_client(config)

    # Send test message with system prompt
    messages = [
        Message(
            role="system",
            content="You are a concise assistant. Respond with exactly one word.",
        ),
        Message(role="user", content="Say hello"),
    ]

    response = await client.chat(messages=messages, max_tokens=10)

    # Verify response
    assert response.content is not None
    assert len(response.content) > 0


@pytest.mark.integration
@pytest.mark.skipif(
    not (os.getenv("ANTHROPIC_API_KEY") and _is_ollama_available()),
    reason="Both ANTHROPIC_API_KEY and Ollama required - skipping provider switching test",
)
@pytest.mark.asyncio
async def test_provider_switching() -> None:
    """Test switching between providers with same messages.

    Verifies that both providers return responses in the same format,
    demonstrating provider-agnostic abstraction.
    """
    test_messages = [
        Message(role="system", content="You are a helpful assistant."),
        Message(role="user", content="Say hello in one word."),
    ]

    # Test Anthropic
    anthropic_config = IntegrationTestSettings(
        haia_model="anthropic:claude-haiku-4-5-20251001",
        anthropic_api_key=os.getenv("ANTHROPIC_API_KEY"),
    )
    anthropic_client = create_client(anthropic_config)
    anthropic_response = await anthropic_client.chat(messages=test_messages, max_tokens=10)

    # Test Ollama
    ollama_config = IntegrationTestSettings(
        haia_model="ollama:qwen2.5-coder:7b",
    )
    ollama_client = create_client(ollama_config)
    ollama_response = await ollama_client.chat(messages=test_messages, max_tokens=10)

    # Verify both responses have the same structure
    assert anthropic_response.content is not None
    assert ollama_response.content is not None
    assert len(anthropic_response.content) > 0
    assert len(ollama_response.content) > 0

    # Verify both have token usage
    assert anthropic_response.usage.total_tokens > 0
    # Ollama may or may not track tokens, so we just check it exists
    assert hasattr(ollama_response.usage, "total_tokens")

    # Verify both have model information
    assert "claude" in anthropic_response.model.lower()
    assert "qwen" in ollama_response.model.lower() or "coder" in ollama_response.model.lower()

    # Verify both have finish_reason (may be None for some providers)
    assert hasattr(anthropic_response, "finish_reason")
    assert hasattr(ollama_response, "finish_reason")
