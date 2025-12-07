"""Unit tests for ConversationTracker class."""

import pytest
from datetime import datetime, timezone, timedelta
from pathlib import Path
from haia.memory.tracker import ConversationTracker
from haia.memory.models import BoundaryTriggerReason


@pytest.fixture
async def tracker(tmp_path):
    """Provide a ConversationTracker instance for testing."""
    storage_dir = tmp_path / "transcripts"
    return ConversationTracker(
        storage_dir=str(storage_dir),
        idle_threshold_minutes=10,
        message_drop_threshold=0.5,
        max_tracked_conversations=100,
    )


@pytest.fixture
def sample_messages():
    """Provide sample message list for testing."""
    return [
        {"role": "user", "content": "What is the status of my homelab?"},
        {"role": "assistant", "content": "Your homelab has 3 Proxmox nodes..."},
        {"role": "user", "content": "Check disk usage on node1"},
    ]


class TestMetadataUpdates:
    """Tests for ConversationTracker metadata update logic."""

    @pytest.mark.asyncio
    async def test_first_request_creates_metadata(self, tracker, sample_messages):
        """First request creates new metadata entry."""
        conv_id = "test-conv-1"

        result = await tracker.process_request(conv_id, sample_messages)

        # First request should not detect boundary
        assert result.detected is False

        # Metadata should be created
        metadata = await tracker.get_metadata(conv_id)
        assert metadata is not None
        assert metadata.conversation_id == conv_id
        assert metadata.message_count == len(sample_messages)

    @pytest.mark.asyncio
    async def test_subsequent_request_updates_metadata(self, tracker, sample_messages):
        """Subsequent requests update existing metadata."""
        conv_id = "test-conv-2"

        # First request
        await tracker.process_request(conv_id, sample_messages)
        metadata_before = await tracker.get_metadata(conv_id)

        # Second request (2 minutes later, no boundary)
        new_messages = sample_messages + [
            {"role": "assistant", "content": "Disk usage is 45%"}
        ]
        await tracker.process_request(conv_id, new_messages)

        metadata_after = await tracker.get_metadata(conv_id)

        # Metadata should be updated
        assert metadata_after.message_count == len(new_messages)
        assert metadata_after.last_seen > metadata_before.last_seen

    @pytest.mark.asyncio
    async def test_metadata_timestamps_updated(self, tracker, sample_messages):
        """Metadata timestamps are updated correctly."""
        conv_id = "test-conv-3"

        # First request
        await tracker.process_request(conv_id, sample_messages)
        metadata_1 = await tracker.get_metadata(conv_id)

        # Wait a tiny bit (simulate time passing)
        import asyncio
        await asyncio.sleep(0.01)

        # Second request
        await tracker.process_request(conv_id, sample_messages)
        metadata_2 = await tracker.get_metadata(conv_id)

        # last_seen should be updated
        assert metadata_2.last_seen > metadata_1.last_seen
        # start_time should remain unchanged
        assert metadata_2.start_time == metadata_1.start_time

    @pytest.mark.asyncio
    async def test_first_message_hash_tracked(self, tracker):
        """First message hash is computed and tracked."""
        conv_id = "test-conv-4"
        messages = [{"role": "user", "content": "Original first message"}]

        await tracker.process_request(conv_id, messages)
        metadata = await tracker.get_metadata(conv_id)

        assert metadata.first_message_hash is not None
        assert len(metadata.first_message_hash) == 64  # SHA-256 hex

    @pytest.mark.asyncio
    async def test_nonexistent_conversation_returns_none(self, tracker):
        """Getting metadata for nonexistent conversation returns None."""
        metadata = await tracker.get_metadata("nonexistent-conv")
        assert metadata is None


class TestLRUEviction:
    """Tests for ConversationTracker LRU eviction logic."""

    @pytest.mark.asyncio
    async def test_lru_eviction_when_max_reached(self, tmp_path):
        """Oldest conversation is evicted when max limit reached."""
        storage_dir = tmp_path / "transcripts"
        tracker = ConversationTracker(
            storage_dir=str(storage_dir),
            idle_threshold_minutes=10,
            message_drop_threshold=0.5,
            max_tracked_conversations=3,  # Small limit for testing
        )

        messages = [{"role": "user", "content": "Test message"}]

        # Create 3 conversations (fills to max)
        await tracker.process_request("conv-1", messages)
        await tracker.process_request("conv-2", messages)
        await tracker.process_request("conv-3", messages)

        # All 3 should exist
        assert await tracker.get_metadata("conv-1") is not None
        assert await tracker.get_metadata("conv-2") is not None
        assert await tracker.get_metadata("conv-3") is not None

        # Add 4th conversation (should evict conv-1, the oldest)
        await tracker.process_request("conv-4", messages)

        # conv-1 should be evicted
        assert await tracker.get_metadata("conv-1") is None
        # Others should still exist
        assert await tracker.get_metadata("conv-2") is not None
        assert await tracker.get_metadata("conv-3") is not None
        assert await tracker.get_metadata("conv-4") is not None

    @pytest.mark.asyncio
    async def test_lru_access_updates_order(self, tmp_path):
        """Accessing a conversation updates its LRU position."""
        storage_dir = tmp_path / "transcripts"
        tracker = ConversationTracker(
            storage_dir=str(storage_dir),
            idle_threshold_minutes=10,
            message_drop_threshold=0.5,
            max_tracked_conversations=3,
        )

        messages = [{"role": "user", "content": "Test message"}]

        # Create 3 conversations
        await tracker.process_request("conv-1", messages)
        await tracker.process_request("conv-2", messages)
        await tracker.process_request("conv-3", messages)

        # Access conv-1 again (should move it to most recent)
        await tracker.process_request("conv-1", messages)

        # Add 4th conversation (should evict conv-2 now, not conv-1)
        await tracker.process_request("conv-4", messages)

        # conv-2 should be evicted (oldest unreferenced)
        assert await tracker.get_metadata("conv-2") is None
        # conv-1 should still exist (was accessed recently)
        assert await tracker.get_metadata("conv-1") is not None
        assert await tracker.get_metadata("conv-3") is not None
        assert await tracker.get_metadata("conv-4") is not None

    @pytest.mark.asyncio
    async def test_no_eviction_below_max(self, tmp_path):
        """No eviction occurs when below max limit."""
        storage_dir = tmp_path / "transcripts"
        tracker = ConversationTracker(
            storage_dir=str(storage_dir),
            idle_threshold_minutes=10,
            message_drop_threshold=0.5,
            max_tracked_conversations=100,  # High limit
        )

        messages = [{"role": "user", "content": "Test message"}]

        # Create 10 conversations (well below max)
        for i in range(10):
            await tracker.process_request(f"conv-{i}", messages)

        # All should still exist
        for i in range(10):
            assert await tracker.get_metadata(f"conv-{i}") is not None


class TestConcurrency:
    """Tests for ConversationTracker thread safety."""

    @pytest.mark.asyncio
    async def test_concurrent_requests_different_conversations(self, tracker):
        """Concurrent requests to different conversations are safe."""
        messages_1 = [{"role": "user", "content": "Request 1"}]
        messages_2 = [{"role": "user", "content": "Request 2"}]

        # Process two conversations concurrently
        import asyncio
        results = await asyncio.gather(
            tracker.process_request("conv-1", messages_1),
            tracker.process_request("conv-2", messages_2),
        )

        # Both should complete successfully
        assert len(results) == 2
        assert all(r.detected is False for r in results)  # First requests

        # Both metadata entries should exist
        assert await tracker.get_metadata("conv-1") is not None
        assert await tracker.get_metadata("conv-2") is not None

    @pytest.mark.asyncio
    async def test_concurrent_requests_same_conversation(self, tracker):
        """Concurrent requests to same conversation are serialized safely."""
        messages = [{"role": "user", "content": "Test"}]

        # Process same conversation concurrently
        import asyncio
        results = await asyncio.gather(
            tracker.process_request("conv-1", messages),
            tracker.process_request("conv-1", messages),
            tracker.process_request("conv-1", messages),
        )

        # All should complete
        assert len(results) == 3

        # Metadata should exist and be consistent
        metadata = await tracker.get_metadata("conv-1")
        assert metadata is not None
        assert metadata.message_count == len(messages)
