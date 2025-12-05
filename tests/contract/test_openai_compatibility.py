"""Contract tests for OpenAI Chat Completions API v1 compatibility.

These tests verify that the API adheres to the OpenAI Chat Completions API specification,
ensuring compatibility with OpenWebUI and other OpenAI-compatible clients.
"""

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(mocker):
    """Create test client with mocked agent."""
    # Mock PydanticAI agent creation
    mock_agent = mocker.Mock()
    mocker.patch("haia.api.app.create_agent", return_value=mock_agent)

    # Import app after mocking
    from haia.api.app import app
    from haia.api.deps import set_agent

    # Set the agent explicitly for tests
    set_agent(mock_agent)

    test_client = TestClient(app)
    yield test_client


class TestChatCompletionsNonStreaming:
    """Contract tests for non-streaming chat completions."""

    def test_basic_chat_completion_request_format(self, client, mocker):
        """Test that API accepts OpenAI-formatted chat completion requests."""
        # Mock agent.run to return a simple response
        from haia.api.deps import get_agent
        mock_agent = get_agent()

        # Create a mock result
        mock_result = mocker.AsyncMock()
        mock_result.output ="This is a test response from HAIA."
        mock_agent.run = mocker.AsyncMock(return_value=mock_result)

        # Mock ConversationRepository
        mock_conversation = mocker.Mock()
        mock_conversation.id = 1

        mock_message = mocker.Mock()
        mock_message.role = "user"
        mock_message.content = "What is Proxmox?"

        mock_repo = mocker.AsyncMock()
        mock_repo.create_conversation = mocker.AsyncMock(return_value=mock_conversation)
        mock_repo.add_message = mocker.AsyncMock(return_value=mock_message)
        mock_repo.get_context_messages = mocker.AsyncMock(return_value=[mock_message])

        mocker.patch("haia.api.routes.chat.ConversationRepository", return_value=mock_repo)

        # Send OpenAI-compatible request
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

        # Should return 200 OK
        assert response.status_code == 200

    def test_response_has_required_openai_fields(self, client, mocker):
        """Test that response includes all required OpenAI API fields."""
        # Mock agent.run
        from haia.api.deps import get_agent
        mock_agent = get_agent()

        mock_result = mocker.Mock()
        mock_result.output ="Proxmox VE is a virtualization platform."
        mock_agent.run.return_value = mock_result

        response = client.post(
            "/v1/chat/completions",
            json={
                "model": "haia",
                "messages": [{"role": "user", "content": "What is Proxmox?"}],
                "stream": False,
            },
        )

        data = response.json()

        # Required OpenAI fields
        assert "id" in data, "Response must include 'id' field"
        assert "object" in data, "Response must include 'object' field"
        assert "created" in data, "Response must include 'created' timestamp"
        assert "model" in data, "Response must include 'model' field"
        assert "choices" in data, "Response must include 'choices' array"
        assert "usage" in data, "Response must include 'usage' field"

        # Validate field types
        assert isinstance(data["id"], str)
        assert data["object"] == "chat.completion"
        assert isinstance(data["created"], int)
        assert isinstance(data["choices"], list)
        assert len(data["choices"]) > 0

    def test_choice_format_matches_openai_spec(self, client, mocker):
        """Test that choice structure matches OpenAI specification."""
        from haia.api.deps import get_agent
        mock_agent = get_agent()

        mock_result = mocker.Mock()
        mock_result.output ="Test response"
        mock_agent.run.return_value = mock_result

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

        # Required choice fields
        assert "index" in choice
        assert "message" in choice
        assert "finish_reason" in choice

        # Validate message structure
        message = choice["message"]
        assert "role" in message
        assert "content" in message
        assert message["role"] == "assistant"
        assert isinstance(message["content"], str)

    def test_usage_statistics_format(self, client, mocker):
        """Test that usage statistics match OpenAI format."""
        from haia.api.deps import get_agent
        mock_agent = get_agent()

        mock_result = mocker.Mock()
        mock_result.output ="Response"
        mock_agent.run.return_value = mock_result

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

        # Required usage fields
        assert "prompt_tokens" in usage
        assert "completion_tokens" in usage
        assert "total_tokens" in usage

        # Validate field types
        assert isinstance(usage["prompt_tokens"], int)
        assert isinstance(usage["completion_tokens"], int)
        assert isinstance(usage["total_tokens"], int)
        assert usage["total_tokens"] == usage["prompt_tokens"] + usage["completion_tokens"]

    def test_conversation_with_system_message(self, client, mocker):
        """Test that system messages are accepted in the conversation."""
        from haia.api.deps import get_agent
        mock_agent = get_agent()

        mock_result = mocker.Mock()
        mock_result.output ="I understand my role."
        mock_agent.run.return_value = mock_result

        response = client.post(
            "/v1/chat/completions",
            json={
                "model": "haia",
                "messages": [
                    {"role": "system", "content": "You are a helpful assistant."},
                    {"role": "user", "content": "Hello"},
                ],
                "stream": False,
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["choices"][0]["message"]["role"] == "assistant"

    def test_multi_turn_conversation(self, client, mocker):
        """Test that multi-turn conversations are handled correctly."""
        from haia.api.deps import get_agent
        mock_agent = get_agent()

        mock_result = mocker.Mock()
        mock_result.output ="Yes, I remember your previous question."
        mock_agent.run.return_value = mock_result

        response = client.post(
            "/v1/chat/completions",
            json={
                "model": "haia",
                "messages": [
                    {"role": "user", "content": "What is Docker?"},
                    {"role": "assistant", "content": "Docker is a containerization platform."},
                    {"role": "user", "content": "Can you tell me more?"},
                ],
                "stream": False,
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["choices"][0]["message"]["content"]

    def test_error_response_for_missing_messages(self, client):
        """Test that missing 'messages' field returns proper error."""
        response = client.post(
            "/v1/chat/completions",
            json={
                "model": "haia",
                "stream": False,
            },
        )

        # Should return 422 Unprocessable Entity for validation error
        assert response.status_code == 422

    def test_error_response_for_empty_messages(self, client):
        """Test that empty messages array returns proper error."""
        response = client.post(
            "/v1/chat/completions",
            json={
                "model": "haia",
                "messages": [],
                "stream": False,
            },
        )

        # Should return 422 for validation error
        assert response.status_code == 422
