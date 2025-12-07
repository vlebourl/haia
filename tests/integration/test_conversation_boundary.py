"""Integration tests for conversation boundary detection end-to-end flow."""

import pytest
import asyncio
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import patch
from haia.memory.tracker import ConversationTracker
from haia.memory.models import BoundaryTriggerReason


@pytest.fixture
async def tracker_with_storage(tmp_path):
    """Provide a ConversationTracker with real filesystem storage."""
    storage_dir = tmp_path / "transcripts"
    storage_dir.mkdir(parents=True, exist_ok=True)

    return ConversationTracker(
        storage_dir=str(storage_dir),
        idle_threshold_minutes=10,
        message_drop_threshold=0.5,
        max_tracked_conversations=1000,
    ), storage_dir


class TestBoundaryDetectionScenarios:
    """End-to-end tests for varied conversation patterns."""

    @pytest.mark.asyncio
    async def test_scenario_1_short_conversation_no_boundary(
        self, tracker_with_storage
    ):
        """Short conversation (5 messages, 1min) - no boundary."""
        tracker, storage_dir = tracker_with_storage
        conv_id = "scenario-1"

        messages = [
            {"role": "user", "content": "Message 1"},
            {"role": "assistant", "content": "Response 1"},
            {"role": "user", "content": "Message 2"},
            {"role": "assistant", "content": "Response 2"},
            {"role": "user", "content": "Message 3"},
        ]

        # Send request
        result = await tracker.process_request(conv_id, messages)

        # No boundary on first request
        assert result.detected is False

        # No transcript should be stored
        transcripts = list(storage_dir.glob("*.json"))
        assert len(transcripts) == 0

    @pytest.mark.asyncio
    async def test_scenario_2_long_continuous_conversation(
        self, tracker_with_storage
    ):
        """Long conversation (30min continuous, 5min intervals) - no boundary."""
        tracker, storage_dir = tracker_with_storage
        conv_id = "scenario-2"

        # Simulate 6 requests over 30 minutes with 5-minute intervals
        base_time = datetime(2025, 12, 7, 10, 0, 0, tzinfo=timezone.utc)
        messages = [{"role": "user", "content": "Initial message"}]

        for i in range(6):
            current_time = base_time + timedelta(minutes=i * 5)

            with patch('haia.memory.boundary.datetime') as mock_dt:
                mock_dt.now.return_value = current_time
                mock_dt.side_effect = lambda *args, **kwargs: datetime(*args, **kwargs)

                # Add more messages each time (growing conversation)
                messages.append({"role": "assistant", "content": f"Response {i}"})
                messages.append({"role": "user", "content": f"Follow-up {i}"})

                result = await tracker.process_request(conv_id, messages)

                # No boundary should be detected (intervals < 10 min)
                assert result.detected is False

        # No transcript should be stored
        transcripts = list(storage_dir.glob("*.json"))
        assert len(transcripts) == 0

    @pytest.mark.asyncio
    async def test_scenario_3_idle_timeout_with_message_drop(
        self, tracker_with_storage
    ):
        """Interrupted conversation (2min, then 15min idle, message drop) - boundary."""
        tracker, storage_dir = tracker_with_storage
        conv_id = "scenario-3"

        # Request 1: 5 messages
        base_time = datetime(2025, 12, 7, 10, 0, 0, tzinfo=timezone.utc)
        messages_1 = [
            {"role": "user", "content": "Message 1"},
            {"role": "assistant", "content": "Response 1"},
            {"role": "user", "content": "Message 2"},
            {"role": "assistant", "content": "Response 2"},
            {"role": "user", "content": "Message 3"},
        ]

        with patch('haia.memory.boundary.datetime') as mock_dt:
            mock_dt.now.return_value = base_time
            mock_dt.side_effect = lambda *args, **kwargs: datetime(*args, **kwargs)
            result_1 = await tracker.process_request(conv_id, messages_1)

        assert result_1.detected is False

        # Request 2: 15 minutes later, only 2 messages (60% drop)
        later_time = base_time + timedelta(minutes=15)
        messages_2 = [{"role": "user", "content": "New topic"}]

        with patch('haia.memory.boundary.datetime') as mock_dt:
            mock_dt.now.return_value = later_time
            mock_dt.side_effect = lambda *args, **kwargs: datetime(*args, **kwargs)
            result_2 = await tracker.process_request(conv_id, messages_2)

        # Boundary should be detected
        assert result_2.detected is True
        assert result_2.reason == BoundaryTriggerReason.IDLE_AND_MESSAGE_DROP
        assert result_2.idle_duration_seconds == 900.0  # 15 minutes

        # Transcript should be stored
        await asyncio.sleep(0.1)  # Give filesystem time to write
        transcripts = list(storage_dir.glob("*.json"))
        assert len(transcripts) == 1

    @pytest.mark.asyncio
    async def test_scenario_4_idle_timeout_with_hash_change(
        self, tracker_with_storage
    ):
        """Rapid context switch (same message count, different first message) - boundary."""
        tracker, storage_dir = tracker_with_storage
        conv_id = "scenario-4"

        # Request 1
        base_time = datetime(2025, 12, 7, 10, 0, 0, tzinfo=timezone.utc)
        messages_1 = [
            {"role": "user", "content": "Talk about Proxmox"},
            {"role": "assistant", "content": "Proxmox is great..."},
        ]

        with patch('haia.memory.boundary.datetime') as mock_dt:
            mock_dt.now.return_value = base_time
            mock_dt.side_effect = lambda *args, **kwargs: datetime(*args, **kwargs)
            result_1 = await tracker.process_request(conv_id, messages_1)

        assert result_1.detected is False

        # Request 2: 12 minutes later, same count but different first message
        later_time = base_time + timedelta(minutes=12)
        messages_2 = [
            {"role": "user", "content": "Talk about Docker"},  # Different first msg
            {"role": "assistant", "content": "Docker is useful..."},
        ]

        with patch('haia.memory.boundary.datetime') as mock_dt:
            mock_dt.now.return_value = later_time
            mock_dt.side_effect = lambda *args, **kwargs: datetime(*args, **kwargs)
            result_2 = await tracker.process_request(conv_id, messages_2)

        # Boundary should be detected (hash changed)
        assert result_2.detected is True
        assert result_2.reason == BoundaryTriggerReason.IDLE_AND_HASH_CHANGE
        assert result_2.hash_changed is True

        # Transcript should be stored
        await asyncio.sleep(0.1)
        transcripts = list(storage_dir.glob("*.json"))
        assert len(transcripts) == 1

    @pytest.mark.asyncio
    async def test_scenario_5_concurrent_conversations_no_contamination(
        self, tracker_with_storage
    ):
        """Multiple concurrent conversations don't interfere with each other."""
        tracker, storage_dir = tracker_with_storage

        messages_a = [{"role": "user", "content": "Conversation A"}]
        messages_b = [{"role": "user", "content": "Conversation B"}]
        messages_c = [{"role": "user", "content": "Conversation C"}]

        # Process 3 conversations concurrently
        results = await asyncio.gather(
            tracker.process_request("conv-a", messages_a),
            tracker.process_request("conv-b", messages_b),
            tracker.process_request("conv-c", messages_c),
        )

        # All should be first requests (no boundaries)
        assert all(r.detected is False for r in results)

        # All metadata should exist independently
        meta_a = await tracker.get_metadata("conv-a")
        meta_b = await tracker.get_metadata("conv-b")
        meta_c = await tracker.get_metadata("conv-c")

        assert meta_a.conversation_id == "conv-a"
        assert meta_b.conversation_id == "conv-b"
        assert meta_c.conversation_id == "conv-c"

        # Different first message hashes
        assert meta_a.first_message_hash != meta_b.first_message_hash
        assert meta_b.first_message_hash != meta_c.first_message_hash

    @pytest.mark.asyncio
    async def test_scenario_6_idle_and_both_triggers(
        self, tracker_with_storage
    ):
        """Boundary with both message drop AND hash change."""
        tracker, storage_dir = tracker_with_storage
        conv_id = "scenario-6"

        # Request 1: 10 messages
        base_time = datetime(2025, 12, 7, 10, 0, 0, tzinfo=timezone.utc)
        messages_1 = [{"role": "user", "content": f"Message {i}"} for i in range(10)]

        with patch('haia.memory.boundary.datetime') as mock_dt:
            mock_dt.now.return_value = base_time
            mock_dt.side_effect = lambda *args, **kwargs: datetime(*args, **kwargs)
            await tracker.process_request(conv_id, messages_1)

        # Request 2: 20 minutes later, 2 messages (80% drop) + different first message
        later_time = base_time + timedelta(minutes=20)
        messages_2 = [
            {"role": "user", "content": "Completely new topic"},
            {"role": "assistant", "content": "New response"},
        ]

        with patch('haia.memory.boundary.datetime') as mock_dt:
            mock_dt.now.return_value = later_time
            mock_dt.side_effect = lambda *args, **kwargs: datetime(*args, **kwargs)
            result = await tracker.process_request(conv_id, messages_2)

        # Should trigger with BOTH reason
        assert result.detected is True
        assert result.reason == BoundaryTriggerReason.IDLE_AND_BOTH
        assert result.message_count_drop_percent == 80.0
        assert result.hash_changed is True

    @pytest.mark.asyncio
    async def test_scenario_7_edge_case_exactly_threshold(
        self, tracker_with_storage
    ):
        """Edge case: exactly 10 minutes idle, exactly 50% drop."""
        tracker, storage_dir = tracker_with_storage
        conv_id = "scenario-7"

        # Request 1: 10 messages
        base_time = datetime(2025, 12, 7, 10, 0, 0, tzinfo=timezone.utc)
        messages_1 = [{"role": "user", "content": f"Message {i}"} for i in range(10)]

        with patch('haia.memory.boundary.datetime') as mock_dt:
            mock_dt.now.return_value = base_time
            mock_dt.side_effect = lambda *args, **kwargs: datetime(*args, **kwargs)
            await tracker.process_request(conv_id, messages_1)

        # Request 2: Exactly 10 minutes later, exactly 5 messages (50% drop)
        later_time = base_time + timedelta(minutes=10, seconds=1)  # Just over
        messages_2 = [{"role": "user", "content": f"Message {i}"} for i in range(5)]

        with patch('haia.memory.boundary.datetime') as mock_dt:
            mock_dt.now.return_value = later_time
            mock_dt.side_effect = lambda *args, **kwargs: datetime(*args, **kwargs)
            result = await tracker.process_request(conv_id, messages_2)

        # Should NOT detect (threshold is >, not >=)
        assert result.detected is False

    @pytest.mark.asyncio
    async def test_scenario_8_rapid_requests_no_false_positive(
        self, tracker_with_storage
    ):
        """Rapid-fire requests (<1 second apart) don't trigger false positives."""
        tracker, storage_dir = tracker_with_storage
        conv_id = "scenario-8"

        messages = [{"role": "user", "content": "Test"}]

        # Send 5 requests in quick succession
        for _ in range(5):
            result = await tracker.process_request(conv_id, messages)
            # First is new, others should not detect boundary
            # (idle time < threshold)
            await asyncio.sleep(0.01)

        # No boundary should be detected
        # No transcripts should be stored
        transcripts = list(storage_dir.glob("*.json"))
        assert len(transcripts) == 0

    @pytest.mark.asyncio
    async def test_scenario_9_very_long_gap(
        self, tracker_with_storage
    ):
        """Very long gap (>1 day) still detected as boundary."""
        tracker, storage_dir = tracker_with_storage
        conv_id = "scenario-9"

        # Request 1
        base_time = datetime(2025, 12, 7, 10, 0, 0, tzinfo=timezone.utc)
        messages = [{"role": "user", "content": "Old message"}]

        with patch('haia.memory.boundary.datetime') as mock_dt:
            mock_dt.now.return_value = base_time
            mock_dt.side_effect = lambda *args, **kwargs: datetime(*args, **kwargs)
            await tracker.process_request(conv_id, messages)

        # Request 2: 2 days later
        later_time = base_time + timedelta(days=2)
        new_messages = [{"role": "user", "content": "New message"}]

        with patch('haia.memory.boundary.datetime') as mock_dt:
            mock_dt.now.return_value = later_time
            mock_dt.side_effect = lambda *args, **kwargs: datetime(*args, **kwargs)
            result = await tracker.process_request(conv_id, new_messages)

        # Should detect boundary (idle >> threshold)
        assert result.detected is True
        assert result.idle_duration_seconds > 86400  # > 1 day

    @pytest.mark.asyncio
    async def test_scenario_10_message_count_growth_no_boundary(
        self, tracker_with_storage
    ):
        """Growing message count (negative drop) doesn't trigger boundary."""
        tracker, storage_dir = tracker_with_storage
        conv_id = "scenario-10"

        # Request 1: 5 messages
        base_time = datetime(2025, 12, 7, 10, 0, 0, tzinfo=timezone.utc)
        messages_1 = [{"role": "user", "content": f"Message {i}"} for i in range(5)]

        with patch('haia.memory.boundary.datetime') as mock_dt:
            mock_dt.now.return_value = base_time
            mock_dt.side_effect = lambda *args, **kwargs: datetime(*args, **kwargs)
            await tracker.process_request(conv_id, messages_1)

        # Request 2: 15 minutes later, 15 messages (growth, not drop)
        later_time = base_time + timedelta(minutes=15)
        messages_2 = [{"role": "user", "content": f"Message {i}"} for i in range(15)]

        with patch('haia.memory.boundary.datetime') as mock_dt:
            mock_dt.now.return_value = later_time
            mock_dt.side_effect = lambda *args, **kwargs: datetime(*args, **kwargs)
            result = await tracker.process_request(conv_id, messages_2)

        # Should NOT detect boundary (message count increased)
        assert result.detected is False
        assert result.message_count_drop_percent == 0.0


class TestTranscriptCompleteness:
    """Tests for 100% message retention in stored transcripts."""

    @pytest.mark.asyncio
    async def test_transcript_contains_all_messages(
        self, tracker_with_storage
    ):
        """Stored transcript contains 100% of conversation messages."""
        tracker, storage_dir = tracker_with_storage
        conv_id = "completeness-test"

        # Request 1: Large conversation
        base_time = datetime(2025, 12, 7, 10, 0, 0, tzinfo=timezone.utc)
        messages_1 = []
        for i in range(50):
            messages_1.append({"role": "user", "content": f"User message {i}"})
            messages_1.append({"role": "assistant", "content": f"Assistant response {i}"})

        with patch('haia.memory.boundary.datetime') as mock_dt:
            mock_dt.now.return_value = base_time
            mock_dt.side_effect = lambda *args, **kwargs: datetime(*args, **kwargs)
            await tracker.process_request(conv_id, messages_1)

        # Request 2: Trigger boundary
        later_time = base_time + timedelta(minutes=15)
        messages_2 = [{"role": "user", "content": "New conversation"}]

        with patch('haia.memory.boundary.datetime') as mock_dt:
            mock_dt.now.return_value = later_time
            mock_dt.side_effect = lambda *args, **kwargs: datetime(*args, **kwargs)
            result = await tracker.process_request(conv_id, messages_2)

        assert result.detected is True

        # Load transcript and verify completeness
        await asyncio.sleep(0.1)
        transcripts = list(storage_dir.glob("*.json"))
        assert len(transcripts) == 1

        import json
        with open(transcripts[0]) as f:
            transcript_data = json.load(f)

        # Should have all 100 messages from conversation 1
        assert transcript_data["message_count"] == len(messages_1)
        assert len(transcript_data["messages"]) == len(messages_1)

        # Verify message content matches
        for i, msg in enumerate(messages_1):
            assert transcript_data["messages"][i]["content"] == msg["content"]
