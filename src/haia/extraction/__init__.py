"""Memory extraction service for HAIA.

This package provides automatic memory extraction from conversation transcripts
using PydanticAI with confidence scoring and structured output.
"""

from haia.extraction.extractor import ExtractionService
from haia.extraction.models import (
    ConversationTranscript,
    ExtractedMemory,
    ExtractionResult,
    Message,
    MemoryCategory,
    ConfidenceLevel,
)

__all__ = [
    "ExtractionService",
    "ConversationTranscript",
    "ExtractedMemory",
    "ExtractionResult",
    "Message",
    "MemoryCategory",
    "ConfidenceLevel",
]
