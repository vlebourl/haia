"""
Integration tests for streaming with tool call status indicators.

These tests verify end-to-end behavior with real tool invocations
and OpenWebUI-compatible SSE status events.
"""

import json
import pytest
from unittest.mock import patch, AsyncMock
from httpx import AsyncClient, ASGITransport

from haia.api.app import app


@pytest.fixture
def mock_search_tool():
    """Mock the web search tool to control responses."""
    async def mock_search(ctx, query: str, max_results: int = 10):
        """Mock web search that returns predictable results."""
        return json.dumps({
            "results": [
                {
                    "title": "Docker 24.0 Release Notes",
                    "snippet": "Docker Engine 24.0 is now available with new features...",
                    "url": "https://docs.docker.com/engine/release-notes/24.0/",
                }
            ],
            "query": query,
            "count": 1,
        })

    return mock_search


class TestSingleToolWithStatus:
    """Integration test for single tool invocation with status indicators."""

    @pytest.mark.asyncio
    async def test_single_tool_with_status(self, mock_search_tool):
        """
        Test end-to-end streaming with web search tool showing status indicators.

        Verification:
        1. Status event emitted when tool starts
        2. Status event emitted when tool completes
        3. Response text streams completely after tool execution
        4. No truncation (response should be > 50 characters)
        """
        # Patch the web search tool
        with patch("haia.tools.search.web_search", new=mock_search_tool):
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                # Send chat completion request with streaming
                response = await client.post(
                    "/v1/chat/completions",
                    json={
                        "model": "haia",
                        "messages": [
                            {"role": "user", "content": "What is the latest Docker version?"}
                        ],
                        "stream": True,
                    },
                )

                assert response.status_code == 200
                assert response.headers["content-type"] == "text/event-stream; charset=utf-8"

                # Collect all SSE events
                events = []
                accumulated_text = ""
                status_events = []

                async for line in response.aiter_lines():
                    if line.startswith("data: "):
                        data_str = line[6:]  # Remove "data: " prefix

                        if data_str == "[DONE]":
                            break

                        try:
                            event_data = json.loads(data_str)
                            events.append(event_data)

                            # Track status events
                            if event_data.get("type") == "status":
                                status_events.append(event_data)

                            # Accumulate text content
                            if "choices" in event_data:
                                for choice in event_data["choices"]:
                                    delta_content = choice.get("delta", {}).get("content", "")
                                    if delta_content:
                                        accumulated_text += delta_content
                        except json.JSONDecodeError:
                            pass  # Skip non-JSON lines

                # Verify status events were emitted
                assert len(status_events) >= 1, "Expected at least one status event"

                # Verify at least one status event indicates tool execution
                tool_status_found = any(
                    "search" in event["data"]["description"].lower() or
                    "tool" in event["data"]["description"].lower()
                    for event in status_events
                    if "data" in event and "description" in event["data"]
                )
                assert tool_status_found, "No tool execution status found in status events"

                # Verify response text is not truncated (should be substantial)
                assert len(accumulated_text) > 50, (
                    f"Response appears truncated: only {len(accumulated_text)} characters. "
                    f"Full text: {accumulated_text}"
                )

                # Verify response mentions Docker (shows tool results were used)
                assert "docker" in accumulated_text.lower(), (
                    "Response doesn't mention Docker - tool results may not have been used"
                )


class TestNonToolResponse:
    """Integration test for responses without tool invocation."""

    @pytest.mark.asyncio
    async def test_no_status_for_non_tool_query(self):
        """
        Test that queries not requiring tools don't show status indicators.

        Verification:
        1. No status events emitted
        2. Response streams normally
        3. No delay or truncation
        """
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/v1/chat/completions",
                json={
                    "model": "haia",
                    "messages": [
                        {"role": "user", "content": "What is a homelab?"}
                    ],
                    "stream": True,
                },
            )

            assert response.status_code == 200

            # Collect events
            status_events = []
            accumulated_text = ""

            async for line in response.aiter_lines():
                if line.startswith("data: "):
                    data_str = line[6:]

                    if data_str == "[DONE]":
                        break

                    try:
                        event_data = json.loads(data_str)

                        if event_data.get("type") == "status":
                            status_events.append(event_data)

                        if "choices" in event_data:
                            for choice in event_data["choices"]:
                                delta_content = choice.get("delta", {}).get("content", "")
                                if delta_content:
                                    accumulated_text += delta_content
                    except json.JSONDecodeError:
                        pass

            # Verify NO status events for non-tool query
            assert len(status_events) == 0, (
                f"Expected no status events for non-tool query, got {len(status_events)}"
            )

            # Verify response was still generated
            assert len(accumulated_text) > 0, "No response text generated"
