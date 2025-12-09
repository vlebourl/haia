"""Background worker for backfilling embeddings on existing memories.

This module provides automatic embedding generation for memories that don't
have embeddings yet. It runs asynchronously in the background and processes
memories in batches.

Session 8 - Memory Retrieval System
"""

import asyncio
import logging
from datetime import datetime
from typing import Any

from haia.embedding.ollama_client import OllamaClient
from haia.services.memory_storage import MemoryStorageService
from haia.services.neo4j import Neo4jService

logger = logging.getLogger(__name__)


class EmbeddingBackfillWorker:
    """Background worker for backfilling embeddings on existing memories.

    Processes memories without embeddings in batches, generating and storing
    embeddings asynchronously. Includes progress tracking, error handling,
    and dead letter queue for failed attempts.

    Features:
    - Batch processing with configurable batch size
    - Concurrent worker coordination
    - Progress tracking and reporting
    - Dead letter queue for retry logic
    - Graceful shutdown support

    Example:
        >>> worker = EmbeddingBackfillWorker(
        ...     neo4j_service=neo4j,
        ...     ollama_client=ollama,
        ...     memory_storage=storage,
        ...     batch_size=25,
        ... )
        >>> await worker.start()  # Runs in background
        >>> await worker.stop()   # Graceful shutdown
    """

    def __init__(
        self,
        neo4j_service: Neo4jService,
        ollama_client: OllamaClient,
        memory_storage: MemoryStorageService,
        batch_size: int = 25,
        max_workers: int = 2,
        embedding_version: str = "nomic-embed-text-v1",
        poll_interval: float = 30.0,
    ):
        """Initialize backfill worker.

        Args:
            neo4j_service: Neo4j service for querying unprocessed memories
            ollama_client: Ollama client for embedding generation
            memory_storage: Storage service for persisting embeddings
            batch_size: Number of memories to process per batch
            max_workers: Maximum concurrent workers (not yet implemented)
            embedding_version: Model version identifier
            poll_interval: Seconds between checking for new memories
        """
        self.neo4j = neo4j_service
        self.ollama = ollama_client
        self.storage = memory_storage
        self.batch_size = batch_size
        self.max_workers = max_workers
        self.embedding_version = embedding_version
        self.poll_interval = poll_interval

        # State tracking
        self.is_running = False
        self.processed_count = 0
        self.failed_count = 0
        self.dead_letter_queue: list[dict[str, Any]] = []

        # Background task handle
        self._task: asyncio.Task | None = None

        logger.info(
            "EmbeddingBackfillWorker initialized",
            extra={
                "batch_size": batch_size,
                "embedding_version": embedding_version,
                "poll_interval": poll_interval,
            },
        )

    async def start(self) -> None:
        """Start the backfill worker in background.

        Continuously polls for memories without embeddings and processes them
        in batches until stopped.

        Note:
            This method runs indefinitely until stop() is called.
        """
        if self.is_running:
            logger.warning("Backfill worker already running")
            return

        self.is_running = True
        logger.info("Starting embedding backfill worker")

        try:
            while self.is_running:
                # Get next batch of memories to process
                batch = await self.get_next_batch()

                if batch:
                    # Process batch
                    result = await self.process_batch(batch)
                    logger.info(
                        f"Backfill batch complete: processed={result['processed']}, "
                        f"failed={result['failed']}, skipped={result['skipped']}"
                    )
                else:
                    # No memories to process, wait before next check
                    logger.debug(
                        f"No memories to process, waiting {self.poll_interval}s"
                    )

                # Wait before next poll
                await asyncio.sleep(self.poll_interval)

        except asyncio.CancelledError:
            logger.info("Backfill worker cancelled")
            raise
        except Exception as e:
            logger.error(f"Backfill worker error: {e}", exc_info=True)
            raise
        finally:
            self.is_running = False
            logger.info("Backfill worker stopped")

    async def stop(self) -> None:
        """Stop the backfill worker gracefully."""
        if not self.is_running:
            logger.debug("Backfill worker not running")
            return

        logger.info("Stopping backfill worker")
        self.is_running = False

        # Wait a bit for current batch to complete
        await asyncio.sleep(0.5)

    async def get_next_batch(self) -> list[dict[str, Any]]:
        """Fetch next batch of memories without embeddings.

        Returns:
            List of memory dictionaries from Neo4j

        Raises:
            Exception: If Neo4j query fails
        """
        try:
            memories = await self.neo4j.get_memories_without_embeddings(
                batch_size=self.batch_size
            )
            return memories
        except Exception as e:
            logger.error(f"Failed to fetch batch: {e}", exc_info=True)
            return []

    async def process_batch(self, batch: list[dict[str, Any]]) -> dict[str, int]:
        """Process a batch of memories, generating and storing embeddings.

        Args:
            batch: List of memory dictionaries from Neo4j

        Returns:
            Dictionary with counts: processed, failed, skipped

        Note:
            Failures are added to dead letter queue for retry.
        """
        if not batch:
            return {"processed": 0, "failed": 0, "skipped": 0}

        logger.info(f"Processing batch of {len(batch)} memories")

        processed = 0
        failed = 0
        skipped = 0

        for memory_dict in batch:
            try:
                memory_id = memory_dict.get("memory_id")
                content = memory_dict.get("content")

                if not memory_id or not content:
                    logger.warning(f"Invalid memory data: {memory_dict}")
                    skipped += 1
                    continue

                # Generate embedding
                embedding = await self.ollama.embed(content)

                # Store embedding
                success = await self.storage.store_embedding(
                    memory_id=memory_id,
                    embedding=embedding,
                    embedding_version=self.embedding_version,
                )

                if success:
                    processed += 1
                    self.processed_count += 1
                else:
                    failed += 1
                    self.failed_count += 1
                    self.dead_letter_queue.append(memory_dict)

            except Exception as e:
                # Add to dead letter queue for retry
                failed += 1
                self.failed_count += 1
                self.dead_letter_queue.append(memory_dict)

                logger.warning(
                    f"Failed to process memory {memory_dict.get('memory_id')}: {e}",
                    extra={"memory_id": memory_dict.get("memory_id")},
                )

        return {"processed": processed, "failed": failed, "skipped": skipped}

    async def retry_dead_letter_queue(self) -> dict[str, int]:
        """Retry processing memories from the dead letter queue.

        Returns:
            Dictionary with counts: processed, failed

        Note:
            Successfully processed memories are removed from queue.
        """
        if not self.dead_letter_queue:
            return {"processed": 0, "failed": 0}

        logger.info(f"Retrying {len(self.dead_letter_queue)} failed memories")

        # Take a copy to iterate over
        to_retry = list(self.dead_letter_queue)
        self.dead_letter_queue.clear()

        processed = 0
        failed = 0

        for memory_dict in to_retry:
            try:
                memory_id = memory_dict.get("memory_id")
                content = memory_dict.get("content")

                # Generate embedding
                embedding = await self.ollama.embed(content)

                # Store embedding
                success = await self.storage.store_embedding(
                    memory_id=memory_id,
                    embedding=embedding,
                    embedding_version=self.embedding_version,
                )

                if success:
                    processed += 1
                    self.processed_count += 1
                else:
                    failed += 1
                    self.failed_count += 1
                    self.dead_letter_queue.append(memory_dict)

            except Exception as e:
                failed += 1
                self.failed_count += 1
                self.dead_letter_queue.append(memory_dict)

                logger.warning(
                    f"Retry failed for memory {memory_dict.get('memory_id')}: {e}"
                )

        return {"processed": processed, "failed": failed}

    def get_progress(self) -> dict[str, Any]:
        """Get current progress statistics.

        Returns:
            Dictionary with progress metrics:
            - processed: Total memories processed
            - failed: Total failures
            - total: Total attempts
            - success_rate: Percentage of successes
            - dead_letter_queue_size: Current dead letter queue size
            - is_running: Whether worker is active
        """
        total = self.processed_count + self.failed_count
        success_rate = self.processed_count / total if total > 0 else 0.0

        return {
            "processed": self.processed_count,
            "failed": self.failed_count,
            "total": total,
            "success_rate": success_rate,
            "dead_letter_queue_size": len(self.dead_letter_queue),
            "is_running": self.is_running,
        }

    async def health_check(self) -> bool:
        """Check if backfill worker dependencies are healthy.

        Returns:
            True if all dependencies are available
        """
        try:
            ollama_ok = await self.ollama.health_check()
            neo4j_ok = await self.neo4j.health_check()

            return ollama_ok and neo4j_ok
        except Exception as e:
            logger.warning(f"Backfill worker health check failed: {e}")
            return False
