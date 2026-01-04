"""
Unit tests for SSE streaming with tool call status events.

Tests the OpenWebUI-compatible status event format and streaming behavior
when tools are invoked during chat completion.
"""

import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from pydantic_ai.messages import (
    PartStartEvent,
    PartDeltaEvent,
    TextPartDelta,
    ToolCallPartDelta,
    FunctionToolCallEvent,
    FunctionToolResultEvent,
    ToolCallPart,
    ToolReturnPart,
    TextPart,
)

from haia.api.routes.chat import stream_chat_response
from haia.api.models.chat import ChatCompletionRequest, ChatMessage


@pytest.fixture
def mock_agent():
    """Create a mock PydanticAI agent."""
    agent = AsyncMock()
    return agent


@pytest.fixture
def sample_request():
    """Create a sample chat completion request."""
    return ChatCompletionRequest(
        model="haia",
        messages=[
            ChatMessage(role="user", content="What is the latest Docker version?")
        ],
        stream=True,
    )


class TestStatusEventFormat:
    """Test SSE status event format for tool execution."""

    @pytest.mark.asyncio
    async def test_status_event_format_on_tool_start(
        self, mock_agent, sample_request
    ):
        """Test that status events are properly formatted when tool starts."""
        # Mock run_stream_events to yield tool call event
        async def mock_stream_events(*args, **kwargs):
            yield FunctionToolCallEvent(
                part=ToolCallPart(
                    tool_name="web_search",
                    args={"query": "Docker version"},
                    tool_call_id="call_001"
                )
            )

        mock_agent.run_stream_events = mock_stream_events

        # Collect SSE chunks
        chunks = []
        async for chunk in stream_chat_response(
            sample_request, mock_agent, "test-corr-id"
        ):
            chunks.append(chunk)

        # Find status event in chunks
        status_events = [
            chunk for chunk in chunks if '"type": "status"' in chunk or '"type":"status"' in chunk
        ]

        assert len(status_events) > 0, "No status events found"

        # Parse first status event
        status_line = status_events[0].strip()
        if status_line.startswith("data: "):
            status_json_str = status_line[6:]  # Remove "data: " prefix
            status_data = json.loads(status_json_str)

            assert status_data["type"] == "status"
            assert "data" in status_data
            assert "description" in status_data["data"]
            assert "done" in status_data["data"]
            assert isinstance(status_data["data"]["done"], bool)
            assert status_data["data"]["done"] is False  # Tool just started

    @pytest.mark.asyncio
    async def test_status_event_format_on_tool_complete(
        self, mock_agent, sample_request
    ):
        """Test that status events are properly formatted when tool completes."""
        # Mock run_stream_events to yield tool complete sequence
        async def mock_stream_events(*args, **kwargs):
            yield FunctionToolCallEvent(
                part=ToolCallPart(
                    tool_name="web_search",
                    args={"query": "Docker version"},
                    tool_call_id="call_001"
                )
            )
            yield FunctionToolResultEvent(
                result=ToolReturnPart(
                    tool_name="web_search",
                    content="Docker 24.0 is the latest version",
                    tool_call_id="call_001"
                )
            )

        mock_agent.run_stream_events = mock_stream_events

        # Collect SSE chunks
        chunks = []
        async for chunk in stream_chat_response(
            sample_request, mock_agent, "test-corr-id"
        ):
            chunks.append(chunk)

        # Find status events
        status_events = [
            chunk for chunk in chunks if '"type": "status"' in chunk or '"type":"status"' in chunk
        ]

        # Should have at least 2 status events (start and complete)
        assert len(status_events) >= 2, f"Expected at least 2 status events, got {len(status_events)}"

        # Check completion status event (last one)
        completion_status = status_events[-1].strip()
        if completion_status.startswith("data: "):
            status_json_str = completion_status[6:]
            status_data = json.loads(status_json_str)

            assert status_data["type"] == "status"
            assert status_data["data"]["done"] is True  # Tool completed

    @pytest.mark.asyncio
    async def test_text_streaming_after_tool(self, mock_agent, sample_request):
        """Test that text deltas stream correctly after tool completes."""
        # Mock run_stream_events to yield tool + text sequence
        async def mock_stream_events(*args, **kwargs):
            yield FunctionToolCallEvent(
                part=ToolCallPart(
                    tool_name="web_search",
                    args={"query": "Docker version"},
                    tool_call_id="call_001"
                )
            )
            yield FunctionToolResultEvent(
                result=ToolReturnPart(
                    tool_name="web_search",
                    content="Docker 24.0 is latest",
                    tool_call_id="call_001"
                )
            )
            yield PartDeltaEvent(
                index=0,
                delta=TextPartDelta(content_delta="Docker")
            )
            yield PartDeltaEvent(
                index=0,
                delta=TextPartDelta(content_delta=" 24.0")
            )
            yield PartDeltaEvent(
                index=0,
                delta=TextPartDelta(content_delta=" is")
            )
            yield PartDeltaEvent(
                index=0,
                delta=TextPartDelta(content_delta=" the latest version")
            )

        mock_agent.run_stream_events = mock_stream_events

        # Collect SSE chunks
        chunks = []
        async for chunk in stream_chat_response(
            sample_request, mock_agent, "test-corr-id"
        ):
            chunks.append(chunk)

        # Find message chunks (not status events)
        message_chunks = [
            chunk
            for chunk in chunks
            if chunk.startswith("data: {") and '"type": "status"' not in chunk and '"type":"status"' not in chunk
        ]

        # Should have text content chunks
        assert len(message_chunks) > 0, "No message chunks found"

        # Verify text content is streamed
        has_text_content = any(
            "Docker" in chunk or "24.0" in chunk or "latest version" in chunk
            for chunk in message_chunks
        )
        assert has_text_content, "Expected text content not found in streamed messages"
