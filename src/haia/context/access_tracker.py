"""Access pattern tracking for memory usage statistics.

Tracks when and how often memories are accessed to support:
- Frequency-based re-ranking
- Usage analytics
- Memory lifecycle management

Usage:
    tracker = AccessTracker(neo4j_service)
    await tracker.record_access(memory_ids=["mem_001", "mem_002"])

    # Get metadata for re-ranking
    metadata = await tracker.get_access_metadata(["mem_001"])
"""

import logging
from datetime import datetime, timezone
from typing import Optional

from haia.context.models import AccessMetadata
from haia.services.neo4j import Neo4jService

logger = logging.getLogger(__name__)


class AccessTracker:
    """Tracks memory access patterns for usage-based ranking.

    Records access timestamps and frequency in Neo4j to enable:
    - Recency-based scoring (recent memories rank higher)
    - Frequency-based scoring (commonly used memories rank higher)
    - Usage analytics and reporting
    """

    def __init__(self, neo4j_service: Neo4jService):
        """Initialize access tracker.

        Args:
            neo4j_service: Neo4j service for database operations
        """
        self.neo4j = neo4j_service

    async def record_access(
        self,
        memory_ids: list[str],
        access_time: Optional[datetime] = None,
    ) -> int:
        """Record access to one or more memories.

        Updates last_accessed timestamp and increments access_count.
        Creates access records if they don't exist.

        Args:
            memory_ids: List of memory IDs that were accessed
            access_time: When memories were accessed (defaults to now)

        Returns:
            Number of memories successfully tracked
        """
        if not memory_ids:
            return 0

        access_time = access_time or datetime.now(timezone.utc)

        try:
            updated_count = await self.neo4j.record_memory_access(
                memory_ids=memory_ids,
                access_time=access_time,
            )

            logger.debug(
                f"Recorded access for {updated_count}/{len(memory_ids)} memories"
            )

            return updated_count

        except Exception as e:
            logger.error(f"Failed to record access: {e}", exc_info=True)
            # Don't raise - access tracking is non-critical
            return 0

    async def get_access_metadata(
        self, memory_ids: list[str]
    ) -> dict[str, AccessMetadata]:
        """Get access metadata for multiple memories.

        Returns a dictionary mapping memory_id to AccessMetadata.
        Missing memories will have default metadata (0 accesses, None last_accessed).

        Args:
            memory_ids: List of memory IDs to get metadata for

        Returns:
            Dictionary mapping memory_id -> AccessMetadata
        """
        if not memory_ids:
            return {}

        try:
            metadata_dict = await self.neo4j.get_access_metadata(memory_ids)

            logger.debug(f"Retrieved access metadata for {len(metadata_dict)} memories")

            return metadata_dict

        except Exception as e:
            logger.error(f"Failed to retrieve access metadata: {e}", exc_info=True)
            # Return empty metadata on error
            return {
                memory_id: AccessMetadata(
                    memory_id=memory_id,
                    last_accessed=None,
                    access_count=0,
                )
                for memory_id in memory_ids
            }

    async def get_usage_stats(self, memory_id: str) -> dict:
        """Get detailed usage statistics for a memory.

        Args:
            memory_id: Memory ID to get stats for

        Returns:
            Dictionary with usage statistics:
            - total_accesses: Total access count
            - last_accessed: Most recent access timestamp
            - first_accessed: First access timestamp
            - days_since_last_access: Days since last accessed
        """
        try:
            stats = await self.neo4j.get_memory_usage_stats(memory_id)
            return stats

        except Exception as e:
            logger.error(
                f"Failed to get usage stats for {memory_id}: {e}",
                exc_info=True,
            )
            return {
                "total_accesses": 0,
                "last_accessed": None,
                "first_accessed": None,
                "days_since_last_access": None,
            }

    async def reset_access_tracking(self, memory_ids: list[str]) -> int:
        """Reset access tracking for specified memories.

        Useful for testing or manual cleanup.
        Sets access_count to 0 and last_accessed to None.

        Args:
            memory_ids: List of memory IDs to reset

        Returns:
            Number of memories reset
        """
        if not memory_ids:
            return 0

        try:
            reset_count = await self.neo4j.reset_access_metadata(memory_ids)

            logger.info(f"Reset access tracking for {reset_count} memories")

            return reset_count

        except Exception as e:
            logger.error(f"Failed to reset access tracking: {e}", exc_info=True)
            return 0
