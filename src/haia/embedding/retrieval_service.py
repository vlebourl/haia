"""Retrieval service for semantic memory search.

This module provides the core retrieval functionality for memory search,
including relevance scoring, ranking, and deduplication.
"""

import logging
import time
from datetime import datetime, timezone
from typing import Optional

from haia.embedding.models import (
    RetrievalQuery,
    RetrievalResponse,
    RetrievalResult,
    RelevanceScore,
)
from haia.embedding.ollama_client import OllamaClient
from haia.extraction.models import ExtractedMemory
from haia.services.neo4j import Neo4jService

logger = logging.getLogger(__name__)


class RetrievalService:
    """Service for semantic memory retrieval.

    This service orchestrates:
    - Query embedding generation via Ollama
    - Vector similarity search via Neo4j
    - Relevance scoring and ranking
    - Deduplication of near-duplicate results
    """

    def __init__(
        self,
        neo4j_service: Neo4jService,
        ollama_client: OllamaClient,
        similarity_weight: float = 0.5,
        confidence_weight: float = 0.3,
        recency_weight: float = 0.2,
        type_weights: dict[str, float] | None = None,
        recency_decay_days: float = 43.3,
    ):
        """Initialize retrieval service.

        Args:
            neo4j_service: Neo4j database service
            ollama_client: Ollama embedding client
            similarity_weight: Weight for similarity score (α) - default 0.5 (50%)
            confidence_weight: Weight for confidence score (β) - default 0.3 (30%)
            recency_weight: Weight for recency score (γ) - default 0.2 (20%)
            type_weights: Weight multipliers by memory type (δ) - defaults to 1.0 for all
            recency_decay_days: Days for recency to decay to ~0.5 (default 43.3)
        """
        self.neo4j = neo4j_service
        self.ollama = ollama_client
        self.similarity_weight = similarity_weight
        self.confidence_weight = confidence_weight
        self.recency_weight = recency_weight
        self.recency_decay_days = recency_decay_days

        # Default type weights (1.0 = neutral)
        self.type_weights = type_weights or {
            "preference": 1.2,
            "technical_context": 1.1,
            "decision": 1.0,
            "personal_fact": 0.9,
            "correction": 1.3,
        }

        logger.info(
            f"RetrievalService initialized (α={similarity_weight}, β={confidence_weight}, "
            f"γ={recency_weight}, type_weights={self.type_weights})"
        )

    async def retrieve(self, query: RetrievalQuery) -> RetrievalResponse:
        """Retrieve relevant memories for a query.

        Args:
            query: Retrieval query with text, filters, and thresholds

        Returns:
            Retrieval response with ranked results and metadata

        Raises:
            Exception: If retrieval fails
        """
        start_time = time.time()

        # Step 1: Generate query embedding (or use precomputed)
        if query.query_embedding is not None:
            query_vector = query.query_embedding
            embedding_latency_ms = 0.0
            logger.debug("Using precomputed query embedding")
        else:
            embedding_start = time.time()
            query_vector = await self.generate_embedding(query.query_text)
            embedding_latency_ms = (time.time() - embedding_start) * 1000
            logger.debug(f"Generated query embedding ({embedding_latency_ms:.1f}ms)")

        # Step 2: Search similar memories via Neo4j vector index
        search_start = time.time()
        raw_memories = await self.neo4j.search_similar_memories(
            query_vector=query_vector,
            top_k=query.top_k,
            min_confidence=query.min_confidence,
            min_similarity=query.min_similarity,
            memory_types=query.memory_types,
        )
        search_latency_ms = (time.time() - search_start) * 1000

        memories_searched = len(raw_memories)
        logger.debug(
            f"Neo4j search returned {memories_searched} memories ({search_latency_ms:.1f}ms)"
        )

        # Step 3: Convert to ExtractedMemory objects and calculate relevance
        results = []
        for mem_data in raw_memories:
            try:
                memory = self._dict_to_memory(mem_data)
                similarity_score = mem_data["similarity_score"]
                relevance_score = self._calculate_relevance_score(
                    memory=memory,
                    similarity=similarity_score,
                )
                results.append((memory, similarity_score, relevance_score))
            except Exception as e:
                logger.warning(f"Failed to process memory {mem_data.get('memory_id')}: {e}")
                continue

        # Step 4: Deduplicate near-identical memories
        dedup_start = time.time()
        deduplicated_results, dedup_count = self._deduplicate_memories(results)
        logger.debug(f"Deduplication removed {dedup_count} near-duplicates")

        # Step 5: Rank by relevance score
        ranked_results = self._rank_memories(deduplicated_results)

        # Step 6: Limit to top_k
        final_results = ranked_results[: query.top_k]

        # Step 7: Create RetrievalResult objects
        retrieval_results = []
        for rank, (memory, similarity, relevance) in enumerate(final_results, start=1):
            retrieval_results.append(
                RetrievalResult(
                    memory=memory,
                    similarity_score=similarity,
                    relevance_score=relevance,
                    rank=rank,
                )
            )

        total_latency_ms = (time.time() - start_time) * 1000

        response = RetrievalResponse(
            query=query.query_text,
            results=retrieval_results,
            total_results=len(retrieval_results),
            total_latency_ms=total_latency_ms,
            embedding_latency_ms=embedding_latency_ms,
            search_latency_ms=search_latency_ms,
            top_k=query.top_k,
            min_similarity=query.min_similarity,
            min_confidence=query.min_confidence,
            memories_searched=memories_searched,
            memories_matched=len(ranked_results),
            memories_deduplicated=dedup_count,
        )

        top_relevance = retrieval_results[0].relevance_score if retrieval_results else 0.0
        logger.info(
            f"Retrieved {len(retrieval_results)} memories "
            f"(total: {total_latency_ms:.1f}ms, top relevance: {top_relevance:.3f})"
        )

        return response

    async def generate_embedding(self, text: str) -> list[float]:
        """Generate embedding vector for text.

        Args:
            text: Text to embed

        Returns:
            768-dimensional embedding vector

        Raises:
            EmbeddingError: If embedding generation fails
        """
        return await self.ollama.embed(text)

    def _calculate_relevance_score(
        self,
        memory: ExtractedMemory,
        similarity: float,
    ) -> float:
        """Calculate relevance score using multi-factor weighted combination.

        Formula: (α * similarity + β * confidence + γ * recency) * δ
        where:
        - α = similarity_weight (0.5 = 50%)
        - β = confidence_weight (0.3 = 30%)
        - γ = recency_weight (0.2 = 20%)
        - δ = type_weight (memory type multiplier)

        Recency uses exponential decay: exp(-days / decay_constant)
        where decay_constant controls the decay rate (default: 43.3 for ~0.5 at 30 days)

        Args:
            memory: Extracted memory with confidence, type, and timestamp
            similarity: Cosine similarity score (0.0-1.0)

        Returns:
            Relevance score (0.0+, typically 0.0-1.3 with default type weights)
        """
        confidence = memory.confidence

        # Calculate recency score using exponential decay
        recency_score = self._calculate_recency_score(memory.extraction_timestamp)

        # Get type weight multiplier (default to 1.0 if type not found)
        type_weight = self.type_weights.get(memory.memory_type, 1.0)

        # Combine all factors with weights
        base_score = (
            self.similarity_weight * similarity
            + self.confidence_weight * confidence
            + self.recency_weight * recency_score
        )

        # Apply type weight multiplier
        final_score = base_score * type_weight

        return max(0.0, final_score)  # Clamp to non-negative

    def _calculate_recency_score(self, extraction_timestamp: datetime | None) -> float:
        """Calculate recency score using exponential decay.

        Args:
            extraction_timestamp: When the memory was extracted

        Returns:
            Recency score (0.0-1.0), where 1.0 is most recent
        """
        if extraction_timestamp is None:
            # No timestamp available - use neutral score
            return 0.5

        # Calculate days since extraction
        now = datetime.now(timezone.utc)

        # Ensure extraction_timestamp is timezone-aware
        if extraction_timestamp.tzinfo is None:
            extraction_timestamp = extraction_timestamp.replace(tzinfo=timezone.utc)

        days_ago = (now - extraction_timestamp).total_seconds() / 86400.0

        # Exponential decay: exp(-days / decay_constant)
        # decay_constant = 43.3 gives ~0.5 at 30 days, ~0.1 at 100 days
        import math
        recency_score = math.exp(-days_ago / self.recency_decay_days)

        return min(1.0, max(0.0, recency_score))  # Clamp to [0, 1]

    def _rank_memories(
        self,
        memories: list[tuple[ExtractedMemory, float, float]],
    ) -> list[tuple[ExtractedMemory, float, float]]:
        """Rank memories by relevance score (descending).

        Args:
            memories: List of (memory, similarity, relevance) tuples

        Returns:
            Sorted list by relevance score (highest first)
        """
        return sorted(memories, key=lambda x: x[2], reverse=True)

    def _deduplicate_memories(
        self,
        memories: list[tuple[ExtractedMemory, float, float]],
        similarity_threshold: float = 0.95,
    ) -> tuple[list[tuple[ExtractedMemory, float, float]], int]:
        """Remove near-duplicate memories.

        Uses content-based similarity to detect duplicates. When duplicates
        are found, keeps the one with higher confidence.

        Args:
            memories: List of (memory, similarity, relevance) tuples
            similarity_threshold: Threshold for considering memories duplicates

        Returns:
            Tuple of (deduplicated list, count of removed duplicates)
        """
        if len(memories) <= 1:
            return memories, 0

        # Simple content-based deduplication using string similarity
        # For production, could use embeddings for more accurate comparison
        deduplicated = []
        removed_count = 0

        for mem, sim, rel in memories:
            is_duplicate = False
            duplicate_index = -1

            for idx, (existing_mem, existing_sim, existing_rel) in enumerate(deduplicated):
                # Check if content is very similar
                if self._are_similar_contents(
                    mem.content, existing_mem.content, similarity_threshold
                ):
                    is_duplicate = True
                    duplicate_index = idx
                    # If new memory has higher confidence, replace existing
                    if mem.confidence > existing_mem.confidence:
                        deduplicated[idx] = (mem, sim, rel)
                        logger.debug(
                            f"Replaced duplicate {existing_mem.memory_id} with {mem.memory_id} "
                            f"(higher confidence: {mem.confidence:.3f} > {existing_mem.confidence:.3f})"
                        )
                    else:
                        removed_count += 1
                        logger.debug(
                            f"Removed duplicate {mem.memory_id} "
                            f"(lower confidence: {mem.confidence:.3f} <= {existing_mem.confidence:.3f})"
                        )
                    break

            if not is_duplicate:
                deduplicated.append((mem, sim, rel))

        return deduplicated, removed_count

    def _are_similar_contents(
        self, content1: str, content2: str, threshold: float
    ) -> bool:
        """Check if two contents are similar enough to be duplicates.

        Uses simple character-level similarity for now.
        Could be enhanced with more sophisticated algorithms.

        Args:
            content1: First content string
            content2: Second content string
            threshold: Similarity threshold (0.0-1.0)

        Returns:
            True if contents are similar above threshold
        """
        # Normalize
        c1 = content1.lower().strip()
        c2 = content2.lower().strip()

        # Exact match
        if c1 == c2:
            return True

        # Calculate simple similarity (Jaccard on words)
        words1 = set(c1.split())
        words2 = set(c2.split())

        if not words1 or not words2:
            return False

        intersection = words1.intersection(words2)
        union = words1.union(words2)

        similarity = len(intersection) / len(union) if union else 0.0

        return similarity >= threshold

    def _dict_to_memory(self, data: dict) -> ExtractedMemory:
        """Convert Neo4j result dictionary to ExtractedMemory.

        Args:
            data: Dictionary from Neo4j query

        Returns:
            ExtractedMemory instance
        """
        # Convert Neo4j DateTime to Python datetime
        extraction_ts = data.get("extraction_timestamp")
        if hasattr(extraction_ts, "to_native"):
            extraction_ts = extraction_ts.to_native()

        embedding_updated = data.get("embedding_updated_at")
        if hasattr(embedding_updated, "to_native"):
            embedding_updated = embedding_updated.to_native()

        # Handle metadata - ensure it's always a dict
        metadata = data.get("metadata")
        if metadata is None:
            metadata = {}

        return ExtractedMemory(
            memory_id=data["memory_id"],
            memory_type=data["memory_type"],
            content=data["content"],
            confidence=data["confidence"],
            source_conversation_id=data["source_conversation_id"],
            extraction_timestamp=extraction_ts,
            category=data.get("category"),
            metadata=metadata,
            has_embedding=True,  # If it's in results, it has an embedding
            embedding_version=data.get("embedding_version"),
            embedding_updated_at=embedding_updated,
        )

    async def health_check(self) -> bool:
        """Check if retrieval service is operational.

        Returns:
            True if all dependencies are healthy
        """
        try:
            neo4j_ok = await self.neo4j.health_check()
            ollama_ok = await self.ollama.health_check()

            if neo4j_ok and ollama_ok:
                logger.debug("RetrievalService health check: OK")
                return True
            else:
                logger.warning(
                    f"RetrievalService health check: DEGRADED "
                    f"(Neo4j: {neo4j_ok}, Ollama: {ollama_ok})"
                )
                return False
        except Exception as e:
            logger.error(f"RetrievalService health check failed: {e}")
            return False
