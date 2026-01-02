"""Unit tests for RRFMerger service.

Tests cover:
- RRF formula correctness (score = sum(1/(k+rank_i)))
- Source attribution tracking
- Deduplication within methods
- Edge cases (empty inputs, single method, no overlap)
"""

import pytest
from datetime import datetime

from src.haia.models.hybrid_retrieval import MethodResult, RRFScore, RetrievedMemory
from src.haia.services.rrf_merger import RRFMerger


class TestRRFMerger:
    """Test suite for RRFMerger service."""

    def test_rrf_formula_correctness_single_method(self):
        """Test RRF formula with single method (k=60)."""
        merger = RRFMerger(default_k=60)

        # Create simple test data
        mem1 = RetrievedMemory(
            memory_id="mem_001",
            content="Test memory 1",
            type="test",
            confidence=0.9,
            valid_from=datetime(2025, 1, 1),
            valid_until=None,
        )
        mem2 = RetrievedMemory(
            memory_id="mem_002",
            content="Test memory 2",
            type="test",
            confidence=0.8,
            valid_from=datetime(2025, 1, 1),
            valid_until=None,
        )

        vector_result = MethodResult(
            method="vector",
            memories=[mem1, mem2],  # mem1 rank 1, mem2 rank 2
            scores={"mem_001": 0.95, "mem_002": 0.87},
        )

        # Merge
        rrf_scores = merger.merge([vector_result], top_k=10)

        # Verify formula: score = 1/(k+rank)
        # mem1: 1/(60+1) = 1/61 ≈ 0.0164
        # mem2: 1/(60+2) = 1/62 ≈ 0.0161
        assert len(rrf_scores) == 2
        assert rrf_scores[0].memory_id == "mem_001"
        assert abs(rrf_scores[0].rrf_score - 1.0/61) < 0.0001
        assert rrf_scores[1].memory_id == "mem_002"
        assert abs(rrf_scores[1].rrf_score - 1.0/62) < 0.0001

    def test_rrf_formula_correctness_multiple_methods(self):
        """Test RRF formula with multiple methods (consensus)."""
        merger = RRFMerger(default_k=60)

        mem1 = RetrievedMemory(
            memory_id="mem_001",
            content="Docker preference",
            type="preference",
            confidence=0.9,
            valid_from=datetime(2025, 1, 1),
            valid_until=None,
        )
        mem2 = RetrievedMemory(
            memory_id="mem_002",
            content="Proxmox infrastructure",
            type="technical_context",
            confidence=0.88,
            valid_from=datetime(2025, 1, 1),
            valid_until=None,
        )
        mem3 = RetrievedMemory(
            memory_id="mem_003",
            content="Container networking",
            type="technical_context",
            confidence=0.75,
            valid_from=datetime(2025, 1, 1),
            valid_until=None,
        )

        # Vector: mem1 (rank 1), mem2 (rank 2)
        vector_result = MethodResult(
            method="vector",
            memories=[mem1, mem2],
            scores={"mem_001": 0.95, "mem_002": 0.87},
        )

        # BM25: mem2 (rank 1), mem3 (rank 2), mem1 (rank 3)
        bm25_result = MethodResult(
            method="bm25",
            memories=[mem2, mem3, mem1],
            scores={"mem_002": 1.19, "mem_003": 1.05, "mem_001": 0.92},
        )

        # Graph: mem3 (rank 1), mem2 (rank 2)
        graph_result = MethodResult(
            method="graph",
            memories=[mem3, mem2],
            scores={"mem_003": 1.0, "mem_002": 0.5},
        )

        # Merge all three methods
        rrf_scores = merger.merge([vector_result, bm25_result, graph_result], top_k=10)

        # Verify RRF scores:
        # mem2 found in all 3: 1/62 (vector rank 2) + 1/61 (BM25 rank 1) + 1/62 (graph rank 2)
        #      = 1/62 + 1/61 + 1/62 = 0.0161 + 0.0164 + 0.0161 = 0.0486
        # mem1 found in 2: 1/61 (vector rank 1) + 1/63 (BM25 rank 3)
        #      = 1/61 + 1/63 = 0.0164 + 0.0159 = 0.0323
        # mem3 found in 2: 1/62 (BM25 rank 2) + 1/61 (graph rank 1)
        #      = 1/62 + 1/61 = 0.0161 + 0.0164 = 0.0325

        assert len(rrf_scores) == 3

        # mem2 should be first (highest score)
        assert rrf_scores[0].memory_id == "mem_002"
        expected_mem2_score = 1.0/62 + 1.0/61 + 1.0/62
        assert abs(rrf_scores[0].rrf_score - expected_mem2_score) < 0.0001

        # mem3 should be second
        assert rrf_scores[1].memory_id == "mem_003"
        expected_mem3_score = 1.0/62 + 1.0/61
        assert abs(rrf_scores[1].rrf_score - expected_mem3_score) < 0.0001

        # mem1 should be third
        assert rrf_scores[2].memory_id == "mem_001"
        expected_mem1_score = 1.0/61 + 1.0/63
        assert abs(rrf_scores[2].rrf_score - expected_mem1_score) < 0.0001

    def test_source_attribution_single_method(self):
        """Test source attribution with single method."""
        merger = RRFMerger()

        mem1 = RetrievedMemory(
            memory_id="mem_001",
            content="Test",
            type="test",
            confidence=0.9,
            valid_from=datetime(2025, 1, 1),
            valid_until=None,
        )

        vector_result = MethodResult(
            method="vector",
            memories=[mem1],
            scores={"mem_001": 0.95},
        )

        rrf_scores = merger.merge([vector_result], top_k=10)

        assert len(rrf_scores) == 1
        score = rrf_scores[0]

        # Verify source methods
        assert score.source_methods == ["vector"]

        # Verify method contributions
        assert "vector" in score.method_contributions
        rank, contribution = score.method_contributions["vector"]
        assert rank == 1  # First rank
        assert abs(contribution - 1.0/61) < 0.0001  # k=60, rank=1

    def test_source_attribution_multiple_methods(self):
        """Test source attribution tracks all contributing methods."""
        merger = RRFMerger()

        mem1 = RetrievedMemory(
            memory_id="mem_001",
            content="Test",
            type="test",
            confidence=0.9,
            valid_from=datetime(2025, 1, 1),
            valid_until=None,
        )

        vector_result = MethodResult(
            method="vector",
            memories=[mem1],
            scores={"mem_001": 0.95},
        )

        bm25_result = MethodResult(
            method="bm25",
            memories=[mem1],  # Same memory, different method
            scores={"mem_001": 1.2},
        )

        graph_result = MethodResult(
            method="graph",
            memories=[mem1],  # Found by all three
            scores={"mem_001": 0.8},
        )

        rrf_scores = merger.merge([vector_result, bm25_result, graph_result], top_k=10)

        assert len(rrf_scores) == 1
        score = rrf_scores[0]

        # Verify all methods tracked
        assert set(score.source_methods) == {"vector", "bm25", "graph"}

        # Verify contributions from each method
        assert "vector" in score.method_contributions
        assert "bm25" in score.method_contributions
        assert "graph" in score.method_contributions

        # All rank 1 (only memory in each method)
        for method in ["vector", "bm25", "graph"]:
            rank, contribution = score.method_contributions[method]
            assert rank == 1
            assert abs(contribution - 1.0/61) < 0.0001

    def test_edge_case_empty_input(self):
        """Test RRF handles empty method results gracefully."""
        merger = RRFMerger()

        rrf_scores = merger.merge([], top_k=10)

        assert rrf_scores == []

    def test_edge_case_single_method_empty_memories(self):
        """Test RRF handles method with no memories."""
        merger = RRFMerger()

        empty_result = MethodResult(
            method="vector",
            memories=[],  # No results
            scores={},
        )

        rrf_scores = merger.merge([empty_result], top_k=10)

        assert rrf_scores == []

    def test_edge_case_no_overlap_between_methods(self):
        """Test RRF when methods return completely different memories."""
        merger = RRFMerger()

        mem1 = RetrievedMemory(
            memory_id="mem_001",
            content="Vector only",
            type="test",
            confidence=0.9,
            valid_from=datetime(2025, 1, 1),
            valid_until=None,
        )
        mem2 = RetrievedMemory(
            memory_id="mem_002",
            content="BM25 only",
            type="test",
            confidence=0.8,
            valid_from=datetime(2025, 1, 1),
            valid_until=None,
        )
        mem3 = RetrievedMemory(
            memory_id="mem_003",
            content="Graph only",
            type="test",
            confidence=0.7,
            valid_from=datetime(2025, 1, 1),
            valid_until=None,
        )

        vector_result = MethodResult(method="vector", memories=[mem1], scores={})
        bm25_result = MethodResult(method="bm25", memories=[mem2], scores={})
        graph_result = MethodResult(method="graph", memories=[mem3], scores={})

        rrf_scores = merger.merge([vector_result, bm25_result, graph_result], top_k=10)

        # All three memories should have same score (1/(60+1))
        assert len(rrf_scores) == 3
        for score in rrf_scores:
            assert abs(score.rrf_score - 1.0/61) < 0.0001
            assert len(score.source_methods) == 1  # Each from single method

    def test_top_k_limiting(self):
        """Test top_k parameter limits results correctly."""
        merger = RRFMerger()

        # Create 10 memories
        memories = [
            RetrievedMemory(
                memory_id=f"mem_{i:03d}",
                content=f"Memory {i}",
                type="test",
                confidence=0.9,
                valid_from=datetime(2025, 1, 1),
                valid_until=None,
            )
            for i in range(10)
        ]

        vector_result = MethodResult(
            method="vector",
            memories=memories,
            scores={f"mem_{i:03d}": 1.0 - i*0.05 for i in range(10)},
        )

        # Request only top 5
        rrf_scores = merger.merge([vector_result], top_k=5)

        assert len(rrf_scores) == 5

        # Verify ordering (first memory should have highest score)
        assert rrf_scores[0].memory_id == "mem_000"
        assert rrf_scores[4].memory_id == "mem_004"

    def test_custom_k_parameter(self):
        """Test RRF with custom k parameter."""
        merger = RRFMerger(default_k=60)

        mem1 = RetrievedMemory(
            memory_id="mem_001",
            content="Test",
            type="test",
            confidence=0.9,
            valid_from=datetime(2025, 1, 1),
            valid_until=None,
        )

        vector_result = MethodResult(
            method="vector",
            memories=[mem1],
            scores={"mem_001": 0.95},
        )

        # Use k=30 instead of default 60
        rrf_scores = merger.merge([vector_result], k=30, top_k=10)

        assert len(rrf_scores) == 1
        # score should be 1/(30+1) instead of 1/(60+1)
        assert abs(rrf_scores[0].rrf_score - 1.0/31) < 0.0001

    def test_deduplication_within_method(self):
        """Test deduplication removes exact duplicates within a method."""
        merger = RRFMerger()

        mem1 = RetrievedMemory(
            memory_id="mem_001",
            content="Test",
            type="test",
            confidence=0.9,
            valid_from=datetime(2025, 1, 1),
            valid_until=None,
        )

        # Same memory appears twice (should not happen, but test handling)
        vector_result = MethodResult(
            method="vector",
            memories=[mem1, mem1],  # Duplicate
            scores={"mem_001": 0.95},
        )

        rrf_scores = merger.merge_with_deduplication([vector_result], top_k=10)

        # Should only count mem_001 once
        assert len(rrf_scores) == 1
        assert rrf_scores[0].memory_id == "mem_001"

        # Score should be based on first occurrence (rank 1)
        assert abs(rrf_scores[0].rrf_score - 1.0/61) < 0.0001

    def test_consensus_signal_higher_score(self):
        """Test that memories found by multiple methods get higher scores."""
        merger = RRFMerger()

        mem_consensus = RetrievedMemory(
            memory_id="mem_consensus",
            content="Found by all methods",
            type="test",
            confidence=0.9,
            valid_from=datetime(2025, 1, 1),
            valid_until=None,
        )
        mem_single = RetrievedMemory(
            memory_id="mem_single",
            content="Found by one method",
            type="test",
            confidence=0.9,
            valid_from=datetime(2025, 1, 1),
            valid_until=None,
        )

        # All methods return consensus memory at rank 1
        vector_result = MethodResult(
            method="vector",
            memories=[mem_consensus, mem_single],
            scores={},
        )
        bm25_result = MethodResult(
            method="bm25",
            memories=[mem_consensus],
            scores={},
        )
        graph_result = MethodResult(
            method="graph",
            memories=[mem_consensus],
            scores={},
        )

        rrf_scores = merger.merge([vector_result, bm25_result, graph_result], top_k=10)

        # mem_consensus should rank higher (found by 3 methods)
        assert rrf_scores[0].memory_id == "mem_consensus"
        assert rrf_scores[1].memory_id == "mem_single"

        # mem_consensus score = 3 * (1/61) = 0.0492
        # mem_single score = 1 * (1/62) = 0.0161
        assert rrf_scores[0].rrf_score > rrf_scores[1].rrf_score
