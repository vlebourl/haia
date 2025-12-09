"""Unit tests for retrieval service.

Tests semantic search, ranking algorithms, and relevance scoring.
All tests use mocked Neo4j and Ollama dependencies.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime

from haia.embedding.retrieval_service import RetrievalService
from haia.embedding.models import (
    RetrievalQuery,
    RetrievalResponse,
    RetrievalResult,
    RelevanceScore,
)
from haia.extraction.models import ExtractedMemory


@pytest.fixture
def mock_neo4j_service():
    """Mock Neo4j service for testing."""
    service = AsyncMock()
    service.search_similar_memories = AsyncMock()
    return service


@pytest.fixture
def mock_ollama_client():
    """Mock Ollama client for testing."""
    client = AsyncMock()
    client.embed = AsyncMock(return_value=[0.01] * 768)
    return client


@pytest.fixture
def retrieval_service(mock_neo4j_service, mock_ollama_client):
    """Create retrieval service instance for testing."""
    return RetrievalService(
        neo4j_service=mock_neo4j_service,
        ollama_client=mock_ollama_client,
    )


@pytest.fixture
def sample_memories():
    """Sample memory data for testing."""
    return [
        {
            "memory_id": "mem_001",
            "memory_type": "preference",
            "content": "User prefers Docker over Kubernetes",
            "confidence": 0.92,
            "similarity_score": 0.85,
            "source_conversation_id": "conv_123",
            "extraction_timestamp": datetime.utcnow().isoformat(),
            "category": "infrastructure",
            "metadata": {},
            "embedding_version": "nomic-embed-text-v1",
            "embedding_updated_at": datetime.utcnow().isoformat(),
        },
        {
            "memory_id": "mem_002",
            "memory_type": "technical_context",
            "content": "Uses Proxmox VE for virtualization",
            "confidence": 0.88,
            "similarity_score": 0.78,
            "source_conversation_id": "conv_124",
            "extraction_timestamp": datetime.utcnow().isoformat(),
            "category": "infrastructure",
            "metadata": {},
            "embedding_version": "nomic-embed-text-v1",
            "embedding_updated_at": datetime.utcnow().isoformat(),
        },
        {
            "memory_id": "mem_003",
            "memory_type": "decision",
            "content": "Decided to use Ceph for storage",
            "confidence": 0.75,
            "similarity_score": 0.72,
            "source_conversation_id": "conv_125",
            "extraction_timestamp": datetime.utcnow().isoformat(),
            "category": "storage",
            "metadata": {},
            "embedding_version": "nomic-embed-text-v1",
            "embedding_updated_at": datetime.utcnow().isoformat(),
        },
    ]


@pytest.mark.asyncio
async def test_retrieve_basic_query(retrieval_service, mock_neo4j_service, sample_memories):
    """Test basic retrieval query."""
    mock_neo4j_service.search_similar_memories.return_value = sample_memories

    query = RetrievalQuery(
        query_text="How should I deploy services?",
        top_k=10,
        min_similarity=0.65,
        min_confidence=0.4,
    )

    response = await retrieval_service.retrieve(query)

    assert response.has_results
    assert len(response.results) == 3
    assert response.total_results == 3
    assert response.results[0].rank == 1
    assert response.embedding_latency_ms > 0


@pytest.mark.asyncio
async def test_retrieve_empty_results(retrieval_service, mock_neo4j_service):
    """Test retrieval with no matching memories."""
    mock_neo4j_service.search_similar_memories.return_value = []

    query = RetrievalQuery(query_text="Test query", top_k=10)

    response = await retrieval_service.retrieve(query)

    assert not response.has_results
    assert len(response.results) == 0
    assert response.total_results == 0
    assert response.top_result is None


@pytest.mark.asyncio
async def test_relevance_scoring(retrieval_service, mock_neo4j_service, sample_memories):
    """Test relevance score calculation."""
    mock_neo4j_service.search_similar_memories.return_value = sample_memories

    query = RetrievalQuery(query_text="Test query", top_k=10)

    response = await retrieval_service.retrieve(query)

    # Verify relevance scores are calculated correctly
    # Formula: α * similarity + β * confidence (α=0.65, β=0.35)
    for result in response.results:
        expected_score = (
            0.65 * result.similarity_score + 0.35 * result.memory.confidence
        )
        assert abs(result.relevance_score - expected_score) < 0.01


@pytest.mark.asyncio
async def test_ranking_by_relevance(retrieval_service, mock_neo4j_service, sample_memories):
    """Test that results are ranked by relevance score."""
    # Shuffle memories to ensure ranking works
    shuffled = [sample_memories[2], sample_memories[0], sample_memories[1]]
    mock_neo4j_service.search_similar_memories.return_value = shuffled

    query = RetrievalQuery(query_text="Test query", top_k=10)

    response = await retrieval_service.retrieve(query)

    # Results should be sorted by relevance score (descending)
    for i in range(len(response.results) - 1):
        assert response.results[i].relevance_score >= response.results[i + 1].relevance_score
        assert response.results[i].rank == i + 1


@pytest.mark.asyncio
async def test_threshold_filtering(retrieval_service, mock_neo4j_service, sample_memories):
    """Test filtering by similarity and confidence thresholds."""
    mock_neo4j_service.search_similar_memories.return_value = sample_memories

    query = RetrievalQuery(
        query_text="Test query",
        top_k=10,
        min_similarity=0.80,  # High threshold
        min_confidence=0.90,  # High threshold
    )

    response = await retrieval_service.retrieve(query)

    # Neo4j should be called with threshold parameters
    mock_neo4j_service.search_similar_memories.assert_called_once()
    call_kwargs = mock_neo4j_service.search_similar_memories.call_args.kwargs
    assert call_kwargs["min_similarity"] == 0.80
    assert call_kwargs["min_confidence"] == 0.90


@pytest.mark.asyncio
async def test_memory_type_filtering(retrieval_service, mock_neo4j_service, sample_memories):
    """Test filtering by memory types."""
    filtered_memories = [m for m in sample_memories if m["memory_type"] == "preference"]
    mock_neo4j_service.search_similar_memories.return_value = filtered_memories

    query = RetrievalQuery(
        query_text="Test query",
        top_k=10,
        memory_types=["preference"],
    )

    response = await retrieval_service.retrieve(query)

    # Verify type filtering was applied
    mock_neo4j_service.search_similar_memories.assert_called_once()
    call_kwargs = mock_neo4j_service.search_similar_memories.call_args.kwargs
    assert call_kwargs["memory_types"] == ["preference"]


@pytest.mark.asyncio
async def test_generate_embedding(retrieval_service, mock_ollama_client):
    """Test embedding generation for query text."""
    mock_ollama_client.embed.return_value = [0.02] * 768

    embedding = await retrieval_service.generate_embedding("Test query")

    assert len(embedding) == 768
    assert isinstance(embedding[0], float)
    mock_ollama_client.embed.assert_called_once_with("Test query")


@pytest.mark.asyncio
async def test_deduplication(retrieval_service, mock_neo4j_service):
    """Test deduplication of near-duplicate memories."""
    # Create near-duplicate memories with high similarity
    duplicate_memories = [
        {
            "memory_id": "mem_001",
            "memory_type": "preference",
            "content": "User prefers Docker",
            "confidence": 0.92,
            "similarity_score": 0.95,
            "source_conversation_id": "conv_123",
            "extraction_timestamp": datetime.utcnow().isoformat(),
            "category": None,
            "metadata": {},
            "embedding_version": "nomic-embed-text-v1",
            "embedding_updated_at": datetime.utcnow().isoformat(),
        },
        {
            "memory_id": "mem_002",
            "memory_type": "preference",
            "content": "User prefers Docker containers",
            "confidence": 0.90,
            "similarity_score": 0.94,
            "source_conversation_id": "conv_124",
            "extraction_timestamp": datetime.utcnow().isoformat(),
            "category": None,
            "metadata": {},
            "embedding_version": "nomic-embed-text-v1",
            "embedding_updated_at": datetime.utcnow().isoformat(),
        },
    ]
    mock_neo4j_service.search_similar_memories.return_value = duplicate_memories

    query = RetrievalQuery(query_text="Docker preferences", top_k=10)

    response = await retrieval_service.retrieve(query)

    # Deduplication should keep only the higher-confidence memory
    assert response.memories_deduplicated > 0


@pytest.mark.asyncio
async def test_performance_metrics(retrieval_service, mock_neo4j_service, sample_memories):
    """Test that performance metrics are tracked."""
    mock_neo4j_service.search_similar_memories.return_value = sample_memories

    query = RetrievalQuery(query_text="Test query", top_k=10)

    response = await retrieval_service.retrieve(query)

    # Verify all latency metrics are present
    assert response.total_latency_ms > 0
    assert response.embedding_latency_ms > 0
    assert response.search_latency_ms > 0
    assert response.total_latency_ms >= (
        response.embedding_latency_ms + response.search_latency_ms
    )


@pytest.mark.asyncio
async def test_error_handling(retrieval_service, mock_neo4j_service):
    """Test error handling when retrieval fails."""
    mock_neo4j_service.search_similar_memories.side_effect = Exception("Neo4j error")

    query = RetrievalQuery(query_text="Test query", top_k=10)

    with pytest.raises(Exception):
        await retrieval_service.retrieve(query)


@pytest.mark.asyncio
async def test_empty_query_text():
    """Test validation of empty query text."""
    with pytest.raises(ValueError):
        RetrievalQuery(query_text="", top_k=10)


@pytest.mark.asyncio
async def test_invalid_top_k():
    """Test validation of invalid top_k parameter."""
    with pytest.raises(ValueError):
        RetrievalQuery(query_text="Test", top_k=0)

    with pytest.raises(ValueError):
        RetrievalQuery(query_text="Test", top_k=101)


@pytest.mark.asyncio
async def test_precomputed_embedding(retrieval_service, mock_neo4j_service, sample_memories):
    """Test retrieval with precomputed query embedding."""
    mock_neo4j_service.search_similar_memories.return_value = sample_memories

    precomputed_embedding = [0.03] * 768
    query = RetrievalQuery(
        query_text="Test query",
        query_embedding=precomputed_embedding,
        top_k=10,
    )

    response = await retrieval_service.retrieve(query)

    # Should use precomputed embedding, not generate new one
    assert response.has_results
    # Embedding latency should be 0 or very small since it was precomputed
    assert response.embedding_latency_ms < 1.0
