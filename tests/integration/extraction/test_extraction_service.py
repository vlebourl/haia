"""Integration tests for ExtractionService with real LLM.

These tests require an actual LLM (Anthropic API or Ollama) and verify
end-to-end extraction accuracy across all memory categories.
"""

import json
import os
from datetime import datetime, timezone
from pathlib import Path

import pytest

from haia.extraction import (
    ConversationTranscript,
    ExtractionService,
    Message,
)

# Get model from environment or use default
TEST_MODEL = os.getenv("HAIA_MODEL", "anthropic:claude-haiku-4-5-20251001")

# Load sample conversations
FIXTURES_DIR = Path(__file__).parent / "fixtures"
SAMPLE_CONVERSATIONS = json.loads((FIXTURES_DIR / "sample_conversations.json").read_text())


@pytest.fixture
def extraction_service():
    """Create ExtractionService instance for testing."""
    return ExtractionService(model=TEST_MODEL)


def load_conversation(conversation_data: dict) -> ConversationTranscript:
    """Load a conversation from test fixture data.

    Args:
        conversation_data: Dictionary with conversation fixture data

    Returns:
        ConversationTranscript instance
    """
    messages = [
        Message(
            content=msg["content"],
            timestamp=datetime.fromisoformat(msg["timestamp"].replace("Z", "+00:00")),
            speaker=msg["speaker"],
        )
        for msg in conversation_data["messages"]
    ]

    return ConversationTranscript(
        conversation_id=conversation_data["conversation_id"],
        messages=messages,
        start_time=datetime.fromisoformat(
            conversation_data["start_time"].replace("Z", "+00:00")
        ),
        end_time=datetime.fromisoformat(
            conversation_data["end_time"].replace("Z", "+00:00")
        ),
        message_count=conversation_data["message_count"],
    )


@pytest.mark.asyncio
async def test_extract_explicit_preferences(extraction_service):
    """Test extracting explicit user preferences.

    Validates:
    - Preference memory type extracted
    - High confidence (≥0.7) for explicit statements
    - Content accurately reflects user preference
    """
    # Load test conversation
    conversation_data = next(
        c for c in SAMPLE_CONVERSATIONS if c["conversation_id"] == "test_explicit_preference"
    )
    transcript = load_conversation(conversation_data)

    # Extract memories
    result = await extraction_service.extract_memories(transcript)

    # Verify extraction succeeded
    assert result.is_successful, f"Extraction failed: {result.error}"
    assert result.memory_count >= 1, "Should extract at least one memory"

    # Find preference memory
    preferences = [m for m in result.memories if m.memory_type == "preference"]
    assert len(preferences) >= 1, "Should extract at least one preference"

    # Validate first preference
    pref = preferences[0]
    assert pref.confidence >= 0.7, f"Preference confidence {pref.confidence} too low"
    assert "docker" in pref.content.lower(), "Content should mention Docker"
    assert pref.source_conversation_id == transcript.conversation_id

    # Verify performance
    assert result.extraction_duration < 10.0, "Extraction should complete in <10s"


@pytest.mark.asyncio
async def test_extract_personal_facts(extraction_service):
    """Test extracting personal facts and interests.

    Validates:
    - Personal fact memory type extracted
    - Appropriate confidence level (≥0.6)
    - Content captures personal interest
    """
    conversation_data = next(
        c for c in SAMPLE_CONVERSATIONS if c["conversation_id"] == "test_personal_fact"
    )
    transcript = load_conversation(conversation_data)

    result = await extraction_service.extract_memories(transcript)

    assert result.is_successful
    assert result.memory_count >= 1

    personal_facts = [m for m in result.memories if m.memory_type == "personal_fact"]
    assert len(personal_facts) >= 1

    fact = personal_facts[0]
    assert fact.confidence >= 0.6
    assert "automation" in fact.content.lower()


@pytest.mark.asyncio
async def test_extract_technical_context(extraction_service):
    """Test extracting technical infrastructure context.

    Validates:
    - Technical context memory type extracted
    - Appropriate confidence for infrastructure info
    - Content includes technical details
    """
    conversation_data = next(
        c for c in SAMPLE_CONVERSATIONS if c["conversation_id"] == "test_technical_context"
    )
    transcript = load_conversation(conversation_data)

    result = await extraction_service.extract_memories(transcript)

    assert result.is_successful
    assert result.memory_count >= 1

    tech_context = [m for m in result.memories if m.memory_type == "technical_context"]
    assert len(tech_context) >= 1

    context = tech_context[0]
    assert context.confidence >= 0.6
    assert "proxmox" in context.content.lower()


@pytest.mark.asyncio
async def test_extract_decisions(extraction_service):
    """Test extracting architectural decisions.

    Validates:
    - Decision memory type extracted
    - High confidence for explicit decisions
    - Content captures both decision and rationale
    """
    conversation_data = next(
        c for c in SAMPLE_CONVERSATIONS if c["conversation_id"] == "test_decision"
    )
    transcript = load_conversation(conversation_data)

    result = await extraction_service.extract_memories(transcript)

    assert result.is_successful
    assert result.memory_count >= 1

    decisions = [m for m in result.memories if m.memory_type == "decision"]
    assert len(decisions) >= 1

    decision = decisions[0]
    assert decision.confidence >= 0.7
    assert "docker" in decision.content.lower() or "swarm" in decision.content.lower()


@pytest.mark.asyncio
async def test_extract_corrections(extraction_service):
    """Test extracting corrections of previous statements.

    Validates:
    - Correction memory type extracted
    - Very high confidence (≥0.8) for corrections
    - Content reflects the corrected information
    """
    conversation_data = next(
        c for c in SAMPLE_CONVERSATIONS if c["conversation_id"] == "test_correction"
    )
    transcript = load_conversation(conversation_data)

    result = await extraction_service.extract_memories(transcript)

    assert result.is_successful
    assert result.memory_count >= 1

    corrections = [m for m in result.memories if m.memory_type == "correction"]
    assert len(corrections) >= 1

    correction = corrections[0]
    assert correction.confidence >= 0.8, f"Correction confidence {correction.confidence} too low"
    assert "docker" in correction.content.lower()


@pytest.mark.asyncio
async def test_empty_conversation_no_memories(extraction_service):
    """Test that conversations with no extractable memories return empty list."""
    transcript = ConversationTranscript(
        conversation_id="test_empty",
        messages=[
            Message(
                content="Hello",
                timestamp=datetime.now(timezone.utc),
                speaker="user",
            ),
            Message(
                content="Hi there!",
                timestamp=datetime.now(timezone.utc),
                speaker="assistant",
            ),
        ],
        start_time=datetime.now(timezone.utc),
        end_time=datetime.now(timezone.utc),
        message_count=2,
    )

    result = await extraction_service.extract_memories(transcript)

    assert result.is_successful
    # May return 0 or very few memories for generic greetings
    assert result.memory_count <= 1


@pytest.mark.asyncio
async def test_batch_extraction(extraction_service):
    """Test batch extraction with multiple transcripts.

    Validates:
    - All transcripts processed
    - Results returned in same order
    - Performance scales reasonably
    """
    transcripts = [load_conversation(c) for c in SAMPLE_CONVERSATIONS]

    results = await extraction_service.extract_batch(transcripts, max_concurrency=3)

    assert len(results) == len(transcripts)

    # Verify conversation IDs match (order preserved)
    for i, result in enumerate(results):
        assert result.conversation_id == transcripts[i].conversation_id

    # Verify at least some extractions succeeded
    successful = sum(1 for r in results if r.is_successful)
    assert successful >= len(transcripts) * 0.8  # At least 80% success rate


@pytest.mark.asyncio
async def test_confidence_threshold_filtering(extraction_service):
    """Test that memories below confidence threshold are filtered.

    Validates:
    - Only memories with confidence ≥0.4 are returned
    - Confidence threshold enforcement
    """
    # Create service with default threshold
    service = ExtractionService(model=TEST_MODEL, min_confidence=0.4)

    conversation_data = SAMPLE_CONVERSATIONS[0]
    transcript = load_conversation(conversation_data)

    result = await service.extract_memories(transcript)

    # Verify all returned memories meet threshold
    for memory in result.memories:
        assert memory.confidence >= 0.4, (
            f"Memory confidence {memory.confidence} below threshold"
        )


@pytest.mark.asyncio
async def test_extraction_metadata_populated(extraction_service):
    """Test that extraction result metadata is properly populated.

    Validates:
    - conversation_id set correctly
    - extraction_duration > 0
    - model_used matches configuration
    """
    conversation_data = SAMPLE_CONVERSATIONS[0]
    transcript = load_conversation(conversation_data)

    result = await extraction_service.extract_memories(transcript)

    assert result.conversation_id == transcript.conversation_id
    assert result.extraction_duration > 0
    assert result.model_used == TEST_MODEL
    assert result.extraction_timestamp is not None
