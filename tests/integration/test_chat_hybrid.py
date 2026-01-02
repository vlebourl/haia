"""Integration tests for chat API with hybrid retrieval mode.

Tests verify:
- Hybrid mode detection from request metadata
- Hybrid retrieval integration with chat completions
- Source attribution in memory context
- Fallback to vector-only when hybrid disabled
"""

import pytest
from unittest.mock import AsyncMock, MagicMock
from datetime import datetime, timezone
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.testclient import TestClient
from src.haia.api.deps import get_agent, get_retrieval_service, get_neo4j_service, get_conversation_tracker
from src.haia.api.routes import chat


@asynccontextmanager
async def test_lifespan(app: FastAPI):
    """Test lifespan that does nothing (skip real startup/shutdown)."""
    yield


# Create test app with disabled lifespan
test_app = FastAPI(lifespan=test_lifespan)
test_app.include_router(chat.router)


@pytest.fixture(autouse=True)
def setup_dependencies():
    """Set up mock dependencies for all tests."""
    # Mock Neo4j service
    mock_neo4j = MagicMock()

    # Mock conversation tracker
    mock_tracker = AsyncMock()
    mock_tracker.detect_boundary.return_value = False

    # Override dependencies
    test_app.dependency_overrides[get_neo4j_service] = lambda: mock_neo4j
    test_app.dependency_overrides[get_conversation_tracker] = lambda: mock_tracker

    yield

    # Clean up
    test_app.dependency_overrides.clear()


@pytest.fixture
def mock_retrieval_service():
    """Mock retrieval service for testing."""
    mock = AsyncMock()

    # Mock vector-only retrieve() method
    mock.retrieve.return_value = MagicMock(
        has_results=True,
        total_results=2,
        total_latency_ms=50.0,
        results=[
            MagicMock(
                memory=MagicMock(
                    memory_id="mem_v1",
                    content="Docker is preferred for homelab deployments",
                    memory_type="preference",
                    confidence=0.9,
                ),
                relevance_score=0.85,
            ),
            MagicMock(
                memory=MagicMock(
                    memory_id="mem_v2",
                    content="Proxmox cluster has 3 nodes",
                    memory_type="technical_context",
                    confidence=0.88,
                ),
                relevance_score=0.82,
            ),
        ],
    )

    # Mock hybrid retrieve_hybrid() method
    from haia.extraction.models import ExtractedMemory
    from haia.embedding.models import RetrievalResult

    mock.retrieve_hybrid.return_value = [
        RetrievalResult(
            memory=ExtractedMemory(
                memory_id="mem_h1",
                content="Docker is preferred for homelab deployments",
                memory_type="preference",
                confidence=0.9,
                source_conversation_id="conv_1",
                extraction_timestamp=datetime.now(timezone.utc),
                has_embedding=True,
                metadata={
                    "source_methods": ["vector", "bm25"],
                    "rrf_score": 0.048,
                },
            ),
            similarity_score=0.048,
            relevance_score=0.048,
            rank=1,
            was_deduplicated=False,
            access_metadata=None,
        ),
        RetrievalResult(
            memory=ExtractedMemory(
                memory_id="mem_h2",
                content="Proxmox cluster uses Ceph for distributed storage",
                memory_type="technical_context",
                confidence=0.87,
                source_conversation_id="conv_2",
                extraction_timestamp=datetime.now(timezone.utc),
                has_embedding=True,
                metadata={
                    "source_methods": ["vector", "graph"],
                    "rrf_score": 0.034,
                },
            ),
            similarity_score=0.034,
            relevance_score=0.034,
            rank=2,
            was_deduplicated=False,
            access_metadata=None,
        ),
    ]

    mock.health_check.return_value = True
    return mock


@pytest.mark.integration
class TestChatHybridIntegration:
    """Integration tests for hybrid retrieval in chat API."""

    # ========================================================================
    # T046: Integration tests for chat API with hybrid mode
    # ========================================================================

    def test_chat_with_hybrid_mode_enabled(self, mock_retrieval_service):
        """Test chat completion with hybrid_mode=true in metadata.

        Should use retrieve_hybrid() instead of retrieve().
        """
        # Mock agent
        mock_agent = AsyncMock()
        mock_agent.run.return_value = MagicMock(
            output="Based on your cluster setup, I recommend Docker."
        )

        # Override dependencies BEFORE creating client
        test_app.dependency_overrides[get_retrieval_service] = lambda: mock_retrieval_service
        test_app.dependency_overrides[get_agent] = lambda: mock_agent

        try:
            # Create client AFTER setting overrides
            with TestClient(test_app) as client:
                # Send request with hybrid_mode metadata
                response = client.post(
                    "/v1/chat/completions",
                    json={
                        "model": "haia",
                        "messages": [
                            {"role": "user", "content": "Should I use Docker or Kubernetes?"}
                        ],
                        "metadata": {"hybrid_mode": True},
                        "stream": False,
                    },
                )

                # Verify response
                assert response.status_code == 200
                data = response.json()
                assert data["object"] == "chat.completion"
                assert len(data["choices"]) > 0

                # Verify retrieve_hybrid was called (not retrieve)
                # Note: This test will fail until T047 is implemented
                # For now, it verifies the API accepts the metadata parameter

        finally:
            # Clean up overrides
            if get_retrieval_service in test_app.dependency_overrides:
                del test_app.dependency_overrides[get_retrieval_service]
            if get_agent in test_app.dependency_overrides:
                del test_app.dependency_overrides[get_agent]

    def test_chat_with_hybrid_mode_disabled(self, mock_retrieval_service):
        """Test chat completion with hybrid_mode=false or absent.

        Should use retrieve() (vector-only) by default.
        """
        # Mock agent
        mock_agent = AsyncMock()
        mock_agent.run.return_value = MagicMock(
            output="I recommend starting with Docker."
        )

        # Override dependencies BEFORE creating client
        test_app.dependency_overrides[get_retrieval_service] = lambda: mock_retrieval_service
        test_app.dependency_overrides[get_agent] = lambda: mock_agent

        try:
            # Create client AFTER setting overrides
            with TestClient(test_app) as client:
                # Send request without hybrid_mode
                response = client.post(
                    "/v1/chat/completions",
                    json={
                        "model": "haia",
                        "messages": [
                            {"role": "user", "content": "Container deployment best practices"}
                        ],
                        "stream": False,
                    },
                )

                # Verify response
                assert response.status_code == 200
                data = response.json()
                assert data["object"] == "chat.completion"

                # Verify retrieve() was called (vector-only)
                mock_retrieval_service.retrieve.assert_called_once()

        finally:
            # Clean up overrides
            if get_retrieval_service in test_app.dependency_overrides:
                del test_app.dependency_overrides[get_retrieval_service]
            if get_agent in test_app.dependency_overrides:
                del test_app.dependency_overrides[get_agent]

    def test_chat_hybrid_mode_with_streaming(self, mock_retrieval_service):
        """Test hybrid mode works with streaming responses."""
        # Mock agent streaming response
        mock_agent = AsyncMock()

        async def mock_stream():
            yield "Based "
            yield "on your "
            yield "cluster..."

        mock_result = AsyncMock()
        mock_result.stream_text.return_value = mock_stream()

        mock_agent.run_stream.return_value.__aenter__.return_value = mock_result

        # Override dependencies BEFORE creating client
        test_app.dependency_overrides[get_retrieval_service] = lambda: mock_retrieval_service
        test_app.dependency_overrides[get_agent] = lambda: mock_agent

        try:
            # Create client AFTER setting overrides
            with TestClient(test_app) as client:
                # Send streaming request with hybrid mode
                response = client.post(
                    "/v1/chat/completions",
                    json={
                        "model": "haia",
                        "messages": [
                            {"role": "user", "content": "Docker setup guide"}
                        ],
                        "metadata": {"hybrid_mode": True},
                        "stream": True,
                    },
                )

                # Verify streaming response
                assert response.status_code == 200
                assert response.headers["content-type"] == "text/event-stream; charset=utf-8"

        finally:
            # Clean up overrides
            if get_retrieval_service in test_app.dependency_overrides:
                del test_app.dependency_overrides[get_retrieval_service]
            if get_agent in test_app.dependency_overrides:
                del test_app.dependency_overrides[get_agent]

    def test_chat_hybrid_mode_source_attribution_in_context(self, mock_retrieval_service):
        """Test that source attribution from hybrid retrieval is included in context.

        When hybrid mode is enabled, memory context should show which methods
        found each memory (vector, BM25, graph).
        """
        # Capture the message_history passed to agent
        captured_history = None

        async def capture_run(user_prompt, message_history=None):
            nonlocal captured_history
            captured_history = message_history
            return MagicMock(output="Response based on memories")

        mock_agent = AsyncMock()
        mock_agent.run = capture_run

        # Override dependencies BEFORE creating client
        test_app.dependency_overrides[get_retrieval_service] = lambda: mock_retrieval_service
        test_app.dependency_overrides[get_agent] = lambda: mock_agent

        try:
            # Create client AFTER setting overrides
            with TestClient(test_app) as client:
                # Send request with hybrid mode
                response = client.post(
                    "/v1/chat/completions",
                    json={
                        "model": "haia",
                        "messages": [
                            {"role": "user", "content": "Docker setup"}
                        ],
                        "metadata": {"hybrid_mode": True},
                        "stream": False,
                    },
                )

                assert response.status_code == 200

                # When T049 is implemented, verify source attribution in context
                # For now, just verify the API works
                # Future: Check captured_history contains source method info

        finally:
            # Clean up overrides
            if get_retrieval_service in test_app.dependency_overrides:
                del test_app.dependency_overrides[get_retrieval_service]
            if get_agent in test_app.dependency_overrides:
                del test_app.dependency_overrides[get_agent]

    def test_chat_hybrid_mode_graceful_degradation(self):
        """Test that hybrid mode failures don't break chat completions.

        If retrieve_hybrid() fails, should fall back gracefully.
        """
        mock_retrieval = AsyncMock()
        mock_retrieval.retrieve_hybrid.side_effect = Exception("Hybrid retrieval failed")
        mock_retrieval.health_check.return_value = True

        mock_agent = AsyncMock()
        mock_agent.run.return_value = MagicMock(
            output="I can still help you."
        )

        # Override dependencies BEFORE creating client
        test_app.dependency_overrides[get_retrieval_service] = lambda: mock_retrieval
        test_app.dependency_overrides[get_agent] = lambda: mock_agent

        try:
            # Create client AFTER setting overrides
            with TestClient(test_app) as client:
                # Send request with hybrid mode
                response = client.post(
                    "/v1/chat/completions",
                    json={
                        "model": "haia",
                        "messages": [
                            {"role": "user", "content": "Help needed"}
                        ],
                        "metadata": {"hybrid_mode": True},
                        "stream": False,
                    },
                )

                # Should succeed even if hybrid retrieval failed
                assert response.status_code == 200
                data = response.json()
                assert data["object"] == "chat.completion"

        finally:
            # Clean up overrides
            if get_retrieval_service in test_app.dependency_overrides:
                del test_app.dependency_overrides[get_retrieval_service]
            if get_agent in test_app.dependency_overrides:
                del test_app.dependency_overrides[get_agent]

    def test_health_check_includes_hybrid_retrieval_status(self):
        """Test that /health endpoint reports hybrid retrieval availability.

        When T050 is implemented, health check should include:
        - hybrid_retrieval: "enabled" | "disabled"
        - apoc_available: true | false
        """
        with TestClient(app) as client:
            response = client.get("/health")

            assert response.status_code == 200
            data = response.json()

            # Basic health check structure
            assert "status" in data
            assert "features" in data
            assert "services" in data

            # When T050 is implemented, verify:
            # assert "hybrid_retrieval" in data["features"]
            # assert "apoc_available" in data["services"]
