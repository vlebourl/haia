"""Conversation tracker for boundary detection and transcript management."""

import asyncio
import logging
from collections import OrderedDict
from datetime import UTC, datetime, timedelta

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

logger = logging.getLogger(__name__)


class ConversationTracker:
    """Tracks conversation metadata and detects conversation boundaries.

    This class maintains in-memory metadata for active conversations and
    triggers boundary detection based on idle time and message history changes.
    When boundaries are detected, complete transcripts are stored for later
    memory extraction.
    """

    def __init__(
        self,
        storage_dir: str,
        idle_threshold_minutes: int = 10,
        message_drop_threshold: float = 0.5,
        max_tracked_conversations: int = 1000,
    ):
        """Initialize the conversation tracker.

        Args:
            storage_dir: Directory for storing conversation transcripts
            idle_threshold_minutes: Minimum idle time to consider for boundaries
            message_drop_threshold: Minimum message count drop (fraction)
            max_tracked_conversations: Maximum conversations to track (LRU eviction)
        """
        self._storage = TranscriptStorage(storage_dir)
        self._idle_threshold_minutes = idle_threshold_minutes
        self._message_drop_threshold = message_drop_threshold
        self._max_tracked_conversations = max_tracked_conversations

        # In-memory metadata storage with LRU tracking
        self._metadata: dict[str, ConversationMetadata] = {}
        self._access_order: OrderedDict[str, None] = OrderedDict()
        self._lock = asyncio.Lock()

        # Message history for transcript creation (temporary storage)
        self._message_history: dict[str, list[dict[str, str]]] = {}

        logger.info(
            "ConversationTracker initialized",
            extra={
                "storage_dir": storage_dir,
                "idle_threshold_minutes": idle_threshold_minutes,
                "message_drop_threshold": message_drop_threshold,
                "max_conversations": max_tracked_conversations,
            },
        )

    async def process_request(
        self,
        conversation_id: str,
        messages: list[dict[str, str]],
    ) -> BoundaryDetectionResult:
        """Process an incoming chat request and check for conversation boundaries.

        Args:
            conversation_id: Unique identifier for the conversation
            messages: List of chat messages from the request (OpenAI format)

        Returns:
            BoundaryDetectionResult with detection status and metadata

        Raises:
            ValueError: If messages list is empty
        """
        if not messages:
            raise ValueError("Messages list cannot be empty")

        async with self._lock:
            current_time = datetime.now(UTC)
            new_message_count = len(messages)
            new_first_hash = compute_first_message_hash(messages)

            # Check if this is a known conversation
            if conversation_id in self._metadata:
                # Existing conversation - check for boundary
                current_metadata = self._metadata[conversation_id]

                result = detect_boundary(
                    current_metadata=current_metadata,
                    new_message_count=new_message_count,
                    new_first_hash=new_first_hash,
                    current_time=current_time,
                    idle_threshold_minutes=self._idle_threshold_minutes,
                    message_drop_threshold=self._message_drop_threshold,
                )

                if result.detected:
                    # Boundary detected - store transcript and log event
                    await self._handle_boundary_detection(
                        conversation_id=conversation_id,
                        current_metadata=current_metadata,
                        result=result,
                        current_time=current_time,
                    )

                    # Reset metadata for new conversation
                    self._create_new_metadata(
                        conversation_id=conversation_id,
                        message_count=new_message_count,
                        first_hash=new_first_hash,
                        current_time=current_time,
                    )
                else:
                    # No boundary - update existing metadata
                    self._update_metadata(
                        conversation_id=conversation_id,
                        message_count=new_message_count,
                        first_hash=new_first_hash,
                        current_time=current_time,
                    )

                # Update message history
                self._message_history[conversation_id] = messages.copy()

                # Update access order for LRU
                self._update_access_order(conversation_id)

                return result
            else:
                # New conversation - create metadata
                self._create_new_metadata(
                    conversation_id=conversation_id,
                    message_count=new_message_count,
                    first_hash=new_first_hash,
                    current_time=current_time,
                )

                # Store initial message history
                self._message_history[conversation_id] = messages.copy()

                # Add to access order
                self._update_access_order(conversation_id)

                # Check if we need to evict oldest conversation
                await self._evict_if_needed()

                # First request - no boundary
                return BoundaryDetectionResult(
                    detected=False,
                    reason=None,
                    idle_duration_seconds=0.0,
                    message_count_drop_percent=0.0,
                    hash_changed=False,
                )

    async def get_metadata(
        self,
        conversation_id: str,
    ) -> ConversationMetadata | None:
        """Retrieve metadata for a conversation (for debugging/testing).

        Args:
            conversation_id: Conversation to look up

        Returns:
            ConversationMetadata if exists, None otherwise
        """
        async with self._lock:
            return self._metadata.get(conversation_id)

    async def get_stored_transcripts(
        self,
        limit: int = 100,
    ) -> list[str]:
        """List filenames of stored transcripts (most recent first).

        Args:
            limit: Maximum number of filenames to return

        Returns:
            List of transcript filenames
        """
        return await self._storage.list_transcripts(limit=limit)

    def _create_new_metadata(
        self,
        conversation_id: str,
        message_count: int,
        first_hash: str,
        current_time: datetime,
    ) -> None:
        """Create new metadata entry for a conversation.

        Args:
            conversation_id: Conversation identifier
            message_count: Number of messages in current request
            first_hash: SHA-256 hash of first message
            current_time: Current timestamp (UTC)
        """
        metadata = ConversationMetadata(
            conversation_id=conversation_id,
            last_seen=current_time,
            message_count=message_count,
            first_message_hash=first_hash,
            start_time=current_time,
        )
        self._metadata[conversation_id] = metadata

        logger.debug(
            "Created new conversation metadata",
            extra={
                "conversation_id": conversation_id,
                "message_count": message_count,
                "start_time": current_time.isoformat(),
            },
        )

    def _update_metadata(
        self,
        conversation_id: str,
        message_count: int,
        first_hash: str,
        current_time: datetime,
    ) -> None:
        """Update existing metadata for a conversation.

        Args:
            conversation_id: Conversation identifier
            message_count: Number of messages in current request
            first_hash: SHA-256 hash of first message
            current_time: Current timestamp (UTC)
        """
        if conversation_id not in self._metadata:
            return

        metadata = self._metadata[conversation_id]

        # Update mutable fields
        self._metadata[conversation_id] = ConversationMetadata(
            conversation_id=metadata.conversation_id,
            last_seen=current_time,
            message_count=message_count,
            first_message_hash=first_hash,
            start_time=metadata.start_time,  # Keep original start time
        )

        logger.debug(
            "Updated conversation metadata",
            extra={
                "conversation_id": conversation_id,
                "message_count": message_count,
                "last_seen": current_time.isoformat(),
            },
        )

    def _update_access_order(self, conversation_id: str) -> None:
        """Update LRU access order for a conversation.

        Args:
            conversation_id: Conversation to mark as recently accessed
        """
        # Remove if exists (to move to end)
        if conversation_id in self._access_order:
            del self._access_order[conversation_id]

        # Add to end (most recent)
        self._access_order[conversation_id] = None

    async def _evict_if_needed(self) -> None:
        """Evict oldest conversation if max limit is reached (LRU eviction)."""
        if len(self._metadata) > self._max_tracked_conversations:
            # Get oldest conversation (first in OrderedDict)
            oldest_id = next(iter(self._access_order))

            # Remove from all tracking structures
            del self._metadata[oldest_id]
            del self._access_order[oldest_id]
            if oldest_id in self._message_history:
                del self._message_history[oldest_id]

            logger.debug(
                "Evicted oldest conversation (LRU)",
                extra={
                    "conversation_id": oldest_id,
                    "remaining_conversations": len(self._metadata),
                },
            )

    async def _handle_boundary_detection(
        self,
        conversation_id: str,
        current_metadata: ConversationMetadata,
        result: BoundaryDetectionResult,
        current_time: datetime,
    ) -> None:
        """Handle detected conversation boundary.

        Args:
            conversation_id: Conversation that ended
            current_metadata: Metadata from ended conversation
            result: Boundary detection result
            current_time: Current timestamp (UTC)
        """
        # Create transcript from message history
        messages_data = self._message_history.get(conversation_id, [])

        # Convert to ChatMessage models with timestamps
        chat_messages = []
        for i, msg in enumerate(messages_data):
            # Estimate timestamps (spread evenly across conversation duration)
            duration = (current_time - current_metadata.start_time).total_seconds()
            msg_offset = (duration / len(messages_data)) * i if messages_data else 0
            msg_time = current_metadata.start_time + timedelta(seconds=msg_offset)

            chat_messages.append(
                ChatMessage(
                    role=msg.get("role", "user"),
                    content=msg.get("content", ""),
                    timestamp=msg_time,
                )
            )

        if not chat_messages:
            logger.warning(
                "No messages in history for ended conversation",
                extra={"conversation_id": conversation_id},
            )
            return

        transcript = ConversationTranscript(
            conversation_id=conversation_id,
            start_time=current_metadata.start_time,
            end_time=current_time,
            message_count=len(chat_messages),
            trigger_reason=result.reason or BoundaryTriggerReason.IDLE_AND_MESSAGE_DROP,
            messages=chat_messages,
            metadata={},
        )

        # Store transcript (async, but don't block on errors)
        try:
            filename = await self._storage.store_transcript(transcript)

            # Log boundary detection event
            event = BoundaryDetectionEvent(
                timestamp=current_time,
                conversation_id=conversation_id,
                idle_duration_seconds=result.idle_duration_seconds,
                previous_message_count=current_metadata.message_count,
                current_message_count=len(messages_data),
                message_count_drop_percent=result.message_count_drop_percent,
                previous_first_hash=current_metadata.first_message_hash,
                current_first_hash=compute_first_message_hash(messages_data),
                hash_changed=result.hash_changed,
                trigger_reason=result.reason or BoundaryTriggerReason.IDLE_AND_MESSAGE_DROP,
                transcript_filename=filename,
            )

            logger.info(
                "Conversation boundary detected",
                extra=event.to_log_dict(),
            )

        except Exception as e:
            logger.error(
                "Failed to store transcript",
                extra={
                    "conversation_id": conversation_id,
                    "error": str(e),
                },
                exc_info=True,
            )
