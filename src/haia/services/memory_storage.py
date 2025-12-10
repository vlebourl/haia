"""Neo4j storage service for extracted memories."""

import logging
from datetime import datetime
from typing import Optional

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
        Session 10: Now includes contradiction detection and superseding.

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
                # Session 10: Check for contradictions before storing
                contradicting_memory = await self.detect_contradiction(memory)

                if contradicting_memory:
                    # Handle superseding: update old memory, create link
                    await self.handle_superseding(
                        new_memory=memory, old_memory_id=contradicting_memory["memory_id"]
                    )
                    logger.info(
                        f"Memory {memory.memory_id} supersedes {contradicting_memory['memory_id']}"
                    )

                # Store the new memory
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
        Session 10: Includes temporal properties and tier.

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
            created_at: datetime($extraction_time),
            // Session 10: Temporal properties
            valid_from: datetime($valid_from),
            valid_until: CASE WHEN $valid_until IS NULL THEN null ELSE datetime($valid_until) END,
            learned_at: datetime($learned_at),
            superseded_by: $superseded_by,
            supersedes: $supersedes,
            // Session 10: Tier property
            tier: $tier
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
            # Session 10: Temporal properties
            "valid_from": memory.valid_from.isoformat(),
            "valid_until": memory.valid_until.isoformat() if memory.valid_until else None,
            "learned_at": memory.learned_at.isoformat(),
            "superseded_by": memory.superseded_by,
            "supersedes": memory.supersedes,
            # Session 10: Tier property
            "tier": memory.tier,
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

    async def store_embedding(
        self,
        memory_id: str,
        embedding: list[float],
        embedding_version: str,
    ) -> bool:
        """Store embedding vector for an existing memory.

        Updates an existing Memory node with its embedding vector and metadata.
        This method is used for:
        - Immediate embedding generation after memory extraction (Session 8)
        - Backfilling embeddings for existing memories

        Args:
            memory_id: ID of the memory to update
            embedding: 768-dimensional embedding vector
            embedding_version: Model version used (e.g., 'nomic-embed-text-v1')

        Returns:
            True if embedding stored successfully, False if memory not found

        Raises:
            ValueError: If embedding dimensions are invalid
            Exception: If Neo4j update fails

        Example:
            >>> await storage.store_embedding(
            ...     memory_id="mem_123",
            ...     embedding=[0.1, 0.2, ...],  # 768 dimensions
            ...     embedding_version="nomic-embed-text-v1"
            ... )
            True
        """
        # Validate embedding dimensions
        if not embedding:
            raise ValueError("Embedding vector cannot be empty")

        if len(embedding) != 768:
            raise ValueError(f"Embedding must be 768 dimensions, got {len(embedding)}")

        # Cypher query to update memory with embedding
        query = """
        MATCH (m:Memory {id: $memory_id})
        SET
            m.embedding = $embedding,
            m.has_embedding = $has_embedding,
            m.embedding_version = $embedding_version,
            m.embedding_updated_at = datetime()
        RETURN m.id as memory_id
        """

        params = {
            "memory_id": memory_id,
            "embedding": embedding,
            "has_embedding": True,
            "embedding_version": embedding_version,
        }

        try:
            async with self.neo4j.driver.session() as session:
                result = await session.run(query, **params)
                record = await result.single()

                if record is None:
                    logger.warning(f"Memory {memory_id} not found, cannot store embedding")
                    return False

                logger.debug(
                    f"Stored embedding for memory {memory_id}",
                    extra={
                        "embedding_version": embedding_version,
                        "embedding_dimensions": len(embedding),
                    },
                )

                return True

        except Exception as e:
            logger.error(
                f"Failed to store embedding for memory {memory_id}: {e}",
                exc_info=True,
                extra={"embedding_version": embedding_version},
            )
            raise

    # =========================================================================
    # SESSION 10: TEMPORAL TRACKING (Phase 1 - User Story 1)
    # =========================================================================

    async def detect_contradiction(
        self, new_memory: ExtractedMemory, similarity_threshold: float = 0.75
    ) -> Optional[dict]:
        """Detect if new memory contradicts existing memories.

        Finds semantically similar memories with temporal overlap and different content.
        Used to identify memories that need to be superseded.

        Args:
            new_memory: New memory being stored
            similarity_threshold: Cosine similarity threshold (default: 0.75)

        Returns:
            Dict with old memory details if contradiction found, None otherwise

        Example contradiction:
            Old: "I have 3 Proxmox nodes" (valid_from: 2024-10-01)
            New: "I have 4 Proxmox nodes" (valid_from: 2024-12-01)
            -> Similar content, temporal overlap, contradiction detected
        """
        if not self.neo4j.driver or not new_memory.embedding:
            return None

        try:
            # Query for semantically similar memories with temporal overlap
            query = """
            MATCH (m:Memory)
            WHERE m.has_embedding = true
              AND m.id <> $new_memory_id
              AND (m.valid_until IS NULL OR m.valid_until > datetime($valid_from))
            WITH m,
                 gds.similarity.cosine(m.embedding, $new_embedding) AS similarity
            WHERE similarity >= $similarity_threshold
              AND m.content <> $new_content
            RETURN
                m.id AS memory_id,
                m.content AS content,
                m.memory_type AS memory_type,
                m.valid_from AS valid_from,
                m.valid_until AS valid_until,
                similarity
            ORDER BY similarity DESC
            LIMIT 1
            """

            params = {
                "new_memory_id": new_memory.memory_id,
                "new_embedding": new_memory.embedding,
                "new_content": new_memory.content,
                "valid_from": new_memory.valid_from.isoformat(),
                "similarity_threshold": similarity_threshold,
            }

            async with self.neo4j.driver.session() as session:
                result = await session.run(query, **params)
                record = await result.single()

                if record:
                    contradiction = dict(record)
                    logger.info(
                        f"Detected contradiction: new memory {new_memory.memory_id} "
                        f"contradicts {contradiction['memory_id']} "
                        f"(similarity: {contradiction['similarity']:.3f})"
                    )
                    return contradiction

                return None

        except Exception as e:
            logger.warning(
                f"Contradiction detection failed (continuing without): {e}",
                exc_info=True,
            )
            # Graceful degradation: continue without contradiction detection
            return None

    async def handle_superseding(self, new_memory: ExtractedMemory, old_memory_id: str) -> None:
        """Handle superseding relationship between new and old memories.

        Updates old memory's valid_until to mark when it stopped being valid.
        Creates SUPERSEDES relationship from new to old memory.
        Preserves old memory for historical queries (P2: Temporal Truth).

        Args:
            new_memory: New memory that supersedes the old one
            old_memory_id: ID of memory being superseded

        Example:
            Old memory: "3 Proxmox nodes" becomes invalid on 2024-12-01
            New memory: "4 Proxmox nodes" valid from 2024-12-01
            SUPERSEDES relationship created for temporal chain
        """
        if not self.neo4j.driver:
            logger.error("Neo4j driver not initialized for superseding")
            return

        try:
            # Update old memory and create relationship
            query = """
            MATCH (old:Memory {id: $old_memory_id})
            MATCH (new:Memory {id: $new_memory_id})
            SET
                old.valid_until = datetime($new_valid_from),
                old.superseded_by = $new_memory_id
            SET
                new.supersedes = $old_memory_id
            CREATE (new)-[:SUPERSEDES {created_at: datetime()}]->(old)
            RETURN
                old.id AS old_id,
                old.valid_until AS old_valid_until,
                new.id AS new_id
            """

            params = {
                "old_memory_id": old_memory_id,
                "new_memory_id": new_memory.memory_id,
                "new_valid_from": new_memory.valid_from.isoformat(),
            }

            async with self.neo4j.driver.session() as session:
                result = await session.run(query, **params)
                record = await result.single()

                if record:
                    logger.info(
                        f"Superseding complete: {new_memory.memory_id} supersedes {old_memory_id}",
                        extra={
                            "old_memory_id": old_memory_id,
                            "new_memory_id": new_memory.memory_id,
                            "old_valid_until": record["old_valid_until"],
                        },
                    )
                else:
                    logger.warning(
                        f"Superseding relationship not created - memories may not exist"
                    )

        except Exception as e:
            logger.error(
                f"Failed to handle superseding for {old_memory_id}: {e}", exc_info=True
            )
            # Don't raise - allow memory storage to continue
