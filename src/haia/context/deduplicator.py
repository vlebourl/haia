"""Memory deduplication service using embedding similarity.

This module provides deduplication logic to remove:
1. Exact duplicates (identical content)
2. Semantic duplicates (high embedding similarity >0.92)
3. Superseded memories (when corrections exist)
"""

import logging
from typing import Any

import numpy as np
from numpy.typing import NDArray

from haia.context.models import DeduplicationResult
from haia.embedding.models import RetrievalResult

logger = logging.getLogger(__name__)


class Deduplicator:
    """Service for memory deduplication using embedding similarity.

    Uses cosine similarity on cached embeddings to detect:
    - Exact duplicates (similarity ~1.0)
    - Semantic duplicates (similarity > threshold, default 0.92)
    - Correction superseding (correction type memories supersede older memories)
    """

    def __init__(self):
        """Initialize deduplicator."""
        logger.debug("Deduplicator initialized")

    async def deduplicate(
        self,
        memories: list[RetrievalResult],
        similarity_threshold: float = 0.92,
    ) -> DeduplicationResult:
        """Remove duplicate and similar memories from retrieval results.

        Args:
            memories: List of retrieved memories to deduplicate
            similarity_threshold: Cosine similarity threshold for duplicates (0.0-1.0)

        Returns:
            DeduplicationResult with unique memories and removal statistics

        Raises:
            ValueError: If memories list is empty, threshold invalid, or embeddings missing
        """
        # Validation
        if not memories:
            raise ValueError("At least one memory required for deduplication")

        if not (0.0 <= similarity_threshold <= 1.0):
            raise ValueError(
                f"Threshold must be between 0.0 and 1.0, got {similarity_threshold}"
            )

        # Filter out memories without embeddings - deduplicate only those with embeddings
        memories_with_embeddings = []
        memories_without_embeddings = []

        for mem in memories:
            if mem.memory.embedding is None or not mem.memory.has_embedding:
                logger.warning(
                    f"Memory {mem.memory.memory_id} has no embedding, excluding from deduplication"
                )
                memories_without_embeddings.append(mem)
            else:
                memories_with_embeddings.append(mem)

        # If no memories have embeddings, return all as unique (no dedup possible)
        if not memories_with_embeddings:
            logger.warning("No memories have embeddings, deduplication skipped")
            return DeduplicationResult(
                unique_memories=memories,
                duplicate_count=0,
                similar_count=0,
                superseded_count=0,
                dedup_metadata={
                    "similarity_threshold": similarity_threshold,
                    "removed_memory_ids": [],
                    "removal_reasons": {},
                },
            )

        # Single memory edge case - no deduplication needed
        if len(memories_with_embeddings) == 1:
            return DeduplicationResult(
                unique_memories=memories,  # Include all memories (with and without embeddings)
                duplicate_count=0,
                similar_count=0,
                superseded_count=0,
                dedup_metadata={
                    "similarity_threshold": similarity_threshold,
                    "removed_memory_ids": [],
                    "removal_reasons": {},
                },
            )

        # Step 1: Handle correction superseding first (only for memories with embeddings)
        memories_after_corrections, superseded_ids = self._handle_corrections(memories_with_embeddings)
        superseded_count = len(superseded_ids)

        # Step 2: Compute similarity matrix for remaining memories
        similarity_matrix = self._compute_similarity_matrix(memories_after_corrections)

        # Step 3: Identify exact duplicates (similarity ~1.0)
        duplicate_indices, duplicate_ids = self._identify_duplicates(
            memories_after_corrections, similarity_matrix
        )
        duplicate_count = len(duplicate_ids)

        # Step 4: Identify semantic duplicates (similarity > threshold)
        similar_indices, similar_ids = self._identify_similar(
            memories_after_corrections, similarity_matrix, similarity_threshold, duplicate_indices
        )
        similar_count = len(similar_ids)

        # Step 5: Build final unique memories list
        all_removed_indices = duplicate_indices.union(similar_indices)
        unique_memories = [
            mem
            for idx, mem in enumerate(memories_after_corrections)
            if idx not in all_removed_indices
        ]

        # Add back memories that were excluded due to missing embeddings
        unique_memories.extend(memories_without_embeddings)

        # Build removal reasons metadata
        removal_reasons: dict[str, str] = {}
        for mem_id in superseded_ids:
            removal_reasons[mem_id] = "superseded_by_correction"
        for mem_id in duplicate_ids:
            removal_reasons[mem_id] = "exact_duplicate"
        for mem_id in similar_ids:
            removal_reasons[mem_id] = f"semantic_similar (>{similarity_threshold})"

        all_removed_ids = superseded_ids + duplicate_ids + similar_ids

        dedup_metadata = {
            "similarity_threshold": similarity_threshold,
            "removed_memory_ids": all_removed_ids,
            "removal_reasons": removal_reasons,
        }

        result = DeduplicationResult(
            unique_memories=unique_memories,
            duplicate_count=duplicate_count,
            similar_count=similar_count,
            superseded_count=superseded_count,
            dedup_metadata=dedup_metadata,
        )

        logger.info(
            f"Deduplication complete: {len(unique_memories)} unique, "
            f"{result.total_removed} removed "
            f"({duplicate_count} exact, {similar_count} similar, {superseded_count} superseded)"
        )

        return result

    def _compute_similarity_matrix(
        self, memories: list[RetrievalResult]
    ) -> NDArray[np.float64]:
        """Compute pairwise cosine similarity matrix using numpy.

        Args:
            memories: List of memories with embeddings

        Returns:
            NxN similarity matrix where [i,j] is cosine similarity between memory i and j
        """
        # Extract embeddings as numpy array
        embeddings = np.array([mem.memory.embedding for mem in memories])

        # Normalize embeddings for cosine similarity
        norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
        normalized = embeddings / norms

        # Compute cosine similarity matrix (dot product of normalized vectors)
        similarity_matrix = np.dot(normalized, normalized.T)

        return similarity_matrix

    def _identify_duplicates(
        self,
        memories: list[RetrievalResult],
        similarity_matrix: NDArray[np.float64],
    ) -> tuple[set[int], list[str]]:
        """Identify exact duplicates (similarity ~1.0).

        When duplicates are found, keeps the one with higher confidence.

        Args:
            memories: List of memories
            similarity_matrix: Pairwise similarity matrix

        Returns:
            Tuple of (indices to remove, memory IDs removed)
        """
        duplicate_indices: set[int] = set()
        duplicate_ids: list[str] = []

        n = len(memories)
        for i in range(n):
            if i in duplicate_indices:
                continue  # Already marked for removal

            for j in range(i + 1, n):
                if j in duplicate_indices:
                    continue  # Already marked for removal

                # Consider exact duplicate if similarity >= 0.999
                if similarity_matrix[i, j] >= 0.999:
                    # Keep the one with higher confidence
                    if memories[i].memory.confidence >= memories[j].memory.confidence:
                        duplicate_indices.add(j)
                        duplicate_ids.append(memories[j].memory.memory_id)
                        logger.debug(
                            f"Exact duplicate: Removing {memories[j].memory.memory_id} "
                            f"(lower confidence {memories[j].memory.confidence:.3f} vs "
                            f"{memories[i].memory.confidence:.3f})"
                        )
                    else:
                        duplicate_indices.add(i)
                        duplicate_ids.append(memories[i].memory.memory_id)
                        logger.debug(
                            f"Exact duplicate: Removing {memories[i].memory.memory_id} "
                            f"(lower confidence {memories[i].memory.confidence:.3f} vs "
                            f"{memories[j].memory.confidence:.3f})"
                        )
                        break  # i is removed, move to next i

        return duplicate_indices, duplicate_ids

    def _identify_similar(
        self,
        memories: list[RetrievalResult],
        similarity_matrix: NDArray[np.float64],
        threshold: float,
        already_removed: set[int],
    ) -> tuple[set[int], list[str]]:
        """Identify semantically similar memories (similarity > threshold).

        When similar memories are found, keeps the one with higher confidence.

        Args:
            memories: List of memories
            similarity_matrix: Pairwise similarity matrix
            threshold: Similarity threshold (e.g., 0.92)
            already_removed: Indices already marked for removal

        Returns:
            Tuple of (indices to remove, memory IDs removed)
        """
        similar_indices: set[int] = set()
        similar_ids: list[str] = []

        n = len(memories)
        for i in range(n):
            if i in already_removed or i in similar_indices:
                continue  # Already removed or marked

            for j in range(i + 1, n):
                if j in already_removed or j in similar_indices:
                    continue  # Already removed or marked

                # Check if semantically similar (excluding exact duplicates)
                if threshold < similarity_matrix[i, j] < 0.999:
                    # Keep the one with higher confidence
                    if memories[i].memory.confidence >= memories[j].memory.confidence:
                        similar_indices.add(j)
                        similar_ids.append(memories[j].memory.memory_id)
                        logger.debug(
                            f"Semantic similar: Removing {memories[j].memory.memory_id} "
                            f"(similarity {similarity_matrix[i, j]:.3f}, "
                            f"lower confidence {memories[j].memory.confidence:.3f} vs "
                            f"{memories[i].memory.confidence:.3f})"
                        )
                    else:
                        similar_indices.add(i)
                        similar_ids.append(memories[i].memory.memory_id)
                        logger.debug(
                            f"Semantic similar: Removing {memories[i].memory.memory_id} "
                            f"(similarity {similarity_matrix[i, j]:.3f}, "
                            f"lower confidence {memories[i].memory.confidence:.3f} vs "
                            f"{memories[j].memory.confidence:.3f})"
                        )
                        break  # i is removed, move to next i

        return similar_indices, similar_ids

    def _handle_corrections(
        self, memories: list[RetrievalResult]
    ) -> tuple[list[RetrievalResult], list[str]]:
        """Handle correction memories superseding older memories.

        Corrections (memory_type="correction") supersede older memories if:
        1. metadata["supersedes"] field points to an older memory
        2. The superseded memory exists in the list

        Args:
            memories: List of memories including possible corrections

        Returns:
            Tuple of (memories after correction filtering, superseded memory IDs)
        """
        # Find correction memories
        corrections = [
            mem for mem in memories if mem.memory.memory_type == "correction"
        ]

        if not corrections:
            return memories, []

        # Build set of memory IDs to supersede
        superseded_ids: list[str] = []
        for correction in corrections:
            supersedes_id = correction.memory.metadata.get("supersedes")
            if supersedes_id:
                superseded_ids.append(supersedes_id)
                logger.debug(
                    f"Correction {correction.memory.memory_id} supersedes {supersedes_id}"
                )

        # Filter out superseded memories
        filtered_memories = [
            mem for mem in memories if mem.memory.memory_id not in superseded_ids
        ]

        return filtered_memories, superseded_ids
