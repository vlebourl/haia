"""
Theme discovery service using DBSCAN clustering.

Automatically discovers semantic themes in memory corpus by clustering
memory embeddings and generating human-readable theme labels.

Session 14 (US7): Theme Discovery
"""

import logging
import time
from datetime import datetime, timezone
from typing import Optional
from uuid import uuid4

import numpy as np
from pydantic_ai import Agent
from sklearn.cluster import DBSCAN
from sklearn.metrics import silhouette_score

from haia.discovery.models import (
    ClusteringConfig,
    ClusteringReport,
    ClusterStatus,
    MemoryClusterAssignment,
    Theme,
)
from haia.services.neo4j import Neo4jService

logger = logging.getLogger(__name__)


class ThemeClusterer:
    """
    Service for automatic theme discovery via DBSCAN clustering (T120-T126).

    Workflow:
    1. Fetch all memories with embeddings from Neo4j
    2. Run DBSCAN clustering on embedding vectors
    3. Calculate silhouette scores for cluster quality
    4. Generate theme labels using LLM
    5. Store themes and assignments in Neo4j
    """

    def __init__(
        self,
        neo4j_service: Neo4jService,
        labeling_model: str = "anthropic:claude-haiku-4-5-20251001",
        config: Optional[ClusteringConfig] = None,
    ):
        """
        Initialize Theme Clusterer.

        Args:
            neo4j_service: Neo4j service for database operations
            labeling_model: LLM model for theme label generation
            config: DBSCAN clustering configuration (default: eps=0.3, min_samples=3)
        """
        self.neo4j = neo4j_service
        self.labeling_model = labeling_model
        self.config = config or ClusteringConfig()

        # Initialize LLM agent for theme labeling
        self.labeling_agent = Agent(
            model=labeling_model,
            system_prompt=(
                "You are a theme labeling expert. Given a set of memory contents, "
                "generate a concise, descriptive theme label (3-8 words) and a brief "
                "description (1-2 sentences) that captures the common topic or pattern."
            ),
        )

        logger.info(
            f"ThemeClusterer initialized: eps={self.config.eps}, "
            f"min_samples={self.config.min_samples}, model={labeling_model}"
        )

    async def _fetch_memories_with_embeddings(self) -> tuple[list[dict], np.ndarray]:
        """
        Fetch all memories with embeddings from Neo4j (T124).

        Returns:
            Tuple of (memory_list, embedding_matrix)
            - memory_list: List of memory dicts with memory_id, content, etc.
            - embedding_matrix: numpy array of shape (n_memories, embedding_dim)
        """
        query = """
        MATCH (m:Memory)
        WHERE m.embedding IS NOT NULL
          AND m.tier IN ['short_term', 'long_term']
        RETURN m.memory_id AS memory_id,
               m.content AS content,
               m.memory_type AS memory_type,
               m.embedding AS embedding,
               m.confidence AS confidence,
               m.created_at AS created_at
        ORDER BY m.created_at DESC
        """

        memories = []
        embeddings = []

        async with self.neo4j.driver.session() as session:
            result = await session.run(query)
            records = [record.data() async for record in result]

            for record in records:
                memories.append(
                    {
                        "memory_id": record["memory_id"],
                        "content": record["content"],
                        "memory_type": record["memory_type"],
                        "confidence": record["confidence"],
                        "created_at": record["created_at"].to_native(),
                    }
                )
                embeddings.append(record["embedding"])

        if not embeddings:
            logger.warning("No memories with embeddings found for clustering")
            return memories, np.array([])

        embedding_matrix = np.array(embeddings, dtype=np.float32)
        logger.debug(f"Fetched {len(memories)} memories with embeddings")

        return memories, embedding_matrix

    def _run_dbscan_clustering(
        self, embeddings: np.ndarray
    ) -> tuple[np.ndarray, int]:
        """
        Run DBSCAN clustering on memory embeddings (T121).

        Args:
            embeddings: Embedding matrix (n_memories, embedding_dim)

        Returns:
            Tuple of (cluster_labels, n_clusters)
            - cluster_labels: Array of cluster IDs for each memory (-1 = outlier)
            - n_clusters: Number of discovered clusters (excluding outliers)
        """
        if len(embeddings) == 0:
            return np.array([]), 0

        # Run DBSCAN
        dbscan = DBSCAN(
            eps=self.config.eps,
            min_samples=self.config.min_samples,
            metric=self.config.metric,
        )

        cluster_labels = dbscan.fit_predict(embeddings)

        # Count clusters (excluding -1 = outliers)
        n_clusters = len(set(cluster_labels)) - (1 if -1 in cluster_labels else 0)

        logger.info(
            f"DBSCAN clustering: {n_clusters} clusters discovered, "
            f"{np.sum(cluster_labels == -1)} outliers"
        )

        return cluster_labels, n_clusters

    def _calculate_silhouette_scores(
        self, embeddings: np.ndarray, cluster_labels: np.ndarray
    ) -> dict[int, float]:
        """
        Calculate silhouette scores for each cluster (T122).

        Silhouette score measures cluster quality:
        - 1.0: Perfect clustering (samples far from other clusters)
        - 0.0: Overlapping clusters
        - -1.0: Samples assigned to wrong cluster

        Args:
            embeddings: Embedding matrix
            cluster_labels: Cluster assignments from DBSCAN

        Returns:
            Dict mapping cluster_id -> silhouette_score
        """
        if len(embeddings) < 2 or len(set(cluster_labels)) < 2:
            logger.warning("Insufficient data for silhouette score calculation")
            return {}

        # Calculate silhouette score per sample
        silhouette_values = silhouette_score(
            embeddings, cluster_labels, metric=self.config.metric, sample_size=min(1000, len(embeddings))
        )

        # Group by cluster
        cluster_scores = {}
        unique_clusters = set(cluster_labels)

        # Calculate average silhouette per cluster
        for cluster_id in unique_clusters:
            if cluster_id == -1:
                continue  # Skip outliers

            # Get silhouette scores for this cluster
            cluster_mask = cluster_labels == cluster_id
            cluster_silhouettes = silhouette_score(
                embeddings[cluster_mask],
                cluster_labels[cluster_mask],
                metric=self.config.metric,
            ) if np.sum(cluster_mask) >= 2 else 0.0

            cluster_scores[cluster_id] = float(cluster_silhouettes) if isinstance(cluster_silhouettes, (int, float, np.number)) else 0.0

        logger.debug(f"Silhouette scores calculated for {len(cluster_scores)} clusters")

        return cluster_scores

    async def _generate_theme_label(
        self, memories: list[dict]
    ) -> tuple[str, str]:
        """
        Generate theme label and description using LLM (T123).

        Args:
            memories: List of memory dicts in this cluster

        Returns:
            Tuple of (label, description)
            - label: Concise theme label (3-8 words)
            - description: Brief description (1-2 sentences)
        """
        # Build prompt with memory contents
        memory_contents = "\n".join(
            f"- {mem['content'][:200]}" for mem in memories[:10]  # Max 10 samples
        )

        prompt = f"""
Analyze these {len(memories)} related memories and generate a theme:

{memory_contents}

Generate:
1. A concise theme label (3-8 words, descriptive and specific)
2. A brief description (1-2 sentences explaining the common pattern)

Format your response as:
LABEL: <your label>
DESCRIPTION: <your description>
"""

        try:
            result = await self.labeling_agent.run(prompt)
            response = result.data

            # Parse response
            lines = response.split("\n")
            label = "Unknown Theme"
            description = "A cluster of related memories"

            for line in lines:
                if line.startswith("LABEL:"):
                    label = line.replace("LABEL:", "").strip()
                elif line.startswith("DESCRIPTION:"):
                    description = line.replace("DESCRIPTION:", "").strip()

            # Validate label length
            if len(label.split()) < 3:
                label = f"{label} memories"  # Pad short labels
            elif len(label.split()) > 8:
                label = " ".join(label.split()[:8])  # Truncate long labels

            logger.debug(f"Generated theme label: {label}")

            return label, description

        except Exception as e:
            logger.error(f"Failed to generate theme label: {e}")
            return "Unlabeled Theme", "A cluster of related memories"

    async def _store_themes_in_neo4j(
        self,
        themes: list[Theme],
        assignments: list[MemoryClusterAssignment],
    ):
        """
        Store discovered themes and cluster assignments in Neo4j (T125).

        Creates:
        - Theme nodes with labels and metadata
        - BELONGS_TO_THEME relationships from memories to themes

        Args:
            themes: List of discovered themes
            assignments: List of memory-to-theme assignments
        """
        # Clear old themes (mark as stale)
        clear_query = """
        MATCH (t:Theme)
        WHERE t.status = 'active'
        SET t.status = 'stale', t.updated_at = datetime()
        """

        async with self.neo4j.driver.session() as session:
            await session.run(clear_query)

        # Create new theme nodes
        theme_query = """
        CREATE (t:Theme {
            theme_id: $theme_id,
            label: $label,
            description: $description,
            cluster_id: $cluster_id,
            memory_count: $memory_count,
            silhouette_score: $silhouette_score,
            status: $status,
            created_at: $created_at,
            updated_at: $updated_at
        })
        RETURN t.theme_id
        """

        async with self.neo4j.driver.session() as session:
            for theme in themes:
                await session.run(
                    theme_query,
                    theme_id=theme.theme_id,
                    label=theme.label,
                    description=theme.description,
                    cluster_id=theme.cluster_id,
                    memory_count=theme.memory_count,
                    silhouette_score=theme.silhouette_score,
                    status=theme.status.value,
                    created_at=theme.created_at,
                    updated_at=theme.updated_at,
                )

        logger.info(f"Created {len(themes)} theme nodes in Neo4j")

        # Clear old BELONGS_TO_THEME relationships
        clear_rel_query = """
        MATCH (m:Memory)-[r:BELONGS_TO_THEME]->(:Theme)
        DELETE r
        """

        async with self.neo4j.driver.session() as session:
            await session.run(clear_rel_query)

        # Create new BELONGS_TO_THEME relationships
        assignment_query = """
        MATCH (m:Memory {memory_id: $memory_id})
        MATCH (t:Theme {theme_id: $theme_id})
        CREATE (m)-[r:BELONGS_TO_THEME {
            distance_to_centroid: $distance,
            assigned_at: $assigned_at
        }]->(t)
        """

        async with self.neo4j.driver.session() as session:
            for assignment in assignments:
                await session.run(
                    assignment_query,
                    memory_id=assignment.memory_id,
                    theme_id=assignment.theme_id,
                    distance=assignment.distance_to_centroid,
                    assigned_at=assignment.assigned_at,
                )

        logger.info(f"Created {len(assignments)} BELONGS_TO_THEME relationships")

    async def run_clustering(self) -> ClusteringReport:
        """
        Execute full theme discovery workflow (T126).

        Orchestrates:
        1. Fetch memories with embeddings
        2. Run DBSCAN clustering
        3. Calculate silhouette scores
        4. Generate theme labels
        5. Store themes in Neo4j
        6. Generate report

        Returns:
            ClusteringReport with execution summary
        """
        start_time = time.time()
        timestamp = datetime.now(timezone.utc)

        logger.info("=" * 60)
        logger.info("Starting theme discovery clustering job...")
        logger.info("=" * 60)

        try:
            # Step 1: Fetch memories
            memories, embeddings = await self._fetch_memories_with_embeddings()

            if len(memories) < self.config.min_cluster_size:
                logger.warning(
                    f"Insufficient memories for clustering: {len(memories)} < {self.config.min_cluster_size}"
                )
                execution_time_ms = (time.time() - start_time) * 1000
                return ClusteringReport(
                    timestamp=timestamp,
                    memories_analyzed=len(memories),
                    themes_discovered=0,
                    outliers_count=0,
                    execution_time_ms=execution_time_ms,
                )

            # Step 2: Run DBSCAN
            cluster_labels, n_clusters = self._run_dbscan_clustering(embeddings)

            if n_clusters == 0:
                logger.warning("No clusters discovered by DBSCAN")
                execution_time_ms = (time.time() - start_time) * 1000
                return ClusteringReport(
                    timestamp=timestamp,
                    memories_analyzed=len(memories),
                    themes_discovered=0,
                    outliers_count=np.sum(cluster_labels == -1),
                    execution_time_ms=execution_time_ms,
                )

            # Step 3: Calculate silhouette scores
            silhouette_scores = self._calculate_silhouette_scores(
                embeddings, cluster_labels
            )

            # Step 4: Generate theme labels and create Theme objects
            themes = []
            assignments = []

            for cluster_id in range(n_clusters):
                # Get memories in this cluster
                cluster_mask = cluster_labels == cluster_id
                cluster_memories = [
                    mem for i, mem in enumerate(memories) if cluster_mask[i]
                ]

                if len(cluster_memories) < self.config.min_cluster_size:
                    logger.debug(
                        f"Skipping cluster {cluster_id}: only {len(cluster_memories)} memories"
                    )
                    continue

                # Generate theme label
                label, description = await self._generate_theme_label(cluster_memories)

                # Get silhouette score
                silhouette = silhouette_scores.get(cluster_id)

                # Skip low-quality clusters
                if silhouette is not None and silhouette < self.config.min_silhouette_score:
                    logger.debug(
                        f"Skipping cluster {cluster_id}: silhouette {silhouette:.2f} < {self.config.min_silhouette_score}"
                    )
                    continue

                # Create Theme object
                theme_id = f"theme_{uuid4().hex[:8]}"
                theme = Theme(
                    theme_id=theme_id,
                    label=label,
                    description=description,
                    cluster_id=cluster_id,
                    memory_count=len(cluster_memories),
                    silhouette_score=silhouette,
                    status=ClusterStatus.ACTIVE,
                    created_at=timestamp,
                    updated_at=timestamp,
                )
                themes.append(theme)

                # Create assignments
                cluster_embeddings = embeddings[cluster_mask]
                centroid = np.mean(cluster_embeddings, axis=0)

                for i, mem in enumerate(cluster_memories):
                    # Calculate distance to centroid (cosine distance)
                    mem_embedding = cluster_embeddings[i]
                    distance = float(
                        1.0 - np.dot(mem_embedding, centroid) / (
                            np.linalg.norm(mem_embedding) * np.linalg.norm(centroid)
                        )
                    )

                    assignment = MemoryClusterAssignment(
                        memory_id=mem["memory_id"],
                        theme_id=theme_id,
                        cluster_id=cluster_id,
                        distance_to_centroid=distance,
                        assigned_at=timestamp,
                    )
                    assignments.append(assignment)

            # Step 5: Store in Neo4j
            if themes:
                await self._store_themes_in_neo4j(themes, assignments)

            # Step 6: Generate report
            execution_time_ms = (time.time() - start_time) * 1000

            # Calculate aggregate silhouette scores
            valid_scores = [t.silhouette_score for t in themes if t.silhouette_score is not None]
            avg_silhouette = np.mean(valid_scores) if valid_scores else None
            min_silhouette = np.min(valid_scores) if valid_scores else None
            max_silhouette = np.max(valid_scores) if valid_scores else None

            report = ClusteringReport(
                timestamp=timestamp,
                memories_analyzed=len(memories),
                themes_discovered=len(themes),
                outliers_count=int(np.sum(cluster_labels == -1)),
                avg_silhouette_score=float(avg_silhouette) if avg_silhouette is not None else None,
                min_silhouette_score=float(min_silhouette) if min_silhouette is not None else None,
                max_silhouette_score=float(max_silhouette) if max_silhouette is not None else None,
                execution_time_ms=execution_time_ms,
                themes=themes,
            )

            logger.info("=" * 60)
            logger.info(report.summary())
            logger.info("=" * 60)

            return report

        except Exception as e:
            logger.error(f"Theme discovery clustering failed: {e}", exc_info=True)

            # Return error report
            execution_time_ms = (time.time() - start_time) * 1000
            return ClusteringReport(
                timestamp=timestamp,
                memories_analyzed=0,
                themes_discovered=0,
                outliers_count=0,
                execution_time_ms=execution_time_ms,
            )
