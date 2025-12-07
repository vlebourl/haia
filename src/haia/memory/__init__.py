"""Memory extraction subsystem for HAIA.

This module provides conversation boundary detection and transcript storage
for long-term memory extraction from chat conversations.
"""

from haia.memory.boundary import compute_first_message_hash, detect_boundary
from haia.memory.models import (
    BoundaryDetectionEvent,
    BoundaryDetectionResult,
    BoundaryTriggerReason,
    ChatMessage,
    ConversationMetadata,
    ConversationTranscript,
)
from haia.memory.storage import TranscriptStorage
from haia.memory.tracker import ConversationTracker

__all__ = [
    "BoundaryTriggerReason",
    "ChatMessage",
    "ConversationMetadata",
    "ConversationTranscript",
    "BoundaryDetectionEvent",
    "BoundaryDetectionResult",
    "ConversationTracker",
    "TranscriptStorage",
    "compute_first_message_hash",
    "detect_boundary",
]
