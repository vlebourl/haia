"""
Acceptance validation tests for US6: Memory Consolidation Lifecycle (Session 14).

Tests cover:
- T113: Promotion logic validation (~30% promoted)
- T114: Archival logic validation (~20% archived)
- T115: Priority calculation formula validation
- T116: Decay strategy validation
- T117: Observability logging validation
- T118: Performance validation (<5s for 1000 memories)
- T119: Archived memory retrieval validation

Test Strategy:
- Create synthetic memories with varying access patterns, recency, and confidence
- Run consolidation and validate expected tier transitions
- Verify priority scoring formula
- Verify logging and observability
- Validate performance at scale

Requires:
- Neo4j running (docker compose up neo4j)
- RUN_INTEGRATION_TESTS=1 environment variable
"""

import logging
import os
import time
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from haia.consolidation.consolidator import MemoryConsolidator
from haia.consolidation.decay import (
    DecayStrategy,
    EbbinghausDecay,
    ExponentialDecay,
    LinearDecay,
)
from haia.consolidation.models import ConsolidationReport, MemoryTier
from haia.services.neo4j import Neo4jService

logger = logging.getLogger(__name__)

# Skip all tests in this file unless RUN_INTEGRATION_TESTS=1
pytestmark = pytest.mark.skipif(
    os.getenv("RUN_INTEGRATION_TESTS") != "1",
    reason="Integration tests require RUN_INTEGRATION_TESTS=1 and running Neo4j",
)


@pytest.fixture
async def neo4j():
    """Neo4j service fixture."""
    service = Neo4jService(
        uri=os.getenv("NEO4J_URI", "bolt://localhost:7687"),
        user=os.getenv("NEO4J_USER", "neo4j"),
        password=os.getenv("NEO4J_PASSWORD", "haia_neo4j_secure_2024"),
    )
    await service.connect()
    yield service
    await service.close()


@pytest.fixture
async def consolidator(neo4j: Neo4jService):
    """MemoryConsolidator fixture with default configuration."""
    return MemoryConsolidator(
        neo4j_service=neo4j,
        decay_strategy=ExponentialDecay(),
        promotion_threshold=0.7,
        archival_threshold=0.2,
        short_term_days=7,
        access_weight=0.40,
        recency_weight=0.30,
        confidence_weight=0.30,
    )


async def create_test_memory(
    neo4j: Neo4jService,
    tier: MemoryTier,
    confidence: float = 0.8,
    access_count: int = 0,
    created_days_ago: int = 10,
    last_accessed_days_ago: int | None = None,
) -> str:
    """
    Create a test memory with specified attributes for consolidation testing.

    Args:
        neo4j: Neo4j service
        tier: Initial memory tier
        confidence: Extraction confidence (0.0-1.0)
        access_count: Number of times accessed
        created_days_ago: Days since creation
        last_accessed_days_ago: Days since last access (None if never accessed)

    Returns:
        memory_id of created memory
    """
    memory_id = str(uuid4())
    created_at = datetime.now(timezone.utc) - timedelta(days=created_days_ago)
    last_accessed = (
        datetime.now(timezone.utc) - timedelta(days=last_accessed_days_ago)
        if last_accessed_days_ago is not None
        else None
    )

    query = """
    CREATE (m:Memory {
        memory_id: $memory_id,
        content: $content,
        memory_type: "test_type",
        confidence: $confidence,
        tier: $tier,
        access_count: $access_count,
        created_at: $created_at,
        last_accessed: $last_accessed,
        valid_from: $created_at,
        valid_until: null,
        extracted_at: $created_at
    })
    RETURN m.memory_id
    """

    async with neo4j.driver.session() as session:
        await session.run(
            query,
            memory_id=memory_id,
            content=f"Test memory {memory_id}",
            confidence=confidence,
            tier=tier.value,
            access_count=access_count,
            created_at=created_at,
            last_accessed=last_accessed,
        )

    return memory_id


async def cleanup_test_memories(neo4j: Neo4jService):
    """Delete all test memories created during tests."""
    query = """
    MATCH (m:Memory)
    WHERE m.memory_type = "test_type"
    DELETE m
    """

    async with neo4j.driver.session() as session:
        result = await session.run(query)
        summary = await result.consume()
        deleted = summary.counters.nodes_deleted
        logger.info(f"Cleaned up {deleted} test memories")


@pytest.mark.asyncio
async def test_t113_promotion_logic(neo4j: Neo4jService, consolidator: MemoryConsolidator):
    """
    T113: Validate promotion logic (~30% promoted).

    Creates 100 SHORT_TERM memories with varying characteristics.
    Expects ~30% to be promoted to LONG_TERM based on priority thresholds.
    """
    await cleanup_test_memories(neo4j)

    # Create 100 SHORT_TERM memories with diverse characteristics
    memory_ids = []

    # High priority group (30 memories): High access, recent, high confidence
    # Expected: PROMOTED to LONG_TERM
    for i in range(30):
        memory_id = await create_test_memory(
            neo4j,
            tier=MemoryTier.SHORT_TERM,
            confidence=0.9,
            access_count=20 + i,  # High access
            created_days_ago=10,
            last_accessed_days_ago=1,  # Very recent
        )
        memory_ids.append(memory_id)

    # Medium priority group (40 memories): Medium access, medium recency
    # Expected: REMAIN in SHORT_TERM
    for i in range(40):
        memory_id = await create_test_memory(
            neo4j,
            tier=MemoryTier.SHORT_TERM,
            confidence=0.6,
            access_count=5,
            created_days_ago=10,
            last_accessed_days_ago=5,
        )
        memory_ids.append(memory_id)

    # Low priority group (30 memories): Low access, old, low confidence
    # Expected: REMAIN in SHORT_TERM (not eligible for archival yet)
    for i in range(30):
        memory_id = await create_test_memory(
            neo4j,
            tier=MemoryTier.SHORT_TERM,
            confidence=0.4,
            access_count=1,
            created_days_ago=10,
            last_accessed_days_ago=None,  # Never accessed
        )
        memory_ids.append(memory_id)

    logger.info(f"Created {len(memory_ids)} SHORT_TERM test memories")

    # Run consolidation
    report: ConsolidationReport = await consolidator.run_consolidation()

    # Validate results
    logger.info(f"Promotion rate: {report.promotion_rate:.1f}%")
    logger.info(f"Promoted: {report.promoted_count}/{report.processed_count}")

    # Expect ~30% promotion (allowing 10% variance)
    assert 20 <= report.promotion_rate <= 40, \
        f"Expected 20-40% promotion rate, got {report.promotion_rate:.1f}%"

    # Verify promoted memories are now in LONG_TERM tier
    promoted_count = 0
    async with neo4j.driver.session() as session:
        result = await session.run(
            "MATCH (m:Memory {tier: $tier}) WHERE m.memory_type = 'test_type' RETURN count(m) AS count",
            tier=MemoryTier.LONG_TERM.value,
        )
        record = await result.single()
        promoted_count = record["count"]

    assert promoted_count == report.promoted_count, \
        f"Promoted count mismatch: report={report.promoted_count}, actual={promoted_count}"

    logger.info(f"✓ T113 PASSED: Promotion logic validated ({report.promotion_rate:.1f}% promoted)")

    await cleanup_test_memories(neo4j)


@pytest.mark.asyncio
async def test_t114_archival_logic(neo4j: Neo4jService, consolidator: MemoryConsolidator):
    """
    T114: Validate archival logic (~20% archived).

    Creates 100 LONG_TERM memories with varying characteristics.
    Expects ~20% to be archived based on low priority scores.
    """
    await cleanup_test_memories(neo4j)

    # Create 100 LONG_TERM memories with diverse characteristics
    memory_ids = []

    # High priority group (30 memories): High access, recent, high confidence
    # Expected: REMAIN in LONG_TERM
    for i in range(30):
        memory_id = await create_test_memory(
            neo4j,
            tier=MemoryTier.LONG_TERM,
            confidence=0.9,
            access_count=50 + i,
            created_days_ago=30,
            last_accessed_days_ago=2,
        )
        memory_ids.append(memory_id)

    # Medium priority group (50 memories): Medium characteristics
    # Expected: REMAIN in LONG_TERM
    for i in range(50):
        memory_id = await create_test_memory(
            neo4j,
            tier=MemoryTier.LONG_TERM,
            confidence=0.6,
            access_count=10,
            created_days_ago=60,
            last_accessed_days_ago=20,
        )
        memory_ids.append(memory_id)

    # Low priority group (20 memories): Very low access, very old, low confidence
    # Expected: ARCHIVED
    for i in range(20):
        memory_id = await create_test_memory(
            neo4j,
            tier=MemoryTier.LONG_TERM,
            confidence=0.3,
            access_count=0,
            created_days_ago=180,  # 6 months old
            last_accessed_days_ago=None,
        )
        memory_ids.append(memory_id)

    logger.info(f"Created {len(memory_ids)} LONG_TERM test memories")

    # Run consolidation
    report: ConsolidationReport = await consolidator.run_consolidation()

    # Validate results
    logger.info(f"Archival rate: {report.archival_rate:.1f}%")
    logger.info(f"Archived: {report.archived_count}/{report.processed_count}")

    # Expect ~20% archival (allowing 10% variance)
    assert 10 <= report.archival_rate <= 30, \
        f"Expected 10-30% archival rate, got {report.archival_rate:.1f}%"

    # Verify archived memories are now in ARCHIVED tier
    archived_count = 0
    async with neo4j.driver.session() as session:
        result = await session.run(
            "MATCH (m:Memory {tier: $tier}) WHERE m.memory_type = 'test_type' RETURN count(m) AS count",
            tier=MemoryTier.ARCHIVED.value,
        )
        record = await result.single()
        archived_count = record["count"]

    assert archived_count == report.archived_count, \
        f"Archived count mismatch: report={report.archived_count}, actual={archived_count}"

    logger.info(f"✓ T114 PASSED: Archival logic validated ({report.archival_rate:.1f}% archived)")

    await cleanup_test_memories(neo4j)


@pytest.mark.asyncio
async def test_t115_priority_formula(consolidator: MemoryConsolidator):
    """
    T115: Validate priority calculation formula.

    Formula: 0.40 * access_freq + 0.30 * recency + 0.30 * confidence

    Tests edge cases and verifies correct weighting.
    """
    # Test case 1: High access, high recency, high confidence -> High priority
    priority1, metrics1 = consolidator.calculate_priority_score(
        confidence=1.0,
        created_at=datetime.now(timezone.utc) - timedelta(days=1),
        last_accessed=datetime.now(timezone.utc),
        access_count=100,
        max_access_count=100,
    )

    # Expected: 0.40 * 1.0 + 0.30 * ~1.0 + 0.30 * 1.0 = ~1.0
    assert 0.95 <= priority1 <= 1.0, f"High priority case: expected ~1.0, got {priority1:.3f}"
    assert metrics1.access_frequency == 1.0
    assert metrics1.confidence_score == 1.0
    logger.info(f"High priority case: {priority1:.3f} (access={metrics1.access_frequency:.2f}, recency={metrics1.recency_score:.2f})")

    # Test case 2: Low access, low recency, low confidence -> Low priority
    priority2, metrics2 = consolidator.calculate_priority_score(
        confidence=0.3,
        created_at=datetime.now(timezone.utc) - timedelta(days=365),
        last_accessed=None,
        access_count=0,
        max_access_count=100,
    )

    # Expected: 0.40 * 0.0 + 0.30 * ~0.0 + 0.30 * 0.3 = ~0.09
    assert priority2 < 0.15, f"Low priority case: expected <0.15, got {priority2:.3f}"
    assert metrics2.access_frequency == 0.0
    assert metrics2.confidence_score == 0.3
    logger.info(f"Low priority case: {priority2:.3f} (access={metrics2.access_frequency:.2f}, recency={metrics2.recency_score:.2f})")

    # Test case 3: Medium access, medium recency, medium confidence -> Medium priority
    priority3, metrics3 = consolidator.calculate_priority_score(
        confidence=0.6,
        created_at=datetime.now(timezone.utc) - timedelta(days=30),
        last_accessed=datetime.now(timezone.utc) - timedelta(days=10),
        access_count=10,
        max_access_count=100,
    )

    # Expected: 0.40 * 0.1 + 0.30 * ~0.6 + 0.30 * 0.6 = ~0.40-0.55 (recency varies with decay)
    assert 0.25 <= priority3 <= 0.55, f"Medium priority case: expected 0.25-0.55, got {priority3:.3f}"
    logger.info(f"Medium priority case: {priority3:.3f} (access={metrics3.access_frequency:.2f}, recency={metrics3.recency_score:.2f})")

    # Verify formula components
    assert metrics1.access_frequency == 1.0
    assert metrics2.access_frequency == 0.0
    assert 0.08 <= metrics3.access_frequency <= 0.12  # ~0.1 (10/100)

    logger.info("✓ T115 PASSED: Priority formula validated")


@pytest.mark.asyncio
async def test_t116_decay_strategies():
    """
    T116: Validate decay strategy implementations.

    Tests all three decay strategies:
    - ExponentialDecay: Adaptive half-life
    - EbbinghausDecay: Forgetting curve
    - LinearDecay: Simple linear decay
    """
    # Common test parameters
    created_at = datetime.now(timezone.utc) - timedelta(days=30)
    recent_access = datetime.now(timezone.utc) - timedelta(days=5)
    old_access = datetime.now(timezone.utc) - timedelta(days=100)

    # Test 1: ExponentialDecay
    exp_decay = ExponentialDecay(base_half_life_days=43.3)

    # Recent access with high access count -> High recency
    score1 = exp_decay.calculate_decay(created_at, recent_access, access_count=20)
    assert 0.8 <= score1 <= 1.0, f"ExponentialDecay (recent, high access): expected 0.8-1.0, got {score1:.3f}"

    # Old access with low access count -> Lower recency (but adaptive half-life boosts it)
    # Note: access_count=1 gives effective half-life ~73 days, so score at 100 days is ~0.39
    score2 = exp_decay.calculate_decay(created_at, old_access, access_count=1)
    assert 0.0 <= score2 <= 0.45, f"ExponentialDecay (old, low access): expected 0.0-0.45, got {score2:.3f}"

    logger.info(f"ExponentialDecay: recent={score1:.3f}, old={score2:.3f}")

    # Test 2: EbbinghausDecay
    ebb_decay = EbbinghausDecay(base_stability_days=30.0)

    score3 = ebb_decay.calculate_decay(created_at, recent_access, access_count=20)
    score4 = ebb_decay.calculate_decay(created_at, old_access, access_count=1)

    assert score3 > score4, "EbbinghausDecay: recent access should score higher than old"
    logger.info(f"EbbinghausDecay: recent={score3:.3f}, old={score4:.3f}")

    # Test 3: LinearDecay
    linear_decay = LinearDecay(max_days=365.0)

    score5 = linear_decay.calculate_decay(created_at, recent_access, access_count=20)
    score6 = linear_decay.calculate_decay(created_at, old_access, access_count=1)

    assert score5 > score6, "LinearDecay: recent access should score higher than old"
    logger.info(f"LinearDecay: recent={score5:.3f}, old={score6:.3f}")

    # Verify all strategies return scores in [0.0, 1.0]
    for score in [score1, score2, score3, score4, score5, score6]:
        assert 0.0 <= score <= 1.0, f"Decay score out of bounds: {score:.3f}"

    logger.info("✓ T116 PASSED: Decay strategies validated")


@pytest.mark.asyncio
async def test_t117_observability_logging(
    neo4j: Neo4jService, consolidator: MemoryConsolidator, caplog
):
    """
    T117: Validate observability logging (P5).

    Ensures all consolidation decisions are logged with reasoning.
    """
    await cleanup_test_memories(neo4j)

    # Create high-priority memory that will be promoted
    high_priority_id = await create_test_memory(
        neo4j,
        tier=MemoryTier.SHORT_TERM,
        confidence=0.95,
        access_count=50,
        created_days_ago=10,
        last_accessed_days_ago=1,
    )

    # Create low-priority memory that will be archived
    low_priority_id = await create_test_memory(
        neo4j,
        tier=MemoryTier.LONG_TERM,
        confidence=0.2,
        access_count=0,
        created_days_ago=200,
        last_accessed_days_ago=None,
    )

    # Run consolidation with logging
    with caplog.at_level(logging.INFO):
        report = await consolidator.run_consolidation()

    # Verify logging contains consolidation events
    log_messages = [record.message for record in caplog.records]

    # Check for job start/end messages
    assert any("Starting memory consolidation job" in msg for msg in log_messages), \
        "Missing job start log"
    assert any("Consolidation Report" in msg for msg in log_messages), \
        "Missing consolidation report log"

    # Check for promotion/archival logs with memory IDs
    promoted_logs = [msg for msg in log_messages if "✓ PROMOTED" in msg]
    archived_logs = [msg for msg in log_messages if "✓ ARCHIVED" in msg]

    if report.promoted_count > 0:
        assert len(promoted_logs) > 0, "Missing promotion logs"
        # Verify reasoning is included
        assert any("score:" in msg and "LONG_TERM" in msg for msg in promoted_logs), \
            "Promotion logs missing reasoning"

    if report.archived_count > 0:
        assert len(archived_logs) > 0, "Missing archival logs"
        # Verify reasoning is included
        assert any("score:" in msg and "ARCHIVED" in msg for msg in archived_logs), \
            "Archival logs missing reasoning"

    logger.info(f"Logged {len(promoted_logs)} promotions and {len(archived_logs)} archival events")
    logger.info("✓ T117 PASSED: Observability logging validated")

    await cleanup_test_memories(neo4j)


@pytest.mark.asyncio
@pytest.mark.slow
async def test_t118_performance_at_scale(neo4j: Neo4jService, consolidator: MemoryConsolidator):
    """
    T118: Validate consolidation performance (<5s for 1000 memories).

    Creates 1000 test memories and measures consolidation execution time.
    """
    await cleanup_test_memories(neo4j)

    # Create 1000 memories across both tiers
    logger.info("Creating 1000 test memories...")
    memory_ids = []

    # 500 SHORT_TERM memories
    for i in range(500):
        memory_id = await create_test_memory(
            neo4j,
            tier=MemoryTier.SHORT_TERM,
            confidence=0.5 + (i % 5) * 0.1,
            access_count=i % 30,
            created_days_ago=10 + (i % 20),
            last_accessed_days_ago=(i % 10) if i % 3 == 0 else None,
        )
        memory_ids.append(memory_id)

    # 500 LONG_TERM memories
    for i in range(500):
        memory_id = await create_test_memory(
            neo4j,
            tier=MemoryTier.LONG_TERM,
            confidence=0.4 + (i % 6) * 0.1,
            access_count=i % 50,
            created_days_ago=30 + (i % 100),
            last_accessed_days_ago=(i % 20) if i % 2 == 0 else None,
        )
        memory_ids.append(memory_id)

    logger.info(f"Created {len(memory_ids)} test memories")

    # Run consolidation and measure time
    start_time = time.time()
    report = await consolidator.run_consolidation()
    execution_time = time.time() - start_time

    logger.info(f"Consolidation execution time: {execution_time:.2f}s")
    logger.info(f"Report execution time: {report.execution_time_ms:.0f}ms")
    logger.info(f"Processed: {report.processed_count} memories")
    logger.info(f"Promoted: {report.promoted_count}, Archived: {report.archived_count}")

    # Validate performance (<5 seconds for 1000 memories)
    assert execution_time < 5.0, \
        f"Consolidation too slow: {execution_time:.2f}s (expected <5.0s for 1000 memories)"

    # Verify all memories were processed
    assert report.processed_count == 1000, \
        f"Expected 1000 processed, got {report.processed_count}"

    logger.info(f"✓ T118 PASSED: Performance validated ({execution_time:.2f}s for 1000 memories)")

    await cleanup_test_memories(neo4j)


@pytest.mark.asyncio
async def test_t119_archived_retrieval(neo4j: Neo4jService, consolidator: MemoryConsolidator):
    """
    T119: Validate that archived memories can still be retrieved.

    Archives memories and verifies they remain queryable in Neo4j.
    """
    await cleanup_test_memories(neo4j)

    # Create low-priority LONG_TERM memory that will be archived
    memory_id = await create_test_memory(
        neo4j,
        tier=MemoryTier.LONG_TERM,
        confidence=0.2,
        access_count=0,
        created_days_ago=365,
        last_accessed_days_ago=None,
    )

    # Run consolidation to archive the memory
    report = await consolidator.run_consolidation()

    assert report.archived_count >= 1, "Expected at least 1 memory to be archived"

    # Query archived memory
    query = """
    MATCH (m:Memory {memory_id: $memory_id})
    RETURN m.tier AS tier, m.content AS content
    """

    async with neo4j.driver.session() as session:
        result = await session.run(query, memory_id=memory_id)
        record = await result.single()

        assert record is not None, f"Archived memory {memory_id} not found"
        assert record["tier"] == MemoryTier.ARCHIVED.value, \
            f"Expected tier=ARCHIVED, got {record['tier']}"

        logger.info(f"Archived memory retrieved: {record['content']}")

    # Verify archived memories can be queried in bulk
    bulk_query = """
    MATCH (m:Memory {tier: $tier})
    WHERE m.memory_type = 'test_type'
    RETURN count(m) AS count
    """

    async with neo4j.driver.session() as session:
        result = await session.run(bulk_query, tier=MemoryTier.ARCHIVED.value)
        record = await result.single()
        archived_count = record["count"]

        assert archived_count >= 1, f"Expected >=1 archived memory, found {archived_count}"
        logger.info(f"Found {archived_count} archived memories via bulk query")

    logger.info("✓ T119 PASSED: Archived memory retrieval validated")

    await cleanup_test_memories(neo4j)
