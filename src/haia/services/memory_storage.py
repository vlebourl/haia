"""Neo4j storage service for extracted memories."""

import logging
from datetime import datetime

from haia.extraction.models import ExtractedMemory, ExtractionResult
from haia.services.neo4j import Neo4jService

logger = logging.getLogger(__name__)


class MemoryStorageService:
    """Service for storing extracted memories in Neo4j graph database."""

    def __init__(self, neo4j_service: Neo4jService):
        """Initialize memory storage service.

        Args:
            neo4j_service: Neo4j service instance for database operations
        """
        self.neo4j = neo4j_service
        logger.info("MemoryStorageService initialized")

    async def store_extraction_result(self, result: ExtractionResult) -> int:
        """Store extraction result with all memories in Neo4j.

        Creates memory nodes and links them to the source conversation.

        Args:
            result: Extraction result with memories to store

        Returns:
            Number of memories successfully stored

        Note:
            Continues on errors, logs failures, returns count of successful stores.
        """
        if not result.is_successful:
            logger.warning(
                f"Skipping storage for failed extraction: {result.error}",
                extra={"conversation_id": result.conversation_id},
            )
            return 0

        if result.memory_count == 0:
            logger.info(
                "No memories to store",
                extra={"conversation_id": result.conversation_id},
            )
            return 0

        logger.info(
            f"Storing {result.memory_count} memories for conversation {result.conversation_id}"
        )

        stored_count = 0
        for memory in result.memories:
            try:
                await self._store_memory(memory)
                stored_count += 1
            except Exception as e:
                logger.error(
                    f"Failed to store memory {memory.memory_id}: {e}",
                    exc_info=True,
                    extra={
                        "memory_id": memory.memory_id,
                        "conversation_id": result.conversation_id,
                    },
                )

        logger.info(
            f"Stored {stored_count}/{result.memory_count} memories",
            extra={
                "conversation_id": result.conversation_id,
                "model_used": result.model_used,
                "extraction_duration": result.extraction_duration,
            },
        )

        return stored_count

    async def _store_memory(self, memory: ExtractedMemory) -> None:
        """Store a single memory in Neo4j.

        Creates a Memory node with properties and links to Conversation node.

        Args:
            memory: Memory to store

        Raises:
            Exception: If Neo4j write fails
        """
        query = """
        // Create or merge conversation node
        MERGE (c:Conversation {id: $conversation_id})
        ON CREATE SET
            c.created_at = datetime($extraction_time)

        // Create memory node
        CREATE (m:Memory {
            id: $memory_id,
            type: $memory_type,
            content: $content,
            confidence: $confidence,
            category: $category,
            created_at: datetime($extraction_time)
        })

        // Link memory to conversation
        CREATE (c)-[:CONTAINS_MEMORY]->(m)

        // Store metadata as separate properties
        SET m += $metadata

        RETURN m.id as memory_id
        """

        params = {
            "conversation_id": memory.source_conversation_id,
            "memory_id": memory.memory_id,
            "memory_type": memory.memory_type,
            "content": memory.content,
            "confidence": memory.confidence,
            "category": memory.category or "",
            "extraction_time": memory.extraction_timestamp.isoformat(),
            "metadata": memory.metadata or {},
        }

        result = await self.neo4j.execute_write(query, params)

        logger.debug(
            f"Stored memory {memory.memory_id}",
            extra={
                "memory_type": memory.memory_type,
                "confidence": memory.confidence,
                "conversation_id": memory.source_conversation_id,
            },
        )
