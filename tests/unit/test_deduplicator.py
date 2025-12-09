"""Unit tests for memory deduplication.

Following TDD - these tests should FAIL initially before implementation.
"""

import pytest
from datetime import datetime

from haia.context.deduplicator import Deduplicator
from haia.context.models import DeduplicationResult
from haia.embedding.models import RetrievalResult
from haia.extraction.models import ExtractedMemory


# Test fixtures
@pytest.fixture
def sample_memories_exact_duplicates():
    """Create sample memories with exact duplicates."""
    # Create truly orthogonal embeddings for different content
    embedding_1 = [1.0 if i < 384 else 0.0 for i in range(768)]  # First half 1, second half 0
    embedding_2 = [0.0 if i < 384 else 1.0 for i in range(768)]  # First half 0, second half 1

    memories = [
        RetrievalResult(
            memory=ExtractedMemory(
                memory_id="mem_1",
                memory_type="preference",
                content="User prefers Docker for containerization",
                confidence=0.9,
                source_conversation_id="conv_1",
                embedding=embedding_1,  # Same embedding for duplicate
                has_embedding=True,
            ),
            similarity_score=0.95,
            relevance_score=0.93,
            rank=1,
        ),
        RetrievalResult(
            memory=ExtractedMemory(
                memory_id="mem_2",
                memory_type="preference",
                content="User prefers Docker for containerization",  # Exact duplicate
                confidence=0.85,
                source_conversation_id="conv_1",
                embedding=embedding_1,  # Same embedding
                has_embedding=True,
            ),
            similarity_score=0.94,
            relevance_score=0.90,
            rank=2,
        ),
        RetrievalResult(
            memory=ExtractedMemory(
                memory_id="mem_3",
                memory_type="technical_context",
                content="User has a Proxmox VE cluster with 3 nodes",
                confidence=0.88,
                source_conversation_id="conv_1",
                embedding=embedding_2,  # Orthogonal embedding (similarity ~0)
                has_embedding=True,
            ),
            similarity_score=0.87,
            relevance_score=0.88,
            rank=3,
        ),
    ]
    return memories


@pytest.fixture
def sample_memories_semantic_similar():
    """Create sample memories with semantic similarity."""
    # Create embeddings with controlled similarity
    # Normalize to have unit length for proper cosine similarity
    import math
    import random

    # Base vector for Python preference - random but consistent
    random.seed(42)
    base_vec = [random.random() for _ in range(768)]
    norm = math.sqrt(sum(x**2 for x in base_vec))
    embedding_1 = [x/norm for x in base_vec]

    # Similar vector - same base with 15% of components flipped/modified
    # This should give ~0.93-0.96 similarity (not exact duplicate 0.999+)
    similar_vec = base_vec.copy()
    flip_indices = random.sample(range(768), 115)  # Flip ~15% of values
    for idx in flip_indices:
        similar_vec[idx] = random.random()  # Replace with new random value
    norm2 = math.sqrt(sum(x**2 for x in similar_vec))
    embedding_2 = [x/norm2 for x in similar_vec]

    # Very different vector (orthogonal) - will have ~0 similarity
    different_vec = [0.0 if i < 384 else 1.0 for i in range(768)]
    norm3 = math.sqrt(sum(x**2 for x in different_vec))
    embedding_3 = [x/norm3 for x in different_vec]

    memories = [
        RetrievalResult(
            memory=ExtractedMemory(
                memory_id="mem_1",
                memory_type="preference",
                content="User prefers Python for scripting",
                confidence=0.92,
                source_conversation_id="conv_1",
                embedding=embedding_1,
                has_embedding=True,
            ),
            similarity_score=0.95,
            relevance_score=0.94,
            rank=1,
        ),
        RetrievalResult(
            memory=ExtractedMemory(
                memory_id="mem_2",
                memory_type="preference",
                content="Python is user's preferred scripting language",  # Semantically similar
                confidence=0.88,
                source_conversation_id="conv_1",
                embedding=embedding_2,  # Very similar embedding (>0.92)
                has_embedding=True,
            ),
            similarity_score=0.93,
            relevance_score=0.91,
            rank=2,
        ),
        RetrievalResult(
            memory=ExtractedMemory(
                memory_id="mem_3",
                memory_type="preference",
                content="User also uses Bash for automation",  # Different topic
                confidence=0.85,
                source_conversation_id="conv_1",
                embedding=embedding_3,  # Very different embedding
                has_embedding=True,
            ),
            similarity_score=0.80,
            relevance_score=0.83,
            rank=3,
        ),
    ]
    return memories


@pytest.fixture
def sample_memories_with_correction():
    """Create sample memories with correction superseding old memory."""
    # Use similar embeddings (they refer to same topic)
    embedding = [1.0 if i < 384 else 0.0 for i in range(768)]

    memories = [
        RetrievalResult(
            memory=ExtractedMemory(
                memory_id="mem_old",
                memory_type="technical_context",
                content="User has 3 Proxmox nodes",
                confidence=0.85,
                source_conversation_id="conv_1",
                extraction_timestamp=datetime(2025, 11, 1, 10, 0),
                embedding=embedding,
                has_embedding=True,
            ),
            similarity_score=0.88,
            relevance_score=0.87,
            rank=2,
        ),
        RetrievalResult(
            memory=ExtractedMemory(
                memory_id="mem_correction",
                memory_type="correction",
                content="User actually has 4 Proxmox nodes, not 3",
                confidence=0.80,  # Corrections get fixed 0.8 confidence
                source_conversation_id="conv_2",
                extraction_timestamp=datetime(2025, 12, 1, 10, 0),
                metadata={"supersedes": "mem_old"},
                embedding=embedding,
                has_embedding=True,
            ),
            similarity_score=0.90,
            relevance_score=0.85,
            rank=1,
        ),
    ]
    return memories


@pytest.fixture
def deduplicator():
    """Create Deduplicator instance."""
    return Deduplicator()


# Test cases for T017: Exact duplicates
@pytest.mark.asyncio
async def test_deduplicate_exact_duplicates(deduplicator, sample_memories_exact_duplicates):
    """Test deduplication removes exact duplicate memories."""
    result = await deduplicator.deduplicate(
        memories=sample_memories_exact_duplicates,
        similarity_threshold=0.92,
    )

    # Should keep 2 unique memories (remove 1 exact duplicate)
    assert isinstance(result, DeduplicationResult)
    assert len(result.unique_memories) == 2
    assert result.duplicate_count == 1
    assert result.similar_count == 0
    assert result.superseded_count == 0
    assert result.total_removed == 1
    assert result.dedup_ratio == pytest.approx(0.333, rel=0.01)

    # Should keep the one with higher confidence (mem_1, not mem_2)
    memory_ids = [m.memory.memory_id for m in result.unique_memories]
    assert "mem_1" in memory_ids
    assert "mem_2" not in memory_ids  # Duplicate removed
    assert "mem_3" in memory_ids


# Test cases for T018: Semantic similarity
@pytest.mark.asyncio
async def test_deduplicate_semantic_similar(deduplicator, sample_memories_semantic_similar):
    """Test deduplication removes semantically similar memories (>0.92 threshold)."""
    result = await deduplicator.deduplicate(
        memories=sample_memories_semantic_similar,
        similarity_threshold=0.92,
    )

    # Should keep 2 unique memories (remove 1 semantically similar)
    assert len(result.unique_memories) == 2
    assert result.duplicate_count == 0  # Not exact duplicate
    assert result.similar_count == 1  # Semantic similarity
    assert result.superseded_count == 0
    assert result.total_removed == 1

    # Should keep mem_1 (higher confidence) and mem_3 (different topic)
    memory_ids = [m.memory.memory_id for m in result.unique_memories]
    assert "mem_1" in memory_ids
    assert "mem_2" not in memory_ids  # Similar removed
    assert "mem_3" in memory_ids

    # Check metadata includes removal reason
    assert "similarity_threshold" in result.dedup_metadata
    assert result.dedup_metadata["similarity_threshold"] == 0.92
    assert "removed_memory_ids" in result.dedup_metadata
    assert "mem_2" in result.dedup_metadata["removed_memory_ids"]


# Test cases for T019: Correction superseding
@pytest.mark.asyncio
async def test_deduplicate_correction_supersedes(deduplicator, sample_memories_with_correction):
    """Test that correction memories supersede older memories."""
    result = await deduplicator.deduplicate(
        memories=sample_memories_with_correction,
        similarity_threshold=0.92,
    )

    # Should keep only the correction, remove old memory
    assert len(result.unique_memories) == 1
    assert result.duplicate_count == 0
    assert result.similar_count == 0
    assert result.superseded_count == 1
    assert result.total_removed == 1

    # Should keep correction, not old memory
    memory_ids = [m.memory.memory_id for m in result.unique_memories]
    assert "mem_correction" in memory_ids
    assert "mem_old" not in memory_ids

    # Check metadata
    assert "removal_reasons" in result.dedup_metadata
    assert "mem_old" in result.dedup_metadata["removal_reasons"]
    assert "superseded" in result.dedup_metadata["removal_reasons"]["mem_old"]


# Test cases for T020: Partial overlap
@pytest.mark.asyncio
async def test_deduplicate_partial_overlap_preserved(deduplicator):
    """Test that partially overlapping memories are preserved."""
    import math

    # Create embeddings with similarity < 0.92 (should NOT be removed)
    # Use different patterns that result in ~0.7-0.8 similarity
    vec1 = [1.0 if i % 3 == 0 else 0.3 for i in range(768)]
    norm1 = math.sqrt(sum(x**2 for x in vec1))
    embedding_1 = [x/norm1 for x in vec1]

    vec2 = [1.0 if i % 3 == 1 else 0.3 for i in range(768)]
    norm2 = math.sqrt(sum(x**2 for x in vec2))
    embedding_2 = [x/norm2 for x in vec2]

    memories = [
        RetrievalResult(
            memory=ExtractedMemory(
                memory_id="mem_1",
                memory_type="preference",
                content="User prefers Python and Rust",
                confidence=0.90,
                source_conversation_id="conv_1",
                embedding=embedding_1,
                has_embedding=True,
            ),
            similarity_score=0.95,
            relevance_score=0.93,
            rank=1,
        ),
        RetrievalResult(
            memory=ExtractedMemory(
                memory_id="mem_2",
                memory_type="preference",
                content="User prefers Python for data analysis",
                confidence=0.88,
                source_conversation_id="conv_1",
                embedding=embedding_2,  # Different enough (<0.92)
                has_embedding=True,
            ),
            similarity_score=0.90,
            relevance_score=0.89,
            rank=2,
        ),
    ]

    result = await deduplicator.deduplicate(
        memories=memories,
        similarity_threshold=0.92,
    )

    # Should keep both (partial overlap, but <0.92 similarity)
    assert len(result.unique_memories) == 2
    assert result.total_removed == 0


# Test cases for T021: Edge cases
@pytest.mark.asyncio
async def test_deduplicate_empty_list(deduplicator):
    """Test deduplication with empty memory list."""
    with pytest.raises(ValueError, match="At least one memory required"):
        await deduplicator.deduplicate(memories=[], similarity_threshold=0.92)


@pytest.mark.asyncio
async def test_deduplicate_single_memory(deduplicator):
    """Test deduplication with single memory."""
    memories = [
        RetrievalResult(
            memory=ExtractedMemory(
                memory_id="mem_1",
                memory_type="preference",
                content="User prefers Docker",
                confidence=0.90,
                source_conversation_id="conv_1",
                embedding=[0.1] * 768,
                has_embedding=True,
            ),
            similarity_score=0.95,
            relevance_score=0.93,
            rank=1,
        ),
    ]

    result = await deduplicator.deduplicate(
        memories=memories,
        similarity_threshold=0.92,
    )

    # Should return single memory unchanged
    assert len(result.unique_memories) == 1
    assert result.total_removed == 0
    assert result.unique_memories[0].memory.memory_id == "mem_1"


@pytest.mark.asyncio
async def test_deduplicate_missing_embeddings(deduplicator):
    """Test deduplication handles gracefully with missing embeddings.

    When memories lack embeddings, they are excluded from deduplication
    but still returned in the final result.
    """
    memories = [
        RetrievalResult(
            memory=ExtractedMemory(
                memory_id="mem_1",
                memory_type="preference",
                content="User prefers Docker",
                confidence=0.90,
                source_conversation_id="conv_1",
                embedding=None,  # Missing embedding
                has_embedding=False,
            ),
            similarity_score=0.95,
            relevance_score=0.93,
            rank=1,
        ),
    ]

    # Should not raise, but should skip deduplication
    result = await deduplicator.deduplicate(memories=memories, similarity_threshold=0.92)

    # Memory is returned as-is (no deduplication possible without embeddings)
    assert len(result.unique_memories) == 1
    assert result.duplicate_count == 0
    assert result.similar_count == 0
    assert result.superseded_count == 0


@pytest.mark.asyncio
async def test_deduplicate_invalid_threshold(deduplicator):
    """Test deduplication with invalid threshold."""
    memories = [
        RetrievalResult(
            memory=ExtractedMemory(
                memory_id="mem_1",
                memory_type="preference",
                content="User prefers Docker",
                confidence=0.90,
                source_conversation_id="conv_1",
                embedding=[0.1] * 768,
                has_embedding=True,
            ),
            similarity_score=0.95,
            relevance_score=0.93,
            rank=1,
        ),
    ]

    # Test threshold < 0
    with pytest.raises(ValueError, match="Threshold must be between 0.0 and 1.0"):
        await deduplicator.deduplicate(memories=memories, similarity_threshold=-0.1)

    # Test threshold > 1.0
    with pytest.raises(ValueError, match="Threshold must be between 0.0 and 1.0"):
        await deduplicator.deduplicate(memories=memories, similarity_threshold=1.5)


@pytest.mark.asyncio
async def test_deduplicate_idempotent(deduplicator, sample_memories_exact_duplicates):
    """Test that deduplication is idempotent: deduplicate(deduplicate(X)) == deduplicate(X)."""
    result1 = await deduplicator.deduplicate(
        memories=sample_memories_exact_duplicates,
        similarity_threshold=0.92,
    )

    # Apply deduplication again to already deduplicated results
    result2 = await deduplicator.deduplicate(
        memories=result1.unique_memories,
        similarity_threshold=0.92,
    )

    # Should be identical (no more duplicates to remove)
    assert len(result2.unique_memories) == len(result1.unique_memories)
    assert result2.total_removed == 0
    assert result2.duplicate_count == 0
    assert result2.similar_count == 0
