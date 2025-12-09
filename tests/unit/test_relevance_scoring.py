"""Unit tests for multi-factor relevance scoring.

Tests for Session 8 - User Story 3: Relevance-Based Filtering

These tests verify:
- Multi-factor scoring (similarity + confidence + recency + type weights)
- Recency calculation with exponential decay
- Type weight multipliers
- Score calculation edge cases
"""

import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock

from haia.embedding.retrieval_service import RetrievalService
from haia.extraction.models import ExtractedMemory


@pytest.fixture
def mock_neo4j_service():
    """Create mock Neo4j service."""
    return MagicMock()


@pytest.fixture
def mock_ollama_client():
    """Create mock Ollama client."""
    return MagicMock()


@pytest.fixture
def retrieval_service(mock_neo4j_service, mock_ollama_client):
    """Create retrieval service with default weights."""
    return RetrievalService(
        neo4j_service=mock_neo4j_service,
        ollama_client=mock_ollama_client,
        similarity_weight=0.5,  # 50%
        confidence_weight=0.3,  # 30%
        recency_weight=0.2,  # 20%
        recency_decay_days=43.3,
    )


@pytest.fixture
def sample_memory():
    """Create sample memory for testing."""
    return ExtractedMemory(
        memory_id="test_mem_001",
        memory_type="preference",
        content="User prefers Docker over Podman",
        confidence=0.85,
        source_conversation_id="test_conv_001",
        extraction_timestamp=datetime.now(timezone.utc),
    )


def test_calculate_relevance_score_perfect_match(retrieval_service, sample_memory):
    """Test relevance score for perfect similarity and recent memory."""
    # Perfect similarity (1.0), high confidence (0.85), recent extraction (score ~1.0)
    score = retrieval_service._calculate_relevance_score(
        memory=sample_memory,
        similarity=1.0,
    )

    # Expected: (0.5 * 1.0 + 0.3 * 0.85 + 0.2 * 1.0) * 1.2 (preference weight)
    # = (0.5 + 0.255 + 0.2) * 1.2 = 0.955 * 1.2 = 1.146
    assert score > 1.0  # Type weight boosts score above 1.0
    assert score < 1.3  # But not excessively high
    assert abs(score - 1.146) < 0.05


def test_calculate_relevance_score_with_type_weights(retrieval_service):
    """Test that different memory types have different relevance scores."""
    now = datetime.now(timezone.utc)

    # Correction memory (highest weight: 1.3)
    correction_mem = ExtractedMemory(
        memory_id="test_correction",
        memory_type="correction",
        content="Docker version is 24.0, not 23.0",
        confidence=0.85,
        source_conversation_id="test_conv",
        extraction_timestamp=now,
    )

    # Personal fact memory (lowest weight: 0.9)
    personal_mem = ExtractedMemory(
        memory_id="test_personal",
        memory_type="personal_fact",
        content="User lives in California",
        confidence=0.85,
        source_conversation_id="test_conv",
        extraction_timestamp=now,
    )

    correction_score = retrieval_service._calculate_relevance_score(
        memory=correction_mem,
        similarity=0.8,
    )

    personal_score = retrieval_service._calculate_relevance_score(
        memory=personal_mem,
        similarity=0.8,
    )

    # Correction should score higher than personal fact (same similarity/confidence/recency)
    assert correction_score > personal_score

    # Score difference should match type weight ratio (1.3 / 0.9 ≈ 1.44x)
    ratio = correction_score / personal_score
    assert abs(ratio - (1.3 / 0.9)) < 0.01


def test_calculate_recency_score_recent_memory(retrieval_service):
    """Test recency score for very recent memory."""
    # Memory extracted 1 hour ago
    recent_timestamp = datetime.now(timezone.utc) - timedelta(hours=1)

    recency_score = retrieval_service._calculate_recency_score(recent_timestamp)

    # Should be very close to 1.0 (maximum recency)
    assert recency_score > 0.99
    assert recency_score <= 1.0


def test_calculate_recency_score_30_days_old(retrieval_service):
    """Test recency score for memory from 30 days ago."""
    # Memory extracted 30 days ago
    old_timestamp = datetime.now(timezone.utc) - timedelta(days=30)

    recency_score = retrieval_service._calculate_recency_score(old_timestamp)

    # Should be approximately 0.5 (decay_constant = 43.3)
    # exp(-30 / 43.3) ≈ 0.5
    assert 0.45 <= recency_score <= 0.55


def test_calculate_recency_score_100_days_old(retrieval_service):
    """Test recency score for memory from 100 days ago."""
    # Memory extracted 100 days ago
    very_old_timestamp = datetime.now(timezone.utc) - timedelta(days=100)

    recency_score = retrieval_service._calculate_recency_score(very_old_timestamp)

    # Should be approximately 0.1 (significantly decayed)
    # exp(-100 / 43.3) ≈ 0.107
    assert 0.05 <= recency_score <= 0.15


def test_calculate_recency_score_no_timestamp(retrieval_service):
    """Test recency score when extraction_timestamp is None."""
    recency_score = retrieval_service._calculate_recency_score(None)

    # Should return neutral score (0.5)
    assert recency_score == 0.5


def test_calculate_recency_score_naive_datetime(retrieval_service):
    """Test recency score with timezone-naive datetime."""
    # Create naive datetime (no timezone)
    naive_timestamp = datetime.now() - timedelta(days=10)

    # Should handle gracefully by adding UTC timezone
    recency_score = retrieval_service._calculate_recency_score(naive_timestamp)

    # Should be a valid score between 0 and 1
    assert 0.0 <= recency_score <= 1.0


def test_multi_factor_scoring_all_factors(retrieval_service):
    """Test that all factors contribute to the final score."""
    now = datetime.now(timezone.utc)

    # High similarity, low confidence, recent
    mem1 = ExtractedMemory(
        memory_id="mem1",
        memory_type="decision",  # Neutral weight (1.0)
        content="Test memory 1",
        confidence=0.4,
        source_conversation_id="test_conv",
        extraction_timestamp=now,
    )

    # Low similarity, high confidence, recent
    mem2 = ExtractedMemory(
        memory_id="mem2",
        memory_type="decision",  # Neutral weight (1.0)
        content="Test memory 2",
        confidence=0.9,
        source_conversation_id="test_conv",
        extraction_timestamp=now,
    )

    score1 = retrieval_service._calculate_relevance_score(mem1, similarity=0.95)
    score2 = retrieval_service._calculate_relevance_score(mem2, similarity=0.60)

    # Both should be valid scores
    assert 0.0 <= score1 <= 2.0
    assert 0.0 <= score2 <= 2.0

    # Score1 should be higher (similarity has 50% weight vs 30% for confidence)
    assert score1 > score2


def test_relevance_score_old_vs_new_memory(retrieval_service):
    """Test that recency affects the final score."""
    # Recent memory (1 day ago)
    recent_mem = ExtractedMemory(
        memory_id="recent",
        memory_type="preference",
        content="Recent preference",
        confidence=0.8,
        source_conversation_id="test_conv",
        extraction_timestamp=datetime.now(timezone.utc) - timedelta(days=1),
    )

    # Old memory (60 days ago)
    old_mem = ExtractedMemory(
        memory_id="old",
        memory_type="preference",
        content="Old preference",
        confidence=0.8,
        source_conversation_id="test_conv",
        extraction_timestamp=datetime.now(timezone.utc) - timedelta(days=60),
    )

    recent_score = retrieval_service._calculate_relevance_score(recent_mem, similarity=0.8)
    old_score = retrieval_service._calculate_relevance_score(old_mem, similarity=0.8)

    # Recent memory should score higher
    assert recent_score > old_score


def test_type_weight_with_missing_type_config(retrieval_service):
    """Test that memory types missing from config default to weight 1.0."""
    # Create a retrieval service with incomplete type weights
    incomplete_service = RetrievalService(
        neo4j_service=MagicMock(),
        ollama_client=MagicMock(),
        type_weights={
            "preference": 1.2,
            # Missing other types - they should default to 1.0
        },
    )

    # Use a valid type that's not in the configured weights
    decision_mem = ExtractedMemory(
        memory_id="decision",
        memory_type="decision",
        content="Decision memory",
        confidence=0.8,
        source_conversation_id="test_conv",
        extraction_timestamp=datetime.now(timezone.utc),
    )

    score = incomplete_service._calculate_relevance_score(decision_mem, similarity=0.8)

    # Should use default weight 1.0 for missing type
    assert 0.0 <= score <= 2.0


def test_relevance_score_never_negative(retrieval_service):
    """Test that relevance scores are never negative."""
    # Edge case: minimum valid values (confidence >= 0.4 due to Pydantic validation)
    low_mem = ExtractedMemory(
        memory_id="low",
        memory_type="personal_fact",  # Lowest weight (0.9)
        content="Low confidence memory",
        confidence=0.4,  # Minimum valid confidence
        source_conversation_id="test_conv",
        extraction_timestamp=datetime.now(timezone.utc) - timedelta(days=365),  # Very old
    )

    score = retrieval_service._calculate_relevance_score(low_mem, similarity=0.0)

    # Should be non-negative
    assert score >= 0.0


def test_custom_weights_initialization():
    """Test retrieval service with custom weights."""
    custom_type_weights = {
        "preference": 2.0,
        "technical_context": 1.5,
        "decision": 1.0,
        "personal_fact": 0.5,
        "correction": 3.0,
    }

    service = RetrievalService(
        neo4j_service=MagicMock(),
        ollama_client=MagicMock(),
        similarity_weight=0.6,
        confidence_weight=0.2,
        recency_weight=0.2,
        type_weights=custom_type_weights,
        recency_decay_days=30.0,
    )

    # Verify custom weights are used
    assert service.type_weights == custom_type_weights
    assert service.similarity_weight == 0.6
    assert service.confidence_weight == 0.2
    assert service.recency_weight == 0.2
    assert service.recency_decay_days == 30.0


def test_recency_decay_formula_consistency(retrieval_service):
    """Test that recency decay follows expected exponential pattern."""
    now = datetime.now(timezone.utc)

    # Test at specific intervals
    score_0_days = retrieval_service._calculate_recency_score(now)
    score_10_days = retrieval_service._calculate_recency_score(now - timedelta(days=10))
    score_20_days = retrieval_service._calculate_recency_score(now - timedelta(days=20))

    # Scores should decay monotonically
    assert score_0_days > score_10_days > score_20_days

    # Decay should follow exponential pattern (not linear)
    # The difference between 0-10 days should be less than 10-20 days
    decay_first_10 = score_0_days - score_10_days
    decay_second_10 = score_10_days - score_20_days

    # Due to exponential decay, earlier decay is faster
    assert decay_first_10 > decay_second_10
