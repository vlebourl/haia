"""Unit tests for extraction models."""

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from haia.extraction.models import (
    ConversationTranscript,
    ExtractedMemory,
    ExtractionResult,
    Message,
    MemoryCategory,
    ConfidenceLevel,
)


class TestMessage:
    """Tests for Message model."""

    def test_message_valid(self):
        """Test creating a valid message."""
        msg = Message(
            content="Test message",
            timestamp=datetime.now(timezone.utc),
            speaker="user",
        )
        assert msg.content == "Test message"
        assert msg.speaker == "user"

    def test_message_invalid_speaker(self):
        """Test message with invalid speaker."""
        with pytest.raises(ValidationError):
            Message(
                content="Test",
                timestamp=datetime.now(timezone.utc),
                speaker="invalid",  # type: ignore
            )


class TestConversationTranscript:
    """Tests for ConversationTranscript model."""

    def test_transcript_valid(self):
        """Test creating a valid transcript."""
        now = datetime.now(timezone.utc)
        transcript = ConversationTranscript(
            conversation_id="test_001",
            messages=[
                Message(content="Hello", timestamp=now, speaker="user"),
                Message(content="Hi", timestamp=now, speaker="assistant"),
            ],
            start_time=now,
            end_time=now,
            message_count=2,
        )
        assert transcript.conversation_id == "test_001"
        assert len(transcript.messages) == 2
        assert transcript.message_count == 2

    def test_transcript_duration_calculation(self):
        """Test duration calculation."""
        start = datetime(2025, 12, 8, 10, 0, 0, tzinfo=timezone.utc)
        end = datetime(2025, 12, 8, 10, 5, 30, tzinfo=timezone.utc)
        transcript = ConversationTranscript(
            conversation_id="test_002",
            messages=[Message(content="Test", timestamp=start, speaker="user")],
            start_time=start,
            end_time=end,
            message_count=1,
        )
        assert transcript.duration_seconds == 330.0  # 5 minutes 30 seconds

    def test_transcript_empty_messages_rejected(self):
        """Test that empty message list is rejected."""
        now = datetime.now(timezone.utc)
        with pytest.raises(ValidationError):
            ConversationTranscript(
                conversation_id="test_003",
                messages=[],  # Empty list should fail
                start_time=now,
                end_time=now,
                message_count=0,
            )


class TestExtractedMemory:
    """Tests for ExtractedMemory model."""

    def test_memory_valid_high_confidence(self):
        """Test creating a memory with high confidence."""
        memory = ExtractedMemory(
            memory_type="preference",
            content="User prefers Docker",
            confidence=0.85,
            source_conversation_id="conv_001",
        )
        assert memory.memory_type == "preference"
        assert memory.confidence == 0.85
        assert memory.is_high_confidence
        assert not memory.is_medium_confidence

    def test_memory_valid_medium_confidence(self):
        """Test creating a memory with medium confidence."""
        memory = ExtractedMemory(
            memory_type="technical_context",
            content="User has Proxmox cluster",
            confidence=0.55,
            source_conversation_id="conv_002",
        )
        assert memory.is_medium_confidence
        assert not memory.is_high_confidence

    def test_memory_confidence_below_threshold_rejected(self):
        """Test that confidence below 0.4 is rejected."""
        with pytest.raises(ValidationError, match="below 0.4 threshold"):
            ExtractedMemory(
                memory_type="preference",
                content="User might like vim",
                confidence=0.25,  # Below threshold
                source_conversation_id="conv_003",
            )

    def test_memory_confidence_out_of_range_rejected(self):
        """Test that confidence outside [0.0, 1.0] is rejected."""
        with pytest.raises(ValidationError):
            ExtractedMemory(
                memory_type="preference",
                content="Test",
                confidence=1.5,  # Above 1.0
                source_conversation_id="conv_004",
            )

    def test_memory_empty_content_rejected(self):
        """Test that empty content is rejected."""
        with pytest.raises(ValidationError):
            ExtractedMemory(
                memory_type="preference",
                content="",  # Empty string
                confidence=0.7,
                source_conversation_id="conv_005",
            )

    def test_memory_metadata_optional(self):
        """Test that metadata is optional."""
        memory = ExtractedMemory(
            memory_type="decision",
            content="User decided to use Docker Swarm",
            confidence=0.8,
            source_conversation_id="conv_006",
        )
        assert memory.metadata == {}

        # Test with metadata
        memory_with_meta = ExtractedMemory(
            memory_type="decision",
            content="User decided to use Docker Swarm",
            confidence=0.8,
            source_conversation_id="conv_006",
            metadata={"is_explicit": True, "mention_count": 2},
        )
        assert memory_with_meta.metadata["is_explicit"] is True


class TestExtractionResult:
    """Tests for ExtractionResult model."""

    def test_result_successful_with_memories(self):
        """Test successful extraction result."""
        result = ExtractionResult(
            conversation_id="conv_001",
            memories=[
                ExtractedMemory(
                    memory_type="preference",
                    content="Docker preferred",
                    confidence=0.85,
                    source_conversation_id="conv_001",
                )
            ],
            extraction_duration=2.5,
            model_used="claude-haiku-4-5-20251001",
        )
        assert result.is_successful
        assert result.memory_count == 1
        assert result.high_confidence_count == 1
        assert result.average_confidence == 0.85
        assert result.memory_types_distribution == {"preference": 1}

    def test_result_empty_memories(self):
        """Test extraction result with no memories."""
        result = ExtractionResult(
            conversation_id="conv_002",
            memories=[],
            extraction_duration=0.5,
            model_used="claude-haiku-4-5-20251001",
        )
        assert result.is_successful
        assert result.memory_count == 0
        assert result.average_confidence == 0.0
        assert result.memory_types_distribution == {}

    def test_result_with_error(self):
        """Test extraction result with error."""
        result = ExtractionResult(
            conversation_id="conv_003",
            memories=[],
            extraction_duration=1.0,
            model_used="claude-haiku-4-5-20251001",
            error="LLM API timeout",
        )
        assert not result.is_successful
        assert result.error == "LLM API timeout"

    def test_result_memory_distribution(self):
        """Test memory type distribution calculation."""
        result = ExtractionResult(
            conversation_id="conv_004",
            memories=[
                ExtractedMemory(
                    memory_type="preference",
                    content="Docker",
                    confidence=0.85,
                    source_conversation_id="conv_004",
                ),
                ExtractedMemory(
                    memory_type="preference",
                    content="Vim",
                    confidence=0.75,
                    source_conversation_id="conv_004",
                ),
                ExtractedMemory(
                    memory_type="technical_context",
                    content="Proxmox",
                    confidence=0.65,
                    source_conversation_id="conv_004",
                ),
            ],
            extraction_duration=3.0,
            model_used="claude-haiku-4-5-20251001",
        )
        assert result.memory_types_distribution == {
            "preference": 2,
            "technical_context": 1,
        }
        assert result.high_confidence_count == 2  # 0.85 and 0.75


class TestConfidenceLevel:
    """Tests for ConfidenceLevel enum."""

    def test_confidence_level_from_score_high(self):
        """Test high confidence level."""
        assert ConfidenceLevel.from_score(0.9) == ConfidenceLevel.HIGH
        assert ConfidenceLevel.from_score(0.7) == ConfidenceLevel.HIGH

    def test_confidence_level_from_score_medium(self):
        """Test medium confidence level."""
        assert ConfidenceLevel.from_score(0.6) == ConfidenceLevel.MEDIUM
        assert ConfidenceLevel.from_score(0.4) == ConfidenceLevel.MEDIUM

    def test_confidence_level_from_score_low(self):
        """Test low confidence level."""
        assert ConfidenceLevel.from_score(0.3) == ConfidenceLevel.LOW
        assert ConfidenceLevel.from_score(0.0) == ConfidenceLevel.LOW
