"""
Semantic clustering of memory types to prevent proliferation.

🔒 IMMUTABLE: Types emerge freely, clustering organizes (P1)
📐 GUIDELINE: Cluster when 3+ similar types exist (G1)
"""

import logging
from datetime import datetime

import numpy as np
from pydantic_ai import Agent
from sentence_transformers import SentenceTransformer
from sklearn.cluster import DBSCAN
from sklearn.metrics.pairwise import cosine_similarity

from haia.clustering.type_models import SemanticNeighbor, TypeCluster, TypeHierarchy
from haia.services.neo4j import Neo4jService

logger = logging.getLogger(__name__)


class TypeClusterer:
    """
    Clusters semantically similar memory types.

    Approach:
    1. LLM generates any type it wants (no constraints)
    2. System groups similar types via embedding similarity
    3. LLM generates human-readable cluster labels
    4. Retrieval expands queries to include cluster members

    🔒 P1: Emergence Over Prescription - Types emerge freely, never hardcoded
    📐 G1: Semantic Clustering - Cluster when 3+ similar types exist
    """

    def __init__(
        self,
        neo4j_service: Neo4jService,
        extraction_model: str = "anthropic:claude-haiku-4-5-20251001",
        min_cluster_size: int = 3,  # 📐 G1: Min 3 types
        similarity_threshold: float = 0.80,  # 📐 G1: Cosine similarity
    ):
        """
        Initialize TypeClusterer.

        Args:
            neo4j_service: Neo4j service for database operations
            extraction_model: Model to use for LLM label generation (Haiku for cost)
            min_cluster_size: Minimum types per cluster (default: 3)
            similarity_threshold: Cosine similarity threshold (default: 0.80)
        """
        self.neo4j = neo4j_service
        self.extraction_model = extraction_model
        self.min_cluster_size = min_cluster_size
        self.similarity_threshold = similarity_threshold

        # Sentence transformer for type embeddings
        # all-MiniLM-L6-v2: Fast, efficient, 384-dim embeddings
        self.type_encoder = SentenceTransformer("all-MiniLM-L6-v2")
        logger.info(
            f"TypeClusterer initialized: min_size={min_cluster_size}, "
            f"threshold={similarity_threshold}"
        )

    async def get_all_types(self) -> list[str]:
        """
        Get all unique memory types from Neo4j.

        Returns:
            List of unique memory type names, sorted alphabetically
        """
        query = """
        MATCH (m:Memory)
        WHERE m.memory_type IS NOT NULL
        RETURN DISTINCT m.memory_type AS type
        ORDER BY type
        """
        try:
            async with self.neo4j.driver.session() as session:
                result = await session.run(query)
                types = [record["type"] async for record in result]
            logger.debug(f"Retrieved {len(types)} unique memory types")
            return types
        except Exception as e:
            logger.error(f"Failed to retrieve memory types: {e}")
            return []

    def embed_types(self, type_names: list[str]) -> dict[str, np.ndarray]:
        """
        Generate embeddings for memory type names.

        Args:
            type_names: List of memory type names

        Returns:
            Dictionary mapping type_name -> embedding vector
        """
        if not type_names:
            return {}

        try:
            embeddings = self.type_encoder.encode(type_names)
            embedding_dict = {
                type_name: embedding
                for type_name, embedding in zip(type_names, embeddings)
            }
            logger.debug(f"Generated embeddings for {len(type_names)} types")
            return embedding_dict
        except Exception as e:
            logger.error(f"Failed to generate type embeddings: {e}")
            return {}

    def cluster_types(
        self, type_embeddings: dict[str, np.ndarray]
    ) -> dict[int, list[str]]:
        """
        Cluster memory types using DBSCAN.

        Args:
            type_embeddings: Dictionary mapping type_name -> embedding vector

        Returns:
            Dictionary mapping cluster_id -> list of type names
            (cluster_id -1 = noise/unclustered points)
        """
        if len(type_embeddings) < self.min_cluster_size:
            logger.info(
                f"Only {len(type_embeddings)} types, skipping clustering "
                f"(min: {self.min_cluster_size})"
            )
            return {}

        type_names = list(type_embeddings.keys())
        embeddings = np.array([type_embeddings[t] for t in type_names])

        # DBSCAN clustering
        # eps = 1 - similarity_threshold (for cosine distance)
        eps = 1.0 - self.similarity_threshold
        clusterer = DBSCAN(eps=eps, min_samples=self.min_cluster_size, metric="cosine")

        try:
            cluster_labels = clusterer.fit_predict(embeddings)

            # Group types by cluster
            clusters: dict[int, list[str]] = {}
            for type_name, cluster_id in zip(type_names, cluster_labels):
                if cluster_id == -1:  # Noise point (unclustered)
                    continue
                if cluster_id not in clusters:
                    clusters[cluster_id] = []
                clusters[cluster_id].append(type_name)

            logger.info(
                f"DBSCAN clustering: {len(clusters)} clusters from {len(type_names)} types "
                f"(eps={eps:.3f}, min_samples={self.min_cluster_size})"
            )
            return clusters

        except Exception as e:
            logger.error(f"DBSCAN clustering failed: {e}")
            return {}

    async def generate_cluster_label(self, type_names: list[str]) -> str:
        """
        Generate human-readable label for type cluster using LLM.

        🎨 FREEDOM: Prompt design is developer's choice (F4)

        Args:
            type_names: List of memory types in cluster

        Returns:
            Human-readable label (2-4 words, Title Case)
        """
        prompt = f"""
Generate a concise, descriptive label for this group of related memory types:

Types: {', '.join(type_names)}

Requirements:
- 2-4 words maximum
- Captures common theme
- Human-readable
- Title case

Examples:
- "Container Runtime Tools"
- "Infrastructure Configuration"
- "Deployment Preferences"

Label:
"""

        try:
            # Use Haiku for cost efficiency
            agent = Agent[None, str](
                model=self.extraction_model,
                output_type=str,
                system_prompt="You generate concise category labels.",
            )

            result = await agent.run(prompt)
            label = result.output.strip().strip('"').strip("'")

            logger.debug(f"Generated cluster label: '{label}' for {len(type_names)} types")
            return label

        except Exception as e:
            logger.error(f"Failed to generate cluster label: {e}")
            # Fallback: use first type name as label
            fallback = type_names[0].replace("_", " ").title()
            logger.warning(f"Using fallback label: '{fallback}'")
            return fallback

    async def store_clusters(self, type_clusters: list[TypeCluster]) -> int:
        """
        Store TypeCluster nodes in Neo4j with CONTAINS relationships.

        Args:
            type_clusters: List of TypeCluster objects to store

        Returns:
            Number of clusters successfully stored
        """
        if not type_clusters:
            return 0

        stored_count = 0

        for cluster in type_clusters:
            query = """
            MERGE (c:TypeCluster {cluster_id: $cluster_id})
            SET c.label = $label,
                c.similarity_threshold = $similarity_threshold,
                c.member_count = $member_count,
                c.created_at = datetime($created_at)
            WITH c
            UNWIND $member_types AS type_name
            MATCH (m:Memory {memory_type: type_name})
            MERGE (c)-[:CONTAINS_TYPE]->(m)
            """

            try:
                async with self.neo4j.driver.session() as session:
                    await session.run(
                        query,
                        cluster_id=cluster.cluster_id,
                        label=cluster.label,
                        similarity_threshold=cluster.similarity_threshold,
                        member_count=cluster.member_count,
                        created_at=cluster.created_at.isoformat(),
                        member_types=cluster.member_types,
                    )
                stored_count += 1
                logger.debug(
                    f"Stored cluster '{cluster.label}' with {cluster.member_count} types"
                )

            except Exception as e:
                logger.error(f"Failed to store cluster {cluster.cluster_id}: {e}")

        logger.info(f"Stored {stored_count}/{len(type_clusters)} clusters in Neo4j")
        return stored_count

    async def find_semantic_neighbors(
        self, memory_type: str, threshold: float | None = None, max_neighbors: int = 10
    ) -> list[SemanticNeighbor]:
        """
        Find types semantically similar to given type.

        Used during retrieval to expand query.

        Args:
            memory_type: The query memory type
            threshold: Similarity threshold (default: use instance threshold)
            max_neighbors: Maximum neighbors to return (default: 10)

        Returns:
            List of SemanticNeighbor objects (sorted by similarity, descending)
        """
        threshold = threshold or self.similarity_threshold

        # Get all types and their embeddings
        types = await self.get_all_types()
        if not types or memory_type not in types:
            logger.warning(f"Memory type '{memory_type}' not found in database")
            return []

        type_embeddings = self.embed_types(types)
        if not type_embeddings:
            return []

        # Encode query type
        query_embedding = type_embeddings.get(memory_type)
        if query_embedding is None:
            return []

        # Calculate cosine similarities
        type_names = list(type_embeddings.keys())
        embeddings_matrix = np.array([type_embeddings[t] for t in type_names])

        try:
            similarities = cosine_similarity([query_embedding], embeddings_matrix)[0]

            # Filter by threshold, exclude self, sort by similarity
            neighbors = [
                SemanticNeighbor(type_name=type_names[i], similarity=float(sim))
                for i, sim in enumerate(similarities)
                if sim >= threshold and type_names[i] != memory_type
            ]
            neighbors.sort(key=lambda x: x.similarity, reverse=True)

            result = neighbors[:max_neighbors]
            logger.debug(
                f"Found {len(result)} semantic neighbors for '{memory_type}' "
                f"(threshold={threshold:.2f})"
            )
            return result

        except Exception as e:
            logger.error(f"Failed to find semantic neighbors: {e}")
            return []

    async def run_clustering(self) -> list[TypeCluster]:
        """
        Run complete type clustering pipeline.

        Orchestrates: get_all_types -> embed_types -> cluster_types
                      -> generate_cluster_label -> store_clusters

        Returns:
            List of created TypeCluster objects
        """
        logger.info("Starting type clustering pipeline")

        # 1. Get all types
        types = await self.get_all_types()
        if len(types) < self.min_cluster_size:
            logger.info(
                f"Only {len(types)} types, skipping clustering "
                f"(min: {self.min_cluster_size})"
            )
            return []

        # 2. Generate embeddings
        type_embeddings = self.embed_types(types)
        if not type_embeddings:
            logger.error("Failed to generate type embeddings")
            return []

        # 3. Cluster types
        clusters = self.cluster_types(type_embeddings)
        if not clusters:
            logger.info("No clusters created")
            return []

        # 4. Generate labels and create TypeCluster objects
        type_clusters = []
        for cluster_id, member_types in clusters.items():
            label = await self.generate_cluster_label(member_types)
            type_clusters.append(
                TypeCluster(
                    cluster_id=f"type_cluster_{cluster_id}",
                    member_types=member_types,
                    label=label,
                    similarity_threshold=self.similarity_threshold,
                    created_at=datetime.utcnow(),
                    member_count=len(member_types),
                )
            )

        logger.info(
            f"Created {len(type_clusters)} type clusters from {len(types)} types"
        )

        # 5. Store clusters in Neo4j
        stored_count = await self.store_clusters(type_clusters)
        logger.info(
            f"Type clustering complete: {stored_count} clusters stored successfully"
        )

        return type_clusters
