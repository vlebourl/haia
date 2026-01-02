"""Pytest configuration and shared fixtures."""

import pytest


@pytest.fixture
def mock_anthropic_response():
    """Mock Anthropic API response."""
    from unittest.mock import Mock

    response = Mock()
    response.content = [Mock(text="Test response")]
    response.model = "claude-haiku-4-5-20251001"
    response.usage = Mock(input_tokens=10, output_tokens=5)
    response.stop_reason = "stop"
    return response


@pytest.fixture
def sample_messages():
    """Sample messages for testing."""
    from haia.llm.models import Message

    return [
        Message(role="user", content="Hello, how are you?")
    ]


# Hybrid Retrieval Fixtures (Session 13)


@pytest.fixture
def sample_memories_with_relationships():
    """Sample memories with graph relationships for testing graph traversal."""
    from datetime import datetime
    from src.haia.models.hybrid_retrieval import RetrievedMemory

    # Create sample memories
    mem1 = RetrievedMemory(
        memory_id="mem_001",
        content="I prefer Docker over Kubernetes for homelab deployments",
        type="docker_deployment_preference",
        confidence=0.85,
        valid_from=datetime(2025, 11, 15),
        valid_until=None,
    )

    mem2 = RetrievedMemory(
        memory_id="mem_002",
        content="Docker setup requires Proxmox cluster with sufficient resources",
        type="infrastructure_dependency",
        confidence=0.90,
        valid_from=datetime(2025, 11, 16),
        valid_until=None,
    )

    mem3 = RetrievedMemory(
        memory_id="mem_003",
        content="Proxmox cluster has 4 nodes with Ceph storage",
        type="infrastructure_technical_context",
        confidence=0.92,
        valid_from=datetime(2025, 12, 1),
        valid_until=None,
    )

    # Relationships (for graph traversal):
    # mem1 DEPENDS_ON mem2 (Docker depends on Proxmox)
    # mem2 RELATED_TO mem3 (Proxmox cluster details)

    return {
        "memories": [mem1, mem2, mem3],
        "relationships": [
            ("mem_001", "DEPENDS_ON", "mem_002"),
            ("mem_002", "RELATED_TO", "mem_003"),
        ],
    }


@pytest.fixture
def mock_method_results():
    """Mock MethodResult objects from vector, BM25, and graph retrieval."""
    from datetime import datetime
    from src.haia.models.hybrid_retrieval import MethodResult, RetrievedMemory

    # Create sample memories
    mem1 = RetrievedMemory(
        memory_id="mem_001",
        content="Docker deployment preference",
        type="preference",
        confidence=0.85,
        valid_from=datetime(2025, 11, 15),
        valid_until=None,
    )

    mem2 = RetrievedMemory(
        memory_id="mem_002",
        content="Proxmox infrastructure details",
        type="technical_context",
        confidence=0.90,
        valid_from=datetime(2025, 11, 16),
        valid_until=None,
    )

    mem3 = RetrievedMemory(
        memory_id="mem_003",
        content="Container networking configuration",
        type="technical_context",
        confidence=0.78,
        valid_from=datetime(2025, 12, 1),
        valid_until=None,
    )

    # Vector search result (ranked by semantic similarity)
    vector_result = MethodResult(
        method="vector",
        memories=[mem1, mem2],
        scores={"mem_001": 0.95, "mem_002": 0.87},
        error=None,
    )

    # BM25 search result (ranked by keyword match)
    bm25_result = MethodResult(
        method="bm25",
        memories=[mem2, mem3, mem1],
        scores={"mem_002": 1.19, "mem_003": 1.05, "mem_001": 0.92},
        error=None,
    )

    # Graph traversal result (ranked by distance from seeds)
    graph_result = MethodResult(
        method="graph",
        memories=[mem3, mem2],
        scores={"mem_003": 1.0, "mem_002": 0.5},  # Distance-based scoring
        error=None,
    )

    return {
        "vector": vector_result,
        "bm25": bm25_result,
        "graph": graph_result,
        "all": [vector_result, bm25_result, graph_result],
    }


@pytest.fixture
def mock_rrf_scores():
    """Mock RRFScore objects for testing result building."""
    from src.haia.models.hybrid_retrieval import RRFScore

    # mem2 found by all three methods (highest RRF score)
    score1 = RRFScore(
        memory_id="mem_002",
        rrf_score=0.0479,  # Sum of 1/(60+2) + 1/(60+1) + 1/(60+2)
        method_contributions={
            "vector": (2, 0.0161),  # Rank 2 in vector
            "bm25": (1, 0.0164),  # Rank 1 in BM25
            "graph": (2, 0.0161),  # Rank 2 in graph
        },
        source_methods=["vector", "bm25", "graph"],
    )

    # mem1 found by vector and BM25 only
    score2 = RRFScore(
        memory_id="mem_001",
        rrf_score=0.0318,  # Sum of 1/(60+1) + 1/(60+3)
        method_contributions={
            "vector": (1, 0.0164),  # Rank 1 in vector
            "bm25": (3, 0.0159),  # Rank 3 in BM25
        },
        source_methods=["vector", "bm25"],
    )

    # mem3 found by BM25 and graph only
    score3 = RRFScore(
        memory_id="mem_003",
        rrf_score=0.0315,  # Sum of 1/(60+2) + 1/(60+1)
        method_contributions={
            "bm25": (2, 0.0161),  # Rank 2 in BM25
            "graph": (1, 0.0164),  # Rank 1 in graph
        },
        source_methods=["bm25", "graph"],
    )

    return [score1, score2, score3]
