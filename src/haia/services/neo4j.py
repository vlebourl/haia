"""Neo4j service for memory graph database operations.

This module provides async database operations for HAIA's memory system.
All operations use async transactions with automatic retry logic.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Optional

from neo4j import AsyncDriver, AsyncGraphDatabase
from pydantic import BaseModel

logger = logging.getLogger(__name__)


class Neo4jService:
    """Async Neo4j database service with CRUD operations.

    This service provides type-safe operations for memory graph entities.
    Uses connection pooling and automatic retry logic for reliability.
    """

    def __init__(self, uri: str, user: str, password: str) -> None:
        """Initialize Neo4j service with connection parameters.

        Args:
            uri: Neo4j connection URI (e.g., 'bolt://localhost:7687')
            user: Neo4j username
            password: Neo4j password
        """
        self.uri = uri
        self.user = user
        self.driver: Optional[AsyncDriver] = None
        self._password = password
        logger.info(f"Neo4j service initialized with URI: {uri}")

    async def connect(self, max_retries: int = 5) -> None:
        """Connect to Neo4j with exponential backoff retry.

        Args:
            max_retries: Maximum number of connection attempts

        Raises:
            Exception: If connection fails after all retries
        """
        retry_delay = 1.0
        for attempt in range(1, max_retries + 1):
            try:
                self.driver = AsyncGraphDatabase.driver(
                    self.uri,
                    auth=(self.user, self._password),
                    max_connection_pool_size=50,
                    connection_timeout=30.0,
                )
                # Verify connectivity
                await self.driver.verify_connectivity()
                logger.info(f"Connected to Neo4j at {self.uri}")
                return
            except Exception as e:
                if attempt < max_retries:
                    logger.warning(
                        f"Neo4j connection attempt {attempt}/{max_retries} failed: {e}. "
                        f"Retrying in {retry_delay}s..."
                    )
                    await asyncio.sleep(retry_delay)
                    retry_delay *= 2  # Exponential backoff
                    retry_delay = min(retry_delay, 30.0)  # Cap at 30s
                else:
                    logger.error(f"Failed to connect to Neo4j after {max_retries} attempts")
                    raise

    async def close(self) -> None:
        """Close Neo4j driver connection."""
        if self.driver:
            await self.driver.close()
            logger.info("Neo4j connection closed")

    async def health_check(self) -> bool:
        """Check Neo4j connection health.

        Returns:
            True if connection is healthy, False otherwise
        """
        if not self.driver:
            return False
        try:
            async with self.driver.session() as session:
                result = await session.run("RETURN 1 AS health")
                record = await result.single()
                return record["health"] == 1
        except Exception as e:
            logger.error(f"Neo4j health check failed: {e}")
            return False

    async def create_node(
        self, label: str, properties: dict[str, Any]
    ) -> Optional[str]:
        """Create a node in the graph.

        Args:
            label: Node label (e.g., 'Person', 'Interest', 'Fact')
            properties: Node properties as dictionary

        Returns:
            Node ID if successful, None otherwise
        """
        if not self.driver:
            logger.error("Cannot create node: Driver not initialized")
            return None

        async def _create_tx(tx: Any, label: str, props: dict[str, Any]) -> Optional[str]:
            # Extract the ID field based on label
            id_field_map = {
                "Person": "user_id",
                "Interest": "interest_id",
                "Infrastructure": "infra_id",
                "TechPreference": "pref_id",
                "Fact": "fact_id",
                "Decision": "decision_id",
                "Conversation": "conversation_id",
            }
            id_field = id_field_map.get(label, "id")

            query = f"CREATE (n:{label} $props) RETURN n.{id_field} AS id"
            result = await tx.run(query, props=props)
            record = await result.single()
            return record["id"] if record else None

        try:
            async with self.driver.session() as session:
                node_id = await session.execute_write(_create_tx, label, properties)
                logger.debug(f"Created {label} node with ID: {node_id}")
                return node_id
        except Exception as e:
            logger.error(f"Failed to create {label} node: {e}")
            return None

    async def read_node(
        self, label: str, node_id: str
    ) -> Optional[dict[str, Any]]:
        """Read a node by ID.

        Args:
            label: Node label
            node_id: Node ID to retrieve

        Returns:
            Node properties as dictionary, or None if not found
        """
        if not self.driver:
            logger.error("Cannot read node: Driver not initialized")
            return None

        async def _read_tx(tx: Any, label: str, node_id: str) -> Optional[dict[str, Any]]:
            # Determine ID field
            id_field_map = {
                "Person": "user_id",
                "Interest": "interest_id",
                "Infrastructure": "infra_id",
                "TechPreference": "pref_id",
                "Fact": "fact_id",
                "Decision": "decision_id",
                "Conversation": "conversation_id",
            }
            id_field = id_field_map.get(label, "id")

            query = f"MATCH (n:{label} {{{id_field}: $node_id}}) RETURN n"
            result = await tx.run(query, node_id=node_id)
            record = await result.single()
            return dict(record["n"]) if record else None

        try:
            async with self.driver.session() as session:
                node_data = await session.execute_read(_read_tx, label, node_id)
                if node_data:
                    logger.debug(f"Read {label} node {node_id}")
                else:
                    logger.debug(f"{label} node {node_id} not found")
                return node_data
        except Exception as e:
            logger.error(f"Failed to read {label} node {node_id}: {e}")
            return None

    async def update_node(
        self, label: str, node_id: str, properties: dict[str, Any]
    ) -> bool:
        """Update node properties.

        Args:
            label: Node label
            node_id: Node ID to update
            properties: Properties to update

        Returns:
            True if successful, False otherwise
        """
        if not self.driver:
            logger.error("Cannot update node: Driver not initialized")
            return False

        async def _update_tx(
            tx: Any, label: str, node_id: str, props: dict[str, Any]
        ) -> bool:
            id_field_map = {
                "Person": "user_id",
                "Interest": "interest_id",
                "Infrastructure": "infra_id",
                "TechPreference": "pref_id",
                "Fact": "fact_id",
                "Decision": "decision_id",
                "Conversation": "conversation_id",
            }
            id_field = id_field_map.get(label, "id")

            query = f"MATCH (n:{label} {{{id_field}: $node_id}}) SET n += $props RETURN n"
            result = await tx.run(query, node_id=node_id, props=props)
            record = await result.single()
            return record is not None

        try:
            async with self.driver.session() as session:
                success = await session.execute_write(_update_tx, label, node_id, properties)
                if success:
                    logger.debug(f"Updated {label} node {node_id}")
                return success
        except Exception as e:
            logger.error(f"Failed to update {label} node {node_id}: {e}")
            return False

    async def delete_node(self, label: str, node_id: str) -> bool:
        """Delete a node and its relationships.

        Args:
            label: Node label
            node_id: Node ID to delete

        Returns:
            True if successful, False otherwise
        """
        if not self.driver:
            logger.error("Cannot delete node: Driver not initialized")
            return False

        async def _delete_tx(tx: Any, label: str, node_id: str) -> bool:
            id_field_map = {
                "Person": "user_id",
                "Interest": "interest_id",
                "Infrastructure": "infra_id",
                "TechPreference": "pref_id",
                "Fact": "fact_id",
                "Decision": "decision_id",
                "Conversation": "conversation_id",
            }
            id_field = id_field_map.get(label, "id")

            query = f"MATCH (n:{label} {{{id_field}: $node_id}}) DETACH DELETE n RETURN count(n) AS deleted"
            result = await tx.run(query, node_id=node_id)
            record = await result.single()
            return record["deleted"] > 0 if record else False

        try:
            async with self.driver.session() as session:
                success = await session.execute_write(_delete_tx, label, node_id)
                if success:
                    logger.info(f"Deleted {label} node {node_id}")
                return success
        except Exception as e:
            logger.error(f"Failed to delete {label} node {node_id}: {e}")
            return False

    # Entity-specific CRUD methods for type safety

    async def create_person(self, person_data: dict[str, Any]) -> Optional[str]:
        """Create a Person node."""
        return await self.create_node("Person", person_data)

    async def create_interest(self, interest_data: dict[str, Any]) -> Optional[str]:
        """Create an Interest node."""
        return await self.create_node("Interest", interest_data)

    async def create_infrastructure(self, infra_data: dict[str, Any]) -> Optional[str]:
        """Create an Infrastructure node."""
        return await self.create_node("Infrastructure", infra_data)

    async def create_tech_preference(self, pref_data: dict[str, Any]) -> Optional[str]:
        """Create a TechPreference node."""
        return await self.create_node("TechPreference", pref_data)

    async def create_fact(self, fact_data: dict[str, Any]) -> Optional[str]:
        """Create a Fact node."""
        return await self.create_node("Fact", fact_data)

    async def create_decision(self, decision_data: dict[str, Any]) -> Optional[str]:
        """Create a Decision node."""
        return await self.create_node("Decision", decision_data)

    async def create_conversation(self, conv_data: dict[str, Any]) -> Optional[str]:
        """Create a Conversation node."""
        return await self.create_node("Conversation", conv_data)

    async def read_person(self, user_id: str) -> Optional[dict[str, Any]]:
        """Read a Person node by user_id."""
        return await self.read_node("Person", user_id)

    async def read_interest(self, interest_id: str) -> Optional[dict[str, Any]]:
        """Read an Interest node by interest_id."""
        return await self.read_node("Interest", interest_id)

    async def read_infrastructure(self, infra_id: str) -> Optional[dict[str, Any]]:
        """Read an Infrastructure node by infra_id."""
        return await self.read_node("Infrastructure", infra_id)

    async def read_tech_preference(self, pref_id: str) -> Optional[dict[str, Any]]:
        """Read a TechPreference node by pref_id."""
        return await self.read_node("TechPreference", pref_id)

    async def read_fact(self, fact_id: str) -> Optional[dict[str, Any]]:
        """Read a Fact node by fact_id."""
        return await self.read_node("Fact", fact_id)

    async def read_decision(self, decision_id: str) -> Optional[dict[str, Any]]:
        """Read a Decision node by decision_id."""
        return await self.read_node("Decision", decision_id)

    async def read_conversation(self, conversation_id: str) -> Optional[dict[str, Any]]:
        """Read a Conversation node by conversation_id."""
        return await self.read_node("Conversation", conversation_id)

    async def update_person(self, user_id: str, properties: dict[str, Any]) -> bool:
        """Update a Person node."""
        return await self.update_node("Person", user_id, properties)

    async def update_interest(self, interest_id: str, properties: dict[str, Any]) -> bool:
        """Update an Interest node."""
        return await self.update_node("Interest", interest_id, properties)

    async def update_infrastructure(self, infra_id: str, properties: dict[str, Any]) -> bool:
        """Update an Infrastructure node."""
        return await self.update_node("Infrastructure", infra_id, properties)

    async def update_tech_preference(self, pref_id: str, properties: dict[str, Any]) -> bool:
        """Update a TechPreference node."""
        return await self.update_node("TechPreference", pref_id, properties)

    async def update_fact(self, fact_id: str, properties: dict[str, Any]) -> bool:
        """Update a Fact node."""
        return await self.update_node("Fact", fact_id, properties)

    async def update_decision(self, decision_id: str, properties: dict[str, Any]) -> bool:
        """Update a Decision node."""
        return await self.update_node("Decision", decision_id, properties)

    async def update_conversation(self, conversation_id: str, properties: dict[str, Any]) -> bool:
        """Update a Conversation node."""
        return await self.update_node("Conversation", conversation_id, properties)

    async def delete_person(self, user_id: str) -> bool:
        """Delete a Person node."""
        return await self.delete_node("Person", user_id)

    async def delete_interest(self, interest_id: str) -> bool:
        """Delete an Interest node."""
        return await self.delete_node("Interest", interest_id)

    async def delete_infrastructure(self, infra_id: str) -> bool:
        """Delete an Infrastructure node."""
        return await self.delete_node("Infrastructure", infra_id)

    async def delete_tech_preference(self, pref_id: str) -> bool:
        """Delete a TechPreference node."""
        return await self.delete_node("TechPreference", pref_id)

    async def delete_fact(self, fact_id: str) -> bool:
        """Delete a Fact node."""
        return await self.delete_node("Fact", fact_id)

    async def delete_decision(self, decision_id: str) -> bool:
        """Delete a Decision node."""
        return await self.delete_node("Decision", decision_id)

    async def delete_conversation(self, conversation_id: str) -> bool:
        """Delete a Conversation node."""
        return await self.delete_node("Conversation", conversation_id)

    # Relationship creation methods (T053)

    async def create_relationship(
        self,
        from_label: str,
        from_id: str,
        rel_type: str,
        to_label: str,
        to_id: str,
        properties: Optional[dict[str, Any]] = None,
    ) -> bool:
        """Create a relationship between two nodes.

        Args:
            from_label: Source node label
            from_id: Source node ID
            rel_type: Relationship type (e.g., 'INTERESTED_IN', 'OWNS')
            to_label: Target node label
            to_id: Target node ID
            properties: Optional relationship properties

        Returns:
            True if successful, False otherwise
        """
        if not self.driver:
            logger.error("Cannot create relationship: Driver not initialized")
            return False

        async def _create_rel_tx(
            tx: Any,
            from_label: str,
            from_id: str,
            rel_type: str,
            to_label: str,
            to_id: str,
            props: Optional[dict[str, Any]],
        ) -> bool:
            # Determine ID fields
            id_field_map = {
                "Person": "user_id",
                "Interest": "interest_id",
                "Infrastructure": "infra_id",
                "TechPreference": "pref_id",
                "Fact": "fact_id",
                "Decision": "decision_id",
                "Conversation": "conversation_id",
            }
            from_field = id_field_map.get(from_label, "id")
            to_field = id_field_map.get(to_label, "id")

            if props:
                query = f"""
                MATCH (a:{from_label} {{{from_field}: $from_id}})
                MATCH (b:{to_label} {{{to_field}: $to_id}})
                MERGE (a)-[r:{rel_type}]->(b)
                SET r += $props
                RETURN r
                """
                result = await tx.run(
                    query, from_id=from_id, to_id=to_id, props=props
                )
            else:
                query = f"""
                MATCH (a:{from_label} {{{from_field}: $from_id}})
                MATCH (b:{to_label} {{{to_field}: $to_id}})
                MERGE (a)-[r:{rel_type}]->(b)
                RETURN r
                """
                result = await tx.run(query, from_id=from_id, to_id=to_id)

            record = await result.single()
            return record is not None

        try:
            async with self.driver.session() as session:
                success = await session.execute_write(
                    _create_rel_tx, from_label, from_id, rel_type, to_label, to_id, properties
                )
                if success:
                    logger.debug(
                        f"Created relationship {from_label}({from_id})-[{rel_type}]->"
                        f"{to_label}({to_id})"
                    )
                return success
        except Exception as e:
            logger.error(f"Failed to create relationship {rel_type}: {e}")
            return False

    # Specific relationship methods for common patterns

    async def link_person_interest(
        self, user_id: str, interest_id: str, properties: Optional[dict[str, Any]] = None
    ) -> bool:
        """Create INTERESTED_IN relationship between Person and Interest."""
        return await self.create_relationship(
            "Person", user_id, "INTERESTED_IN", "Interest", interest_id, properties
        )

    async def link_person_infrastructure(
        self, user_id: str, infra_id: str, properties: Optional[dict[str, Any]] = None
    ) -> bool:
        """Create OWNS relationship between Person and Infrastructure."""
        return await self.create_relationship(
            "Person", user_id, "OWNS", "Infrastructure", infra_id, properties
        )

    async def link_person_tech_preference(
        self, user_id: str, pref_id: str, properties: Optional[dict[str, Any]] = None
    ) -> bool:
        """Create PREFERS relationship between Person and TechPreference."""
        return await self.create_relationship(
            "Person", user_id, "PREFERS", "TechPreference", pref_id, properties
        )

    async def link_person_fact(
        self, user_id: str, fact_id: str, properties: Optional[dict[str, Any]] = None
    ) -> bool:
        """Create HAS_FACT relationship between Person and Fact."""
        return await self.create_relationship(
            "Person", user_id, "HAS_FACT", "Fact", fact_id, properties
        )

    async def link_person_decision(
        self, user_id: str, decision_id: str, properties: Optional[dict[str, Any]] = None
    ) -> bool:
        """Create MADE_DECISION relationship between Person and Decision."""
        return await self.create_relationship(
            "Person", user_id, "MADE_DECISION", "Decision", decision_id, properties
        )

    async def link_conversation_extraction(
        self,
        conversation_id: str,
        entity_label: str,
        entity_id: str,
        properties: Optional[dict[str, Any]] = None,
    ) -> bool:
        """Create EXTRACTED relationship between Conversation and extracted entity."""
        return await self.create_relationship(
            "Conversation", conversation_id, "EXTRACTED", entity_label, entity_id, properties
        )

    async def link_infrastructure_dependency(
        self, from_infra_id: str, to_infra_id: str, properties: Optional[dict[str, Any]] = None
    ) -> bool:
        """Create DEPENDS_ON relationship between Infrastructure nodes."""
        return await self.create_relationship(
            "Infrastructure", from_infra_id, "DEPENDS_ON", "Infrastructure", to_infra_id, properties
        )

    async def link_decision_supersedes(
        self, new_decision_id: str, old_decision_id: str, properties: Optional[dict[str, Any]] = None
    ) -> bool:
        """Create SUPERSEDES relationship between Decision nodes."""
        return await self.create_relationship(
            "Decision", new_decision_id, "SUPERSEDES", "Decision", old_decision_id, properties
        )

    async def link_interest_related(
        self, interest_id_1: str, interest_id_2: str, properties: Optional[dict[str, Any]] = None
    ) -> bool:
        """Create RELATED_TO relationship between Interest nodes."""
        return await self.create_relationship(
            "Interest", interest_id_1, "RELATED_TO", "Interest", interest_id_2, properties
        )

    # ========================================================================
    # Vector Index Operations (Session 8 - Memory Retrieval)
    # ========================================================================

    async def create_vector_index(
        self,
        index_name: str,
        node_label: str,
        property_name: str,
        dimensions: int = 768,
        similarity_function: str = "cosine",
    ) -> bool:
        """Create a vector index for semantic search.

        Args:
            index_name: Name of the index (e.g., 'memory_embeddings')
            node_label: Node label to index (e.g., 'Memory')
            property_name: Property containing embedding vector (e.g., 'embedding')
            dimensions: Embedding vector dimensions (default: 768)
            similarity_function: Similarity metric - 'cosine', 'euclidean' (default: 'cosine')

        Returns:
            True if index created successfully, False otherwise
        """
        if not self.driver:
            logger.error("Cannot create vector index: Driver not initialized")
            return False

        query = f"""
        CREATE VECTOR INDEX {index_name} IF NOT EXISTS
        FOR (n:{node_label}) ON (n.{property_name})
        OPTIONS {{indexConfig: {{
            `vector.dimensions`: {dimensions},
            `vector.similarity_function`: '{similarity_function}'
        }}}}
        """

        try:
            async with self.driver.session() as session:
                await session.run(query)
                logger.info(f"Created vector index '{index_name}' on {node_label}.{property_name}")
                return True
        except Exception as e:
            logger.error(f"Failed to create vector index '{index_name}': {e}")
            return False

    async def search_similar_memories(
        self,
        query_vector: list[float],
        top_k: int = 10,
        min_confidence: float = 0.4,
        min_similarity: float = 0.65,
        memory_types: Optional[list[str]] = None,
    ) -> list[dict[str, Any]]:
        """Search for similar memories using vector similarity.

        Args:
            query_vector: Query embedding vector (768 dimensions)
            top_k: Number of results to return
            min_confidence: Minimum extraction confidence threshold
            min_similarity: Minimum cosine similarity threshold
            memory_types: Optional filter by memory types

        Returns:
            List of memory dictionaries with similarity scores
        """
        if not self.driver:
            logger.error("Cannot search memories: Driver not initialized")
            return []

        # Retrieve more results initially to allow for filtering
        search_k = top_k * 2

        query = """
        CALL db.index.vector.queryNodes('memory_embeddings', $search_k, $query_vector)
        YIELD node AS memory, score
        WHERE memory.confidence >= $min_confidence
          AND score >= $min_similarity
        """

        # Add memory type filter if specified
        if memory_types:
            query += " AND memory.memory_type IN $memory_types"

        query += """
        RETURN
          memory.memory_id AS memory_id,
          memory.memory_type AS memory_type,
          memory.content AS content,
          memory.confidence AS confidence,
          memory.source_conversation_id AS source_conversation_id,
          memory.extraction_timestamp AS extraction_timestamp,
          memory.category AS category,
          memory.metadata AS metadata,
          memory.embedding AS embedding,
          memory.has_embedding AS has_embedding,
          memory.embedding_version AS embedding_version,
          memory.embedding_updated_at AS embedding_updated_at,
          score AS similarity_score
        ORDER BY score DESC
        LIMIT $top_k
        """

        try:
            async with self.driver.session() as session:
                result = await session.run(
                    query,
                    search_k=search_k,
                    query_vector=query_vector,
                    min_confidence=min_confidence,
                    min_similarity=min_similarity,
                    memory_types=memory_types,
                    top_k=top_k,
                )
                records = [record.data() async for record in result]
                logger.debug(f"Found {len(records)} similar memories (top_k={top_k})")
                return records
        except Exception as e:
            logger.error(f"Failed to search similar memories: {e}")
            return []

    async def store_embedding(
        self,
        memory_id: str,
        embedding: list[float],
        embedding_version: str,
    ) -> bool:
        """Store embedding vector on a Memory node.

        Args:
            memory_id: Memory node ID
            embedding: Embedding vector (768 dimensions)
            embedding_version: Model version (e.g., 'nomic-embed-text-v1')

        Returns:
            True if stored successfully, False otherwise
        """
        if not self.driver:
            logger.error("Cannot store embedding: Driver not initialized")
            return False

        query = """
        MATCH (m:Memory {memory_id: $memory_id})
        SET m.embedding = $embedding,
            m.has_embedding = true,
            m.embedding_version = $embedding_version,
            m.embedding_updated_at = datetime()
        RETURN m.memory_id AS id
        """

        try:
            async with self.driver.session() as session:
                result = await session.run(
                    query,
                    memory_id=memory_id,
                    embedding=embedding,
                    embedding_version=embedding_version,
                )
                record = await result.single()
                if record:
                    logger.debug(f"Stored embedding for memory {memory_id}")
                    return True
                else:
                    logger.warning(f"Memory {memory_id} not found")
                    return False
        except Exception as e:
            logger.error(f"Failed to store embedding for {memory_id}: {e}")
            return False

    async def get_memories_without_embeddings(
        self, batch_size: int = 25
    ) -> list[dict[str, Any]]:
        """Retrieve memories that need embeddings generated.

        Args:
            batch_size: Number of memories to retrieve

        Returns:
            List of memory dictionaries (memory_id, memory_type, content)
        """
        if not self.driver:
            logger.error("Cannot query memories: Driver not initialized")
            return []

        query = """
        MATCH (m:Memory)
        WHERE m.has_embedding = false OR m.has_embedding IS NULL
        RETURN
          m.id AS memory_id,
          m.type AS memory_type,
          m.content AS content
        LIMIT $batch_size
        """

        try:
            async with self.driver.session() as session:
                result = await session.run(query, batch_size=batch_size)
                records = [record.data() async for record in result]
                logger.debug(f"Found {len(records)} memories without embeddings")
                return records
        except Exception as e:
            logger.error(f"Failed to query memories without embeddings: {e}")
            return []

    # ========================================================================
    # Access Tracking Methods (Session 9 - Context Optimization)
    # ========================================================================

    async def record_memory_access(
        self,
        memory_ids: list[str],
        access_time: Any,
    ) -> int:
        """Record access to memories for usage tracking.

        Updates last_accessed and increments access_count for all specified memories.
        Creates access tracking properties if they don't exist.

        Args:
            memory_ids: List of memory IDs to track
            access_time: Timestamp of access (datetime)

        Returns:
            Number of memories successfully updated
        """
        if not self.driver:
            raise RuntimeError("Not connected to Neo4j")

        # Convert datetime to ISO string for Neo4j
        access_time_str = access_time.isoformat()

        query = """
        UNWIND $memory_ids AS memory_id
        MATCH (m) WHERE m.memory_id = memory_id
        SET m.last_accessed = datetime($access_time),
            m.access_count = coalesce(m.access_count, 0) + 1
        RETURN count(m) as updated_count
        """

        try:
            async with self.driver.session() as session:
                result = await session.run(
                    query,
                    memory_ids=memory_ids,
                    access_time=access_time_str,
                )
                record = await result.single()
                updated_count = record["updated_count"] if record else 0

                logger.debug(
                    f"Recorded access for {updated_count} memories at {access_time_str}"
                )

                return updated_count

        except Exception as e:
            logger.error(f"Failed to record memory access: {e}", exc_info=True)
            return 0

    async def get_access_metadata(self, memory_ids: list[str]) -> dict:
        """Get access metadata for multiple memories.

        Args:
            memory_ids: List of memory IDs to get metadata for

        Returns:
            Dictionary mapping memory_id -> AccessMetadata dict
        """
        if not self.driver:
            raise RuntimeError("Not connected to Neo4j")

        from haia.context.models import AccessMetadata

        query = """
        UNWIND $memory_ids AS memory_id
        MATCH (m) WHERE m.memory_id = memory_id
        RETURN m.memory_id as memory_id,
               m.last_accessed as last_accessed,
               coalesce(m.access_count, 0) as access_count
        """

        try:
            async with self.driver.session() as session:
                result = await session.run(query, memory_ids=memory_ids)
                records = [record.data() async for record in result]

                # Convert to AccessMetadata objects
                metadata_dict = {}
                for record in records:
                    # Convert Neo4j DateTime to Python datetime
                    last_accessed = record.get("last_accessed")
                    if last_accessed is not None and hasattr(last_accessed, "to_native"):
                        last_accessed = last_accessed.to_native()

                    metadata_dict[record["memory_id"]] = AccessMetadata(
                        memory_id=record["memory_id"],
                        last_accessed=last_accessed,
                        access_count=record.get("access_count", 0),
                    )

                # Fill in missing memories with default metadata
                for memory_id in memory_ids:
                    if memory_id not in metadata_dict:
                        metadata_dict[memory_id] = AccessMetadata(
                            memory_id=memory_id,
                            last_accessed=None,
                            access_count=0,
                        )

                return metadata_dict

        except Exception as e:
            logger.error(f"Failed to get access metadata: {e}", exc_info=True)
            # Return default metadata on error
            return {
                memory_id: AccessMetadata(
                    memory_id=memory_id,
                    last_accessed=None,
                    access_count=0,
                )
                for memory_id in memory_ids
            }

    async def get_memory_usage_stats(self, memory_id: str) -> dict:
        """Get detailed usage statistics for a memory.

        Args:
            memory_id: Memory ID to get stats for

        Returns:
            Dictionary with usage statistics
        """
        if not self.driver:
            raise RuntimeError("Not connected to Neo4j")

        query = """
        MATCH (m) WHERE m.memory_id = $memory_id
        RETURN m.access_count as total_accesses,
               m.last_accessed as last_accessed,
               m.created_at as first_accessed
        """

        try:
            async with self.driver.session() as session:
                result = await session.run(query, memory_id=memory_id)
                record = await result.single()

                if not record:
                    return {
                        "total_accesses": 0,
                        "last_accessed": None,
                        "first_accessed": None,
                        "days_since_last_access": None,
                    }

                stats = {
                    "total_accesses": record.get("total_accesses", 0),
                    "last_accessed": record.get("last_accessed"),
                    "first_accessed": record.get("first_accessed"),
                    "days_since_last_access": None,
                }

                return stats

        except Exception as e:
            logger.error(
                f"Failed to get usage stats for {memory_id}: {e}",
                exc_info=True,
            )
            return {
                "total_accesses": 0,
                "last_accessed": None,
                "first_accessed": None,
                "days_since_last_access": None,
            }

    async def reset_access_metadata(self, memory_ids: list[str]) -> int:
        """Reset access tracking for specified memories.

        Args:
            memory_ids: List of memory IDs to reset

        Returns:
            Number of memories reset
        """
        if not self.driver:
            raise RuntimeError("Not connected to Neo4j")

        query = """
        UNWIND $memory_ids AS memory_id
        MATCH (m) WHERE m.memory_id = memory_id
        SET m.access_count = 0,
            m.last_accessed = NULL
        RETURN count(m) as reset_count
        """

        try:
            async with self.driver.session() as session:
                result = await session.run(query, memory_ids=memory_ids)
                record = await result.single()
                reset_count = record["reset_count"] if record else 0

                logger.debug(f"Reset access metadata for {reset_count} memories")

                return reset_count

        except Exception as e:
            logger.error(f"Failed to reset access metadata: {e}", exc_info=True)
            return 0

    # =========================================================================
    # SESSION 10: TEMPORAL TRACKING & BM25 SEARCH (Phase 1 - User Story 1)
    # =========================================================================

    async def search_memories_bm25(
        self,
        query_text: str,
        top_k: int = 10,
        min_score: float = 0.1,
        memory_types: Optional[list[str]] = None,
    ) -> list[dict[str, Any]]:
        """Search memories using BM25 full-text index on content.

        Uses Neo4j full-text index with BM25-like scoring for keyword relevance.
        Gracefully degrades to empty results if index unavailable.

        Args:
            query_text: Search query (keywords, phrases)
            top_k: Maximum number of results to return
            min_score: Minimum BM25 score threshold (0.0-1.0)
            memory_types: Optional filter by memory types

        Returns:
            List of memory dicts with BM25 scores, sorted by relevance

        Example:
            results = await neo4j.search_memories_bm25(
                "docker container deployment",
                top_k=5,
                min_score=0.2
            )
        """
        if not self.driver:
            logger.error("Neo4j driver not initialized for BM25 search")
            return []

        try:
            async with self.driver.session() as session:
                # Build type filter clause if provided
                type_filter = ""
                params: dict[str, Any] = {
                    "query": query_text,
                    "limit": top_k,
                }

                if memory_types:
                    type_filter = "AND node.memory_type IN $memory_types"
                    params["memory_types"] = memory_types

                # Use full-text index for BM25 search
                query = f"""
                CALL db.index.fulltext.queryNodes(
                    'memory_content_fulltext',
                    $query
                ) YIELD node, score
                WHERE score >= {min_score} {type_filter}
                RETURN
                    node.memory_id AS memory_id,
                    node.content AS content,
                    node.memory_type AS memory_type,
                    node.confidence AS confidence,
                    node.valid_from AS valid_from,
                    node.valid_until AS valid_until,
                    node.learned_at AS learned_at,
                    node.tier AS tier,
                    score AS bm25_score
                ORDER BY score DESC
                LIMIT $limit
                """

                result = await session.run(query, **params)
                records = await result.data()

                logger.debug(
                    f"BM25 search for '{query_text}' returned {len(records)} results"
                )

                return records

        except Exception as e:
            # Graceful degradation: log error but don't crash
            logger.error(
                f"BM25 search failed (index may not exist): {e}",
                exc_info=True,
            )
            logger.warning(
                "Returning empty BM25 results - check if full-text index exists"
            )
            return []

    async def get_memories_valid_at(
        self,
        target_datetime: Any,  # datetime or ISO string
        top_k: int = 100,
        memory_types: Optional[list[str]] = None,
    ) -> list[dict[str, Any]]:
        """Query memories that were valid at a specific point in time.

        Temporal query: Returns memories where:
        - valid_from <= target_datetime
        - valid_until IS NULL OR valid_until > target_datetime

        Args:
            target_datetime: Target time (datetime object or ISO string)
            top_k: Maximum number of results
            memory_types: Optional filter by memory types

        Returns:
            List of memory dicts valid at target time, sorted by valid_from DESC

        Example:
            # Get memories valid on October 15, 2024
            memories = await neo4j.get_memories_valid_at(
                datetime(2024, 10, 15),
                top_k=50
            )
        """
        if not self.driver:
            logger.error("Neo4j driver not initialized for temporal query")
            return []

        try:
            async with self.driver.session() as session:
                # Build type filter clause if provided
                type_filter = ""
                params: dict[str, Any] = {
                    "target_time": target_datetime,
                    "limit": top_k,
                }

                if memory_types:
                    type_filter = "AND m.memory_type IN $memory_types"
                    params["memory_types"] = memory_types

                # Temporal range query using composite index
                query = f"""
                MATCH (m:Memory)
                WHERE m.valid_from <= datetime($target_time)
                  AND (m.valid_until IS NULL OR m.valid_until > datetime($target_time))
                  {type_filter}
                RETURN
                    m.memory_id AS memory_id,
                    m.content AS content,
                    m.memory_type AS memory_type,
                    m.confidence AS confidence,
                    m.valid_from AS valid_from,
                    m.valid_until AS valid_until,
                    m.learned_at AS learned_at,
                    m.tier AS tier,
                    m.superseded_by AS superseded_by,
                    m.supersedes AS supersedes
                ORDER BY m.valid_from DESC
                LIMIT $limit
                """

                result = await session.run(query, **params)
                records = await result.data()

                logger.debug(
                    f"Temporal query for {target_datetime} returned {len(records)} memories"
                )

                return records

        except Exception as e:
            logger.error(f"Temporal query failed: {e}", exc_info=True)
            return []
