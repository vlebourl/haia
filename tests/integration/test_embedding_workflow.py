"""Integration tests for embedding generation workflow.

Tests for Session 8 - User Story 2: Automatic Embedding Generation

These tests require:
- Ollama service running at localhost:11434
- Neo4j database running
- nomic-embed-text model available in Ollama

Run with: RUN_INTEGRATION_TESTS=1 NEO4J_PASSWORD=haia_neo4j_secure_2024 \\
          uv run pytest tests/integration/test_embedding_workflow.py -v
"""

import asyncio
import os
import pytest
from datetime import datetime

from haia.config import settings
from haia.embedding.ollama_client import OllamaClient
from haia.embedding.backfill_worker import EmbeddingBackfillWorker
from haia.extraction.models import ExtractedMemory
from haia.services.memory_storage import MemoryStorageService
from haia.services.neo4j import Neo4jService


# Skip integration tests if environment variable not set
pytestmark = pytest.mark.skipif(
    os.getenv("RUN_INTEGRATION_TESTS") != "1",
    reason="Integration tests require RUN_INTEGRATION_TESTS=1 environment variable"
)


@pytest.fixture
async def neo4j_service():
    """Create and connect to Neo4j service."""
    service = Neo4jService(
        uri=settings.neo4j_uri,
        user=settings.neo4j_user,
        password=settings.neo4j_password,
    )
    await service.connect()

    yield service

    await service.close()


@pytest.fixture
async def ollama_client():
    """Create Ollama client."""
    client = OllamaClient(
        base_url=settings.ollama_base_url,
        model="nomic-embed-text",
        timeout=30.0,
        max_retries=3,
    )

    # Verify Ollama is available
    health = await client.health_check()
    if not health:
        pytest.skip("Ollama service not available")

    yield client

    await client.close()


@pytest.fixture
async def memory_storage(neo4j_service):
    """Create memory storage service."""
    return MemoryStorageService(neo4j_service=neo4j_service)


@pytest.fixture
async def sample_memory():
    """Create sample extracted memory for testing."""
    return ExtractedMemory(
        memory_id=f"test_emb_wf_{datetime.now().timestamp()}",
        memory_type="preference",
        content="User prefers automated testing with pytest and comprehensive coverage",
        confidence=0.88,
        source_conversation_id="test_conv_embedding_wf",
        category="testing",
    )


@pytest.mark.asyncio
async def test_embedding_workflow_end_to_end(neo4j_service, ollama_client, memory_storage, sample_memory):
    """Test complete embedding workflow: extract → store → embed → verify.

    This test validates User Story 2: Automatic Embedding Generation
    """
    memory_id = sample_memory.memory_id

    try:
        # Step 1: Store memory in Neo4j (simulates extraction storage)
        # Manually create memory node
        query = """
        CREATE (m:Memory {
            id: $memory_id,
            type: $memory_type,
            content: $content,
            confidence: $confidence,
            category: $category,
            created_at: datetime()
        })
        RETURN m.id as memory_id
        """

        async with neo4j_service.driver.session() as session:
            result = await session.run(
                query,
                memory_id=sample_memory.memory_id,
                memory_type=sample_memory.memory_type,
                content=sample_memory.content,
                confidence=sample_memory.confidence,
                category=sample_memory.category,
            )
            record = await result.single()
            assert record is not None
            assert record["memory_id"] == memory_id

        print(f"✓ Memory stored: {memory_id}")

        # Step 2: Generate embedding
        embedding = await ollama_client.embed(sample_memory.content)

        assert len(embedding) == 768
        assert all(isinstance(x, float) for x in embedding)
        print(f"✓ Embedding generated: {len(embedding)} dimensions")

        # Step 3: Store embedding with memory
        success = await memory_storage.store_embedding(
            memory_id=memory_id,
            embedding=embedding,
            embedding_version="nomic-embed-text-v1",
        )

        assert success is True
        print(f"✓ Embedding stored for memory {memory_id}")

        # Step 4: Verify memory has embedding in Neo4j
        verify_query = """
        MATCH (m:Memory {id: $memory_id})
        RETURN
            m.id as memory_id,
            m.has_embedding as has_embedding,
            m.embedding_version as embedding_version,
            m.embedding_updated_at as embedding_updated_at,
            size(m.embedding) as embedding_size
        """

        async with neo4j_service.driver.session() as session:
            result = await session.run(verify_query, memory_id=memory_id)
            record = await result.single()

            assert record is not None
            assert record["memory_id"] == memory_id
            assert record["has_embedding"] is True
            assert record["embedding_version"] == "nomic-embed-text-v1"
            assert record["embedding_updated_at"] is not None
            assert record["embedding_size"] == 768

        print(f"✓ Memory verified in Neo4j with embedding")
        print(f"  - has_embedding: {record['has_embedding']}")
        print(f"  - embedding_version: {record['embedding_version']}")
        print(f"  - embedding_size: {record['embedding_size']}")

    finally:
        # Cleanup: Delete test memory
        cleanup_query = "MATCH (m:Memory {id: $memory_id}) DELETE m"
        async with neo4j_service.driver.session() as session:
            await session.run(cleanup_query, memory_id=memory_id)


@pytest.mark.asyncio
async def test_embedding_workflow_multiple_memories(neo4j_service, ollama_client, memory_storage):
    """Test embedding generation for multiple memories in batch."""
    memories = [
        ExtractedMemory(
            memory_id=f"test_batch_{i}_{datetime.now().timestamp()}",
            memory_type="preference",
            content=f"Test memory content {i} for batch embedding generation",
            confidence=0.85,
            source_conversation_id=f"test_conv_batch_{i}",
            category="testing",
        )
        for i in range(5)
    ]

    memory_ids = [m.memory_id for m in memories]

    try:
        # Store all memories
        for memory in memories:
            query = """
            CREATE (m:Memory {
                id: $memory_id,
                type: $memory_type,
                content: $content,
                confidence: $confidence,
                category: $category,
                created_at: datetime()
            })
            RETURN m.id
            """

            async with neo4j_service.driver.session() as session:
                await session.run(
                    query,
                    memory_id=memory.memory_id,
                    memory_type=memory.memory_type,
                    content=memory.content,
                    confidence=memory.confidence,
                    category=memory.category,
                )

        print(f"✓ Created {len(memories)} test memories")

        # Generate and store embeddings for all
        for memory in memories:
            embedding = await ollama_client.embed(memory.content)
            success = await memory_storage.store_embedding(
                memory_id=memory.memory_id,
                embedding=embedding,
                embedding_version="nomic-embed-text-v1",
            )
            assert success is True

        print(f"✓ Generated embeddings for all {len(memories)} memories")

        # Verify all have embeddings
        verify_query = """
        MATCH (m:Memory)
        WHERE m.id IN $memory_ids
        RETURN count(m) as total, count(CASE WHEN m.has_embedding = true THEN 1 END) as with_embeddings
        """

        async with neo4j_service.driver.session() as session:
            result = await session.run(verify_query, memory_ids=memory_ids)
            record = await result.single()

            assert record["total"] == len(memories)
            assert record["with_embeddings"] == len(memories)

        print(f"✓ All {len(memories)} memories have embeddings")

    finally:
        # Cleanup
        cleanup_query = "MATCH (m:Memory) WHERE m.id IN $memory_ids DELETE m"
        async with neo4j_service.driver.session() as session:
            await session.run(cleanup_query, memory_ids=memory_ids)


@pytest.mark.asyncio
async def test_backfill_worker_processes_memories_without_embeddings(neo4j_service, ollama_client, memory_storage):
    """Test backfill worker finds and processes memories without embeddings.

    This test validates backfilling functionality for existing Session 7 memories.
    """
    # Create memories WITHOUT embeddings
    memories = [
        {
            "memory_id": f"test_backfill_{i}_{datetime.now().timestamp()}",
            "content": f"Backfill test memory {i}",
            "memory_type": "preference",
            "confidence": 0.80,
        }
        for i in range(3)
    ]

    memory_ids = [m["memory_id"] for m in memories]

    try:
        # Store memories without embeddings
        for memory in memories:
            query = """
            CREATE (m:Memory {
                id: $memory_id,
                type: $memory_type,
                content: $content,
                confidence: $confidence,
                created_at: datetime()
            })
            RETURN m.id
            """

            async with neo4j_service.driver.session() as session:
                await session.run(
                    query,
                    memory_id=memory["memory_id"],
                    memory_type=memory["memory_type"],
                    content=memory["content"],
                    confidence=memory["confidence"],
                )

        print(f"✓ Created {len(memories)} memories without embeddings")

        # Verify they don't have embeddings
        check_query = """
        MATCH (m:Memory)
        WHERE m.id IN $memory_ids
        RETURN count(CASE WHEN m.has_embedding = true THEN 1 END) as with_embeddings
        """

        async with neo4j_service.driver.session() as session:
            result = await session.run(check_query, memory_ids=memory_ids)
            record = await result.single()
            assert record["with_embeddings"] == 0

        print("✓ Verified memories have no embeddings initially")

        # Create backfill worker
        worker = EmbeddingBackfillWorker(
            neo4j_service=neo4j_service,
            ollama_client=ollama_client,
            memory_storage=memory_storage,
            batch_size=10,
            embedding_version="nomic-embed-text-v1",
            poll_interval=1.0,  # Short interval for testing
        )

        # Get batch of memories to process
        batch = await worker.get_next_batch()

        # Filter to our test memories
        test_batch = [m for m in batch if m.get("memory_id") in memory_ids]

        assert len(test_batch) >= len(memories)
        print(f"✓ Backfill worker found {len(test_batch)} memories to process")

        # Process batch
        result = await worker.process_batch(test_batch)

        assert result["processed"] >= len(memories)
        assert result["failed"] == 0
        print(f"✓ Backfill processed {result['processed']} memories successfully")

        # Verify all now have embeddings
        async with neo4j_service.driver.session() as session:
            result = await session.run(check_query, memory_ids=memory_ids)
            record = await result.single()
            assert record["with_embeddings"] == len(memories)

        print(f"✓ All {len(memories)} memories now have embeddings after backfill")

    finally:
        # Cleanup
        cleanup_query = "MATCH (m:Memory) WHERE m.id IN $memory_ids DELETE m"
        async with neo4j_service.driver.session() as session:
            await session.run(cleanup_query, memory_ids=memory_ids)


@pytest.mark.asyncio
async def test_backfill_worker_progress_tracking(neo4j_service, ollama_client, memory_storage):
    """Test that backfill worker tracks progress correctly."""
    worker = EmbeddingBackfillWorker(
        neo4j_service=neo4j_service,
        ollama_client=ollama_client,
        memory_storage=memory_storage,
        batch_size=10,
        embedding_version="nomic-embed-text-v1",
    )

    # Initial progress
    progress = worker.get_progress()
    assert progress["processed"] == 0
    assert progress["failed"] == 0
    assert progress["total"] == 0
    assert progress["success_rate"] == 0.0

    print("✓ Initial progress state verified")

    # Create and process a test memory
    test_memory_id = f"test_progress_{datetime.now().timestamp()}"

    try:
        # Create memory without embedding
        query = """
        CREATE (m:Memory {
            id: $memory_id,
            type: 'preference',
            content: 'Progress tracking test memory',
            confidence: 0.85,
            created_at: datetime()
        })
        RETURN m.id
        """

        async with neo4j_service.driver.session() as session:
            await session.run(query, memory_id=test_memory_id)

        # Get and process batch
        batch = await worker.get_next_batch()
        test_batch = [m for m in batch if m.get("memory_id") == test_memory_id]

        if test_batch:
            await worker.process_batch(test_batch)

            # Check progress updated
            progress = worker.get_progress()
            assert progress["processed"] > 0
            assert progress["total"] > 0
            assert progress["success_rate"] > 0.0

            print(f"✓ Progress updated: {progress}")

    finally:
        # Cleanup
        cleanup_query = "MATCH (m:Memory {id: $memory_id}) DELETE m"
        async with neo4j_service.driver.session() as session:
            await session.run(cleanup_query, memory_id=test_memory_id)


@pytest.mark.asyncio
async def test_backfill_worker_health_check(neo4j_service, ollama_client, memory_storage):
    """Test backfill worker health check."""
    worker = EmbeddingBackfillWorker(
        neo4j_service=neo4j_service,
        ollama_client=ollama_client,
        memory_storage=memory_storage,
        batch_size=10,
    )

    health = await worker.health_check()
    assert health is True

    print("✓ Backfill worker health check passed")
