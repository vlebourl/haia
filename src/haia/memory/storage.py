"""Filesystem storage for conversation transcripts."""

import json
import logging
from pathlib import Path

import aiofiles

from haia.memory.models import ConversationTranscript

logger = logging.getLogger(__name__)


class TranscriptStorage:
    """Manages filesystem storage of conversation transcripts."""

    def __init__(self, storage_dir: str):
        """Initialize transcript storage.

        Args:
            storage_dir: Directory path for storing transcripts
        """
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)

        logger.info(
            "TranscriptStorage initialized",
            extra={"storage_dir": str(self.storage_dir)},
        )

    async def store_transcript(
        self,
        transcript: ConversationTranscript,
    ) -> str:
        """Store a conversation transcript to the filesystem.

        Args:
            transcript: Complete conversation to store

        Returns:
            Filename of the stored transcript

        Raises:
            IOError: If disk write fails
            PermissionError: If directory is not writable
        """
        filename = transcript.filename
        filepath = self.storage_dir / filename

        # Convert to JSON-serializable dict
        transcript_dict = transcript.model_dump(mode="json")

        # Write to file asynchronously
        async with aiofiles.open(filepath, "w") as f:
            await f.write(json.dumps(transcript_dict, indent=2))

        logger.debug(
            "Transcript stored",
            extra={
                "filename": filename,
                "conversation_id": transcript.conversation_id,
                "message_count": transcript.message_count,
            },
        )

        return filename

    async def load_transcript(
        self,
        filename: str,
    ) -> ConversationTranscript:
        """Load a transcript from the filesystem.

        Args:
            filename: Name of the transcript file (without path)

        Returns:
            Parsed ConversationTranscript

        Raises:
            FileNotFoundError: If file doesn't exist
            ValueError: If JSON is malformed
        """
        filepath = self.storage_dir / filename

        if not filepath.exists():
            raise FileNotFoundError(f"Transcript not found: {filename}")

        async with aiofiles.open(filepath) as f:
            content = await f.read()
            data = json.loads(content)

        return ConversationTranscript(**data)

    async def list_transcripts(
        self,
        limit: int = 100,
    ) -> list[str]:
        """List stored transcript filenames (most recent first).

        Args:
            limit: Maximum number to return

        Returns:
            List of filenames sorted by modification time (newest first)
        """
        # Get all JSON files in storage directory
        files = list(self.storage_dir.glob("*.json"))

        # Sort by modification time (newest first)
        files.sort(key=lambda f: f.stat().st_mtime, reverse=True)

        # Return filenames (not full paths)
        return [f.name for f in files[:limit]]
