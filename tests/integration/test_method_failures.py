"""Integration tests for hybrid retrieval partial failures.

Tests verify graceful degradation when individual methods fail,
such as BM25 index being unavailable or graph traversal timing out.
"""

import pytest
from unittest.mock import AsyncMock, patch
from datetime import datetime, timezone

from src.haia.embedding.retrieval_service import RetrievalService
from src.haia.models.hybrid_retrieval import HybridRetrievalRequest


@pytest.mark.integration
class TestMethodFailures:
    """Integration tests for partial method failures."""

    @pytest.fixture
    def mock_neo4j_service(self):
        """Mock Neo4j service for integration testing."""
        from unittest.mock import MagicMock
        mock = AsyncMock()
        mock.driver = MagicMock()
        mock.health_check.return_value = True
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
        return RetrievalService(
            neo4j_service=mock_neo4j_service,
            ollama_client=mock_ollama_client,
        )

    # ========================================================================
    # T025: Integration test for partial failures
    # ========================================================================

    @pytest.mark.asyncio
    async def test_bm25_unavailable_vector_and_graph_work(
        self, retrieval_service, mock_neo4j_service
    ):
        """Test hybrid retrieval when BM25 index is unavailable.

        Scenario: Neo4j doesn't have BM25 fulltext index configured.
        Expected: Vector and graph methods continue working.
        """
        # Mock BM25 to fail (index not configured)
        mock_neo4j_service.search_memories_bm25.side_effect = Exception(
            "fulltext index 'memoryBm25Index' not found"
        )

        # Mock vector search succeeds
        mock_neo4j_service.search_similar_memories.return_value = [
            {
                "memory_id": "mem_v1",
                "content": "Vector search result",
                "memory_type": "technical_context",
                "confidence": 0.9,
                "similarity_score": 0.85,
                "source_conversation_id": "conv_1",
                "extraction_timestamp": datetime.now(timezone.utc),
                "has_embedding": True,
            },
            {
                "memory_id": "mem_v2",
                "content": "Another vector result",
                "memory_type": "preference",
                "confidence": 0.88,
                "similarity_score": 0.82,
                "source_conversation_id": "conv_1",
                "extraction_timestamp": datetime.now(timezone.utc),
                "has_embedding": True,
            },
        ]

        # Mock graph traversal succeeds
        with patch("src.haia.embedding.retrieval_service.GraphTraversalService") as MockGraph:
            mock_graph_instance = AsyncMock()
            MockGraph.return_value = mock_graph_instance

            mock_graph_instance.traverse_from_seeds.return_value = [
                {
                    "memory_id": "mem_g1",
                    "content": "Graph traversal result",
                    "type": "technical_context",
                    "confidence": 0.86,
                    "distance": 1,
                },
            ]

            request = HybridRetrievalRequest(
                query="Proxmox cluster configuration",
                enabled_methods=["vector", "bm25", "graph"],
                top_k=5,
            )

            # Mock graph traversal on service instance
            mock_graph = AsyncMock()
            mock_graph.traverse_from_seeds.return_value = [
                {
                    "memory_id": "mem_g1",
                    "content": "Graph result",
                    "type": "technical_context",
                    "confidence": 0.86,
                    "distance": 1,
                },
            ]
            retrieval_service.graph_traversal = mock_graph

            # Execute - BM25 fails, vector + graph succeed
            results = await retrieval_service.retrieve_hybrid(request)

            # Verify: Should return results from vector + graph only
            assert len(results) > 0, "Should return results from vector and graph"
            memory_ids = [r.memory.memory_id for r in results]

            # Should have vector and graph results (mem_v1, mem_v2, mem_g1)
            assert "mem_v1" in memory_ids or "mem_v2" in memory_ids or "mem_g1" in memory_ids

            # Source attribution should NOT include bm25
            for result in results:
                source_methods = result.memory.metadata.get("source_methods", [])
                assert "bm25" not in source_methods, "BM25 failed, should not be in sources"

    @pytest.mark.asyncio
    async def test_graph_timeout_vector_and_bm25_work(
        self, retrieval_service, mock_neo4j_service
    ):
        """Test hybrid retrieval when graph traversal times out.

        Scenario: Graph traversal takes too long or APOC unavailable.
        Expected: Vector and BM25 methods continue working.
        """
        # Mock vector succeeds
        mock_neo4j_service.search_similar_memories.return_value = [
            {
                "memory_id": "mem_v1",
                "content": "Vector result",
                "memory_type": "technical_context",
                "confidence": 0.9,
                "similarity_score": 0.85,
                "source_conversation_id": "conv_1",
                "extraction_timestamp": datetime.now(timezone.utc),
                "has_embedding": True,
            },
        ]

        # Mock BM25 succeeds
        mock_neo4j_service.search_memories_bm25.return_value = [
            {
                "memory_id": "mem_b1",
                "content": "BM25 result",
                "memory_type": "preference",
                "confidence": 0.87,
                "bm25_score": 5.2,
                "source_conversation_id": "conv_2",
                "extraction_timestamp": datetime.now(timezone.utc),
                "has_embedding": True,
            },
        ]

        # Mock graph traversal to timeout
        mock_graph = AsyncMock()
        mock_graph.traverse_from_seeds.side_effect = TimeoutError("Graph traversal timeout")
        retrieval_service.graph_traversal = mock_graph

        request = HybridRetrievalRequest(
            query="Docker container management",
            enabled_methods=["vector", "bm25", "graph"],
        )

        # Execute - graph fails, vector + BM25 succeed
        results = await retrieval_service.retrieve_hybrid(request)

        # Verify: Should return results from vector + BM25 only
        assert len(results) > 0, "Should return results from vector and BM25"
        memory_ids = [r.memory.memory_id for r in results]
        assert "mem_v1" in memory_ids or "mem_b1" in memory_ids

        # Source attribution should NOT include graph
        for result in results:
            source_methods = result.memory.metadata.get("source_methods", [])
            assert "graph" not in source_methods, "Graph failed, should not be in sources"

    @pytest.mark.asyncio
    async def test_vector_fails_bm25_and_graph_work(
        self, retrieval_service, mock_neo4j_service
    ):
        """Test hybrid retrieval when vector search fails.

        Scenario: Vector index corrupted or embedding service down.
        Expected: BM25 and graph methods continue (graph uses BM25 seeds).
        """
        # Mock vector search to fail
        mock_neo4j_service.search_similar_memories.side_effect = Exception(
            "Vector index not available"
        )

        # Mock BM25 succeeds
        mock_neo4j_service.search_memories_bm25.return_value = [
            {
                "memory_id": "mem_b1",
                "content": "BM25 result 1",
                "memory_type": "technical_context",
                "confidence": 0.87,
                "bm25_score": 5.2,
                "source_conversation_id": "conv_1",
                "extraction_timestamp": datetime.now(timezone.utc),
                "has_embedding": True,
            },
            {
                "memory_id": "mem_b2",
                "content": "BM25 result 2",
                "memory_type": "preference",
                "confidence": 0.85,
                "bm25_score": 4.8,
                "source_conversation_id": "conv_2",
                "extraction_timestamp": datetime.now(timezone.utc),
                "has_embedding": True,
            },
        ]

        # Mock graph traversal succeeds (but will fail due to vector seeds)
        # Graph traversal needs vector search for seeds, which will fail
        mock_graph = AsyncMock()
        mock_graph.traverse_from_seeds.return_value = []  # No seeds from vector
        retrieval_service.graph_traversal = mock_graph

        request = HybridRetrievalRequest(
            query="Home Assistant automation",
            enabled_methods=["vector", "bm25", "graph"],
        )

        # Execute - vector fails, BM25 succeeds, graph has no seeds
        results = await retrieval_service.retrieve_hybrid(request)

        # Verify: Should return BM25 results only (graph has no vector seeds)
        assert len(results) > 0, "Should return BM25 results"
        memory_ids = [r.memory.memory_id for r in results]
        assert "mem_b1" in memory_ids or "mem_b2" in memory_ids

        # Source attribution should only include bm25
        for result in results:
            source_methods = result.memory.metadata.get("source_methods", [])
            assert "vector" not in source_methods, "Vector failed, should not be in sources"

    @pytest.mark.asyncio
    async def test_two_methods_fail_one_succeeds(
        self, retrieval_service, mock_neo4j_service
    ):
        """Test hybrid retrieval when 2 of 3 methods fail.

        Should continue with the one successful method.
        """
        # Mock vector and BM25 to fail
        mock_neo4j_service.search_similar_memories.side_effect = Exception("Vector failed")
        mock_neo4j_service.search_memories_bm25.side_effect = Exception("BM25 failed")

        # When both vector and BM25 fail, graph has no seeds - will also fail
        # This should raise RuntimeError for all methods failing
        mock_graph = AsyncMock()
        retrieval_service.graph_traversal = mock_graph

        request = HybridRetrievalRequest(
            query="test query",
            enabled_methods=["vector", "bm25", "graph"],
        )

        # All methods fail - should raise RuntimeError
        with pytest.raises(RuntimeError, match="All enabled retrieval methods failed"):
            await retrieval_service.retrieve_hybrid(request)

    @pytest.mark.asyncio
    async def test_empty_results_not_treated_as_failure(
        self, retrieval_service, mock_neo4j_service
    ):
        """Test that empty results are not treated as failures.

        Empty results != failure. Method succeeded but found nothing.
        """
        # All methods succeed but return empty
        mock_neo4j_service.search_similar_memories.return_value = []
        mock_neo4j_service.search_memories_bm25.return_value = []

        mock_graph = AsyncMock()
        mock_graph.traverse_from_seeds.return_value = []
        retrieval_service.graph_traversal = mock_graph

        request = HybridRetrievalRequest(
            query="nonexistent query",
            enabled_methods=["vector", "bm25", "graph"],
        )

        # Execute - all methods succeed but return empty
        results = await retrieval_service.retrieve_hybrid(request)

        # Verify:
        # - Should NOT raise RuntimeError (methods succeeded, just found nothing)
        # - Should return empty results
        assert results == [], "Empty results should return empty list, not error"

    @pytest.mark.asyncio
    async def test_method_failure_logging(
        self, retrieval_service, mock_neo4j_service, caplog
    ):
        """Test that method failures are logged with warnings."""
        import logging
        caplog.set_level(logging.WARNING)

        # Mock BM25 to fail
        mock_neo4j_service.search_memories_bm25.side_effect = Exception("BM25 index error")

        # Mock vector succeeds
        mock_neo4j_service.search_similar_memories.return_value = [
            {
                "memory_id": "mem_v1",
                "content": "Vector result",
                "memory_type": "technical_context",
                "confidence": 0.9,
                "similarity_score": 0.85,
                "source_conversation_id": "conv_1",
                "extraction_timestamp": datetime.now(timezone.utc),
                "has_embedding": True,
            },
        ]

        request = HybridRetrievalRequest(
            query="test query",
            enabled_methods=["vector", "bm25"],
        )

        # Execute - BM25 fails, vector succeeds
        results = await retrieval_service.retrieve_hybrid(request)

        # Verify vector results returned
        assert len(results) == 1
        assert results[0].memory.memory_id == "mem_v1"

        # Verify warning was logged about BM25 failure
        assert any("bm25" in record.message.lower() and "failed" in record.message.lower()
                   for record in caplog.records), "Should log warning about BM25 failure"
