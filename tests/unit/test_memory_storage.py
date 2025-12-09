"""Unit tests for memory storage service with embedding support.

Tests for Session 8 embedding storage functionality including:
- Storing embeddings with memory nodes
- Updating memory nodes with embedding metadata
- Error handling for storage failures
"""

import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

from haia.services.memory_storage import MemoryStorageService
from haia.extraction.models import ExtractedMemory


@pytest.fixture
def mock_neo4j_service():
    """Create mock Neo4j service for testing."""
    service = MagicMock()
    service.driver = MagicMock()
    service.driver.session = MagicMock()
    return service


@pytest.fixture
def memory_storage_service(mock_neo4j_service):
    """Create memory storage service with mocked Neo4j."""
    return MemoryStorageService(neo4j_service=mock_neo4j_service)


@pytest.fixture
def sample_memory():
    """Create sample extracted memory for testing."""
    return ExtractedMemory(
        memory_id="test_mem_001",
        memory_type="preference",
        content="User prefers Docker over Kubernetes",
        confidence=0.85,
        source_conversation_id="conv_001",
        category="infrastructure",
    )


@pytest.fixture
def sample_embedding():
    """Create sample 768-dimensional embedding vector."""
    return [0.1] * 768


@pytest.mark.asyncio
async def test_store_embedding_success(memory_storage_service, mock_neo4j_service, sample_embedding):
    """Test successful embedding storage."""
    # Setup mock session
    mock_session = AsyncMock()
    mock_result = AsyncMock()
    mock_result.single = AsyncMock(return_value={"updated": True})
    mock_session.run = AsyncMock(return_value=mock_result)
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock()
    mock_neo4j_service.driver.session.return_value = mock_session

    # Execute
    result = await memory_storage_service.store_embedding(
        memory_id="test_mem_001",
        embedding=sample_embedding,
        embedding_version="nomic-embed-text-v1",
    )

    # Verify
    assert result is True
    mock_session.run.assert_called_once()

    # Verify query parameters
    call_args = mock_session.run.call_args
    assert call_args.kwargs["memory_id"] == "test_mem_001"
    assert call_args.kwargs["embedding"] == sample_embedding
    assert call_args.kwargs["embedding_version"] == "nomic-embed-text-v1"
    assert call_args.kwargs["has_embedding"] is True


@pytest.mark.asyncio
async def test_store_embedding_memory_not_found(memory_storage_service, mock_neo4j_service, sample_embedding):
    """Test embedding storage when memory doesn't exist."""
    # Setup mock session - return None (memory not found)
    mock_session = AsyncMock()
    mock_result = AsyncMock()
    mock_result.single = AsyncMock(return_value=None)
    mock_session.run = AsyncMock(return_value=mock_result)
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock()
    mock_neo4j_service.driver.session.return_value = mock_session

    # Execute
    result = await memory_storage_service.store_embedding(
        memory_id="nonexistent_memory",
        embedding=sample_embedding,
        embedding_version="nomic-embed-text-v1",
    )

    # Verify - should return False when memory not found
    assert result is False


@pytest.mark.asyncio
async def test_store_embedding_invalid_dimensions(memory_storage_service):
    """Test embedding storage with invalid vector dimensions."""
    invalid_embedding = [0.1] * 512  # Wrong dimensions (should be 768)

    # Should raise ValueError for incorrect dimensions
    with pytest.raises(ValueError, match="768"):
        await memory_storage_service.store_embedding(
            memory_id="test_mem_001",
            embedding=invalid_embedding,
            embedding_version="nomic-embed-text-v1",
        )


@pytest.mark.asyncio
async def test_store_embedding_empty_vector(memory_storage_service):
    """Test embedding storage with empty vector."""
    empty_embedding = []

    # Should raise ValueError for empty vector
    with pytest.raises(ValueError, match="cannot be empty"):
        await memory_storage_service.store_embedding(
            memory_id="test_mem_001",
            embedding=empty_embedding,
            embedding_version="nomic-embed-text-v1",
        )


@pytest.mark.asyncio
async def test_store_embedding_updates_metadata(memory_storage_service, mock_neo4j_service, sample_embedding):
    """Test that embedding storage updates all metadata fields."""
    # Setup mock
    mock_session = AsyncMock()
    mock_result = AsyncMock()
    mock_result.single = AsyncMock(return_value={"updated": True})
    mock_session.run = AsyncMock(return_value=mock_result)
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock()
    mock_neo4j_service.driver.session.return_value = mock_session

    # Execute
    await memory_storage_service.store_embedding(
        memory_id="test_mem_001",
        embedding=sample_embedding,
        embedding_version="nomic-embed-text-v1",
    )

    # Verify all metadata fields are set
    call_args = mock_session.run.call_args
    query = call_args.args[0]

    # Check query sets all required fields
    assert "has_embedding" in query
    assert "embedding_version" in query
    assert "embedding_updated_at" in query
    assert "embedding" in query


@pytest.mark.asyncio
async def test_store_embedding_database_error(memory_storage_service, mock_neo4j_service, sample_embedding):
    """Test embedding storage handles database errors gracefully."""
    # Setup mock to raise exception
    mock_session = AsyncMock()
    mock_session.run = AsyncMock(side_effect=Exception("Database connection failed"))
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock()
    mock_neo4j_service.driver.session.return_value = mock_session

    # Execute - should raise exception
    with pytest.raises(Exception, match="Database connection failed"):
        await memory_storage_service.store_embedding(
            memory_id="test_mem_001",
            embedding=sample_embedding,
            embedding_version="nomic-embed-text-v1",
        )


@pytest.mark.asyncio
async def test_store_embedding_with_memory_integration(memory_storage_service, mock_neo4j_service, sample_memory, sample_embedding):
    """Test storing embedding immediately after memory creation."""
    # Setup mock for both operations
    mock_session = AsyncMock()
    mock_result = AsyncMock()
    mock_result.single = AsyncMock(return_value={"memory_id": "test_mem_001"})
    mock_session.run = AsyncMock(return_value=mock_result)
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock()
    mock_neo4j_service.driver.session.return_value = mock_session

    # First create memory (mocked)
    mock_session.run.return_value.single = AsyncMock(return_value={"memory_id": "test_mem_001"})

    # Then store embedding
    result = await memory_storage_service.store_embedding(
        memory_id="test_mem_001",
        embedding=sample_embedding,
        embedding_version="nomic-embed-text-v1",
    )

    # Verify success
    assert result is True


@pytest.mark.asyncio
async def test_store_embedding_version_tracking(memory_storage_service, mock_neo4j_service, sample_embedding):
    """Test that embedding version is properly tracked."""
    # Setup mock
    mock_session = AsyncMock()
    mock_result = AsyncMock()
    mock_result.single = AsyncMock(return_value={"updated": True})
    mock_session.run = AsyncMock(return_value=mock_result)
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock()
    mock_neo4j_service.driver.session.return_value = mock_session

    # Execute with specific version
    version = "nomic-embed-text-v1.5"
    await memory_storage_service.store_embedding(
        memory_id="test_mem_001",
        embedding=sample_embedding,
        embedding_version=version,
    )

    # Verify version is passed correctly
    call_args = mock_session.run.call_args
    assert call_args.kwargs["embedding_version"] == version


@pytest.mark.asyncio
async def test_store_embedding_concurrent_updates(memory_storage_service, mock_neo4j_service, sample_embedding):
    """Test that concurrent embedding updates are handled safely."""
    # Setup mock
    mock_session = AsyncMock()
    mock_result = AsyncMock()
    mock_result.single = AsyncMock(return_value={"updated": True})
    mock_session.run = AsyncMock(return_value=mock_result)
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock()
    mock_neo4j_service.driver.session.return_value = mock_session

    # Execute multiple concurrent stores
    import asyncio
    results = await asyncio.gather(
        memory_storage_service.store_embedding("mem1", sample_embedding, "v1"),
        memory_storage_service.store_embedding("mem2", sample_embedding, "v1"),
        memory_storage_service.store_embedding("mem3", sample_embedding, "v1"),
    )

    # Verify all succeeded
    assert all(results)
    assert mock_session.run.call_count == 3
