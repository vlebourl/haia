"""Unit tests for BudgetManager (token budget management).

Tests token counting, truncation strategies, and budget enforcement.

TDD: These tests should FAIL initially before implementation.
"""

import pytest
from datetime import datetime, timezone, timedelta

from haia.context.budget_manager import BudgetManager
from haia.context.models import TruncationStrategy
from haia.embedding.models import RetrievalResult
from haia.extraction.models import ExtractedMemory


@pytest.fixture
def budget_manager():
    """Create BudgetManager with default settings."""
    return BudgetManager(model_name="claude-sonnet-4")


@pytest.fixture
def sample_memories():
    """Create sample memories with known token counts."""
    now = datetime.now(timezone.utc)

    return [
        RetrievalResult(
            memory=ExtractedMemory(
                memory_id="mem_001",
                memory_type="preference",
                content="Short memory (10 tokens).",
                confidence=0.95,
                source_conversation_id="conv_001",
                extraction_timestamp=now - timedelta(days=1),
                category="test",
            ),
            similarity_score=0.95,
            relevance_score=0.93,
            rank=1,
            token_count=10,
        ),
        RetrievalResult(
            memory=ExtractedMemory(
                memory_id="mem_002",
                memory_type="technical_context",
                content="Medium length memory with more tokens (approximately 30 tokens for testing purposes).",
                confidence=0.85,
                source_conversation_id="conv_002",
                extraction_timestamp=now - timedelta(days=10),
                category="test",
            ),
            similarity_score=0.85,
            relevance_score=0.82,
            rank=2,
            token_count=30,
        ),
        RetrievalResult(
            memory=ExtractedMemory(
                memory_id="mem_003",
                memory_type="decision",
                content="Very long memory with lots of content " * 10,  # ~100 tokens
                confidence=0.80,
                source_conversation_id="conv_003",
                extraction_timestamp=now - timedelta(days=30),
                category="test",
            ),
            similarity_score=0.75,
            relevance_score=0.73,
            rank=3,
            token_count=100,
        ),
        RetrievalResult(
            memory=ExtractedMemory(
                memory_id="mem_004",
                memory_type="personal_fact",
                content="Another medium memory (20 tokens test).",
                confidence=0.90,
                source_conversation_id="conv_004",
                extraction_timestamp=now - timedelta(days=5),
                category="test",
            ),
            similarity_score=0.80,
            relevance_score=0.78,
            rank=4,
            token_count=20,
        ),
    ]


def test_budget_manager_initialization():
    """Test T056: BudgetManager initializes with default settings."""
    manager = BudgetManager()

    assert manager.model_name == "claude-sonnet-4"  # Default
    assert manager.default_budget == 2000  # Default
    assert manager.token_buffer == 50  # Default buffer


def test_budget_manager_custom_settings():
    """Test T056: BudgetManager accepts custom settings."""
    manager = BudgetManager(
        model_name="gpt-4",
        default_budget=5000,
        token_buffer=100,
    )

    assert manager.model_name == "gpt-4"
    assert manager.default_budget == 5000
    assert manager.token_buffer == 100


def test_count_tokens_basic():
    """Test T057: Token counting for simple text."""
    manager = BudgetManager()

    # Short text
    short_text = "Hello world"
    short_count = manager.count_tokens(short_text)
    assert short_count > 0
    assert short_count < 10

    # Medium text
    medium_text = "This is a longer sentence with more words to count tokens accurately."
    medium_count = manager.count_tokens(medium_text)
    assert medium_count > short_count
    assert 10 < medium_count < 30


def test_count_tokens_memory():
    """Test T057: Token counting for ExtractedMemory."""
    manager = BudgetManager()
    now = datetime.now(timezone.utc)

    memory = ExtractedMemory(
        memory_id="test_mem",
        memory_type="preference",
        content="This is test memory content for token counting.",
        confidence=0.85,
        source_conversation_id="conv_test",
        extraction_timestamp=now,
        category="test",
    )

    token_count = manager.count_tokens_for_memory(memory)
    assert token_count > 0
    # Should count content + metadata (type, confidence, etc.)
    assert token_count >= manager.count_tokens(memory.content)


def test_estimate_total_tokens(budget_manager, sample_memories):
    """Test T058: Total token estimation for memory list."""
    total_tokens = budget_manager.estimate_total_tokens(sample_memories)

    # Should sum all individual token counts
    expected_total = sum(m.token_count for m in sample_memories)
    assert total_tokens == expected_total


def test_apply_budget_within_limit(budget_manager, sample_memories):
    """Test T059: Budget enforcement when memories fit within budget."""
    # Budget of 250 tokens - all memories fit (total = 160, buffer = 50, effective = 200)
    result = budget_manager.apply_budget(
        memories=sample_memories,
        token_budget=250,
        strategy=TruncationStrategy.HARD_CUTOFF,
    )

    assert len(result) == len(sample_memories)  # All memories included
    assert budget_manager.estimate_total_tokens(result) <= 250


def test_apply_budget_hard_cutoff(budget_manager, sample_memories):
    """Test T060: HARD_CUTOFF strategy removes memories to fit budget."""
    # Budget of 50 tokens - only first 2 memories fit (10 + 30 = 40)
    result = budget_manager.apply_budget(
        memories=sample_memories,
        token_budget=50,
        strategy=TruncationStrategy.HARD_CUTOFF,
    )

    assert len(result) < len(sample_memories)
    assert budget_manager.estimate_total_tokens(result) <= 50
    assert result[0].memory.memory_id == "mem_001"
    assert result[1].memory.memory_id == "mem_002"
    # mem_003 (100 tokens) should be excluded

    # Budget enforcement flag should be set
    for mem in result:
        assert mem.budget_enforced is True


def test_apply_budget_truncate_strategy(budget_manager, sample_memories):
    """Test T061: TRUNCATE strategy shortens content to fit budget."""
    # Budget of 50 tokens - truncate content to fit
    result = budget_manager.apply_budget(
        memories=sample_memories,
        token_budget=50,
        strategy=TruncationStrategy.TRUNCATE,
    )

    assert len(result) > 0
    total_tokens = budget_manager.estimate_total_tokens(result)
    assert total_tokens <= 50

    # Check that some memories were truncated
    for mem in result:
        assert mem.budget_enforced is True


def test_apply_budget_empty_list(budget_manager):
    """Test T058: Budget enforcement on empty memory list."""
    result = budget_manager.apply_budget(
        memories=[],
        token_budget=1000,
        strategy=TruncationStrategy.HARD_CUTOFF,
    )

    assert result == []


def test_apply_budget_zero_budget(budget_manager, sample_memories):
    """Test T059: Budget enforcement with zero budget returns empty list."""
    result = budget_manager.apply_budget(
        memories=sample_memories,
        token_budget=0,
        strategy=TruncationStrategy.HARD_CUTOFF,
    )

    assert result == []


def test_apply_budget_preserves_order(budget_manager, sample_memories):
    """Test T060: Budget enforcement preserves memory order."""
    result = budget_manager.apply_budget(
        memories=sample_memories,
        token_budget=50,
        strategy=TruncationStrategy.HARD_CUTOFF,
    )

    # Verify order is preserved (by rank)
    for i in range(len(result) - 1):
        assert result[i].rank < result[i + 1].rank


def test_count_tokens_caching():
    """Test T057: Token counting uses caching for efficiency."""
    manager = BudgetManager()

    text = "This is a test sentence for caching."

    # First call
    count1 = manager.count_tokens(text)

    # Second call should use cache (same result)
    count2 = manager.count_tokens(text)

    assert count1 == count2


def test_apply_budget_default_strategy(budget_manager, sample_memories):
    """Test T059: Default strategy is HARD_CUTOFF."""
    result = budget_manager.apply_budget(
        memories=sample_memories,
        token_budget=50,
        # No strategy specified - should use default
    )

    assert len(result) < len(sample_memories)
    assert budget_manager.estimate_total_tokens(result) <= 50


def test_truncate_memory_content():
    """Test T061: Memory content truncation works correctly."""
    manager = BudgetManager()
    now = datetime.now(timezone.utc)

    long_memory = ExtractedMemory(
        memory_id="long_mem",
        memory_type="technical_context",
        content="This is a very long memory content that should be truncated " * 20,
        confidence=0.85,
        source_conversation_id="conv_test",
        extraction_timestamp=now,
        category="test",
    )

    # Truncate to 50 tokens
    truncated = manager.truncate_memory_content(long_memory, max_tokens=50)

    assert len(truncated.content) < len(long_memory.content)
    assert manager.count_tokens(truncated.content) <= 50
    assert truncated.memory_id == long_memory.memory_id  # ID preserved


def test_calculate_budget_margin(budget_manager, sample_memories):
    """Test T058: Calculate remaining budget margin."""
    total_tokens = budget_manager.estimate_total_tokens(sample_memories)
    budget = 200

    margin = budget_manager.calculate_budget_margin(sample_memories, budget)

    assert margin == budget - total_tokens
    assert margin > 0  # Sample memories fit in budget


def test_budget_enforcement_with_buffer(sample_memories):
    """Test T059: Token buffer reserves space for system overhead."""
    manager = BudgetManager(token_buffer=50)

    # Budget 100 with 50 buffer = 50 effective budget
    result = manager.apply_budget(
        memories=sample_memories,
        token_budget=100,
        strategy=TruncationStrategy.HARD_CUTOFF,
    )

    # Should only fit mem_001 (10 tokens) + mem_002 (30 tokens) = 40 tokens
    total_tokens = manager.estimate_total_tokens(result)
    assert total_tokens <= (100 - manager.token_buffer)
