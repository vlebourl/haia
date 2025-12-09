"""Unit tests for embedding Pydantic models.

Tests model validation, field constraints, and computed properties.
"""

import pytest
from datetime import datetime
from pydantic import ValidationError

from haia.embedding.models import (
    EmbeddingRequest,
    EmbeddingResponse,
    RetrievalQuery,
    RetrievalResult,
    RetrievalResponse,
    RelevanceScore,
    BackfillProgress,
    EmbeddingError,
)
from haia.extraction.models import ExtractedMemory


def test_embedding_request_validation():
    """Test EmbeddingRequest model validation."""
    # Valid request
    request = EmbeddingRequest(
        model="nomic-embed-text",
        input="Test text",
        truncate=True,
        dimensions=768,
    )
    assert request.model == "nomic-embed-text"
    assert request.input == "Test text"
    assert request.dimensions == 768

    # Valid batch request
    batch_request = EmbeddingRequest(
        model="nomic-embed-text",
        input=["Text 1", "Text 2", "Text 3"],
    )
    assert isinstance(batch_request.input, list)
    assert len(batch_request.input) == 3


def test_embedding_request_defaults():
    """Test EmbeddingRequest default values."""
    request = EmbeddingRequest(input="Test")
    assert request.model == "nomic-embed-text"
    assert request.truncate is True
    assert request.dimensions == 768
    assert request.keep_alive == "5m"


def test_embedding_response_validation():
    """Test EmbeddingResponse model validation."""
    response = EmbeddingResponse(
        model="nomic-embed-text",
        embeddings=[[0.01, 0.02, 0.03]],
        total_duration=14143917,
        load_duration=1019500,
        prompt_eval_count=8,
    )
    assert response.model == "nomic-embed-text"
    assert len(response.embeddings) == 1
    assert len(response.embeddings[0]) == 3


def test_embedding_response_latency_property():
    """Test latency_ms computed property."""
    response = EmbeddingResponse(
        model="nomic-embed-text",
        embeddings=[[0.01]],
        total_duration=14143917,  # nanoseconds
    )
    expected_latency = 14143917 / 1_000_000  # Convert to milliseconds
    assert response.latency_ms == expected_latency

    # Test with None duration
    response_no_duration = EmbeddingResponse(
        model="nomic-embed-text",
        embeddings=[[0.01]],
    )
    assert response_no_duration.latency_ms == 0.0


def test_retrieval_query_validation():
    """Test RetrievalQuery model validation."""
    query = RetrievalQuery(
        query_text="How to deploy services?",
        top_k=10,
        min_similarity=0.65,
        min_confidence=0.4,
    )
    assert query.query_text == "How to deploy services?"
    assert query.top_k == 10
    assert query.min_similarity == 0.65


def test_retrieval_query_constraints():
    """Test RetrievalQuery field constraints."""
    # Empty query text should fail
    with pytest.raises(ValidationError):
        RetrievalQuery(query_text="", top_k=10)

    # top_k out of range
    with pytest.raises(ValidationError):
        RetrievalQuery(query_text="Test", top_k=0)

    with pytest.raises(ValidationError):
        RetrievalQuery(query_text="Test", top_k=101)

    # min_similarity out of range
    with pytest.raises(ValidationError):
        RetrievalQuery(query_text="Test", top_k=10, min_similarity=1.5)

    with pytest.raises(ValidationError):
        RetrievalQuery(query_text="Test", top_k=10, min_similarity=-0.1)


def test_retrieval_query_defaults():
    """Test RetrievalQuery default values."""
    query = RetrievalQuery(query_text="Test")
    assert query.top_k == 10
    assert query.min_similarity == 0.65
    assert query.min_confidence == 0.4
    assert query.include_metadata is True


def test_retrieval_result_properties():
    """Test RetrievalResult computed properties."""
    memory = ExtractedMemory(
        memory_id="mem_001",
        memory_type="preference",
        content="Test content",
        confidence=0.92,
        source_conversation_id="conv_123",
    )

    result = RetrievalResult(
        memory=memory,
        similarity_score=0.85,
        relevance_score=0.87,
        rank=1,
    )

    # Test is_high_confidence
    assert result.is_high_confidence is True

    # Test is_highly_relevant
    assert result.is_highly_relevant is True

    # Test with lower scores
    low_result = RetrievalResult(
        memory=ExtractedMemory(
            memory_id="mem_002",
            memory_type="preference",
            content="Test",
            confidence=0.55,
            source_conversation_id="conv_123",
        ),
        similarity_score=0.65,
        relevance_score=0.60,
        rank=2,
    )
    assert low_result.is_high_confidence is False
    assert low_result.is_highly_relevant is False


def test_retrieval_response_properties():
    """Test RetrievalResponse computed properties."""
    memory = ExtractedMemory(
        memory_id="mem_001",
        memory_type="preference",
        content="Test",
        confidence=0.92,
        source_conversation_id="conv_123",
    )

    results = [
        RetrievalResult(
            memory=memory,
            similarity_score=0.85,
            relevance_score=0.87,
            rank=1,
        )
    ]

    response = RetrievalResponse(
        query="Test query",
        results=results,
        total_results=1,
        total_latency_ms=50.0,
        embedding_latency_ms=20.0,
        search_latency_ms=30.0,
        top_k=10,
        min_similarity=0.65,
        min_confidence=0.4,
        memories_searched=100,
        memories_matched=5,
    )

    assert response.has_results is True
    assert response.top_result == results[0]

    # Test empty response
    empty_response = RetrievalResponse(
        query="Test",
        results=[],
        total_results=0,
        total_latency_ms=50.0,
        embedding_latency_ms=20.0,
        search_latency_ms=30.0,
        top_k=10,
        min_similarity=0.65,
        min_confidence=0.4,
        memories_searched=100,
        memories_matched=0,
    )
    assert empty_response.has_results is False
    assert empty_response.top_result is None


def test_relevance_score_calculation():
    """Test RelevanceScore final score calculation."""
    score = RelevanceScore(
        similarity=0.85,
        confidence=0.92,
        recency=0.95,
        type_weight=1.2,
        similarity_weight=0.65,
        confidence_weight=0.35,
    )

    # Calculate expected score: (0.85 * 0.65 + 0.92 * 0.35) * 1.2
    expected = (0.85 * 0.65 + 0.92 * 0.35) * 1.2
    assert abs(score.final_score - expected) < 0.01

    # Test score breakdown
    breakdown = score.score_breakdown
    assert "similarity_contribution" in breakdown
    assert "confidence_contribution" in breakdown
    assert "type_multiplier" in breakdown
    assert "final_score" in breakdown


def test_relevance_score_capping():
    """Test that relevance score is capped at 1.0."""
    score = RelevanceScore(
        similarity=1.0,
        confidence=1.0,
        recency=1.0,
        type_weight=2.0,  # High weight that would push score > 1.0
        similarity_weight=0.65,
        confidence_weight=0.35,
    )

    # Score should be capped at 1.0
    assert score.final_score <= 1.0


def test_backfill_progress_properties():
    """Test BackfillProgress computed properties."""
    progress = BackfillProgress(
        progress_id="backfill_001",
        status="running",
        started_at=datetime.utcnow(),
        total_nodes=1000,
        processed_nodes=750,
        failed_nodes=10,
        worker_count=3,
        batch_size=25,
    )

    assert progress.percent_complete == 75.0
    assert progress.success_rate == (740 / 750) * 100
    assert progress.is_complete is False

    # Test completed status
    completed_progress = BackfillProgress(
        progress_id="backfill_002",
        status="completed",
        started_at=datetime.utcnow(),
        completed_at=datetime.utcnow(),
        total_nodes=100,
        processed_nodes=100,
        failed_nodes=0,
        worker_count=3,
        batch_size=25,
    )
    assert completed_progress.percent_complete == 100.0
    assert completed_progress.success_rate == 100.0
    assert completed_progress.is_complete is True


def test_embedding_error_validation():
    """Test EmbeddingError model validation."""
    error = EmbeddingError(
        error_type="connection_error",
        error_message="Connection refused",
        memory_id="mem_001",
        retry_count=2,
        recoverable=True,
    )

    assert error.error_type == "connection_error"
    assert error.recoverable is True
    assert error.retry_count == 2


def test_embedding_error_types():
    """Test all valid error types."""
    valid_types = [
        "connection_error",
        "model_error",
        "timeout",
        "validation_error",
        "unknown",
    ]

    for error_type in valid_types:
        error = EmbeddingError(
            error_type=error_type,
            error_message="Test error",
            recoverable=True,
        )
        assert error.error_type == error_type

    # Invalid type should fail
    with pytest.raises(ValidationError):
        EmbeddingError(
            error_type="invalid_type",
            error_message="Test",
            recoverable=True,
        )


def test_extracted_memory_with_embeddings():
    """Test ExtractedMemory model with embedding fields."""
    memory = ExtractedMemory(
        memory_id="mem_001",
        memory_type="preference",
        content="Test content",
        confidence=0.92,
        source_conversation_id="conv_123",
        embedding=[0.01] * 768,
        has_embedding=True,
        embedding_version="nomic-embed-text-v1",
        embedding_updated_at=datetime.utcnow(),
    )

    assert memory.has_embedding is True
    assert len(memory.embedding) == 768
    assert memory.embedding_version == "nomic-embed-text-v1"
    assert memory.embedding_updated_at is not None


def test_extracted_memory_without_embeddings():
    """Test ExtractedMemory model without embeddings."""
    memory = ExtractedMemory(
        memory_id="mem_001",
        memory_type="preference",
        content="Test content",
        confidence=0.92,
        source_conversation_id="conv_123",
    )

    assert memory.has_embedding is False
    assert memory.embedding is None
    assert memory.embedding_version is None
    assert memory.embedding_updated_at is None
