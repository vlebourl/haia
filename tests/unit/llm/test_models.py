"""Unit tests for Pydantic models."""

import pytest
from pydantic import ValidationError

from haia.llm.models import LLMResponse, LLMResponseChunk, Message, TokenUsage


class TestMessage:
    """Tests for Message model."""

    def test_valid_user_message(self) -> None:
        """Test creating valid user message."""
        msg = Message(role="user", content="Hello")
        assert msg.role == "user"
        assert msg.content == "Hello"

    def test_valid_assistant_message(self) -> None:
        """Test creating valid assistant message."""
        msg = Message(role="assistant", content="Hi there!")
        assert msg.role == "assistant"
        assert msg.content == "Hi there!"

    def test_valid_system_message(self) -> None:
        """Test creating valid system message."""
        msg = Message(role="system", content="You are a helpful assistant.")
        assert msg.role == "system"

    def test_invalid_role(self) -> None:
        """Test that invalid role raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            Message(role="invalid", content="test")
        assert "role" in str(exc_info.value)

    def test_empty_content(self) -> None:
        """Test that empty content raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            Message(role="user", content="")
        assert "content" in str(exc_info.value)


class TestTokenUsage:
    """Tests for TokenUsage model."""

    def test_valid_token_usage(self) -> None:
        """Test creating valid token usage."""
        usage = TokenUsage(prompt_tokens=10, completion_tokens=5, total_tokens=15)
        assert usage.prompt_tokens == 10
        assert usage.completion_tokens == 5
        assert usage.total_tokens == 15

    def test_negative_prompt_tokens(self) -> None:
        """Test that negative prompt_tokens raises ValidationError."""
        with pytest.raises(ValidationError):
            TokenUsage(prompt_tokens=-1, completion_tokens=5, total_tokens=4)

    def test_negative_completion_tokens(self) -> None:
        """Test that negative completion_tokens raises ValidationError."""
        with pytest.raises(ValidationError):
            TokenUsage(prompt_tokens=10, completion_tokens=-5, total_tokens=5)

    def test_negative_total_tokens(self) -> None:
        """Test that negative total_tokens raises ValidationError."""
        with pytest.raises(ValidationError):
            TokenUsage(prompt_tokens=10, completion_tokens=5, total_tokens=-1)

    def test_cost_estimate(self) -> None:
        """Test cost estimation for Anthropic Claude Haiku."""
        # 1M prompt tokens = $0.25, 1M completion tokens = $1.25
        usage = TokenUsage(
            prompt_tokens=1_000_000, completion_tokens=1_000_000, total_tokens=2_000_000
        )
        # Cost = (1M / 1M) * 0.25 + (1M / 1M) * 1.25 = $1.50
        assert usage.cost_estimate == pytest.approx(1.50, rel=1e-6)

    def test_small_usage_cost(self) -> None:
        """Test cost for typical small request."""
        usage = TokenUsage(prompt_tokens=47, completion_tokens=65, total_tokens=112)
        # Very small cost, should be less than a cent
        assert 0 < usage.cost_estimate < 0.01


class TestLLMResponse:
    """Tests for LLMResponse model."""

    def test_valid_response(self) -> None:
        """Test creating valid LLM response."""
        response = LLMResponse(
            content="Hello!",
            model="claude-haiku-4-5-20251001",
            usage=TokenUsage(prompt_tokens=10, completion_tokens=5, total_tokens=15),
            finish_reason="stop",
        )
        assert response.content == "Hello!"
        assert response.model == "claude-haiku-4-5-20251001"
        assert response.usage.total_tokens == 15
        assert response.finish_reason == "stop"

    def test_response_without_finish_reason(self) -> None:
        """Test response with None finish_reason."""
        response = LLMResponse(
            content="Hello!",
            model="test-model",
            usage=TokenUsage(prompt_tokens=10, completion_tokens=5, total_tokens=15),
        )
        assert response.finish_reason is None

    def test_empty_content(self) -> None:
        """Test that empty content raises ValidationError."""
        with pytest.raises(ValidationError):
            LLMResponse(
                content="",
                model="test-model",
                usage=TokenUsage(prompt_tokens=10, completion_tokens=5, total_tokens=15),
            )


class TestLLMResponseChunk:
    """Tests for LLMResponseChunk model."""

    def test_intermediate_chunk(self) -> None:
        """Test intermediate streaming chunk."""
        chunk = LLMResponseChunk(content="Hello")
        assert chunk.content == "Hello"
        assert chunk.finish_reason is None
        assert chunk.usage is None

    def test_final_chunk(self) -> None:
        """Test final streaming chunk with finish_reason and usage."""
        chunk = LLMResponseChunk(
            content="",
            finish_reason="stop",
            usage=TokenUsage(prompt_tokens=10, completion_tokens=5, total_tokens=15),
        )
        assert chunk.content == ""
        assert chunk.finish_reason == "stop"
        assert chunk.usage is not None
        assert chunk.usage.total_tokens == 15
