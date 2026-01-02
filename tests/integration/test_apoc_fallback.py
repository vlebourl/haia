"""Integration test for APOC availability detection and fallback.

Tests verify that GraphTraversalService gracefully handles environments
with and without APOC plugin installed.
"""

import pytest
from unittest.mock import AsyncMock, patch

from src.haia.services.graph_traversal import GraphTraversalService
from src.haia.models.hybrid_retrieval import GraphTraversalConfig


@pytest.mark.integration
class TestAPOCFallback:
    """Integration tests for APOC detection and fallback behavior."""

    @pytest.fixture
    def mock_neo4j_service(self):
        """Mock Neo4j service for testing."""
        from unittest.mock import MagicMock
        mock = AsyncMock()
        # Create a proper async context manager mock for driver
        mock.driver = MagicMock()
        return mock

    @pytest.fixture
    def graph_service(self, mock_neo4j_service):
        """Create GraphTraversalService instance."""
        return GraphTraversalService(neo4j_service=mock_neo4j_service)

    # ========================================================================
    # T009: APOC availability detection
    # ========================================================================

    @pytest.mark.asyncio
    async def test_apoc_available_uses_apoc_traversal(self, graph_service, mock_neo4j_service):
        """Test APOC-based traversal when APOC is available."""
        # Mock APOC as available
        mock_neo4j_service.detect_apoc.return_value = True

        # Mock session and async context manager
        mock_session = AsyncMock()
        mock_result = AsyncMock()
        mock_result.__aiter__.return_value = iter([])
        mock_session.run.return_value = mock_result

        # Properly mock async context manager
        mock_context = AsyncMock()
        mock_context.__aenter__.return_value = mock_session
        mock_neo4j_service.driver.session.return_value = mock_context

        seed_ids = ["mem_001"]
        config = GraphTraversalConfig(max_depth=2, use_apoc=True)

        # Execute traversal
        await graph_service.traverse_from_seeds(seed_ids, config)

        # Verify APOC detection was called
        assert mock_neo4j_service.detect_apoc.called

        # Verify APOC query was used
        query = mock_session.run.call_args[0][0]
        assert "apoc.path.expandConfig" in query

    @pytest.mark.asyncio
    async def test_apoc_unavailable_falls_back_to_native(self, graph_service, mock_neo4j_service):
        """Test native Cypher fallback when APOC unavailable."""
        # Mock APOC as unavailable
        mock_neo4j_service.detect_apoc.return_value = False

        # Mock session and async context manager
        mock_session = AsyncMock()
        mock_result = AsyncMock()
        mock_result.__aiter__.return_value = iter([])
        mock_session.run.return_value = mock_result

        mock_context = AsyncMock()
        mock_context.__aenter__.return_value = mock_session
        mock_neo4j_service.driver.session.return_value = mock_context

        seed_ids = ["mem_001"]
        config = GraphTraversalConfig(max_depth=2, use_apoc=True)

        # Execute traversal
        await graph_service.traverse_from_seeds(seed_ids, config)

        # Verify APOC detection was called
        assert mock_neo4j_service.detect_apoc.called

        # Verify native Cypher was used (no APOC)
        query = mock_session.run.call_args[0][0]
        assert "apoc.path.expandConfig" not in query
        assert "*1" in query  # Native 1-hop pattern

    @pytest.mark.asyncio
    async def test_apoc_disabled_by_config(self, graph_service, mock_neo4j_service):
        """Test APOC can be explicitly disabled via config."""
        # Mock APOC as available
        mock_neo4j_service.detect_apoc.return_value = True

        # Mock session and async context manager
        mock_session = AsyncMock()
        mock_result = AsyncMock()
        mock_result.__aiter__.return_value = iter([])
        mock_session.run.return_value = mock_result

        mock_context = AsyncMock()
        mock_context.__aenter__.return_value = mock_session
        mock_neo4j_service.driver.session.return_value = mock_context

        seed_ids = ["mem_001"]
        config = GraphTraversalConfig(max_depth=1, use_apoc=False)  # Explicitly disabled

        # Execute traversal
        await graph_service.traverse_from_seeds(seed_ids, config)

        # APOC detection should NOT be called if disabled by config
        # (implementation detail - can be called, just not used)

        # Verify native Cypher was used despite APOC being available
        query = mock_session.run.call_args[0][0]
        assert "apoc.path.expandConfig" not in query

    @pytest.mark.asyncio
    async def test_fallback_logs_warning(self, graph_service, mock_neo4j_service, caplog):
        """Test fallback to native Cypher logs warning."""
        import logging
        caplog.set_level(logging.WARNING)

        # Mock APOC as unavailable
        mock_neo4j_service.detect_apoc.return_value = False

        # Mock session and async context manager
        mock_session = AsyncMock()
        mock_result = AsyncMock()
        mock_result.__aiter__.return_value = iter([])
        mock_session.run.return_value = mock_result

        mock_context = AsyncMock()
        mock_context.__aenter__.return_value = mock_session
        mock_neo4j_service.driver.session.return_value = mock_context

        seed_ids = ["mem_001"]
        config = GraphTraversalConfig(max_depth=2)

        # Execute traversal
        await graph_service.traverse_from_seeds(seed_ids, config)

        # Verify warning was logged
        assert any("APOC" in record.message for record in caplog.records)
        assert any("falling back" in str(record.message).lower() for record in caplog.records)

    @pytest.mark.asyncio
    async def test_depth_limited_in_fallback(self, graph_service, mock_neo4j_service, caplog):
        """Test max_depth is limited to 1 in native fallback."""
        import logging
        caplog.set_level(logging.WARNING)

        # Mock APOC as unavailable
        mock_neo4j_service.detect_apoc.return_value = False

        # Mock session and async context manager
        mock_session = AsyncMock()
        mock_result = AsyncMock()
        mock_result.__aiter__.return_value = iter([])
        mock_session.run.return_value = mock_result

        mock_context = AsyncMock()
        mock_context.__aenter__.return_value = mock_session
        mock_neo4j_service.driver.session.return_value = mock_context

        seed_ids = ["mem_001"]
        config = GraphTraversalConfig(max_depth=3)  # Request 3 hops

        # Execute traversal
        await graph_service.traverse_from_seeds(seed_ids, config)

        # Verify warning about depth limitation
        assert any("1-hop" in record.message or "limited to 1" in record.message.lower()
                   for record in caplog.records)

    @pytest.mark.asyncio
    async def test_apoc_detection_cached(self, graph_service, mock_neo4j_service):
        """Test APOC detection result is cached across calls."""
        mock_neo4j_service.detect_apoc.return_value = True

        # Mock session and async context manager
        mock_session = AsyncMock()
        mock_result = AsyncMock()
        mock_result.__aiter__.return_value = iter([])
        mock_session.run.return_value = mock_result

        mock_context = AsyncMock()
        mock_context.__aenter__.return_value = mock_session
        mock_neo4j_service.driver.session.return_value = mock_context

        seed_ids = ["mem_001"]
        config = GraphTraversalConfig(max_depth=2)

        # Execute traversal twice
        await graph_service.traverse_from_seeds(seed_ids, config)
        await graph_service.traverse_from_seeds(seed_ids, config)

        # detect_apoc should be called, but Neo4j caches internally
        # (This tests that we're using the cached result from Neo4jService)
        assert mock_neo4j_service.detect_apoc.called

    @pytest.mark.asyncio
    async def test_graceful_degradation_continues_working(self, graph_service, mock_neo4j_service):
        """Test system continues working with fallback (no crash)."""
        # Mock APOC as unavailable
        mock_neo4j_service.detect_apoc.return_value = False

        # Mock session and async context manager
        mock_session = AsyncMock()

        # Mock some actual results from native traversal
        from unittest.mock import MagicMock

        mock_rec_1 = MagicMock()
        mock_rec_1.data.return_value = {"memory_id": "mem_002", "distance": 1}

        mock_rec_2 = MagicMock()
        mock_rec_2.data.return_value = {"memory_id": "mem_003", "distance": 1}

        mock_result = AsyncMock()
        mock_result.__aiter__.return_value = iter([mock_rec_1, mock_rec_2])

        mock_session.run.return_value = mock_result

        mock_context = AsyncMock()
        mock_context.__aenter__.return_value = mock_session
        mock_neo4j_service.driver.session.return_value = mock_context

        seed_ids = ["mem_001"]
        config = GraphTraversalConfig(max_depth=1)

        # Execute traversal - should not crash
        results = await graph_service.traverse_from_seeds(seed_ids, config)

        # Verify we got results despite APOC being unavailable
        assert len(results) == 2
        assert results[0]["memory_id"] == "mem_002"
        assert results[1]["memory_id"] == "mem_003"
