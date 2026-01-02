"""Graph traversal service for discovering related memories.

This module implements graph-based memory retrieval by following relationships
between memory nodes. Supports both APOC (multi-hop) and native Cypher (1-hop).
"""

import logging
from typing import Any

from src.haia.models.hybrid_retrieval import GraphTraversalConfig
from src.haia.services.neo4j import Neo4jService

logger = logging.getLogger(__name__)


class GraphTraversalService:
    """Service for graph-based memory retrieval.

    Discovers contextually relevant memories by following relationships
    (RELATED_TO, DEPENDS_ON, SUPERSEDES) from seed memories.

    Supports two modes:
    1. APOC mode: Multi-hop traversal with cycle detection (requires APOC plugin)
    2. Native mode: 1-hop traversal using standard Cypher (fallback)
    """

    def __init__(self, neo4j_service: Neo4jService):
        """Initialize graph traversal service.

        Args:
            neo4j_service: Neo4j database service
        """
        self.neo4j = neo4j_service
        logger.info("GraphTraversalService initialized")

    async def _check_apoc_available(self) -> bool:
        """Check if APOC plugin is available.

        Returns:
            True if APOC is available, False otherwise
        """
        return await self.neo4j.detect_apoc()

    async def traverse_from_seeds(
        self,
        seed_memory_ids: list[str],
        config: GraphTraversalConfig,
    ) -> list[dict[str, Any]]:
        """Traverse graph from seed memories to discover related memories.

        Follows relationships up to max_depth hops, excluding seed nodes
        from results. Uses APOC for multi-hop if available, otherwise
        falls back to native 1-hop Cypher.

        Args:
            seed_memory_ids: List of memory IDs to start traversal from
            config: Traversal configuration (depth, relationships, APOC usage)

        Returns:
            List of memory dictionaries with fields:
                - memory_id: str
                - distance: int (1-3, hops from seed)
                - content: str (optional, if fetched)
                - type: str (optional)
                - confidence: float (optional)

        Example:
            seeds = ["mem_001", "mem_002"]
            config = GraphTraversalConfig(max_depth=2)
            results = await service.traverse_from_seeds(seeds, config)
            # Returns memories 1-2 hops from seeds
        """
        # Handle empty seed list
        if not seed_memory_ids:
            logger.debug("Empty seed list provided, returning empty results")
            return []

        # Check if APOC should be used
        use_apoc = config.use_apoc and await self._check_apoc_available()

        if use_apoc:
            logger.info(
                f"Using APOC for {config.max_depth}-hop graph traversal "
                f"from {len(seed_memory_ids)} seeds"
            )
            return await self._traverse_with_apoc(seed_memory_ids, config)
        else:
            # Log warning if fallback due to APOC unavailability
            if config.use_apoc:
                logger.warning(
                    f"APOC unavailable, falling back to native Cypher (limited to 1-hop). "
                    f"Requested {config.max_depth} hops but will only traverse 1 hop."
                )
            else:
                logger.info("Using native Cypher for 1-hop graph traversal")

            return await self._traverse_with_native(seed_memory_ids, config)

    async def _traverse_with_apoc(
        self,
        seed_memory_ids: list[str],
        config: GraphTraversalConfig,
    ) -> list[dict[str, Any]]:
        """Traverse graph using APOC plugin (multi-hop).

        Uses apoc.path.expandConfig for efficient multi-hop traversal
        with NODE_GLOBAL uniqueness to prevent cycles.

        Args:
            seed_memory_ids: Seed memory IDs
            config: Traversal configuration

        Returns:
            List of traversed memory dictionaries
        """
        if not self.neo4j.driver:
            logger.error("Neo4j driver not initialized")
            return []

        # Build relationship type filter
        relationship_filter = "|".join(config.relationship_types)

        # APOC query with NODE_GLOBAL uniqueness (prevents cycles)
        query = """
        UNWIND $seed_ids AS seed_id
        MATCH (start:Memory {memory_id: seed_id})
        CALL apoc.path.expandConfig(start, {
            minLevel: 1,
            maxLevel: $max_depth,
            relationshipFilter: $rel_filter,
            uniqueness: "NODE_GLOBAL",
            bfs: true
        })
        YIELD path
        WITH DISTINCT last(nodes(path)) AS related, length(path) AS distance
        WHERE related.memory_id IS NOT NULL
          AND NOT related.memory_id IN $seed_ids
        RETURN
            related.memory_id AS memory_id,
            distance,
            related.content AS content,
            related.memory_type AS type,
            related.confidence AS confidence
        ORDER BY distance ASC, memory_id ASC
        LIMIT 50
        """

        try:
            async with self.neo4j.driver.session() as session:
                result = await session.run(
                    query,
                    seed_ids=seed_memory_ids,
                    max_depth=config.max_depth,
                    rel_filter=relationship_filter,
                )

                records = [record.data() async for record in result]

                logger.debug(
                    f"APOC traversal found {len(records)} related memories "
                    f"within {config.max_depth} hops"
                )

                return records

        except Exception as e:
            logger.error(f"APOC graph traversal failed: {e}", exc_info=True)
            return []

    async def _traverse_with_native(
        self,
        seed_memory_ids: list[str],
        config: GraphTraversalConfig,
    ) -> list[dict[str, Any]]:
        """Traverse graph using native Cypher (1-hop fallback).

        Uses variable-length pattern matching limited to 1 hop for
        performance and simplicity when APOC is unavailable.

        Args:
            seed_memory_ids: Seed memory IDs
            config: Traversal configuration (max_depth ignored, always 1-hop)

        Returns:
            List of traversed memory dictionaries
        """
        if not self.neo4j.driver:
            logger.error("Neo4j driver not initialized")
            return []

        # Build relationship type filter
        relationship_filter = "|".join(config.relationship_types)

        # Native Cypher query (1-hop only)
        query = f"""
        UNWIND $seed_ids AS seed_id
        MATCH (start:Memory {{memory_id: seed_id}})-[r:{relationship_filter}*1]-(related:Memory)
        WHERE related.memory_id IS NOT NULL
          AND NOT related.memory_id IN $seed_ids
        WITH DISTINCT related, 1 AS distance
        RETURN
            related.memory_id AS memory_id,
            distance,
            related.content AS content,
            related.memory_type AS type,
            related.confidence AS confidence
        ORDER BY memory_id ASC
        LIMIT 50
        """

        try:
            async with self.neo4j.driver.session() as session:
                result = await session.run(
                    query,
                    seed_ids=seed_memory_ids,
                )

                records = [record.data() async for record in result]

                logger.debug(
                    f"Native Cypher traversal found {len(records)} related memories "
                    f"(1-hop only)"
                )

                return records

        except Exception as e:
            logger.error(f"Native graph traversal failed: {e}", exc_info=True)
            return []
