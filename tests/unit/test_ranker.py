"""Unit tests for Ranker (advanced re-ranking with access patterns).

Tests the multi-factor scoring algorithm:
- 40% similarity score
- 25% confidence score
- 20% recency score
- 15% frequency score

TDD: These tests should FAIL initially before implementation.
"""

import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

from haia.context.ranker import Ranker
from haia.context.models import ScoreWeights, AccessMetadata
from haia.embedding.models import RetrievalResult
from haia.extraction.models import ExtractedMemory


@pytest.fixture
def default_ranker():
    """Create ranker with default weights (40/25/20/15)."""
    return Ranker()


@pytest.fixture
def custom_ranker():
    """Create ranker with custom weights."""
    weights = ScoreWeights(
        similarity_weight=0.50,
        confidence_weight=0.30,
        recency_weight=0.10,
        frequency_weight=0.10,
    )
    return Ranker(weights=weights)


@pytest.fixture
def sample_results():
    """Create sample retrieval results for testing."""
    now = datetime.now(timezone.utc)

    results = [
        # High similarity, low recency/frequency
        RetrievalResult(
            memory=ExtractedMemory(
                memory_id="mem_001",
                memory_type="preference",
                content="Recent high-similarity memory",
                confidence=0.85,
                source_conversation_id="conv_001",
                extraction_timestamp=now - timedelta(days=1),
                category="test",
            ),
            similarity_score=0.95,
            relevance_score=0.90,  # Will be recalculated
            rank=1,  # Temporary, will be updated by rerank()
            access_metadata=AccessMetadata(
                memory_id="mem_001",
                last_accessed=now - timedelta(days=30),
                access_count=2,
            ),
        ),
        # Medium similarity, high frequency
        RetrievalResult(
            memory=ExtractedMemory(
                memory_id="mem_002",
                memory_type="technical_context",
                content="Frequently accessed memory",
                confidence=0.80,
                source_conversation_id="conv_002",
                extraction_timestamp=now - timedelta(days=30),
                category="test",
            ),
            similarity_score=0.75,
            relevance_score=0.70,
            rank=1,  # Temporary, will be updated by rerank()
            access_metadata=AccessMetadata(
                memory_id="mem_002",
                last_accessed=now - timedelta(hours=1),
                access_count=50,
            ),
        ),
        # Low similarity, very recent
        RetrievalResult(
            memory=ExtractedMemory(
                memory_id="mem_003",
                memory_type="decision",
                content="Very recent decision",
                confidence=0.90,
                source_conversation_id="conv_003",
                extraction_timestamp=now - timedelta(hours=2),
                category="test",
            ),
            similarity_score=0.65,
            relevance_score=0.60,
            rank=1,  # Temporary, will be updated by rerank()
            access_metadata=AccessMetadata(
                memory_id="mem_003",
                last_accessed=None,  # Never accessed
                access_count=0,
            ),
        ),
        # High confidence, old
        RetrievalResult(
            memory=ExtractedMemory(
                memory_id="mem_004",
                memory_type="correction",
                content="Old but high confidence correction",
                confidence=0.95,
                source_conversation_id="conv_004",
                extraction_timestamp=now - timedelta(days=180),
                category="test",
            ),
            similarity_score=0.70,
            relevance_score=0.65,
            rank=1,  # Temporary, will be updated by rerank()
            access_metadata=AccessMetadata(
                memory_id="mem_004",
                last_accessed=now - timedelta(days=90),
                access_count=5,
            ),
        ),
    ]

    return results


def test_ranker_initialization_default():
    """Test T034: Ranker initializes with default weights."""
    ranker = Ranker()

    # Verify default weights (40/25/20/15)
    assert ranker.weights.similarity_weight == 0.40
    assert ranker.weights.confidence_weight == 0.25
    assert ranker.weights.recency_weight == 0.20
    assert ranker.weights.frequency_weight == 0.15

    # Weights should sum to 1.0
    total = (
        ranker.weights.similarity_weight
        + ranker.weights.confidence_weight
        + ranker.weights.recency_weight
        + ranker.weights.frequency_weight
    )
    assert abs(total - 1.0) < 0.001


def test_ranker_initialization_custom():
    """Test T034: Ranker initializes with custom weights."""
    weights = ScoreWeights(
        similarity_weight=0.50,
        confidence_weight=0.30,
        recency_weight=0.10,
        frequency_weight=0.10,
    )
    ranker = Ranker(weights=weights)

    assert ranker.weights.similarity_weight == 0.50
    assert ranker.weights.confidence_weight == 0.30
    assert ranker.weights.recency_weight == 0.10
    assert ranker.weights.frequency_weight == 0.10


def test_calculate_recency_score():
    """Test T035: Recency score calculation with exponential decay."""
    ranker = Ranker()
    now = datetime.now(timezone.utc)

    # Very recent memory (1 hour ago) -> high score (~0.99)
    recent = now - timedelta(hours=1)
    recent_score = ranker._calculate_recency_score(recent)
    assert recent_score > 0.95

    # 30 days ago -> medium score (~0.5-0.65)
    medium = now - timedelta(days=30)
    medium_score = ranker._calculate_recency_score(medium)
    assert 0.4 < medium_score < 0.7

    # 180 days ago -> low score (~0.1)
    old = now - timedelta(days=180)
    old_score = ranker._calculate_recency_score(old)
    assert old_score < 0.2

    # Very old memory (1 year) -> near zero
    very_old = now - timedelta(days=365)
    very_old_score = ranker._calculate_recency_score(very_old)
    assert very_old_score < 0.05


def test_calculate_frequency_score():
    """Test T036: Frequency score with logarithmic scaling."""
    ranker = Ranker()

    # Never accessed -> 0.0
    assert ranker._calculate_frequency_score(0) == 0.0

    # Single access -> low score (~0.2-0.3)
    single_score = ranker._calculate_frequency_score(1)
    assert 0.15 < single_score < 0.35

    # 10 accesses -> medium-high score
    medium_score = ranker._calculate_frequency_score(10)
    assert 0.70 < medium_score < 0.85

    # 100 accesses -> high score
    high_score = ranker._calculate_frequency_score(100)
    assert 0.85 < high_score < 0.99

    # Very high (1000) -> near max
    very_high_score = ranker._calculate_frequency_score(1000)
    assert very_high_score > 0.90

    # Frequency should increase monotonically
    assert single_score < medium_score < high_score < very_high_score


def test_rerank_with_default_weights(default_ranker, sample_results):
    """Test T037: Re-ranking with default weights (40/25/20/15)."""
    ranked_results = default_ranker.rerank(sample_results)

    # Should return same number of results
    assert len(ranked_results) == len(sample_results)

    # Results should be sorted by composite score (descending)
    scores = [r.relevance_score for r in ranked_results]
    assert scores == sorted(scores, reverse=True)

    # Ranks should be updated (1, 2, 3, 4)
    ranks = [r.rank for r in ranked_results]
    assert ranks == [1, 2, 3, 4]

    # Top result should have highest composite score
    top_result = ranked_results[0]
    assert top_result.relevance_score > 0.5

    # Verify access_metadata is preserved
    for result in ranked_results:
        assert result.access_metadata is not None


def test_rerank_with_custom_weights(custom_ranker, sample_results):
    """Test T038: Re-ranking with custom weights changes ordering."""
    # Custom weights favor similarity (50%) over other factors
    ranked_results = custom_ranker.rerank(sample_results)

    # With higher similarity weight, mem_001 (0.95 similarity) should rank higher
    top_memory_id = ranked_results[0].memory.memory_id

    # Should still return all results
    assert len(ranked_results) == len(sample_results)

    # Ranks should be sequential
    assert [r.rank for r in ranked_results] == [1, 2, 3, 4]


def test_rerank_handles_missing_access_metadata(default_ranker):
    """Test T038: Re-ranking handles memories without access metadata."""
    now = datetime.now(timezone.utc)

    # Create results without access_metadata
    results = [
        RetrievalResult(
            memory=ExtractedMemory(
                memory_id="mem_no_access",
                memory_type="preference",
                content="Memory without access tracking",
                confidence=0.85,
                source_conversation_id="conv_001",
                extraction_timestamp=now - timedelta(days=10),
                category="test",
            ),
            similarity_score=0.80,
            relevance_score=0.75,
            rank=1,  # Temporary, will be updated by rerank()
            access_metadata=None,  # Missing metadata
        ),
    ]

    # Should not raise error, should use defaults (0 count, None last_accessed)
    ranked_results = default_ranker.rerank(results)

    assert len(ranked_results) == 1
    assert ranked_results[0].relevance_score > 0.0


def test_rerank_recency_decay(default_ranker):
    """Test T035: Recency decay affects final ranking."""
    now = datetime.now(timezone.utc)

    # Two identical memories, different extraction times
    results = [
        RetrievalResult(
            memory=ExtractedMemory(
                memory_id="mem_old",
                memory_type="preference",
                content="Old memory",
                confidence=0.85,
                source_conversation_id="conv_001",
                extraction_timestamp=now - timedelta(days=180),
                category="test",
            ),
            similarity_score=0.80,
            relevance_score=0.75,
            rank=1,  # Temporary, will be updated by rerank()
            access_metadata=AccessMetadata(
                memory_id="mem_old",
                last_accessed=None,
                access_count=0,
            ),
        ),
        RetrievalResult(
            memory=ExtractedMemory(
                memory_id="mem_recent",
                memory_type="preference",
                content="Recent memory",
                confidence=0.85,
                source_conversation_id="conv_002",
                extraction_timestamp=now - timedelta(hours=2),
                category="test",
            ),
            similarity_score=0.80,
            relevance_score=0.75,
            rank=1,  # Temporary, will be updated by rerank()
            access_metadata=AccessMetadata(
                memory_id="mem_recent",
                last_accessed=None,
                access_count=0,
            ),
        ),
    ]

    ranked_results = default_ranker.rerank(results)

    # Recent memory should rank higher due to recency factor
    assert ranked_results[0].memory.memory_id == "mem_recent"
    assert ranked_results[1].memory.memory_id == "mem_old"


def test_rerank_frequency_boost(default_ranker):
    """Test T036: Frequency boost affects final ranking."""
    now = datetime.now(timezone.utc)

    # Two identical memories, different access counts
    results = [
        RetrievalResult(
            memory=ExtractedMemory(
                memory_id="mem_rare",
                memory_type="preference",
                content="Rarely accessed",
                confidence=0.85,
                source_conversation_id="conv_001",
                extraction_timestamp=now - timedelta(days=30),
                category="test",
            ),
            similarity_score=0.80,
            relevance_score=0.75,
            rank=1,  # Temporary, will be updated by rerank()
            access_metadata=AccessMetadata(
                memory_id="mem_rare",
                last_accessed=now - timedelta(days=30),
                access_count=1,
            ),
        ),
        RetrievalResult(
            memory=ExtractedMemory(
                memory_id="mem_frequent",
                memory_type="preference",
                content="Frequently accessed",
                confidence=0.85,
                source_conversation_id="conv_002",
                extraction_timestamp=now - timedelta(days=30),
                category="test",
            ),
            similarity_score=0.80,
            relevance_score=0.75,
            rank=1,  # Temporary, will be updated by rerank()
            access_metadata=AccessMetadata(
                memory_id="mem_frequent",
                last_accessed=now - timedelta(hours=1),
                access_count=100,
            ),
        ),
    ]

    ranked_results = default_ranker.rerank(results)

    # Frequently accessed memory should rank higher
    assert ranked_results[0].memory.memory_id == "mem_frequent"
    assert ranked_results[1].memory.memory_id == "mem_rare"


def test_rerank_empty_list(default_ranker):
    """Test T038: Re-ranking empty list returns empty list."""
    ranked_results = default_ranker.rerank([])
    assert ranked_results == []


def test_rerank_single_item(default_ranker, sample_results):
    """Test T038: Re-ranking single item works correctly."""
    single_result = [sample_results[0]]
    ranked_results = default_ranker.rerank(single_result)

    assert len(ranked_results) == 1
    assert ranked_results[0].rank == 1
    assert ranked_results[0].relevance_score > 0.0


def test_rerank_preserves_original_scores(default_ranker, sample_results):
    """Test T037: Original similarity/confidence scores are preserved."""
    original_similarities = [r.similarity_score for r in sample_results]
    original_confidences = [r.memory.confidence for r in sample_results]

    ranked_results = default_ranker.rerank(sample_results)

    # Map results by memory_id to compare
    original_by_id = {r.memory.memory_id: r for r in sample_results}
    ranked_by_id = {r.memory.memory_id: r for r in ranked_results}

    for memory_id in original_by_id:
        assert ranked_by_id[memory_id].similarity_score == original_by_id[memory_id].similarity_score
        assert ranked_by_id[memory_id].memory.confidence == original_by_id[memory_id].memory.confidence


def test_rerank_idempotent(default_ranker, sample_results):
    """Test T038: Re-ranking is idempotent (same input -> same output)."""
    ranked_1 = default_ranker.rerank(sample_results.copy())
    ranked_2 = default_ranker.rerank(sample_results.copy())

    # Should produce identical rankings
    ids_1 = [r.memory.memory_id for r in ranked_1]
    ids_2 = [r.memory.memory_id for r in ranked_2]
    assert ids_1 == ids_2

    scores_1 = [r.relevance_score for r in ranked_1]
    scores_2 = [r.relevance_score for r in ranked_2]
    assert scores_1 == scores_2
