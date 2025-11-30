"""Performance tests for LLM abstraction layer."""

import time

import pytest

from haia.llm import Message, create_client
from pydantic import Field
from pydantic_settings import BaseSettings


class MockSettings(BaseSettings):
    """Mock settings for testing."""

    haia_model: str = Field(..., description="Model selection")
    anthropic_api_key: str | None = None
    llm_timeout: float = 30.0


class TestPerformance:
    """Performance tests for abstraction layer overhead."""

    @pytest.mark.asyncio
    async def test_abstraction_overhead(self, mocker) -> None:
        """Test that abstraction layer overhead is < 10ms.

        This test verifies that the abstraction layer adds minimal latency
        to LLM API calls, ensuring the overhead is within acceptable bounds.
        """
        # Mock the Anthropic API to return instantly
        import anthropic

        mock_message = mocker.Mock()
        mock_message.content = [mocker.Mock(text="Test response")]
        mock_message.usage.input_tokens = 10
        mock_message.usage.output_tokens = 5
        mock_message.model = "claude-haiku-4-5-20251001"
        mock_message.stop_reason = "stop"

        mock_create = mocker.patch.object(
            anthropic.resources.AsyncMessages,
            "create",
            return_value=mock_message,
            new_callable=mocker.AsyncMock,
        )

        # Create client
        config = MockSettings(
            haia_model="anthropic:claude-haiku-4-5-20251001",
            anthropic_api_key="test-key",
        )
        client = create_client(config)

        # Warm up (exclude first call from measurements)
        messages = [Message(role="user", content="Test")]
        await client.chat(messages=messages)

        # Measure overhead over multiple calls
        iterations = 10
        total_overhead = 0.0

        for _ in range(iterations):
            # Measure time for abstraction layer call
            start = time.perf_counter()
            await client.chat(messages=messages)
            abstraction_time = time.perf_counter() - start

            # Baseline is effectively 0 for mocked call (instant return)
            # The abstraction overhead is the entire measured time
            baseline_time = 0

            # Calculate overhead (abstraction time - baseline time)
            overhead = (abstraction_time - baseline_time) * 1000  # Convert to ms
            total_overhead += overhead

        # Average overhead
        avg_overhead = total_overhead / iterations

        # Assert average overhead is < 10ms (per constitution requirement)
        assert avg_overhead < 10.0, (
            f"Abstraction overhead ({avg_overhead:.2f}ms) exceeds 10ms threshold. "
            f"This indicates the abstraction layer is adding significant latency."
        )

        # Log the actual overhead for visibility
        print(f"\nAbstraction layer overhead: {avg_overhead:.2f}ms (target: <10ms)")

    @pytest.mark.asyncio
    async def test_response_mapping_performance(self) -> None:
        """Test that response mapping is fast (<1ms)."""
        from haia.llm.providers.anthropic import AnthropicClient
        import anthropic

        client = AnthropicClient(api_key="test-key", model="test-model", timeout=30.0)

        # Create a mock response
        class MockContent:
            text = "Test response content"

        class MockUsage:
            input_tokens = 100
            output_tokens = 50

        class MockResponse:
            content = [MockContent()]
            usage = MockUsage()
            model = "test-model"
            stop_reason = "stop"

        mock_response = MockResponse()

        # Warm up
        _ = client._map_response(mock_response)

        # Measure mapping time over multiple iterations
        iterations = 100
        total_time = 0.0

        for _ in range(iterations):
            start = time.perf_counter()
            _ = client._map_response(mock_response)
            total_time += time.perf_counter() - start

        avg_time_ms = (total_time / iterations) * 1000

        # Response mapping should be < 1ms
        assert avg_time_ms < 1.0, (
            f"Response mapping took {avg_time_ms:.3f}ms, should be <1ms"
        )

        print(f"\nResponse mapping time: {avg_time_ms:.3f}ms (target: <1ms)")
