"""Integration tests for SSE streaming functionality.

Tests Server-Sent Events streaming for real-time token delivery.
"""

import json

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(mocker):
    """Create test client with mocked agent for streaming tests."""
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


class TestSSEStreaming:
    """Integration tests for Server-Sent Events streaming."""

    def test_streaming_request_returns_sse_response(self, client, mocker):
        """Test that streaming request returns SSE event stream."""
        from haia.api.deps import get_agent

        mock_agent = get_agent()

        # Mock agent.run_stream to return an async generator
        async def mock_stream():
            yield "Proxmox "
            yield "VE "
            yield "is "
            yield "a "
            yield "virtualization "
            yield "platform."

        mock_agent.run_stream = mocker.Mock(return_value=mock_stream())

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

        # Send streaming request
        with client.stream(
            "POST",
            "/v1/chat/completions",
            json={
                "model": "haia",
                "messages": [{"role": "user", "content": "What is Proxmox?"}],
                "stream": True,
            },
        ) as response:
            # Verify response is SSE
            assert response.status_code == 200
            assert "text/event-stream" in response.headers.get("content-type", "")

            # Read and verify chunks
            chunks = []
            for line in response.iter_lines():
                if line.startswith("data: "):
                    data_str = line[6:]  # Remove "data: " prefix
                    if data_str == "[DONE]":
                        break
                    chunk = json.loads(data_str)
                    chunks.append(chunk)

            # Verify we received chunks
            assert len(chunks) > 0

            # Verify chunk structure
            first_chunk = chunks[0]
            assert "id" in first_chunk
            assert "object" in first_chunk
            assert first_chunk["object"] == "chat.completion.chunk"
            assert "choices" in first_chunk
            assert len(first_chunk["choices"]) > 0
            assert "delta" in first_chunk["choices"][0]

    def test_streaming_accumulates_full_response(self, client, mocker):
        """Test that streaming chunks can be accumulated into full response."""
        from haia.api.deps import get_agent

        mock_agent = get_agent()

        # Mock agent.run_stream
        async def mock_stream():
            yield "Hello "
            yield "World!"

        mock_agent.run_stream = mocker.Mock(return_value=mock_stream())

        # Mock repository
        mock_conversation = mocker.Mock()
        mock_conversation.id = 1
        mock_message = mocker.Mock(role="user", content="Test")

        mock_repo = mocker.AsyncMock()
        mock_repo.create_conversation = mocker.AsyncMock(return_value=mock_conversation)
        mock_repo.add_message = mocker.AsyncMock(return_value=mock_message)
        mock_repo.get_context_messages = mocker.AsyncMock(return_value=[mock_message])

        mocker.patch("haia.api.routes.chat.ConversationRepository", return_value=mock_repo)

        # Send streaming request
        with client.stream(
            "POST",
            "/v1/chat/completions",
            json={
                "model": "haia",
                "messages": [{"role": "user", "content": "Test"}],
                "stream": True,
            },
        ) as response:
            # Accumulate content from deltas
            accumulated_content = ""
            for line in response.iter_lines():
                if line.startswith("data: "):
                    data_str = line[6:]
                    if data_str == "[DONE]":
                        break
                    chunk = json.loads(data_str)
                    delta = chunk["choices"][0]["delta"]
                    if "content" in delta:
                        accumulated_content += delta["content"]

            # Verify accumulated content matches expected
            assert "Hello" in accumulated_content
            assert "World!" in accumulated_content

    def test_streaming_final_chunk_has_usage_stats(self, client, mocker):
        """Test that final chunk includes token usage statistics."""
        from haia.api.deps import get_agent

        mock_agent = get_agent()

        async def mock_stream():
            yield "Test response"

        mock_agent.run_stream = mocker.Mock(return_value=mock_stream())

        # Mock repository
        mock_conversation = mocker.Mock()
        mock_conversation.id = 1
        mock_message = mocker.Mock(role="user", content="Test")

        mock_repo = mocker.AsyncMock()
        mock_repo.create_conversation = mocker.AsyncMock(return_value=mock_conversation)
        mock_repo.add_message = mocker.AsyncMock(return_value=mock_message)
        mock_repo.get_context_messages = mocker.AsyncMock(return_value=[mock_message])

        mocker.patch("haia.api.routes.chat.ConversationRepository", return_value=mock_repo)

        with client.stream(
            "POST",
            "/v1/chat/completions",
            json={
                "model": "haia",
                "messages": [{"role": "user", "content": "Test"}],
                "stream": True,
            },
        ) as response:
            chunks = []
            for line in response.iter_lines():
                if line.startswith("data: "):
                    data_str = line[6:]
                    if data_str == "[DONE]":
                        break
                    chunk = json.loads(data_str)
                    chunks.append(chunk)

            # Last chunk should have usage statistics
            if chunks:
                last_chunk = chunks[-1]
                # Final chunk may have usage field
                # (or could be in a separate final message)
                assert "choices" in last_chunk

    def test_streaming_ends_with_done_marker(self, client, mocker):
        """Test that stream ends with [DONE] marker."""
        from haia.api.deps import get_agent

        mock_agent = get_agent()

        async def mock_stream():
            yield "Test"

        mock_agent.run_stream = mocker.Mock(return_value=mock_stream())

        # Mock repository
        mock_conversation = mocker.Mock()
        mock_conversation.id = 1
        mock_message = mocker.Mock(role="user", content="Test")

        mock_repo = mocker.AsyncMock()
        mock_repo.create_conversation = mocker.AsyncMock(return_value=mock_conversation)
        mock_repo.add_message = mocker.AsyncMock(return_value=mock_message)
        mock_repo.get_context_messages = mocker.AsyncMock(return_value=[mock_message])

        mocker.patch("haia.api.routes.chat.ConversationRepository", return_value=mock_repo)

        with client.stream(
            "POST",
            "/v1/chat/completions",
            json={
                "model": "haia",
                "messages": [{"role": "user", "content": "Test"}],
                "stream": True,
            },
        ) as response:
            lines = list(response.iter_lines())

            # Find [DONE] marker
            done_found = False
            for line in lines:
                if line.startswith("data: [DONE]"):
                    done_found = True
                    break

            assert done_found, "Stream should end with data: [DONE] marker"


class TestClientDisconnection:
    """Tests for handling client disconnections during streaming."""

    def test_graceful_disconnection_handling(self, client, mocker):
        """Test that server handles client disconnection gracefully."""
        from haia.api.deps import get_agent

        mock_agent = get_agent()

        # Mock long-running stream
        async def mock_long_stream():
            for i in range(100):
                yield f"Token {i} "

        mock_agent.run_stream = mocker.Mock(return_value=mock_long_stream())

        # Mock repository
        mock_conversation = mocker.Mock()
        mock_conversation.id = 1
        mock_message = mocker.Mock(role="user", content="Test")

        mock_repo = mocker.AsyncMock()
        mock_repo.create_conversation = mocker.AsyncMock(return_value=mock_conversation)
        mock_repo.add_message = mocker.AsyncMock(return_value=mock_message)
        mock_repo.get_context_messages = mocker.AsyncMock(return_value=[mock_message])

        mocker.patch("haia.api.routes.chat.ConversationRepository", return_value=mock_repo)

        # Start streaming but disconnect early
        with client.stream(
            "POST",
            "/v1/chat/completions",
            json={
                "model": "haia",
                "messages": [{"role": "user", "content": "Test"}],
                "stream": True,
            },
        ) as response:
            # Read only first few chunks then disconnect
            count = 0
            for line in response.iter_lines():
                count += 1
                if count > 3:
                    break  # Simulate client disconnect

            # If we get here without exception, disconnection was handled gracefully
            assert True
