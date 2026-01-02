"""
Temporal conflict detection and resolution for memories.

Handles contradiction detection between memories and automatic temporal
resolution by setting valid_until timestamps and creating SUPERSEDES relationships.

🔒 P2: Temporal Truth - Old memories preserved, not deleted
📐 G2: Semantic Similarity - Detect conflicts via embedding cosine similarity >0.75
"""

import logging
from datetime import datetime
from typing import Optional

from haia.services.neo4j import Neo4jService

logger = logging.getLogger(__name__)


class TemporalConflict:
    """Represents a detected temporal conflict between memories."""

    def __init__(
        self,
        new_memory_id: str,
        existing_memory_id: str,
        similarity: float,
        reasoning: str,
    ):
        """
        Initialize temporal conflict.

        Args:
            new_memory_id: ID of the new memory being stored
            existing_memory_id: ID of the conflicting existing memory
            similarity: Cosine similarity score (0.0-1.0)
            reasoning: Human-readable explanation of the conflict
        """
        self.new_memory_id = new_memory_id
        self.existing_memory_id = existing_memory_id
        self.similarity = similarity
        self.reasoning = reasoning


class TemporalManager:
    """
    Manages temporal aspects of memories including conflict detection and resolution.

    Approach:
    1. Detect conflicts via semantic similarity (>0.75 cosine similarity)
    2. Preserve old memory with valid_until timestamp (P2: Temporal Truth)
    3. Create SUPERSEDES relationship from new to old
    4. Log all resolutions for observability (P5)
    """

    def __init__(
        self,
        neo4j_service: Neo4jService,
        similarity_threshold: float = 0.75,
    ):
        """
        Initialize TemporalManager.

        Args:
            neo4j_service: Neo4j service for database operations
            similarity_threshold: Minimum similarity to consider conflict (default: 0.75)
        """
        self.neo4j = neo4j_service
        self.similarity_threshold = similarity_threshold

        logger.info(
            f"TemporalManager initialized (similarity_threshold={similarity_threshold})"
        )

    async def detect_temporal_conflict(
        self,
        new_memory_id: str,
        new_content: str,
        new_valid_from: datetime,
        new_embedding: Optional[list[float]] = None,
    ) -> Optional[TemporalConflict]:
        """
        Detect temporal conflicts with existing memories.

        Searches for semantically similar memories (>similarity_threshold) with
        overlapping temporal validity periods.

        Args:
            new_memory_id: ID of the new memory being stored
            new_content: Content of the new memory
            new_valid_from: Timestamp when new memory becomes valid
            new_embedding: Optional embedding vector for similarity search

        Returns:
            TemporalConflict if conflict found, None otherwise
        """
        if not new_embedding:
            logger.debug(
                f"No embedding provided for {new_memory_id}, skipping conflict detection"
            )
            return None

        # Query for semantically similar memories with overlapping validity
        query = """
        MATCH (m:Memory)
        WHERE m.memory_id <> $new_memory_id
          AND m.embedding IS NOT NULL
          AND m.valid_from <= $new_valid_from
          AND (m.valid_until IS NULL OR m.valid_until > $new_valid_from)
        WITH m,
             gds.similarity.cosine(m.embedding, $new_embedding) AS similarity
        WHERE similarity > $similarity_threshold
        RETURN m.memory_id AS memory_id,
               m.content AS content,
               m.valid_from AS valid_from,
               m.valid_until AS valid_until,
               similarity
        ORDER BY similarity DESC
        LIMIT 1
        """

        try:
            async with self.neo4j.driver.session() as session:
                result = await session.run(
                    query,
                    new_memory_id=new_memory_id,
                    new_valid_from=new_valid_from.isoformat(),
                    new_embedding=new_embedding,
                    similarity_threshold=self.similarity_threshold,
                )

                record = await result.single()

                if not record:
                    logger.debug(f"No temporal conflicts found for {new_memory_id}")
                    return None

                # Conflict detected
                conflict = TemporalConflict(
                    new_memory_id=new_memory_id,
                    existing_memory_id=record["memory_id"],
                    similarity=record["similarity"],
                    reasoning=f"Semantic similarity {record['similarity']:.3f} between "
                    f"new memory and existing memory {record['memory_id'][:8]}...",
                )

                logger.info(
                    f"Temporal conflict detected: {conflict.reasoning} "
                    f"(threshold: {self.similarity_threshold})"
                )

                return conflict

        except Exception as e:
            logger.error(f"Failed to detect temporal conflict: {e}")
            # Graceful degradation: continue without conflict detection
            return None

    async def resolve_conflict(
        self,
        conflict: TemporalConflict,
        new_valid_from: datetime,
    ) -> bool:
        """
        Resolve temporal conflict by updating old memory and creating SUPERSEDES relationship.

        Resolution strategy:
        1. Set valid_until on old memory to new_valid_from
        2. Create SUPERSEDES relationship from new to old
        3. Log resolution with reasoning (P5: Observability)

        Args:
            conflict: The detected temporal conflict
            new_valid_from: When the new memory becomes valid (becomes valid_until for old)

        Returns:
            True if resolution successful, False otherwise
        """
        try:
            # Update old memory's valid_until and create SUPERSEDES relationship
            query = """
            MATCH (old:Memory {memory_id: $old_memory_id})
            MATCH (new:Memory {memory_id: $new_memory_id})
            SET old.valid_until = datetime($new_valid_from),
                old.superseded_at = datetime(),
                old.superseded_by = $new_memory_id
            WITH old, new
            MERGE (new)-[r:SUPERSEDES]->(old)
            SET r.created_at = datetime(),
                r.similarity = $similarity,
                r.reasoning = $reasoning
            RETURN old.memory_id AS resolved_id
            """

            async with self.neo4j.driver.session() as session:
                result = await session.run(
                    query,
                    old_memory_id=conflict.existing_memory_id,
                    new_memory_id=conflict.new_memory_id,
                    new_valid_from=new_valid_from.isoformat(),
                    similarity=conflict.similarity,
                    reasoning=conflict.reasoning,
                )

                record = await result.single()

                if record:
                    logger.info(
                        f"✓ Temporal conflict resolved: Memory {conflict.existing_memory_id[:8]}... "
                        f"superseded by {conflict.new_memory_id[:8]}... "
                        f"(valid_until set to {new_valid_from.isoformat()})"
                    )
                    return True
                else:
                    logger.warning(
                        f"Failed to resolve conflict: Memories not found in database"
                    )
                    return False

        except Exception as e:
            logger.error(f"Failed to resolve temporal conflict: {e}")
            return False
