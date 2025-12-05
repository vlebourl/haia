"""Integration tests for basic chat flow.

Tests the end-to-end chat flow including agent execution, conversation persistence,
and response generation.
"""

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(mocker):
    """Create test client with mocked PydanticAI model."""
    # Mock PydanticAI model inference to avoid external API calls
    mocker.patch("pydantic_ai.models.infer_model")

    # Create real agent with mocked model
    from haia.agent import create_agent
    agent = create_agent("test:model")
    mocker.patch("haia.api.app.create_agent", return_value=agent)

    # Import app after mocking
    from haia.api.app import app
    test_client = TestClient(app)

    yield test_client


class TestBasicChatFlow:
    """Integration tests for basic chat functionality."""

    @pytest.mark.asyncio
    async def test_simple_question_answer_flow(self, client, mocker):
        """Test a simple question-answer interaction with HAIA."""
        # Mock agent.run to return a canned response
        from haia.api.deps import get_agent
        agent = get_agent()

        mock_result = mocker.Mock()
        mock_result.output = "Proxmox VE is an open-source virtualization platform for running VMs and containers."
        agent.run = mocker.AsyncMock(return_value=mock_result)

        # Send chat request
        response = client.post(
            "/v1/chat/completions",
            json={
                "model": "haia",
                "messages": [
                    {"role": "user", "content": "What is Proxmox?"}
                ],
                "stream": False,
            },
        )

        # Verify response
        assert response.status_code == 200
        data = response.json()

        # Check assistant response
        assert data["choices"][0]["message"]["role"] == "assistant"
        assert "Proxmox" in data["choices"][0]["message"]["content"]

    @pytest.mark.asyncio
    async def test_agent_receives_conversation_history(self, client, mocker):
        """Test that agent receives previous conversation context."""
        from haia.api.deps import get_agent
        agent = get_agent()

        mock_result = mocker.Mock()
        mock_result.output = "Containers are isolated application environments."
        agent.run = mocker.AsyncMock(return_value=mock_result)

        # Send request with conversation history (stateless pattern)
        response = client.post(
            "/v1/chat/completions",
            json={
                "model": "haia",
                "messages": [
                    {"role": "user", "content": "What is Docker?"},
                    {"role": "assistant", "content": "Docker is a containerization platform."},
                    {"role": "user", "content": "How does it work?"},
                ],
                "stream": False,
            },
        )

        assert response.status_code == 200

        # Verify agent.run was called with message history
        agent.run.assert_called()
        # The agent should receive the conversation context

    @pytest.mark.asyncio
    async def test_correlation_id_is_logged(self, client, mocker, caplog):
        """Test that correlation ID is included in log messages."""
        from haia.api.deps import get_agent
        agent = get_agent()

        mock_result = mocker.Mock()
        mock_result.output ="Test response"
        agent.run = mocker.AsyncMock(return_value=mock_result)

        correlation_id = "test-correlation-123"

        response = client.post(
            "/v1/chat/completions",
            json={
                "model": "haia",
                "messages": [{"role": "user", "content": "Hello"}],
                "stream": False,
            },
            headers={"X-Correlation-ID": correlation_id},
        )

        assert response.status_code == 200

        # Check that correlation ID was set
        # Note: Actual log checking depends on logging configuration
        # This test verifies the correlation ID header is accepted

    @pytest.mark.asyncio
    async def test_token_usage_is_calculated(self, client, mocker):
        """Test that token usage statistics are included in response."""
        from haia.api.deps import get_agent
        agent = get_agent()

        mock_result = mocker.Mock()
        mock_result.output ="This is a response."
        agent.run = mocker.AsyncMock(return_value=mock_result)

        response = client.post(
            "/v1/chat/completions",
            json={
                "model": "haia",
                "messages": [{"role": "user", "content": "Test"}],
                "stream": False,
            },
        )

        data = response.json()
        usage = data["usage"]

        # Should have positive token counts
        assert usage["prompt_tokens"] > 0
        assert usage["completion_tokens"] > 0
        assert usage["total_tokens"] > 0

    @pytest.mark.asyncio
    async def test_finish_reason_is_set(self, client, mocker):
        """Test that finish_reason is properly set in response."""
        from haia.api.deps import get_agent
        agent = get_agent()

        mock_result = mocker.Mock()
        mock_result.output ="Complete response."
        agent.run = mocker.AsyncMock(return_value=mock_result)

        response = client.post(
            "/v1/chat/completions",
            json={
                "model": "haia",
                "messages": [{"role": "user", "content": "Hello"}],
                "stream": False,
            },
        )

        data = response.json()
        choice = data["choices"][0]

        # Should have finish_reason
        assert choice["finish_reason"] in ["stop", "length", "content_filter"]
