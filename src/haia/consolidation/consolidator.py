"""
Memory consolidation service for lifecycle management.

Automatically promotes high-priority memories (SHORT_TERM → LONG_TERM) and
archives low-priority memories (LONG_TERM → ARCHIVED) based on access patterns,
recency, and confidence.

Session 14 (US6): Memory Consolidation Lifecycle
"""

import logging
import time
from datetime import UTC, datetime, timedelta

from haia.consolidation.decay import DecayStrategy, ExponentialDecay
from haia.consolidation.models import (
    ConsolidationDecision,
    ConsolidationMetrics,
    ConsolidationReport,
    MemoryTier,
)
from haia.services.neo4j import Neo4jService

logger = logging.getLogger(__name__)


class MemoryConsolidator:
    """
    Service for automatic memory lifecycle consolidation (T105).

    Evaluates memories based on priority score and moves them between tiers:
    - SHORT_TERM → LONG_TERM (promotion) if priority >= promotion_threshold
    - LONG_TERM → ARCHIVED (archival) if priority < archival_threshold

    Priority formula: 0.40 * access_freq + 0.30 * recency + 0.30 * confidence
    """

    def __init__(
        self,
        neo4j_service: Neo4jService,
        decay_strategy: DecayStrategy | None = None,
        promotion_threshold: float = 0.7,
        archival_threshold: float = 0.2,
        short_term_days: int = 7,
        access_weight: float = 0.40,
        recency_weight: float = 0.30,
        confidence_weight: float = 0.30,
    ):
        """
        Initialize Memory Consolidator.

        Args:
            neo4j_service: Neo4j service for database operations
            decay_strategy: Decay strategy for recency scoring (default: ExponentialDecay)
            promotion_threshold: Priority threshold for SHORT_TERM → LONG_TERM (default: 0.7)
            archival_threshold: Priority threshold for LONG_TERM → ARCHIVED (default: 0.2)
            short_term_days: Min days before SHORT_TERM memories can be promoted (default: 7)
            access_weight: Weight for access frequency in priority formula (default: 0.40)
            recency_weight: Weight for recency score in priority formula (default: 0.30)
            confidence_weight: Weight for confidence in priority formula (default: 0.30)
        """
        self.neo4j = neo4j_service
        self.decay_strategy = decay_strategy or ExponentialDecay()
        self.promotion_threshold = promotion_threshold
        self.archival_threshold = archival_threshold
        self.short_term_days = short_term_days
        self.access_weight = access_weight
        self.recency_weight = recency_weight
        self.confidence_weight = confidence_weight

        # Validate weights sum to ~1.0
        total_weight = access_weight + recency_weight + confidence_weight
        if not (0.99 <= total_weight <= 1.01):
            logger.warning(
                f"Priority weights sum to {total_weight:.2f}, not 1.0. "
                f"Scores may not be normalized correctly."
            )

        logger.info(
            f"MemoryConsolidator initialized: "
            f"promotion={promotion_threshold}, archival={archival_threshold}, "
            f"weights=({access_weight}/{recency_weight}/{confidence_weight}), "
            f"decay_strategy={decay_strategy.__class__.__name__}"
        )

    def calculate_priority_score(
        self,
        confidence: float,
        created_at: datetime,
        last_accessed: datetime | None,
        access_count: int,
        max_access_count: int,
    ) -> tuple[float, ConsolidationMetrics]:
        """
        Calculate priority score for a memory (T106).

        Formula: 0.40 * access_freq + 0.30 * recency + 0.30 * confidence

        Args:
            confidence: Memory extraction confidence (0.0-1.0)
            created_at: When memory was created
            last_accessed: When memory was last accessed (None if never)
            access_count: Number of times memory was retrieved
            max_access_count: Maximum access count across all memories (for normalization)

        Returns:
            Tuple of (priority_score, metrics_obj)
        """
        # Calculate access frequency (normalized by max)
        if max_access_count > 0:
            access_frequency = access_count / max_access_count
        else:
            access_frequency = 0.0

        # Calculate recency score using decay strategy
        recency_score = self.decay_strategy.calculate_decay(
            created_at=created_at,
            last_accessed=last_accessed,
            access_count=access_count,
        )

        # Calculate weighted priority score
        priority_score = (
            self.access_weight * access_frequency
            + self.recency_weight * recency_score
            + self.confidence_weight * confidence
        )

        # Create metrics object
        metrics = ConsolidationMetrics(
            priority_score=priority_score,
            access_frequency=access_frequency,
            recency_score=recency_score,
            confidence_score=confidence,
            tier=MemoryTier.SHORT_TERM,  # Will be updated by caller
            last_accessed=last_accessed,
            access_count=access_count,
        )

        return priority_score, metrics

    async def evaluate_short_term_memories(
        self, max_access_count: int
    ) -> list[ConsolidationDecision]:
        """
        Evaluate SHORT_TERM memories for promotion to LONG_TERM (T107).

        Only evaluates memories older than short_term_days.
        Recommends promotion if priority >= promotion_threshold.

        Args:
            max_access_count: Maximum access count for normalization

        Returns:
            List of consolidation decisions for SHORT_TERM memories
        """
        cutoff_date = datetime.now(UTC) - timedelta(days=self.short_term_days)

        # Query SHORT_TERM memories older than cutoff
        query = """
        MATCH (m:Memory)
        WHERE m.tier = $tier
          AND m.created_at <= $cutoff_date
        RETURN m.memory_id AS memory_id,
               m.confidence AS confidence,
               m.created_at AS created_at,
               m.last_accessed AS last_accessed,
               m.access_count AS access_count
        """

        decisions = []

        try:
            async with self.neo4j.driver.session() as session:
                result = await session.run(
                    query,
                    tier=MemoryTier.SHORT_TERM.value,
                    cutoff_date=cutoff_date,
                )

                records = [record.data() async for record in result]

                logger.debug(
                    f"Evaluating {len(records)} SHORT_TERM memories "
                    f"(>= {self.short_term_days} days old)"
                )

                for record in records:
                    # Calculate priority score
                    priority, metrics = self.calculate_priority_score(
                        confidence=record["confidence"],
                        created_at=record["created_at"].to_native(),
                        last_accessed=(
                            record["last_accessed"].to_native()
                            if record["last_accessed"]
                            else None
                        ),
                        access_count=record.get("access_count", 0),
                        max_access_count=max_access_count,
                    )

                    metrics.tier = MemoryTier.SHORT_TERM

                    # Determine if promotion is recommended
                    if priority >= self.promotion_threshold:
                        recommended_tier = MemoryTier.LONG_TERM
                        reasoning = (
                            f"HIGH PRIORITY (score: {priority:.3f}). "
                            f"Access frequency: {metrics.access_frequency:.2f}, "
                            f"Recency: {metrics.recency_score:.2f}, "
                            f"Confidence: {metrics.confidence_score:.2f}. "
                            f"Exceeds promotion threshold {self.promotion_threshold}. "
                            f"Promoting to LONG_TERM."
                        )
                    else:
                        recommended_tier = MemoryTier.SHORT_TERM
                        reasoning = (
                            f"Priority {priority:.3f} below promotion "
                            f"threshold {self.promotion_threshold}. "
                            f"Keeping in SHORT_TERM."
                        )

                    decision = ConsolidationDecision(
                        memory_id=record["memory_id"],
                        current_tier=MemoryTier.SHORT_TERM,
                        recommended_tier=recommended_tier,
                        priority_score=priority,
                        reasoning=reasoning,
                        threshold=self.promotion_threshold,
                        metrics=metrics,
                    )

                    decisions.append(decision)

                promoted_count = sum(
                    1 for d in decisions if d.recommended_tier == MemoryTier.LONG_TERM
                )
                logger.info(
                    f"SHORT_TERM evaluation: {promoted_count}/{len(decisions)} "
                    f"recommended for promotion"
                )

        except Exception as e:
            logger.error(f"Failed to evaluate SHORT_TERM memories: {e}")

        return decisions

    async def evaluate_long_term_memories(
        self, max_access_count: int
    ) -> list[ConsolidationDecision]:
        """
        Evaluate LONG_TERM memories for archival to ARCHIVED (T108).

        Recommends archival if priority < archival_threshold.

        Args:
            max_access_count: Maximum access count for normalization

        Returns:
            List of consolidation decisions for LONG_TERM memories
        """
        # Query LONG_TERM memories
        query = """
        MATCH (m:Memory)
        WHERE m.tier = $tier
        RETURN m.memory_id AS memory_id,
               m.confidence AS confidence,
               m.created_at AS created_at,
               m.last_accessed AS last_accessed,
               m.access_count AS access_count
        """

        decisions = []

        try:
            async with self.neo4j.driver.session() as session:
                result = await session.run(query, tier=MemoryTier.LONG_TERM.value)

                records = [record.data() async for record in result]

                logger.debug(f"Evaluating {len(records)} LONG_TERM memories")

                for record in records:
                    # Calculate priority score
                    priority, metrics = self.calculate_priority_score(
                        confidence=record["confidence"],
                        created_at=record["created_at"].to_native(),
                        last_accessed=(
                            record["last_accessed"].to_native()
                            if record["last_accessed"]
                            else None
                        ),
                        access_count=record.get("access_count", 0),
                        max_access_count=max_access_count,
                    )

                    metrics.tier = MemoryTier.LONG_TERM

                    # Determine if archival is recommended
                    if priority < self.archival_threshold:
                        recommended_tier = MemoryTier.ARCHIVED
                        reasoning = (
                            f"LOW PRIORITY (score: {priority:.3f}). "
                            f"Access frequency: {metrics.access_frequency:.2f}, "
                            f"Recency: {metrics.recency_score:.2f}, "
                            f"Confidence: {metrics.confidence_score:.2f}. "
                            f"Below archival threshold {self.archival_threshold}. "
                            f"Archiving to ARCHIVED."
                        )
                    else:
                        recommended_tier = MemoryTier.LONG_TERM
                        reasoning = (
                            f"Priority {priority:.3f} above archival "
                            f"threshold {self.archival_threshold}. "
                            f"Keeping in LONG_TERM."
                        )

                    decision = ConsolidationDecision(
                        memory_id=record["memory_id"],
                        current_tier=MemoryTier.LONG_TERM,
                        recommended_tier=recommended_tier,
                        priority_score=priority,
                        reasoning=reasoning,
                        threshold=self.archival_threshold,
                        metrics=metrics,
                    )

                    decisions.append(decision)

                archived_count = sum(
                    1 for d in decisions if d.recommended_tier == MemoryTier.ARCHIVED
                )
                logger.info(
                    f"LONG_TERM evaluation: {archived_count}/{len(decisions)} "
                    f"recommended for archival"
                )

        except Exception as e:
            logger.error(f"Failed to evaluate LONG_TERM memories: {e}")

        return decisions

    async def apply_decisions(
        self, decisions: list[ConsolidationDecision]
    ) -> tuple[int, int, int]:
        """
        Apply consolidation decisions by updating memory tiers (T109).

        Logs each decision with reasoning for observability (P5).

        Args:
            decisions: List of consolidation decisions

        Returns:
            Tuple of (promoted_count, archived_count, unchanged_count)
        """
        promoted_count = 0
        archived_count = 0
        unchanged_count = 0

        query = """
        MATCH (m:Memory {memory_id: $memory_id})
        SET m.tier = $new_tier,
            m.tier_updated_at = datetime(),
            m.consolidation_score = $priority_score
        RETURN m.memory_id
        """

        for decision in decisions:
            # Skip if no tier change
            if decision.current_tier == decision.recommended_tier:
                unchanged_count += 1
                continue

            try:
                async with self.neo4j.driver.session() as session:
                    result = await session.run(
                        query,
                        memory_id=decision.memory_id,
                        new_tier=decision.recommended_tier.value,
                        priority_score=decision.priority_score,
                    )

                    record = await result.single()

                    if record:
                        # Log decision with reasoning (P5: Observability)
                        if decision.recommended_tier == MemoryTier.LONG_TERM:
                            promoted_count += 1
                            logger.info(
                                f"✓ PROMOTED: {decision.memory_id[:8]}... → LONG_TERM "
                                f"(score: {decision.priority_score:.3f}). "
                                f"{decision.reasoning}"
                            )
                        elif decision.recommended_tier == MemoryTier.ARCHIVED:
                            archived_count += 1
                            logger.info(
                                f"✓ ARCHIVED: {decision.memory_id[:8]}... → ARCHIVED "
                                f"(score: {decision.priority_score:.3f}). "
                                f"{decision.reasoning}"
                            )
                    else:
                        logger.warning(
                            f"Failed to update tier for {decision.memory_id}: Memory not found"
                        )

            except Exception as e:
                logger.error(
                    f"Failed to apply decision for {decision.memory_id}: {e}"
                )

        logger.info(
            f"Applied decisions: {promoted_count} promoted, {archived_count} archived, "
            f"{unchanged_count} unchanged"
        )

        return promoted_count, archived_count, unchanged_count

    async def run_consolidation(self) -> ConsolidationReport:
        """
        Execute full consolidation workflow (T110).

        Orchestrates:
        1. Evaluate SHORT_TERM memories for promotion
        2. Evaluate LONG_TERM memories for archival
        3. Apply decisions
        4. Generate report

        Returns:
            ConsolidationReport with execution summary
        """
        start_time = time.time()
        timestamp = datetime.now(UTC)

        logger.info("=" * 60)
        logger.info("Starting memory consolidation job...")
        logger.info("=" * 60)

        try:
            # Get maximum access count for normalization
            max_access_query = """
            MATCH (m:Memory)
            RETURN max(coalesce(m.access_count, 0)) AS max_access
            """

            async with self.neo4j.driver.session() as session:
                result = await session.run(max_access_query)
                record = await result.single()
                max_access_count = record["max_access"] if record else 0

            logger.debug(f"Maximum access count: {max_access_count}")

            # Step 1: Evaluate SHORT_TERM memories
            short_term_decisions = await self.evaluate_short_term_memories(
                max_access_count
            )

            # Step 2: Evaluate LONG_TERM memories
            long_term_decisions = await self.evaluate_long_term_memories(
                max_access_count
            )

            # Combine all decisions
            all_decisions = short_term_decisions + long_term_decisions

            # Step 3: Apply decisions
            promoted, archived, unchanged = await self.apply_decisions(all_decisions)

            # Step 4: Generate report
            execution_time_ms = (time.time() - start_time) * 1000

            report = ConsolidationReport(
                timestamp=timestamp,
                processed_count=len(all_decisions),
                promoted_count=promoted,
                archived_count=archived,
                unchanged_count=unchanged,
                decisions=[
                    d for d in all_decisions if d.current_tier != d.recommended_tier
                ],
                execution_time_ms=execution_time_ms,
            )

            logger.info("=" * 60)
            logger.info(report.summary())
            logger.info("=" * 60)

            return report

        except Exception as e:
            logger.error(f"Consolidation job failed: {e}", exc_info=True)

            # Return error report
            execution_time_ms = (time.time() - start_time) * 1000
            return ConsolidationReport(
                timestamp=timestamp,
                processed_count=0,
                promoted_count=0,
                archived_count=0,
                unchanged_count=0,
                decisions=[],
                execution_time_ms=execution_time_ms,
            )
