"""Unit tests for embedding backfill worker.

Tests for Session 8 backfill functionality including:
- Batch processing of memories without embeddings
- Progress tracking and reporting
- Error handling and dead letter queue
- Concurrent worker coordination
"""

import asyncio
import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch, call

from haia.embedding.backfill_worker import EmbeddingBackfillWorker
from haia.extraction.models import ExtractedMemory


@pytest.fixture
def mock_neo4j_service():
    """Create mock Neo4j service."""
    service = MagicMock()
    service.driver = MagicMock()
    service.driver.session = MagicMock()
    service.get_memories_without_embeddings = AsyncMock(return_value=[])
    return service


@pytest.fixture
def mock_ollama_client():
    """Create mock Ollama client."""
    client = AsyncMock()
    client.embed = AsyncMock(return_value=[0.1] * 768)
    client.embed_batch = AsyncMock(return_value=[[0.1] * 768] * 10)
    client.health_check = AsyncMock(return_value=True)
    return client


@pytest.fixture
def mock_memory_storage():
    """Create mock memory storage service."""
    storage = AsyncMock()
    storage.store_embedding = AsyncMock(return_value=True)
    return storage


@pytest.fixture
def backfill_worker(mock_neo4j_service, mock_ollama_client, mock_memory_storage):
    """Create backfill worker with mocked dependencies."""
    return EmbeddingBackfillWorker(
        neo4j_service=mock_neo4j_service,
        ollama_client=mock_ollama_client,
        memory_storage=mock_memory_storage,
        batch_size=25,
        max_workers=2,
        embedding_version="nomic-embed-text-v1",
    )


@pytest.fixture
def sample_memories_batch():
    """Create sample batch of memories without embeddings."""
    return [
        {
            "memory_id": f"mem_{i:03d}",
            "content": f"Test memory content {i}",
            "memory_type": "preference",
            "confidence": 0.85,
            "source_conversation_id": f"conv_{i}",
        }
        for i in range(25)
    ]


@pytest.mark.asyncio
async def test_backfill_worker_initialization(backfill_worker):
    """Test backfill worker initializes with correct configuration."""
    assert backfill_worker.batch_size == 25
    assert backfill_worker.max_workers == 2
    assert backfill_worker.embedding_version == "nomic-embed-text-v1"
    assert backfill_worker.is_running is False
    assert backfill_worker.processed_count == 0
    assert backfill_worker.failed_count == 0


@pytest.mark.asyncio
async def test_backfill_worker_start_stop(backfill_worker):
    """Test backfill worker start and stop lifecycle."""
    # Start worker
    task = asyncio.create_task(backfill_worker.start())

    # Give it a moment to start
    await asyncio.sleep(0.1)
    assert backfill_worker.is_running is True

    # Stop worker
    await backfill_worker.stop()
    assert backfill_worker.is_running is False

    # Wait for task to complete
    await task


@pytest.mark.asyncio
async def test_process_batch_success(backfill_worker, mock_ollama_client, mock_memory_storage, sample_memories_batch):
    """Test successful batch processing."""
    # Process batch
    result = await backfill_worker.process_batch(sample_memories_batch)

    # Verify
    assert result["processed"] == 25
    assert result["failed"] == 0
    assert result["skipped"] == 0

    # Verify Ollama called for each memory
    assert mock_ollama_client.embed.call_count == 25

    # Verify storage called for each memory
    assert mock_memory_storage.store_embedding.call_count == 25


@pytest.mark.asyncio
async def test_process_batch_with_failures(backfill_worker, mock_ollama_client, mock_memory_storage, sample_memories_batch):
    """Test batch processing with some failures."""
    # Setup - make some embeddings fail
    mock_ollama_client.embed = AsyncMock(
        side_effect=[
            [0.1] * 768,  # Success
            Exception("Embedding failed"),  # Failure
            [0.1] * 768,  # Success
        ] * 9  # Repeat pattern
    )

    # Process batch (first 3 items)
    result = await backfill_worker.process_batch(sample_memories_batch[:3])

    # Verify - 2 successes, 1 failure
    assert result["processed"] == 2
    assert result["failed"] == 1


@pytest.mark.asyncio
async def test_process_batch_empty(backfill_worker):
    """Test processing empty batch."""
    result = await backfill_worker.process_batch([])

    # Verify
    assert result["processed"] == 0
    assert result["failed"] == 0
    assert result["skipped"] == 0


@pytest.mark.asyncio
async def test_get_next_batch(backfill_worker, mock_neo4j_service, sample_memories_batch):
    """Test fetching next batch of memories to process."""
    # Setup mock to return batch
    mock_neo4j_service.get_memories_without_embeddings = AsyncMock(
        return_value=sample_memories_batch
    )

    # Execute
    batch = await backfill_worker.get_next_batch()

    # Verify
    assert len(batch) == 25
    assert batch[0]["memory_id"] == "mem_000"
    mock_neo4j_service.get_memories_without_embeddings.assert_called_once_with(
        batch_size=25
    )


@pytest.mark.asyncio
async def test_get_next_batch_no_memories(backfill_worker, mock_neo4j_service):
    """Test fetching batch when no memories need processing."""
    # Setup mock to return empty list
    mock_neo4j_service.get_memories_without_embeddings = AsyncMock(return_value=[])

    # Execute
    batch = await backfill_worker.get_next_batch()

    # Verify
    assert len(batch) == 0


@pytest.mark.asyncio
async def test_progress_tracking(backfill_worker, mock_memory_storage, sample_memories_batch):
    """Test progress tracking during batch processing."""
    # Initial state
    assert backfill_worker.processed_count == 0
    assert backfill_worker.failed_count == 0

    # Process batch
    await backfill_worker.process_batch(sample_memories_batch[:10])

    # Verify progress updated
    assert backfill_worker.processed_count == 10
    assert backfill_worker.failed_count == 0


@pytest.mark.asyncio
async def test_progress_tracking_with_failures(backfill_worker, mock_ollama_client, sample_memories_batch):
    """Test progress tracking with failures."""
    # Setup - make all embeddings fail
    mock_ollama_client.embed = AsyncMock(side_effect=Exception("Always fails"))

    # Process batch
    await backfill_worker.process_batch(sample_memories_batch[:5])

    # Verify failure count updated
    assert backfill_worker.processed_count == 0
    assert backfill_worker.failed_count == 5


@pytest.mark.asyncio
async def test_get_progress_stats(backfill_worker):
    """Test getting progress statistics."""
    # Set some progress
    backfill_worker.processed_count = 100
    backfill_worker.failed_count = 5

    # Get stats
    stats = backfill_worker.get_progress()

    # Verify
    assert stats["processed"] == 100
    assert stats["failed"] == 5
    assert stats["total"] == 105
    assert stats["success_rate"] > 0.95
    assert "is_running" in stats


@pytest.mark.asyncio
async def test_dead_letter_queue_on_failure(backfill_worker, mock_ollama_client, sample_memories_batch):
    """Test that failed memories are added to dead letter queue."""
    # Setup - make embedding fail
    mock_ollama_client.embed = AsyncMock(side_effect=Exception("Embedding failed"))

    # Process batch
    await backfill_worker.process_batch(sample_memories_batch[:3])

    # Verify dead letter queue
    assert len(backfill_worker.dead_letter_queue) == 3
    assert backfill_worker.dead_letter_queue[0]["memory_id"] == "mem_000"


@pytest.mark.asyncio
async def test_retry_dead_letter_queue(backfill_worker, mock_ollama_client, sample_memories_batch):
    """Test retrying failed memories from dead letter queue."""
    # Setup - first fail, then succeed
    mock_ollama_client.embed = AsyncMock(
        side_effect=[
            Exception("First attempt fails"),
            [0.1] * 768,  # Second attempt succeeds
        ]
    )

    # First attempt - should fail
    await backfill_worker.process_batch(sample_memories_batch[:1])
    assert len(backfill_worker.dead_letter_queue) == 1

    # Retry dead letter queue
    result = await backfill_worker.retry_dead_letter_queue()

    # Verify success on retry
    assert result["processed"] == 1
    assert result["failed"] == 0
    assert len(backfill_worker.dead_letter_queue) == 0


@pytest.mark.asyncio
async def test_concurrent_batch_processing(backfill_worker, mock_memory_storage, sample_memories_batch):
    """Test processing multiple batches concurrently."""
    # Create multiple batches
    batch1 = sample_memories_batch[:10]
    batch2 = sample_memories_batch[10:20]

    # Process concurrently
    results = await asyncio.gather(
        backfill_worker.process_batch(batch1),
        backfill_worker.process_batch(batch2),
    )

    # Verify both completed
    assert results[0]["processed"] == 10
    assert results[1]["processed"] == 10
    assert backfill_worker.processed_count == 20


@pytest.mark.asyncio
async def test_backfill_worker_health_check(backfill_worker, mock_ollama_client, mock_neo4j_service):
    """Test backfill worker health check."""
    # Setup
    mock_ollama_client.health_check = AsyncMock(return_value=True)
    mock_neo4j_service.health_check = AsyncMock(return_value=True)

    # Execute
    health = await backfill_worker.health_check()

    # Verify
    assert health is True


@pytest.mark.asyncio
async def test_backfill_worker_health_check_ollama_down(backfill_worker, mock_ollama_client):
    """Test health check when Ollama is unavailable."""
    # Setup - Ollama down
    mock_ollama_client.health_check = AsyncMock(return_value=False)

    # Execute
    health = await backfill_worker.health_check()

    # Verify
    assert health is False


@pytest.mark.asyncio
async def test_backfill_worker_batch_size_limit(backfill_worker, sample_memories_batch):
    """Test that batch processing respects batch size limit."""
    # Create oversized batch
    oversized_batch = sample_memories_batch * 4  # 100 memories

    # Process - should handle gracefully
    result = await backfill_worker.process_batch(oversized_batch)

    # Verify all processed (worker handles large batches)
    assert result["processed"] == 100


@pytest.mark.asyncio
async def test_backfill_worker_stop_gracefully(backfill_worker, mock_neo4j_service, sample_memories_batch):
    """Test worker stops gracefully mid-processing."""
    # Setup - return infinite batches to keep worker running
    mock_neo4j_service.get_memories_without_embeddings = AsyncMock(
        side_effect=[sample_memories_batch, sample_memories_batch, []]
    )

    # Start worker
    task = asyncio.create_task(backfill_worker.start())

    # Let it process a bit
    await asyncio.sleep(0.2)

    # Stop worker
    await backfill_worker.stop()

    # Wait for task
    await task

    # Verify worker stopped
    assert backfill_worker.is_running is False


@pytest.mark.asyncio
async def test_embedding_version_passed_correctly(backfill_worker, mock_memory_storage, sample_memories_batch):
    """Test that embedding version is passed to storage correctly."""
    # Process batch
    await backfill_worker.process_batch(sample_memories_batch[:1])

    # Verify version passed to storage
    call_args = mock_memory_storage.store_embedding.call_args
    assert call_args.kwargs["embedding_version"] == "nomic-embed-text-v1"
