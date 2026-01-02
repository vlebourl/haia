"""Unit tests for GraphTraversalService.

Tests cover:
- APOC traversal query generation (apoc.path.expandConfig)
- Native Cypher fallback (1-hop variable-length pattern)
- Cycle detection logic
- Distance tracking
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime

from src.haia.services.graph_traversal import GraphTraversalService
from src.haia.models.hybrid_retrieval import GraphTraversalConfig


class TestGraphTraversalService:
    """Test suite for GraphTraversalService."""

    @pytest.fixture
    def mock_neo4j_service(self):
        """Mock Neo4j service for testing."""
        mock = AsyncMock()
        mock.driver = MagicMock()
        return mock

    @pytest.fixture
    def graph_service(self, mock_neo4j_service):
        """Create GraphTraversalService with mocked dependencies."""
        return GraphTraversalService(neo4j_service=mock_neo4j_service)

    # ========================================================================
    # T007: Unit test for APOC traversal
    # ========================================================================

    @pytest.mark.asyncio
    async def test_apoc_query_generation_2_hops(self, graph_service, mock_neo4j_service):
        """Test APOC query generation for 2-hop traversal."""
        # Configure APOC as available
        mock_neo4j_service.detect_apoc.return_value = True

        # Mock session and result
        mock_session = AsyncMock()
        mock_result = AsyncMock()
        mock_result.__aiter__.return_value = iter([])  # Empty results for now
        mock_session.run.return_value = mock_result
        mock_neo4j_service.driver.session.return_value.__aenter__.return_value = mock_session

        # Call traverse method
        seed_ids = ["mem_001", "mem_002"]
        config = GraphTraversalConfig(max_depth=2, relationship_types=["RELATED_TO", "DEPENDS_ON"])

        await graph_service.traverse_from_seeds(seed_ids, config)

        # Verify APOC query was called
        assert mock_session.run.called
        call_args = mock_session.run.call_args

        # Extract query from call
        query = call_args[0][0]

        # Verify APOC query structure
        assert "apoc.path.expandConfig" in query
        assert "NODE_GLOBAL" in query  # Uniqueness mode
        assert "minLevel: 1" in query
        assert "maxLevel: $max_depth" in query
        assert "relationshipFilter: $rel_filter" in query

        # Verify relationship filter parameter was passed correctly
        call_kwargs = call_args[1]
        assert call_kwargs["rel_filter"] == "RELATED_TO|DEPENDS_ON"

    @pytest.mark.asyncio
    async def test_apoc_cycle_detection(self, graph_service, mock_neo4j_service):
        """Test APOC uniqueness prevents cycles."""
        mock_neo4j_service.detect_apoc.return_value = True

        mock_session = AsyncMock()
        mock_result = AsyncMock()
        mock_result.__aiter__.return_value = iter([])
        mock_session.run.return_value = mock_result
        mock_neo4j_service.driver.session.return_value.__aenter__.return_value = mock_session

        seed_ids = ["mem_001"]
        config = GraphTraversalConfig(max_depth=3, cycle_detection=True)

        await graph_service.traverse_from_seeds(seed_ids, config)

        # Verify NODE_GLOBAL uniqueness is used (prevents cycles)
        query = mock_session.run.call_args[0][0]
        assert "NODE_GLOBAL" in query

    @pytest.mark.asyncio
    async def test_apoc_bfs_traversal(self, graph_service, mock_neo4j_service):
        """Test APOC uses breadth-first search."""
        mock_neo4j_service.detect_apoc.return_value = True

        mock_session = AsyncMock()
        mock_result = AsyncMock()
        mock_result.__aiter__.return_value = iter([])
        mock_session.run.return_value = mock_result
        mock_neo4j_service.driver.session.return_value.__aenter__.return_value = mock_session

        seed_ids = ["mem_001"]
        config = GraphTraversalConfig(max_depth=2)

        await graph_service.traverse_from_seeds(seed_ids, config)

        query = mock_session.run.call_args[0][0]
        assert "bfs: true" in query

    # ========================================================================
    # T008: Unit test for native Cypher fallback
    # ========================================================================

    @pytest.mark.asyncio
    async def test_native_cypher_fallback_1_hop(self, graph_service, mock_neo4j_service):
        """Test native Cypher fallback uses 1-hop pattern."""
        # Configure APOC as unavailable
        mock_neo4j_service.detect_apoc.return_value = False

        mock_session = AsyncMock()
        mock_result = AsyncMock()
        mock_result.__aiter__.return_value = iter([])
        mock_session.run.return_value = mock_result
        mock_neo4j_service.driver.session.return_value.__aenter__.return_value = mock_session

        seed_ids = ["mem_001"]
        config = GraphTraversalConfig(max_depth=2)  # Requested 2, should fallback to 1

        await graph_service.traverse_from_seeds(seed_ids, config)

        # Verify native Cypher query was used
        query = mock_session.run.call_args[0][0]
        assert "apoc.path.expandConfig" not in query
        assert "*1" in query or "*1]" in query  # Variable-length 1-hop

    @pytest.mark.asyncio
    async def test_native_cypher_relationship_filter(self, graph_service, mock_neo4j_service):
        """Test native Cypher applies relationship type filter."""
        mock_neo4j_service.detect_apoc.return_value = False

        mock_session = AsyncMock()
        mock_result = AsyncMock()
        mock_result.__aiter__.return_value = iter([])
        mock_session.run.return_value = mock_result
        mock_neo4j_service.driver.session.return_value.__aenter__.return_value = mock_session

        seed_ids = ["mem_001"]
        config = GraphTraversalConfig(
            max_depth=1,
            relationship_types=["RELATED_TO", "DEPENDS_ON", "SUPERSEDES"]
        )

        await graph_service.traverse_from_seeds(seed_ids, config)

        query = mock_session.run.call_args[0][0]
        # Should include relationship type filter
        assert "RELATED_TO" in query
        assert "DEPENDS_ON" in query
        assert "SUPERSEDES" in query

    @pytest.mark.asyncio
    async def test_native_cypher_excludes_seeds(self, graph_service, mock_neo4j_service):
        """Test native Cypher excludes seed nodes from results."""
        mock_neo4j_service.detect_apoc.return_value = False

        mock_session = AsyncMock()
        mock_result = AsyncMock()
        mock_result.__aiter__.return_value = iter([])
        mock_session.run.return_value = mock_result
        mock_neo4j_service.driver.session.return_value.__aenter__.return_value = mock_session

        seed_ids = ["mem_001", "mem_002"]
        config = GraphTraversalConfig(max_depth=1)

        await graph_service.traverse_from_seeds(seed_ids, config)

        query = mock_session.run.call_args[0][0]
        # Should exclude seed nodes
        assert "WHERE" in query or "where" in query

    @pytest.mark.asyncio
    async def test_native_cypher_limits_results(self, graph_service, mock_neo4j_service):
        """Test native Cypher limits results for performance."""
        mock_neo4j_service.detect_apoc.return_value = False

        mock_session = AsyncMock()
        mock_result = AsyncMock()
        mock_result.__aiter__.return_value = iter([])
        mock_session.run.return_value = mock_result
        mock_neo4j_service.driver.session.return_value.__aenter__.return_value = mock_session

        seed_ids = ["mem_001"]
        config = GraphTraversalConfig(max_depth=1)

        await graph_service.traverse_from_seeds(seed_ids, config)

        query = mock_session.run.call_args[0][0]
        assert "LIMIT" in query

    # ========================================================================
    # Edge Cases
    # ========================================================================

    @pytest.mark.asyncio
    async def test_empty_seed_list(self, graph_service):
        """Test graceful handling of empty seed list."""
        config = GraphTraversalConfig(max_depth=2)
        results = await graph_service.traverse_from_seeds([], config)

        assert results == []

    @pytest.mark.asyncio
    async def test_max_depth_validation(self, graph_service):
        """Test max_depth is validated (1-3 range)."""
        # max_depth=3 should work
        config = GraphTraversalConfig(max_depth=3)
        assert config.max_depth == 3

        # max_depth > 3 should be caught by Pydantic
        with pytest.raises(Exception):  # Pydantic validation error
            GraphTraversalConfig(max_depth=4)

        # max_depth < 1 should be caught by Pydantic
        with pytest.raises(Exception):
            GraphTraversalConfig(max_depth=0)

    @pytest.mark.asyncio
    async def test_custom_relationship_types(self, graph_service, mock_neo4j_service):
        """Test custom relationship types are applied."""
        mock_neo4j_service.detect_apoc.return_value = True

        mock_session = AsyncMock()
        mock_result = AsyncMock()
        mock_result.__aiter__.return_value = iter([])
        mock_session.run.return_value = mock_result
        mock_neo4j_service.driver.session.return_value.__aenter__.return_value = mock_session

        seed_ids = ["mem_001"]
        config = GraphTraversalConfig(
            max_depth=2,
            relationship_types=["CUSTOM_REL_1", "CUSTOM_REL_2"]
        )

        await graph_service.traverse_from_seeds(seed_ids, config)

        # Verify relationship filter parameter contains custom types
        call_kwargs = mock_session.run.call_args[1]
        assert call_kwargs["rel_filter"] == "CUSTOM_REL_1|CUSTOM_REL_2"
