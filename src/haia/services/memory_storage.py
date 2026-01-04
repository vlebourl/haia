"""Neo4j storage service for extracted memories."""

import logging
from datetime import datetime
from typing import Optional

from haia.extraction.models import ExtractedMemory, ExtractionResult
from haia.services.neo4j import Neo4jService
from haia.services.temporal_manager import TemporalManager
from haia.services.relationship_inference import RelationshipInferenceService

logger = logging.getLogger(__name__)


class MemoryStorageService:
    """Service for storing extracted memories in Neo4j graph database."""

    def __init__(
        self,
        neo4j_service: Neo4jService,
        temporal_manager: Optional[TemporalManager] = None,
        relationship_service: Optional[RelationshipInferenceService] = None,
    ):
        """Initialize memory storage service.

        Args:
            neo4j_service: Neo4j service instance for database operations
            temporal_manager: Optional TemporalManager for conflict detection/resolution
            relationship_service: Optional RelationshipInferenceService for relationship discovery
        """
        self.neo4j = neo4j_service
        self.temporal_manager = temporal_manager or TemporalManager(neo4j_service)
        self.relationship_service = relationship_service
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
                # Session 12: Use TemporalManager for conflict detection
                conflict = await self.temporal_manager.detect_temporal_conflict(
                    new_memory_id=memory.memory_id,
                    new_content=memory.content,
                    new_valid_from=memory.valid_from,
                    new_embedding=getattr(memory, 'embedding', None),
                )

                if conflict:
                    # Resolve temporal conflict
                    await self.temporal_manager.resolve_conflict(
                        conflict=conflict,
                        new_valid_from=memory.valid_from,
                    )
                    logger.info(
                        f"Memory {memory.memory_id} supersedes {conflict.existing_memory_id}"
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
            memory_id: $memory_id,
            memory_type: $memory_type,
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

        RETURN m.memory_id as memory_id
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
        MATCH (m:Memory {memory_id: $memory_id})
        SET
            m.embedding = $embedding,
            m.has_embedding = $has_embedding,
            m.embedding_version = $embedding_version,
            m.embedding_updated_at = datetime()
        RETURN m.memory_id as memory_id
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

    async def infer_relationships_batch(
        self,
        conversation_id: str,
        max_pairs: int = 10,
    ) -> int:
        """Infer relationships between memories from a conversation.

        Uses RelationshipInferenceService to discover semantic relationships
        between memories extracted from the same conversation.

        Args:
            conversation_id: Conversation ID to find memories from
            max_pairs: Maximum number of memory pairs to analyze (default: 10)

        Returns:
            Number of relationships successfully stored

        Example:
            After storing 5 memories from a conversation:
            - Analyze pairs: (m1,m2), (m1,m3), (m2,m3), (m1,m4), (m2,m4)...
            - Infer relationships using LLM
            - Store relationships with confidence >= 0.7
        """
        if not self.relationship_service:
            logger.debug("RelationshipInferenceService not configured, skipping inference")
            return 0

        try:
            # Query for memories from this conversation
            query = """
            MATCH (c:Conversation {id: $conversation_id})-[:CONTAINS_MEMORY]->(m:Memory)
            RETURN
                m.id AS memory_id,
                m.content AS content,
                m.type AS memory_type
            ORDER BY m.created_at ASC
            """

            params = {"conversation_id": conversation_id}

            async with self.neo4j.driver.session() as session:
                result = await session.run(query, **params)
                records = await result.values()

                if not records:
                    logger.debug(f"No memories found for conversation {conversation_id}")
                    return 0

                memories = [
                    {
                        "memory_id": record[0],
                        "content": record[1],
                        "memory_type": record[2] or "unknown",
                    }
                    for record in records
                ]

            # Generate memory pairs (avoid n^2 explosion)
            memory_pairs = []
            for i in range(len(memories)):
                for j in range(i + 1, len(memories)):
                    memory_pairs.append((memories[i], memories[j]))
                    if len(memory_pairs) >= max_pairs:
                        break
                if len(memory_pairs) >= max_pairs:
                    break

            if not memory_pairs:
                logger.debug(f"No memory pairs to analyze for conversation {conversation_id}")
                return 0

            logger.info(
                f"Analyzing {len(memory_pairs)} memory pairs for relationships "
                f"(conversation: {conversation_id})"
            )

            # Batch infer relationships
            inferred_relationships = await self.relationship_service.batch_infer_relationships(
                memory_pairs
            )

            # Store relationships in Neo4j
            stored_count = 0
            for from_id, to_id, inference in inferred_relationships:
                success = await self.relationship_service.store_relationship(
                    from_memory_id=from_id,
                    to_memory_id=to_id,
                    inference=inference,
                )
                if success:
                    stored_count += 1

            logger.info(
                f"Stored {stored_count} relationships for conversation {conversation_id}",
                extra={
                    "pairs_analyzed": len(memory_pairs),
                    "relationships_found": len(inferred_relationships),
                    "relationships_stored": stored_count,
                },
            )

            return stored_count

        except Exception as e:
            logger.error(
                f"Failed to infer relationships for conversation {conversation_id}: {e}",
                exc_info=True,
            )
            # Graceful degradation: continue without relationship inference
            return 0

    # =========================================================================
    # NOTE: Old Session 10 methods (detect_contradiction, handle_superseding)
    # have been replaced by TemporalManager in Session 12 (User Story 4)
    # =========================================================================
