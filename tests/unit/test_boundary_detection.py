"""Unit tests for conversation boundary detection heuristic."""

import pytest
from datetime import datetime, timezone, timedelta
from haia.memory.boundary import compute_first_message_hash, detect_boundary
from haia.memory.models import BoundaryTriggerReason, ConversationMetadata


class TestComputeFirstMessageHash:
    """Tests for compute_first_message_hash function."""

    def test_hash_deterministic(self):
        """Same message content produces same hash."""
        messages1 = [{"role": "user", "content": "Hello world"}]
        messages2 = [{"role": "user", "content": "Hello world"}]

        hash1 = compute_first_message_hash(messages1)
        hash2 = compute_first_message_hash(messages2)

        assert hash1 == hash2

    def test_hash_different_content(self):
        """Different message content produces different hash."""
        messages1 = [{"role": "user", "content": "Hello world"}]
        messages2 = [{"role": "user", "content": "Goodbye world"}]

        hash1 = compute_first_message_hash(messages1)
        hash2 = compute_first_message_hash(messages2)

        assert hash1 != hash2

    def test_hash_format(self):
        """Hash is 64-character hex string (SHA-256)."""
        messages = [{"role": "user", "content": "Test"}]
        hash_value = compute_first_message_hash(messages)

        assert len(hash_value) == 64
        assert all(c in "0123456789abcdef" for c in hash_value)

    def test_empty_messages_raises_index_error(self):
        """Empty message list raises IndexError."""
        with pytest.raises(IndexError):
            compute_first_message_hash([])


class TestDetectBoundary:
    """Tests for detect_boundary heuristic function."""

    @pytest.fixture
    def base_metadata(self):
        """Provide base conversation metadata for testing."""
        return ConversationMetadata(
            conversation_id="test-conv-1",
            last_seen=datetime(2025, 12, 7, 10, 0, 0, tzinfo=timezone.utc),
            message_count=10,
            first_message_hash="abc123def456",
            start_time=datetime(2025, 12, 7, 9, 45, 0, tzinfo=timezone.utc),
        )

    def test_no_boundary_idle_below_threshold(self, base_metadata):
        """No boundary detected when idle time < threshold."""
        current_time = base_metadata.last_seen + timedelta(minutes=5)  # 5 min idle

        result = detect_boundary(
            current_metadata=base_metadata,
            new_message_count=10,
            new_first_hash="abc123def456",
            current_time=current_time,
            idle_threshold_minutes=10,
        )

        assert result.detected is False
        assert result.reason is None
        assert result.idle_duration_seconds == 300.0  # 5 minutes

    def test_no_boundary_idle_above_but_no_change(self, base_metadata):
        """No boundary when idle > threshold but no message/hash change."""
        current_time = base_metadata.last_seen + timedelta(minutes=15)  # 15 min idle

        result = detect_boundary(
            current_metadata=base_metadata,
            new_message_count=10,  # Same count
            new_first_hash="abc123def456",  # Same hash
            current_time=current_time,
            idle_threshold_minutes=10,
        )

        assert result.detected is False
        assert result.reason is None
        assert result.idle_duration_seconds == 900.0  # 15 minutes

    def test_boundary_idle_and_message_drop(self, base_metadata):
        """Boundary detected when idle > threshold AND message drop > 50%."""
        current_time = base_metadata.last_seen + timedelta(minutes=12)  # 12 min idle

        result = detect_boundary(
            current_metadata=base_metadata,
            new_message_count=4,  # 60% drop (10 -> 4)
            new_first_hash="abc123def456",  # Same hash
            current_time=current_time,
            idle_threshold_minutes=10,
            message_drop_threshold=0.5,
        )

        assert result.detected is True
        assert result.reason == BoundaryTriggerReason.IDLE_AND_MESSAGE_DROP
        assert result.idle_duration_seconds == 720.0  # 12 minutes
        assert result.message_count_drop_percent == 60.0
        assert result.hash_changed is False

    def test_boundary_idle_and_hash_change(self, base_metadata):
        """Boundary detected when idle > threshold AND first message hash changed."""
        current_time = base_metadata.last_seen + timedelta(minutes=11)  # 11 min idle

        result = detect_boundary(
            current_metadata=base_metadata,
            new_message_count=10,  # Same count
            new_first_hash="different_hash",  # Changed hash
            current_time=current_time,
            idle_threshold_minutes=10,
        )

        assert result.detected is True
        assert result.reason == BoundaryTriggerReason.IDLE_AND_HASH_CHANGE
        assert result.idle_duration_seconds == 660.0  # 11 minutes
        assert result.hash_changed is True

    def test_boundary_idle_and_both(self, base_metadata):
        """Boundary detected when idle > threshold AND both drop + hash change."""
        current_time = base_metadata.last_seen + timedelta(minutes=15)  # 15 min idle

        result = detect_boundary(
            current_metadata=base_metadata,
            new_message_count=2,  # 80% drop (10 -> 2)
            new_first_hash="completely_different",  # Changed hash
            current_time=current_time,
            idle_threshold_minutes=10,
            message_drop_threshold=0.5,
        )

        assert result.detected is True
        assert result.reason == BoundaryTriggerReason.IDLE_AND_BOTH
        assert result.idle_duration_seconds == 900.0  # 15 minutes
        assert result.message_count_drop_percent == 80.0
        assert result.hash_changed is True

    def test_boundary_threshold_edge_case_51_percent(self, base_metadata):
        """Boundary detected at exactly 51% message drop (just above threshold)."""
        current_time = base_metadata.last_seen + timedelta(minutes=11)

        result = detect_boundary(
            current_metadata=base_metadata,
            new_message_count=4,  # 60% drop (just above 50%)
            new_first_hash="abc123def456",
            current_time=current_time,
            idle_threshold_minutes=10,
            message_drop_threshold=0.5,
        )

        assert result.detected is True
        assert result.reason == BoundaryTriggerReason.IDLE_AND_MESSAGE_DROP

    def test_no_boundary_threshold_edge_case_50_percent(self, base_metadata):
        """No boundary at exactly 50% message drop (at threshold, not above)."""
        current_time = base_metadata.last_seen + timedelta(minutes=11)

        result = detect_boundary(
            current_metadata=base_metadata,
            new_message_count=5,  # Exactly 50% drop (10 -> 5)
            new_first_hash="abc123def456",
            current_time=current_time,
            idle_threshold_minutes=10,
            message_drop_threshold=0.5,
        )

        assert result.detected is False  # Threshold is >, not >=

    def test_message_count_increased_no_boundary(self, base_metadata):
        """No boundary when message count increased (negative drop)."""
        current_time = base_metadata.last_seen + timedelta(minutes=15)

        result = detect_boundary(
            current_metadata=base_metadata,
            new_message_count=15,  # Increased from 10
            new_first_hash="abc123def456",
            current_time=current_time,
            idle_threshold_minutes=10,
        )

        assert result.detected is False
        assert result.message_count_drop_percent == 0.0  # Clamped to 0

    def test_custom_thresholds(self, base_metadata):
        """Custom idle and message drop thresholds work correctly."""
        current_time = base_metadata.last_seen + timedelta(minutes=6)  # 6 min idle

        result = detect_boundary(
            current_metadata=base_metadata,
            new_message_count=7,  # 30% drop (10 -> 7)
            new_first_hash="abc123def456",
            current_time=current_time,
            idle_threshold_minutes=5,  # Custom: 5 min threshold
            message_drop_threshold=0.25,  # Custom: 25% threshold
        )

        assert result.detected is True
        assert result.reason == BoundaryTriggerReason.IDLE_AND_MESSAGE_DROP
        assert result.message_count_drop_percent == 30.0
