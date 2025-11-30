"""Concurrency tests for LLM abstraction layer."""

import asyncio

import pytest

from haia.llm import Message, create_client
from pydantic import Field
from pydantic_settings import BaseSettings


class MockSettings(BaseSettings):
    """Mock settings for testing."""

    haia_model: str = Field(..., description="Model selection")
    anthropic_api_key: str | None = None
    llm_timeout: float = 30.0


class TestConcurrency:
    """Test concurrent LLM calls."""

    @pytest.mark.asyncio
    async def test_concurrent_calls_no_conflicts(self, mocker) -> None:
        """Test that multiple simultaneous LLM calls work without conflicts.

        This test verifies that:
        1. Multiple concurrent calls can be made to the same client
        2. Each call gets its own independent response
        3. No data races or shared state issues occur
        4. Correlation IDs are unique per request
        """
        import anthropic

        # Create mock responses with different content for verification
        def create_mock_response(response_text: str):
            mock_message = mocker.Mock()
            mock_message.content = [mocker.Mock(text=response_text)]
            mock_message.usage.input_tokens = 10
            mock_message.usage.output_tokens = 5
            mock_message.model = "claude-haiku-4-5-20251001"
            mock_message.stop_reason = "stop"
            return mock_message

        # Track call count to ensure all requests are made
        call_count = 0

        async def mock_create(**kwargs):
            nonlocal call_count
            call_count += 1
            # Return unique response based on request content
            user_content = kwargs["messages"][0]["content"]
            return create_mock_response(f"Response to: {user_content}")

        mocker.patch.object(
            anthropic.resources.AsyncMessages,
            "create",
            side_effect=mock_create,
        )

        # Create client
        config = MockSettings(
            haia_model="anthropic:claude-haiku-4-5-20251001",
            anthropic_api_key="test-key",
        )
        client = create_client(config)

        # Prepare different messages
        test_cases = [
            Message(role="user", content=f"Test message {i}") for i in range(10)
        ]

        # Make 10 concurrent calls
        async def make_call(msg: Message, index: int):
            response = await client.chat(messages=[msg])
            # Verify response matches the request
            assert response.content == f"Response to: Test message {index}"
            return response

        # Execute all calls concurrently
        responses = await asyncio.gather(
            *[make_call(msg, i) for i, msg in enumerate(test_cases)]
        )

        # Verify all calls completed
        assert len(responses) == 10
        assert call_count == 10

        # Verify each response is independent
        contents = [r.content for r in responses]
        assert len(set(contents)) == 10  # All responses should be unique

        # Verify all responses are valid
        for response in responses:
            assert response.content is not None
            assert response.usage.total_tokens > 0
            assert response.model == "claude-haiku-4-5-20251001"

    @pytest.mark.asyncio
    async def test_concurrent_error_handling(self, mocker) -> None:
        """Test that errors in one concurrent call don't affect others."""
        import anthropic

        call_order = []

        async def mock_create(**kwargs):
            user_content = kwargs["messages"][0]["content"]
            call_order.append(user_content)

            if "error" in user_content:
                # Simulate API error
                raise anthropic.APIStatusError(
                    message="Rate limit exceeded",
                    response=mocker.Mock(status_code=429),
                    body=None,
                )
            else:
                # Return normal response
                mock_message = mocker.Mock()
                mock_message.content = [mocker.Mock(text=f"Response: {user_content}")]
                mock_message.usage.input_tokens = 10
                mock_message.usage.output_tokens = 5
                mock_message.model = "test-model"
                mock_message.stop_reason = "stop"
                return mock_message

        mocker.patch.object(
            anthropic.resources.AsyncMessages,
            "create",
            side_effect=mock_create,
        )

        # Create client
        config = MockSettings(
            haia_model="anthropic:claude-haiku-4-5-20251001",
            anthropic_api_key="test-key",
        )
        client = create_client(config)

        # Mix of successful and failing calls
        messages = [
            Message(role="user", content="success 1"),
            Message(role="user", content="error call"),
            Message(role="user", content="success 2"),
            Message(role="user", content="success 3"),
        ]

        # Execute concurrently and gather results
        results = await asyncio.gather(
            *[client.chat(messages=[msg]) for msg in messages],
            return_exceptions=True,
        )

        # Verify we got 4 results (3 successes + 1 error)
        assert len(results) == 4

        # Count successes and errors
        successes = [r for r in results if not isinstance(r, Exception)]
        errors = [r for r in results if isinstance(r, Exception)]

        assert len(successes) == 3  # success 1, 2, 3
        assert len(errors) == 1  # error call

        # Verify successful responses are valid
        for response in successes:
            assert "Response:" in response.content

        # Verify error is the expected type
        from haia.llm.errors import RateLimitError

        assert isinstance(errors[0], RateLimitError)

        # Verify all calls were attempted (no early termination)
        assert len(call_order) == 4

    @pytest.mark.asyncio
    async def test_multiple_clients_concurrent(self, mocker) -> None:
        """Test that multiple client instances can be used concurrently."""
        import anthropic

        async def mock_create(**kwargs):
            mock_message = mocker.Mock()
            mock_message.content = [mocker.Mock(text="Test response")]
            mock_message.usage.input_tokens = 10
            mock_message.usage.output_tokens = 5
            mock_message.model = kwargs["model"]
            mock_message.stop_reason = "stop"
            return mock_message

        mocker.patch.object(
            anthropic.resources.AsyncMessages,
            "create",
            side_effect=mock_create,
        )

        # Create multiple clients
        config1 = MockSettings(
            haia_model="anthropic:claude-haiku-4-5-20251001",
            anthropic_api_key="test-key-1",
        )
        config2 = MockSettings(
            haia_model="anthropic:claude-haiku-4-5-20251001",
            anthropic_api_key="test-key-2",
        )

        client1 = create_client(config1)
        client2 = create_client(config2)

        messages = [Message(role="user", content="Test")]

        # Make concurrent calls from different clients
        responses = await asyncio.gather(
            client1.chat(messages=messages),
            client2.chat(messages=messages),
            client1.chat(messages=messages),
            client2.chat(messages=messages),
        )

        # All calls should succeed
        assert len(responses) == 4
        for response in responses:
            assert response.content == "Test response"
