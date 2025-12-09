"""Advanced re-ranking with multi-factor scoring.

This module provides the Ranker class for re-ranking retrieval results based on:
- Similarity score (cosine similarity from embedding search)
- Confidence score (extraction confidence)
- Recency score (how recently the memory was created)
- Frequency score (how often the memory is accessed)

Default weights: 40% similarity, 25% confidence, 20% recency, 15% frequency

Usage:
    ranker = Ranker()  # Use default weights
    ranked_results = ranker.rerank(retrieval_results)

    # Custom weights
    weights = ScoreWeights(similarity=0.50, confidence=0.30, recency=0.10, frequency=0.10)
    ranker = Ranker(weights=weights)
"""

import logging
import math
from datetime import datetime, timezone
from typing import Optional

from haia.context.models import ScoreWeights, AccessMetadata
from haia.embedding.models import RetrievalResult

logger = logging.getLogger(__name__)


class Ranker:
    """Multi-factor re-ranking for memory retrieval results.

    Combines similarity, confidence, recency, and frequency into a composite score.
    """

    def __init__(
        self,
        weights: Optional[ScoreWeights] = None,
        recency_half_life_days: float = 43.3,
        frequency_scale_factor: float = 10.0,
    ):
        """Initialize ranker with scoring weights.

        Args:
            weights: Score weights for each factor. If None, uses defaults:
                     40% similarity, 25% confidence, 20% recency, 15% frequency
            recency_half_life_days: Days for recency to decay to 0.5 (default 43.3 = ~6 weeks)
            frequency_scale_factor: Scale factor for log-based frequency scoring (default 10)
        """
        self.weights = weights or ScoreWeights(
            similarity_weight=0.40,
            confidence_weight=0.25,
            recency_weight=0.20,
            frequency_weight=0.15,
        )
        self.recency_half_life_days = recency_half_life_days
        self.frequency_scale_factor = frequency_scale_factor

        logger.info(
            f"Ranker initialized with weights: "
            f"sim={self.weights.similarity_weight:.2f}, "
            f"conf={self.weights.confidence_weight:.2f}, "
            f"rec={self.weights.recency_weight:.2f}, "
            f"freq={self.weights.frequency_weight:.2f}"
        )

    def rerank(self, results: list[RetrievalResult]) -> list[RetrievalResult]:
        """Re-rank retrieval results using multi-factor scoring.

        Args:
            results: List of retrieval results to re-rank

        Returns:
            Re-ranked list sorted by composite score (highest first)
        """
        if not results:
            return []

        if len(results) == 1:
            # Single result - just update rank and return
            results[0].rank = 1
            return results

        # Calculate composite score for each result
        scored_results = []
        for result in results:
            composite_score = self._calculate_composite_score(result)
            # Update relevance_score with composite score
            result.relevance_score = composite_score
            scored_results.append(result)

        # Sort by composite score (descending)
        scored_results.sort(key=lambda r: r.relevance_score, reverse=True)

        # Update ranks (1-indexed)
        for rank, result in enumerate(scored_results, start=1):
            result.rank = rank

        logger.debug(
            f"Re-ranked {len(scored_results)} results. "
            f"Top score: {scored_results[0].relevance_score:.3f}"
        )

        return scored_results

    def _calculate_composite_score(self, result: RetrievalResult) -> float:
        """Calculate weighted composite score for a result.

        Formula:
            score = α*similarity + β*confidence + γ*recency + δ*frequency

        Args:
            result: Retrieval result to score

        Returns:
            Composite score between 0.0 and 1.0
        """
        # Component scores (all normalized to 0.0-1.0)
        similarity_score = result.similarity_score
        confidence_score = result.memory.confidence

        # Recency score from extraction timestamp
        recency_score = self._calculate_recency_score(
            result.memory.extraction_timestamp
        )

        # Frequency score from access metadata
        frequency_score = self._calculate_frequency_score_from_metadata(result)

        # Weighted composite
        composite = (
            self.weights.similarity_weight * similarity_score
            + self.weights.confidence_weight * confidence_score
            + self.weights.recency_weight * recency_score
            + self.weights.frequency_weight * frequency_score
        )

        logger.debug(
            f"Composite score for {result.memory.memory_id}: {composite:.3f} "
            f"(sim={similarity_score:.3f}, conf={confidence_score:.3f}, "
            f"rec={recency_score:.3f}, freq={frequency_score:.3f})"
        )

        return composite

    def _calculate_recency_score(self, extraction_timestamp: datetime) -> float:
        """Calculate recency score using exponential decay.

        Formula:
            score = e^(-λ * days_ago)
            where λ = ln(2) / half_life_days

        Args:
            extraction_timestamp: When memory was extracted

        Returns:
            Score between 0.0 (very old) and 1.0 (very recent)
        """
        now = datetime.now(timezone.utc)

        # Handle timezone-naive timestamps
        if extraction_timestamp.tzinfo is None:
            extraction_timestamp = extraction_timestamp.replace(tzinfo=timezone.utc)

        # Calculate days ago
        time_diff = now - extraction_timestamp
        days_ago = time_diff.total_seconds() / 86400.0

        # Exponential decay: score = e^(-λ * days)
        decay_constant = math.log(2) / self.recency_half_life_days
        recency_score = math.exp(-decay_constant * days_ago)

        return recency_score

    def _calculate_frequency_score_from_metadata(
        self, result: RetrievalResult
    ) -> float:
        """Extract access count from metadata and calculate frequency score.

        Args:
            result: Retrieval result with access_metadata

        Returns:
            Frequency score between 0.0 and 1.0
        """
        if result.access_metadata is None:
            # No access tracking - default to 0
            return 0.0

        access_count = result.access_metadata.access_count
        return self._calculate_frequency_score(access_count)

    def _calculate_frequency_score(self, access_count: int) -> float:
        """Calculate frequency score using logarithmic scaling.

        Formula:
            score = log(1 + count) / log(1 + scale_factor)

        This provides diminishing returns for high access counts.

        Args:
            access_count: Number of times memory was accessed

        Returns:
            Score between 0.0 (never accessed) and ~1.0 (very frequently accessed)
        """
        if access_count == 0:
            return 0.0

        # Logarithmic scaling with diminishing returns
        # log(1 + count) / log(1 + scale_factor)
        # With scale_factor=10, count=10 gives ~0.5, count=100 gives ~0.8
        numerator = math.log(1 + access_count)
        denominator = math.log(1 + access_count + self.frequency_scale_factor)

        frequency_score = numerator / denominator

        return frequency_score
