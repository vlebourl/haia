"""Pytest configuration and shared fixtures."""

import pytest


@pytest.fixture
def mock_anthropic_response():
    """Mock Anthropic API response."""
    from unittest.mock import Mock

    response = Mock()
    response.content = [Mock(text="Test response")]
    response.model = "claude-haiku-4-5-20251001"
    response.usage = Mock(input_tokens=10, output_tokens=5)
    response.stop_reason = "stop"
    return response


@pytest.fixture
def sample_messages():
    """Sample messages for testing."""
    from haia.llm.models import Message

    return [
        Message(role="user", content="Hello, how are you?")
    ]
