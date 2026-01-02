"""Performance tests for hybrid retrieval system.

Tests verify:
- Sequential query performance (p50, p95, max latency)
- Concurrent query performance under load
- Graph traversal depth impact on latency
"""

import pytest
import asyncio
import time
import statistics
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

from src.haia.embedding.retrieval_service import RetrievalService
from src.haia.models.hybrid_retrieval import HybridRetrievalRequest, GraphTraversalConfig


@pytest.mark.integration
@pytest.mark.performance
class TestHybridPerformance:
    """Performance tests for hybrid retrieval."""

    @pytest.fixture
    def mock_neo4j_service(self):
        """Mock Neo4j service with realistic latency."""
        mock = AsyncMock()
        mock.driver = MagicMock()
        mock.detect_apoc.return_value = True

        # Mock vector search with ~50ms latency
        async def vector_search(*args, **kwargs):
            await asyncio.sleep(0.05)  # 50ms
            return [
                {
                    "memory_id": f"mem_v_{i}",
                    "content": f"Vector memory {i}",
                    "memory_type": "technical_context",
                    "confidence": 0.9,
                    "similarity_score": 0.85,
                    "source_conversation_id": "conv_1",
                    "extraction_timestamp": datetime.now(timezone.utc),
                    "has_embedding": True,
                }
                for i in range(5)
            ]

        mock.search_similar_memories = vector_search

        # Mock BM25 search with ~30ms latency
        async def bm25_search(*args, **kwargs):
            await asyncio.sleep(0.03)  # 30ms
            return [
                {
                    "memory_id": f"mem_b_{i}",
                    "content": f"BM25 memory {i}",
                    "memory_type": "technical_context",
                    "confidence": 0.87,
                    "bm25_score": 5.2,
                    "source_conversation_id": "conv_2",
                    "extraction_timestamp": datetime.now(timezone.utc),
                    "has_embedding": True,
                }
                for i in range(5)
            ]

        mock.search_memories_bm25 = bm25_search

        return mock

    @pytest.fixture
    def mock_ollama_client(self):
        """Mock Ollama client with realistic embedding latency."""
        mock = AsyncMock()
        mock.health_check.return_value = True

        # Mock embedding generation with ~20ms latency
        async def embed(*args, **kwargs):
            await asyncio.sleep(0.02)  # 20ms
            return [0.1] * 768

        mock.embed = embed
        return mock

    @pytest.fixture
    def retrieval_service(self, mock_neo4j_service, mock_ollama_client):
        """Create RetrievalService with mocked dependencies."""
        service = RetrievalService(
            neo4j_service=mock_neo4j_service,
            ollama_client=mock_ollama_client,
        )

        # Mock graph traversal with ~40ms latency
        mock_graph = AsyncMock()

        async def traverse(*args, **kwargs):
            await asyncio.sleep(0.04)  # 40ms
            return [
                {
                    "memory_id": f"mem_g_{i}",
                    "content": f"Graph memory {i}",
                    "type": "technical_context",
                    "confidence": 0.86,
                    "distance": 1,
                }
                for i in range(3)
            ]

        mock_graph.traverse_from_seeds = traverse
        service.graph_traversal = mock_graph

        return service

    # ========================================================================
    # T037: Performance test for hybrid retrieval (100 queries)
    # ========================================================================

    @pytest.mark.asyncio
    async def test_sequential_query_performance(
        self, retrieval_service
    ):
        """Test p50/p95/max latency for 100 sequential hybrid queries.

        Target: p95 < 500ms for sequential queries
        Expected: ~100-150ms per query with mocked services (parallel execution)
        """
        num_queries = 100
        latencies = []

        request = HybridRetrievalRequest(
            query="test query",
            enabled_methods=["vector", "bm25", "graph"],
            top_k=5,
        )

        # Run 100 sequential queries
        for i in range(num_queries):
            start = time.perf_counter()
            results = await retrieval_service.retrieve_hybrid(request)
            end = time.perf_counter()

            latency_ms = (end - start) * 1000
            latencies.append(latency_ms)

            # Verify results are returned
            assert len(results) > 0, f"Query {i} returned no results"

        # Calculate percentiles
        p50 = statistics.median(latencies)
        p95 = statistics.quantiles(latencies, n=20)[18]  # 95th percentile
        p99 = statistics.quantiles(latencies, n=100)[98]  # 99th percentile
        max_latency = max(latencies)
        mean_latency = statistics.mean(latencies)

        print(f"\n{'='*60}")
        print(f"Sequential Query Performance ({num_queries} queries)")
        print(f"{'='*60}")
        print(f"Mean:   {mean_latency:.2f}ms")
        print(f"p50:    {p50:.2f}ms")
        print(f"p95:    {p95:.2f}ms")
        print(f"p99:    {p99:.2f}ms")
        print(f"Max:    {max_latency:.2f}ms")
        print(f"{'='*60}\n")

        # Verify performance targets
        # With mocked services (50ms vector + 30ms BM25 + 40ms graph in parallel)
        # Expected: ~50-60ms (longest method + overhead)
        # With real services: target p95 < 500ms
        assert p95 < 200, f"p95 latency {p95:.2f}ms exceeds 200ms threshold (with mocks)"
        assert mean_latency < 150, f"Mean latency {mean_latency:.2f}ms exceeds 150ms"

    # ========================================================================
    # T038: Concurrency test (10 simultaneous requests)
    # ========================================================================

    @pytest.mark.asyncio
    async def test_concurrent_query_performance(
        self, retrieval_service
    ):
        """Test p95 latency with 10 concurrent requests.

        Target: p95 < 800ms with 10 concurrent requests
        Expected: Similar to sequential (methods run in parallel, not competing)
        """
        num_concurrent = 10
        latencies = []

        request = HybridRetrievalRequest(
            query="test query",
            enabled_methods=["vector", "bm25", "graph"],
            top_k=5,
        )

        async def single_query(query_id: int):
            """Execute a single query and record latency."""
            start = time.perf_counter()
            results = await retrieval_service.retrieve_hybrid(request)
            end = time.perf_counter()

            latency_ms = (end - start) * 1000
            assert len(results) > 0, f"Query {query_id} returned no results"
            return latency_ms

        # Run 10 concurrent queries
        tasks = [single_query(i) for i in range(num_concurrent)]
        latencies = await asyncio.gather(*tasks)

        # Calculate percentiles
        p50 = statistics.median(latencies)
        p95 = statistics.quantiles(latencies, n=20)[18]  # 95th percentile
        max_latency = max(latencies)
        mean_latency = statistics.mean(latencies)

        print(f"\n{'='*60}")
        print(f"Concurrent Query Performance ({num_concurrent} concurrent)")
        print(f"{'='*60}")
        print(f"Mean:   {mean_latency:.2f}ms")
        print(f"p50:    {p50:.2f}ms")
        print(f"p95:    {p95:.2f}ms")
        print(f"Max:    {max_latency:.2f}ms")
        print(f"{'='*60}\n")

        # Verify performance targets
        # With mocked async services, concurrent should be similar to sequential
        # Real target: p95 < 800ms with concurrency
        assert p95 < 250, f"p95 latency {p95:.2f}ms exceeds 250ms threshold (with mocks)"
        assert mean_latency < 200, f"Mean latency {mean_latency:.2f}ms exceeds 200ms"

    # ========================================================================
    # T039: Graph traversal depth performance comparison
    # ========================================================================

    @pytest.mark.asyncio
    async def test_graph_traversal_depth_performance(
        self, retrieval_service
    ):
        """Test latency impact of graph traversal depth (1-hop vs 2-hop vs 3-hop).

        Expected: Latency increases with depth, but not linearly (BFS traversal)
        """
        depths = [1, 2, 3]
        depth_latencies = {}

        for depth in depths:
            latencies = []

            request = HybridRetrievalRequest(
                query="test query",
                enabled_methods=["vector", "bm25", "graph"],
                top_k=5,
                graph_depth=depth,
            )

            # Run 20 queries per depth to get stable measurements
            for _ in range(20):
                start = time.perf_counter()
                results = await retrieval_service.retrieve_hybrid(request)
                end = time.perf_counter()

                latency_ms = (end - start) * 1000
                latencies.append(latency_ms)

                assert len(results) > 0, f"Depth {depth} returned no results"

            # Calculate statistics
            mean = statistics.mean(latencies)
            p95 = statistics.quantiles(latencies, n=20)[18]

            depth_latencies[depth] = {
                "mean": mean,
                "p95": p95,
                "samples": latencies
            }

        print(f"\n{'='*60}")
        print(f"Graph Traversal Depth Performance Comparison")
        print(f"{'='*60}")
        for depth in depths:
            stats = depth_latencies[depth]
            print(f"Depth {depth}: mean={stats['mean']:.2f}ms, p95={stats['p95']:.2f}ms")
        print(f"{'='*60}\n")

        # Verify depth impact (with mocks, should be minimal difference)
        # Real scenario: deeper traversal = more graph queries
        for depth in depths:
            assert depth_latencies[depth]["p95"] < 250, \
                f"Depth {depth} p95 {depth_latencies[depth]['p95']:.2f}ms exceeds 250ms"

        # Verify that latencies are reasonable across depths
        # With mocked services, depth shouldn't matter much
        # In real scenarios, we'd verify latency growth is sub-linear
        depth_1_mean = depth_latencies[1]["mean"]
        depth_3_mean = depth_latencies[3]["mean"]

        # Allow up to 2x increase from depth 1 to depth 3 (generous for mocks)
        assert depth_3_mean < depth_1_mean * 2, \
            f"Depth 3 latency ({depth_3_mean:.2f}ms) more than 2x depth 1 ({depth_1_mean:.2f}ms)"

    # ========================================================================
    # Additional edge case: Empty results performance
    # ========================================================================

    @pytest.mark.asyncio
    async def test_empty_results_performance(
        self, mock_neo4j_service, mock_ollama_client
    ):
        """Test performance when no results are found (fast path).

        Expected: Should be faster than normal queries (no RRF merging needed)
        """
        # Configure mocks to return empty results
        mock_neo4j_service.search_similar_memories = AsyncMock(return_value=[])
        mock_neo4j_service.search_memories_bm25 = AsyncMock(return_value=[])

        service = RetrievalService(
            neo4j_service=mock_neo4j_service,
            ollama_client=mock_ollama_client,
        )

        mock_graph = AsyncMock()
        mock_graph.traverse_from_seeds = AsyncMock(return_value=[])
        service.graph_traversal = mock_graph

        request = HybridRetrievalRequest(
            query="nonexistent query",
            enabled_methods=["vector", "bm25", "graph"],
        )

        latencies = []
        for _ in range(50):
            start = time.perf_counter()
            results = await service.retrieve_hybrid(request)
            end = time.perf_counter()

            latency_ms = (end - start) * 1000
            latencies.append(latency_ms)

            assert results == [], "Empty query should return empty results"

        mean = statistics.mean(latencies)
        p95 = statistics.quantiles(latencies, n=20)[18]

        print(f"\n{'='*60}")
        print(f"Empty Results Performance (50 queries)")
        print(f"{'='*60}")
        print(f"Mean:   {mean:.2f}ms")
        print(f"p95:    {p95:.2f}ms")
        print(f"{'='*60}\n")

        # Empty results should be fast (no RRF merging, minimal overhead)
        assert mean < 50, f"Empty results mean latency {mean:.2f}ms exceeds 50ms"
        assert p95 < 100, f"Empty results p95 {p95:.2f}ms exceeds 100ms"
