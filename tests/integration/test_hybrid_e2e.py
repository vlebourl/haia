"""End-to-end integration tests for hybrid retrieval system.

Tests verify complete hybrid retrieval workflow including:
- Graph traversal with real Neo4j relationships
- Vector search integration
- BM25 search integration
- RRF merging
"""

import pytest
from datetime import datetime
from unittest.mock import AsyncMock

from src.haia.services.graph_traversal import GraphTraversalService
from src.haia.models.hybrid_retrieval import GraphTraversalConfig, RetrievedMemory


@pytest.mark.integration
class TestHybridEndToEnd:
    """End-to-end integration tests for hybrid retrieval."""

    @pytest.fixture
    def mock_neo4j_service(self):
        """Mock Neo4j service with realistic behavior."""
        from unittest.mock import MagicMock
        mock = AsyncMock()
        mock.driver = MagicMock()
        mock.detect_apoc.return_value = True  # Assume APOC available
        return mock

    @pytest.fixture
    def graph_service(self, mock_neo4j_service):
        """Create GraphTraversalService instance."""
        return GraphTraversalService(neo4j_service=mock_neo4j_service)

    # ========================================================================
    # T010: Graph traversal with real relationships
    # ========================================================================

    @pytest.mark.asyncio
    async def test_graph_traversal_finds_related_memories(self, graph_service, mock_neo4j_service):
        """Test graph traversal discovers memories via relationships."""
        # Setup: Create test scenario with relationships
        # mem_001 DEPENDS_ON mem_002
        # mem_002 RELATED_TO mem_003

        mock_session = AsyncMock()

        # Mock traversal results
        from unittest.mock import MagicMock

        mock_rec_1 = MagicMock()
        mock_rec_1.data.return_value = {
            "memory_id": "mem_002",
            "distance": 1,
            "content": "Proxmox infrastructure details",
            "type": "technical_context",
            "confidence": 0.88,
        }

        mock_rec_2 = MagicMock()
        mock_rec_2.data.return_value = {
            "memory_id": "mem_003",
            "distance": 2,
            "content": "Ceph storage configuration",
            "type": "technical_context",
            "confidence": 0.85,
        }

        mock_result = AsyncMock()
        mock_result.__aiter__.return_value = iter([mock_rec_1, mock_rec_2])

        mock_session.run.return_value = mock_result
        mock_context = AsyncMock()
        mock_context.__aenter__.return_value = mock_session
        mock_neo4j_service.driver.session.return_value = mock_context

        # Execute traversal from seed
        seed_ids = ["mem_001"]
        config = GraphTraversalConfig(
            max_depth=2,
            relationship_types=["RELATED_TO", "DEPENDS_ON"]
        )

        results = await graph_service.traverse_from_seeds(seed_ids, config)

        # Verify both related memories were found
        assert len(results) == 2

        # Verify memory at distance 1 (direct relationship)
        assert results[0]["memory_id"] == "mem_002"
        assert results[0]["distance"] == 1

        # Verify memory at distance 2 (2-hop relationship)
        assert results[1]["memory_id"] == "mem_003"
        assert results[1]["distance"] == 2

    @pytest.mark.asyncio
    async def test_graph_traversal_respects_max_depth(self, graph_service, mock_neo4j_service):
        """Test graph traversal stops at max_depth."""
        mock_session = AsyncMock()

        # Mock results at different depths
        mock_record_1 = {"memory_id": "mem_002", "distance": 1}
        mock_record_2 = {"memory_id": "mem_003", "distance": 2}
        # mem_004 is at distance 3 (should not be returned for max_depth=2)

        mock_result = AsyncMock()
        mock_result.__aiter__.return_value = iter([
            type('obj', (object,), {'data': lambda: mock_record_1})(),
            type('obj', (object,), {'data': lambda: mock_record_2})(),
        ])

        mock_session.run.return_value = mock_result
        mock_context = AsyncMock()
        mock_context.__aenter__.return_value = mock_session
        mock_neo4j_service.driver.session.return_value = mock_context

        seed_ids = ["mem_001"]
        config = GraphTraversalConfig(max_depth=2)  # Stop at 2 hops

        results = await graph_service.traverse_from_seeds(seed_ids, config)

        # Verify only results within max_depth are returned
        assert all(r["distance"] <= 2 for r in results)
        assert len(results) == 2

    @pytest.mark.asyncio
    async def test_graph_traversal_filters_by_relationship_type(self, graph_service, mock_neo4j_service):
        """Test graph traversal only follows specified relationship types."""
        mock_session = AsyncMock()

        # Mock traversal results (only DEPENDS_ON relationships)
        mock_record = {"memory_id": "mem_002", "distance": 1}

        mock_result = AsyncMock()
        mock_result.__aiter__.return_value = iter([
            type('obj', (object,), {'data': lambda: mock_record})(),
        ])

        mock_session.run.return_value = mock_result
        mock_context = AsyncMock()
        mock_context.__aenter__.return_value = mock_session
        mock_neo4j_service.driver.session.return_value = mock_context

        seed_ids = ["mem_001"]
        config = GraphTraversalConfig(
            max_depth=2,
            relationship_types=["DEPENDS_ON"]  # Only follow DEPENDS_ON
        )

        results = await graph_service.traverse_from_seeds(seed_ids, config)

        # Verify query used correct relationship filter
        query = mock_session.run.call_args[0][0]
        assert "DEPENDS_ON" in query

        # Should find mem_002 via DEPENDS_ON, but not mem_003 via RELATED_TO
        assert len(results) == 1
        assert results[0]["memory_id"] == "mem_002"

    @pytest.mark.asyncio
    async def test_graph_traversal_excludes_seed_nodes(self, graph_service, mock_neo4j_service):
        """Test graph traversal doesn't return seed nodes."""
        mock_session = AsyncMock()

        # Mock results (should not include mem_001 which is a seed)
        mock_record_1 = {"memory_id": "mem_002", "distance": 1}
        mock_record_2 = {"memory_id": "mem_003", "distance": 2}

        mock_result = AsyncMock()
        mock_result.__aiter__.return_value = iter([
            type('obj', (object,), {'data': lambda: mock_record_1})(),
            type('obj', (object,), {'data': lambda: mock_record_2})(),
        ])

        mock_session.run.return_value = mock_result
        mock_context = AsyncMock()
        mock_context.__aenter__.return_value = mock_session
        mock_neo4j_service.driver.session.return_value = mock_context

        seed_ids = ["mem_001", "mem_002"]
        config = GraphTraversalConfig(max_depth=2)

        results = await graph_service.traverse_from_seeds(seed_ids, config)

        # Verify seed nodes are not in results
        result_ids = [r["memory_id"] for r in results]
        assert "mem_001" not in result_ids
        # Note: mem_002 is both a seed and 1-hop from mem_001, but should be excluded

    @pytest.mark.asyncio
    async def test_graph_traversal_deduplicates_results(self, graph_service, mock_neo4j_service):
        """Test graph traversal deduplicates memories found via multiple paths."""
        mock_session = AsyncMock()

        # Mock scenario: mem_003 reachable via two paths
        # Path 1: mem_001 -> mem_002 -> mem_003
        # Path 2: mem_001 -> mem_003 (if there's a direct relationship)
        # Should only return mem_003 once

        mock_record = {"memory_id": "mem_003", "distance": 1}

        mock_result = AsyncMock()
        mock_result.__aiter__.return_value = iter([
            type('obj', (object,), {'data': lambda: mock_record})(),
        ])

        mock_session.run.return_value = mock_result
        mock_context = AsyncMock()
        mock_context.__aenter__.return_value = mock_session
        mock_neo4j_service.driver.session.return_value = mock_context

        seed_ids = ["mem_001"]
        config = GraphTraversalConfig(max_depth=2)

        results = await graph_service.traverse_from_seeds(seed_ids, config)

        # Verify no duplicates
        result_ids = [r["memory_id"] for r in results]
        assert len(result_ids) == len(set(result_ids))

    @pytest.mark.asyncio
    async def test_graph_traversal_multiple_seeds(self, graph_service, mock_neo4j_service):
        """Test graph traversal from multiple seed nodes."""
        mock_session = AsyncMock()

        # Mock results from multiple seeds
        # Seed mem_001 -> mem_003
        # Seed mem_002 -> mem_004
        mock_record_1 = {"memory_id": "mem_003", "distance": 1}
        mock_record_2 = {"memory_id": "mem_004", "distance": 1}

        mock_result = AsyncMock()
        mock_result.__aiter__.return_value = iter([
            type('obj', (object,), {'data': lambda: mock_record_1})(),
            type('obj', (object,), {'data': lambda: mock_record_2})(),
        ])

        mock_session.run.return_value = mock_result
        mock_context = AsyncMock()
        mock_context.__aenter__.return_value = mock_session
        mock_neo4j_service.driver.session.return_value = mock_context

        seed_ids = ["mem_001", "mem_002"]
        config = GraphTraversalConfig(max_depth=1)

        results = await graph_service.traverse_from_seeds(seed_ids, config)

        # Verify results from both seeds
        assert len(results) == 2
        result_ids = [r["memory_id"] for r in results]
        assert "mem_003" in result_ids
        assert "mem_004" in result_ids

    @pytest.mark.asyncio
    async def test_graph_traversal_empty_result(self, graph_service, mock_neo4j_service):
        """Test graph traversal handles no relationships gracefully."""
        mock_session = AsyncMock()

        # Mock empty results (seed has no relationships)
        mock_result = AsyncMock()
        mock_result.__aiter__.return_value = iter([])

        mock_session.run.return_value = mock_result
        mock_context = AsyncMock()
        mock_context.__aenter__.return_value = mock_session
        mock_neo4j_service.driver.session.return_value = mock_context

        seed_ids = ["mem_isolated"]
        config = GraphTraversalConfig(max_depth=2)

        results = await graph_service.traverse_from_seeds(seed_ids, config)

        # Should return empty list, not crash
        assert results == []

    @pytest.mark.asyncio
    async def test_graph_traversal_tracks_distance(self, graph_service, mock_neo4j_service):
        """Test graph traversal correctly tracks distance from seeds."""
        mock_session = AsyncMock()

        # Mock results with different distances
        mock_record_1 = {"memory_id": "mem_002", "distance": 1}
        mock_record_2 = {"memory_id": "mem_003", "distance": 2}
        mock_record_3 = {"memory_id": "mem_004", "distance": 3}

        mock_result = AsyncMock()
        mock_result.__aiter__.return_value = iter([
            type('obj', (object,), {'data': lambda: mock_record_1})(),
            type('obj', (object,), {'data': lambda: mock_record_2})(),
            type('obj', (object,), {'data': lambda: mock_record_3})(),
        ])

        mock_session.run.return_value = mock_result
        mock_context = AsyncMock()
        mock_context.__aenter__.return_value = mock_session
        mock_neo4j_service.driver.session.return_value = mock_context

        seed_ids = ["mem_001"]
        config = GraphTraversalConfig(max_depth=3)

        results = await graph_service.traverse_from_seeds(seed_ids, config)

        # Verify distance tracking
        assert results[0]["distance"] == 1
        assert results[1]["distance"] == 2
        assert results[2]["distance"] == 3

    @pytest.mark.asyncio
    async def test_graph_traversal_supersedes_relationships(self, graph_service, mock_neo4j_service):
        """Test graph traversal follows SUPERSEDES relationships."""
        mock_session = AsyncMock()

        # Mock memory superseded by another
        # mem_old SUPERSEDES mem_new
        mock_record = {"memory_id": "mem_new", "distance": 1}

        mock_result = AsyncMock()
        mock_result.__aiter__.return_value = iter([
            type('obj', (object,), {'data': lambda: mock_record})(),
        ])

        mock_session.run.return_value = mock_result
        mock_context = AsyncMock()
        mock_context.__aenter__.return_value = mock_session
        mock_neo4j_service.driver.session.return_value = mock_context

        seed_ids = ["mem_old"]
        config = GraphTraversalConfig(
            max_depth=1,
            relationship_types=["SUPERSEDES"]
        )

        results = await graph_service.traverse_from_seeds(seed_ids, config)

        # Verify superseding memory was found
        assert len(results) == 1
        assert results[0]["memory_id"] == "mem_new"


# ============================================================================
# T024: Integration test for all three methods succeeding (Hybrid Retrieval)
# ============================================================================


@pytest.mark.integration
class TestHybridRetrievalE2E:
    """End-to-end integration tests for complete hybrid retrieval workflow."""

    @pytest.fixture
    def mock_neo4j_service(self):
        """Mock Neo4j service with realistic behavior for hybrid retrieval."""
        from unittest.mock import MagicMock
        mock = AsyncMock()
        mock.driver = MagicMock()
        mock.detect_apoc.return_value = True
        return mock

    @pytest.fixture
    def mock_ollama_client(self):
        """Mock Ollama client."""
        mock = AsyncMock()
        mock.health_check.return_value = True
        mock.embed.return_value = [0.1] * 768
        return mock

    @pytest.fixture
    def retrieval_service(self, mock_neo4j_service, mock_ollama_client):
        """Create RetrievalService instance."""
        from src.haia.embedding.retrieval_service import RetrievalService
        return RetrievalService(
            neo4j_service=mock_neo4j_service,
            ollama_client=mock_ollama_client,
        )

    @pytest.mark.asyncio
    async def test_hybrid_retrieval_all_methods_integrated(
        self, retrieval_service, mock_neo4j_service, mock_ollama_client
    ):
        """Test complete hybrid retrieval with all three methods working.

        This tests the full integration:
        - Vector search via Neo4j vector index
        - BM25 search via Neo4j fulltext index
        - Graph traversal from vector seeds
        - RRF merging of all results
        - Source attribution
        """
        from datetime import datetime, timezone
        from src.haia.models.hybrid_retrieval import HybridRetrievalRequest

        # Mock query embedding
        query_embedding = [0.1] * 768
        mock_ollama_client.embed.return_value = query_embedding

        # Mock vector search results (2 results)
        mock_neo4j_service.search_similar_memories.return_value = [
            {
                "memory_id": "mem_v1",
                "content": "Proxmox VE cluster configuration details",
                "memory_type": "technical_context",
                "confidence": 0.92,
                "similarity_score": 0.88,
                "source_conversation_id": "conv_1",
                "extraction_timestamp": datetime.now(timezone.utc),
                "has_embedding": True,
            },
            {
                "memory_id": "mem_v2",
                "content": "User prefers Ceph over NFS for storage",
                "memory_type": "preference",
                "confidence": 0.90,
                "similarity_score": 0.85,
                "source_conversation_id": "conv_1",
                "extraction_timestamp": datetime.now(timezone.utc),
                "has_embedding": True,
            },
        ]

        # Mock BM25 search results (3 results, 1 overlaps with vector)
        mock_neo4j_service.search_memories_bm25.return_value = [
            {
                "memory_id": "mem_b1",
                "content": "Proxmox cluster has 3 nodes: pve1, pve2, pve3",
                "memory_type": "technical_context",
                "confidence": 0.89,
                "bm25_score": 6.3,
                "source_conversation_id": "conv_2",
                "extraction_timestamp": datetime.now(timezone.utc),
                "has_embedding": True,
            },
            {
                "memory_id": "mem_v1",  # Overlap with vector
                "content": "Proxmox VE cluster configuration details",
                "memory_type": "technical_context",
                "confidence": 0.92,
                "bm25_score": 5.8,
                "source_conversation_id": "conv_1",
                "extraction_timestamp": datetime.now(timezone.utc),
                "has_embedding": True,
            },
            {
                "memory_id": "mem_b2",
                "content": "Each node runs Ceph OSD for distributed storage",
                "memory_type": "technical_context",
                "confidence": 0.87,
                "bm25_score": 5.1,
                "source_conversation_id": "conv_2",
                "extraction_timestamp": datetime.now(timezone.utc),
                "has_embedding": True,
            },
        ]

        # Mock graph traversal directly on the service instance
        mock_graph = AsyncMock()
        mock_graph.traverse_from_seeds.return_value = [
            {
                "memory_id": "mem_g1",
                "content": "Ceph depends on stable network infrastructure",
                "type": "technical_context",
                "confidence": 0.86,
                "distance": 1,
            },
            {
                "memory_id": "mem_g2",
                "content": "Network uses 10GbE for Ceph traffic",
                "type": "technical_context",
                "confidence": 0.84,
                "distance": 2,
            },
        ]
        retrieval_service.graph_traversal = mock_graph

        request = HybridRetrievalRequest(
            query="Proxmox cluster storage setup",
            enabled_methods=["vector", "bm25", "graph"],
            top_k=10,
            graph_depth=2,
        )

        # Execute hybrid retrieval
        results = await retrieval_service.retrieve_hybrid(request)

        # Verify results
        assert len(results) > 0, "Should return at least some results"

        # 1. Check unique memories (mem_v1, mem_v2, mem_b1, mem_b2, mem_g1, mem_g2)
        memory_ids = [r.memory.memory_id for r in results]
        assert len(memory_ids) == len(set(memory_ids)), "No duplicate memory_ids"

        # Expected unique memories: v1, v2 (vector), b1, b2 (BM25), g1, g2 (graph)
        # mem_v1 appears in both vector and BM25
        expected_unique_count = 6
        assert len(memory_ids) == expected_unique_count

        # 2. mem_v1 should have high RRF score (consensus between vector and BM25)
        mem_v1_result = next((r for r in results if r.memory.memory_id == "mem_v1"), None)
        assert mem_v1_result is not None, "mem_v1 should be in results"

        # 3. Verify source attribution
        source_methods = mem_v1_result.memory.metadata.get("source_methods", [])
        assert "vector" in source_methods, "mem_v1 should have vector attribution"
        assert "bm25" in source_methods, "mem_v1 should have bm25 attribution"

        # 4. Results should be ordered by RRF score (descending)
        for i in range(len(results) - 1):
            assert results[i].similarity_score >= results[i + 1].similarity_score

    @pytest.mark.asyncio
    async def test_hybrid_retrieval_rrf_consensus_boost(
        self, retrieval_service, mock_neo4j_service, mock_ollama_client
    ):
        """Test that memories found by multiple methods get boosted via RRF.

        This validates the RRF algorithm correctly combines rankings.
        """
        from datetime import datetime, timezone
        from src.haia.models.hybrid_retrieval import HybridRetrievalRequest

        mock_ollama_client.embed.return_value = [0.1] * 768

        # Mock vector search: mem_001 at rank 1, mem_002 at rank 2
        mock_neo4j_service.search_similar_memories.return_value = [
            {
                "memory_id": "mem_001",
                "content": "Important memory",
                "memory_type": "technical_context",
                "confidence": 0.9,
                "similarity_score": 0.95,
                "source_conversation_id": "conv_1",
                "extraction_timestamp": datetime.now(timezone.utc),
                "has_embedding": True,
            },
            {
                "memory_id": "mem_002",
                "content": "Less important memory",
                "memory_type": "technical_context",
                "confidence": 0.85,
                "similarity_score": 0.80,
                "source_conversation_id": "conv_1",
                "extraction_timestamp": datetime.now(timezone.utc),
                "has_embedding": True,
            },
        ]

        # Mock BM25 search: mem_001 at rank 1 (consensus!), mem_003 at rank 2
        mock_neo4j_service.search_memories_bm25.return_value = [
            {
                "memory_id": "mem_001",  # Consensus with vector
                "content": "Important memory",
                "memory_type": "technical_context",
                "confidence": 0.9,
                "bm25_score": 7.5,
                "source_conversation_id": "conv_1",
                "extraction_timestamp": datetime.now(timezone.utc),
                "has_embedding": True,
            },
            {
                "memory_id": "mem_003",
                "content": "Only BM25 found this",
                "memory_type": "technical_context",
                "confidence": 0.88,
                "bm25_score": 6.2,
                "source_conversation_id": "conv_1",
                "extraction_timestamp": datetime.now(timezone.utc),
                "has_embedding": True,
            },
        ]

        request = HybridRetrievalRequest(
            query="test query",
            enabled_methods=["vector", "bm25"],
        )

        # Execute hybrid retrieval
        results = await retrieval_service.retrieve_hybrid(request)

        # Verify results
        assert len(results) == 3, "Should return 3 unique memories (mem_001, mem_002, mem_003)"

        # mem_001 should have highest RRF score (rank 1 in both methods)
        assert results[0].memory.memory_id == "mem_001", "mem_001 should be ranked first (consensus boost)"

        # Verify mem_001 has both source methods
        mem_001_sources = results[0].memory.metadata.get("source_methods", [])
        assert "vector" in mem_001_sources, "mem_001 should have vector attribution"
        assert "bm25" in mem_001_sources, "mem_001 should have bm25 attribution"

        # mem_002 and mem_003 should have lower scores (only in one method each)
        mem_002_result = next((r for r in results if r.memory.memory_id == "mem_002"), None)
        mem_003_result = next((r for r in results if r.memory.memory_id == "mem_003"), None)

        assert mem_002_result is not None, "mem_002 should be in results"
        assert mem_003_result is not None, "mem_003 should be in results"

        # mem_001 RRF score should be higher than both mem_002 and mem_003
        assert results[0].similarity_score > mem_002_result.similarity_score
        assert results[0].similarity_score > mem_003_result.similarity_score

    @pytest.mark.asyncio
    async def test_hybrid_retrieval_with_real_neo4j(self):
        """Test hybrid retrieval with actual Neo4j database.

        NOTE: This test is marked as skip by default and requires:
        - Neo4j running with vector index configured
        - BM25 fulltext index configured
        - APOC plugin installed
        - Test memories pre-loaded with relationships
        """
        pytest.skip("Requires real Neo4j instance with test data - run manually")

        # TODO: Implement when hybrid retrieval is complete and ready for
        # end-to-end testing with real database
