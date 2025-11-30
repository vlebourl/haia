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
