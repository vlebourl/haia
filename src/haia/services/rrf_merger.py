"""Reciprocal Rank Fusion (RRF) merger for hybrid retrieval.

This module implements the RRF algorithm to combine ranked results from
multiple retrieval methods (vector, BM25, graph) into a unified ranking.

Based on: Cormack et al. 2009 - "Reciprocal rank fusion outperforms Condorcet"
"""

import logging

from src.haia.models.hybrid_retrieval import MethodResult, RetrievedMemory, RRFScore

logger = logging.getLogger(__name__)


class RRFMerger:
    """Merge ranked results using Reciprocal Rank Fusion algorithm.

    RRF combines multiple ranked lists by assigning scores based on ranks:
        score(d) = Σ (1 / (k + rank_i(d)))

    Where:
        - d = document/memory
        - k = constant parameter (default: 60)
        - rank_i(d) = rank of document d in method i (1-indexed)

    The algorithm is:
    - Parameter-free (k=60 is empirically optimal)
    - Robust across different retrieval methods
    - Rewards consensus across methods
    - Industry standard (Elasticsearch, Milvus, Azure AI Search)
    """

    def __init__(self, default_k: int = 60):
        """Initialize RRF merger.

        Args:
            default_k: Default RRF constant parameter (60 is standard)
        """
        self.default_k = default_k
        logger.debug(f"RRFMerger initialized with k={default_k}")

    def merge(
        self,
        method_results: list[MethodResult],
        k: int | None = None,
        top_k: int = 10,
    ) -> list[RRFScore]:
        """Merge ranked results from multiple methods using RRF.

        Args:
            method_results: Results from each retrieval method
            k: RRF constant parameter (uses default_k if None)
            top_k: Number of top results to return

        Returns:
            List of RRFScore objects sorted by score (descending)

        Example:
            merger = RRFMerger()
            rrf_scores = merger.merge(
                [vector_result, bm25_result, graph_result],
                top_k=10
            )
        """
        if not method_results:
            logger.warning("No method results provided to RRF merger")
            return []

        k_value = k if k is not None else self.default_k

        # Track scores and contributions for each memory
        scores: dict[str, float] = {}
        contributions: dict[str, dict[str, tuple[int, float]]] = {}

        # Collect all unique memories across methods
        all_memories: dict[str, RetrievedMemory] = {}

        # Process each method's results
        for method_result in method_results:
            method_name = method_result.method
            logger.debug(
                f"Processing {len(method_result.memories)} results from '{method_name}'"
            )

            # Iterate through ranked memories (1-indexed ranks)
            for rank, memory in enumerate(method_result.memories, start=1):
                memory_id = memory.memory_id

                # Store memory for later retrieval
                if memory_id not in all_memories:
                    all_memories[memory_id] = memory

                # Calculate RRF contribution for this rank
                rrf_contribution = 1.0 / (k_value + rank)

                # Accumulate total RRF score
                scores[memory_id] = scores.get(memory_id, 0.0) + rrf_contribution

                # Track method contributions for source attribution
                if memory_id not in contributions:
                    contributions[memory_id] = {}
                contributions[memory_id][method_name] = (rank, rrf_contribution)

        # Create RRFScore objects
        rrf_scores = [
            RRFScore(
                memory_id=memory_id,
                rrf_score=score,
                method_contributions=contributions[memory_id],
                source_methods=list(contributions[memory_id].keys()),
            )
            for memory_id, score in scores.items()
        ]

        # Sort by RRF score (descending) and limit to top_k
        sorted_scores = sorted(rrf_scores, key=lambda x: x.rrf_score, reverse=True)[
            :top_k
        ]

        logger.info(
            f"RRF merged {len(all_memories)} unique memories from "
            f"{len(method_results)} methods, returning top {len(sorted_scores)}"
        )

        return sorted_scores

    def merge_with_deduplication(
        self,
        method_results: list[MethodResult],
        k: int | None = None,
        top_k: int = 10,
        dedup_threshold: float = 0.98,
    ) -> list[RRFScore]:
        """Merge results with exact duplicate removal.

        This is a simple deduplication that removes exact duplicate memory_ids
        within a single method's results. Cross-method duplicates are expected
        and contribute to higher RRF scores (consensus signal).

        Args:
            method_results: Results from each retrieval method
            k: RRF constant parameter
            top_k: Number of top results to return
            dedup_threshold: Not used (placeholder for future semantic dedup)

        Returns:
            List of RRFScore objects with duplicates removed
        """
        # Deduplicate within each method
        deduped_results = []
        for method_result in method_results:
            seen_ids = set()
            unique_memories = []

            for memory in method_result.memories:
                if memory.memory_id not in seen_ids:
                    unique_memories.append(memory)
                    seen_ids.add(memory.memory_id)

            deduped_results.append(
                MethodResult(
                    method=method_result.method,
                    memories=unique_memories,
                    scores=method_result.scores,
                    error=method_result.error,
                )
            )

            if len(unique_memories) < len(method_result.memories):
                logger.debug(
                    f"Removed {len(method_result.memories) - len(unique_memories)} "
                    f"duplicate memories from '{method_result.method}'"
                )

        # Use standard merge on deduplicated results
        return self.merge(deduped_results, k=k, top_k=top_k)
