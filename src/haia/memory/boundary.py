"""Conversation boundary detection logic using hybrid heuristic."""

import hashlib
import logging
from datetime import datetime

from haia.memory.models import (
    BoundaryDetectionResult,
    BoundaryTriggerReason,
    ConversationMetadata,
)

logger = logging.getLogger(__name__)


# T013: compute_first_message_hash function
def compute_first_message_hash(messages: list[dict[str, str]]) -> str:
    """Compute SHA-256 hash of the first message content.

    Args:
        messages: List of OpenAI-format messages

    Returns:
        Hex-encoded SHA-256 hash

    Raises:
        IndexError: If messages list is empty
    """
    if not messages:
        raise IndexError("Cannot compute hash of empty message list")

    first_message_content = messages[0].get("content", "")
    return hashlib.sha256(first_message_content.encode("utf-8")).hexdigest()


# T020: detect_boundary function (will be implemented in Phase 3)
def detect_boundary(
    current_metadata: ConversationMetadata,
    new_message_count: int,
    new_first_hash: str,
    current_time: datetime,
    idle_threshold_minutes: int = 10,
    message_drop_threshold: float = 0.5,
) -> BoundaryDetectionResult:
    """Execute the hybrid heuristic for boundary detection.

    Algorithm:
        1. Calculate idle_duration = current_time - current_metadata.last_seen
        2. If idle_duration <= threshold: return (False, None)
        3. Calculate message_count_drop_percent = (prev - new) / prev
        4. Check hash_changed = (new_first_hash != prev_first_hash)
        5. If (message_count_drop_percent > threshold) OR hash_changed:
              return (True, reason)
           Else:
              return (False, None)

    Args:
        current_metadata: Previous conversation state
        new_message_count: Count of messages in current request
        new_first_hash: SHA-256 hash of first message in current request
        current_time: Current request timestamp (UTC)
        idle_threshold_minutes: Minimum idle time to consider (default: 10)
        message_drop_threshold: Minimum message count drop % (default: 0.5)

    Returns:
        BoundaryDetectionResult with detection status

    Pure Function: Yes (no side effects, deterministic)
    Thread-safe: Yes (no shared state)
    """
    # Calculate idle duration
    idle_duration = current_time - current_metadata.last_seen
    idle_duration_seconds = idle_duration.total_seconds()
    idle_threshold_seconds = idle_threshold_minutes * 60

    logger.debug(
        "Boundary detection check",
        extra={
            "conversation_id": current_metadata.conversation_id,
            "idle_duration_seconds": idle_duration_seconds,
            "idle_threshold_seconds": idle_threshold_seconds,
        },
    )

    # If idle time is below threshold, no boundary
    if idle_duration_seconds <= idle_threshold_seconds:
        return BoundaryDetectionResult(
            detected=False,
            reason=None,
            idle_duration_seconds=idle_duration_seconds,
            message_count_drop_percent=0.0,
            hash_changed=False,
        )

    # Calculate message count drop percentage
    prev_count = current_metadata.message_count
    message_drop = max(0, prev_count - new_message_count)
    message_count_drop_percent = (message_drop / prev_count) * 100 if prev_count > 0 else 0.0

    # Check if first message hash changed
    hash_changed = new_first_hash != current_metadata.first_message_hash

    logger.debug(
        "Boundary heuristic evaluation",
        extra={
            "conversation_id": current_metadata.conversation_id,
            "message_count_drop_percent": message_count_drop_percent,
            "message_drop_threshold_percent": message_drop_threshold * 100,
            "hash_changed": hash_changed,
        },
    )

    # Determine if boundary is detected and why
    message_drop_triggered = message_count_drop_percent > (message_drop_threshold * 100)

    if message_drop_triggered and hash_changed:
        reason = BoundaryTriggerReason.IDLE_AND_BOTH
    elif message_drop_triggered:
        reason = BoundaryTriggerReason.IDLE_AND_MESSAGE_DROP
    elif hash_changed:
        reason = BoundaryTriggerReason.IDLE_AND_HASH_CHANGE
    else:
        # Idle time exceeded but neither message drop nor hash change
        return BoundaryDetectionResult(
            detected=False,
            reason=None,
            idle_duration_seconds=idle_duration_seconds,
            message_count_drop_percent=message_count_drop_percent,
            hash_changed=hash_changed,
        )

    return BoundaryDetectionResult(
        detected=True,
        reason=reason,
        idle_duration_seconds=idle_duration_seconds,
        message_count_drop_percent=message_count_drop_percent,
        hash_changed=hash_changed,
    )
