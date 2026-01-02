"""Background task scheduler for HAIA automated operations."""

import logging
from typing import Optional

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from haia.clustering.type_clusterer import TypeClusterer
from haia.consolidation.consolidator import MemoryConsolidator
from haia.consolidation.decay import DecayStrategy, ExponentialDecay
from haia.services.neo4j import Neo4jService

logger = logging.getLogger(__name__)


class HAIAScheduler:
    """
    Background task scheduler for automated HAIA operations.

    Manages scheduled jobs:
    - Memory consolidation (daily at 3 AM) - Session 14, US6
    - Type clustering (daily at 4 AM)
    - Memory clustering (weekly Sundays at 2 AM) - future
    """

    def __init__(
        self,
        neo4j_service: Neo4jService,
        extraction_model: str = "anthropic:claude-haiku-4-5-20251001",
        type_clustering_enabled: bool = True,
        type_clustering_schedule: str = "0 4 * * *",  # Daily at 4 AM
        min_cluster_size: int = 3,
        similarity_threshold: float = 0.80,
        embedding_provider: str = "google",
        google_api_key: Optional[str] = None,
        google_embedding_model: str = "text-embedding-004",
        # Memory consolidation parameters (Session 14, US6)
        consolidation_enabled: bool = True,
        consolidation_schedule: str = "0 3 * * *",  # Daily at 3 AM
        promotion_threshold: float = 0.7,
        archival_threshold: float = 0.2,
        short_term_days: int = 7,
        decay_strategy: Optional[DecayStrategy] = None,
        access_weight: float = 0.40,
        recency_weight: float = 0.30,
        confidence_weight: float = 0.30,
    ):
        """
        Initialize HAIA scheduler.

        Args:
            neo4j_service: Neo4j service instance
            extraction_model: Model for LLM operations
            type_clustering_enabled: Enable type clustering job
            type_clustering_schedule: Cron expression for clustering schedule
            min_cluster_size: Minimum types per cluster
            similarity_threshold: Cosine similarity threshold
            embedding_provider: "google" or "local" for embeddings
            google_api_key: Google API key (required if provider="google")
            google_embedding_model: Google embedding model name
            consolidation_enabled: Enable memory consolidation job
            consolidation_schedule: Cron expression for consolidation schedule
            promotion_threshold: Priority threshold for SHORT_TERM → LONG_TERM
            archival_threshold: Priority threshold for LONG_TERM → ARCHIVED
            short_term_days: Minimum days before promoting SHORT_TERM memories
            decay_strategy: Decay strategy for recency scoring (default: ExponentialDecay)
            access_weight: Weight for access frequency in priority formula
            recency_weight: Weight for recency score in priority formula
            confidence_weight: Weight for confidence in priority formula
        """
        self.neo4j = neo4j_service
        self.extraction_model = extraction_model

        # Type clustering configuration
        self.type_clustering_enabled = type_clustering_enabled
        self.type_clustering_schedule = type_clustering_schedule
        self.min_cluster_size = min_cluster_size
        self.similarity_threshold = similarity_threshold
        self.embedding_provider = embedding_provider
        self.google_api_key = google_api_key
        self.google_embedding_model = google_embedding_model

        # Memory consolidation configuration (Session 14, US6)
        self.consolidation_enabled = consolidation_enabled
        self.consolidation_schedule = consolidation_schedule
        self.promotion_threshold = promotion_threshold
        self.archival_threshold = archival_threshold
        self.short_term_days = short_term_days
        self.decay_strategy = decay_strategy or ExponentialDecay()
        self.access_weight = access_weight
        self.recency_weight = recency_weight
        self.confidence_weight = confidence_weight

        # Initialize scheduler and services
        self.scheduler: Optional[AsyncIOScheduler] = None
        self.type_clusterer: Optional[TypeClusterer] = None
        self.consolidator: Optional[MemoryConsolidator] = None

        logger.info("HAIA Scheduler initialized")

    def _initialize_services(self):
        """Initialize dependent services."""
        if self.type_clustering_enabled and self.type_clusterer is None:
            self.type_clusterer = TypeClusterer(
                neo4j_service=self.neo4j,
                extraction_model=self.extraction_model,
                min_cluster_size=self.min_cluster_size,
                similarity_threshold=self.similarity_threshold,
                embedding_provider=self.embedding_provider,
                google_api_key=self.google_api_key,
                google_embedding_model=self.google_embedding_model,
            )
            logger.info(
                f"TypeClusterer service initialized with {self.embedding_provider} embeddings"
            )

        if self.consolidation_enabled and self.consolidator is None:
            self.consolidator = MemoryConsolidator(
                neo4j_service=self.neo4j,
                decay_strategy=self.decay_strategy,
                promotion_threshold=self.promotion_threshold,
                archival_threshold=self.archival_threshold,
                short_term_days=self.short_term_days,
                access_weight=self.access_weight,
                recency_weight=self.recency_weight,
                confidence_weight=self.confidence_weight,
            )
            logger.info(
                f"MemoryConsolidator initialized: "
                f"promotion={self.promotion_threshold}, archival={self.archival_threshold}, "
                f"decay={self.decay_strategy.__class__.__name__}"
            )

    async def _run_type_clustering_job(self):
        """
        Execute type clustering job.

        Scheduled: Daily at 4 AM (configurable)
        Purpose: Cluster semantically similar memory types
        """
        logger.info("Starting scheduled type clustering job")
        try:
            if self.type_clusterer is None:
                self._initialize_services()

            if self.type_clusterer is not None:
                clusters = await self.type_clusterer.run_clustering()
                logger.info(
                    f"Type clustering job complete: {len(clusters)} clusters created"
                )
            else:
                logger.error("TypeClusterer not initialized")

        except Exception as e:
            logger.error(f"Type clustering job failed: {e}", exc_info=True)

    async def _run_consolidation_job(self):
        """
        Execute memory consolidation job (Session 14, US6, T111).

        Scheduled: Daily at 3 AM (configurable)
        Purpose: Promote high-priority SHORT_TERM memories to LONG_TERM,
                 archive low-priority LONG_TERM memories to ARCHIVED
        """
        logger.info("Starting scheduled memory consolidation job")
        try:
            if self.consolidator is None:
                self._initialize_services()

            if self.consolidator is not None:
                report = await self.consolidator.run_consolidation()
                logger.info(
                    f"Memory consolidation job complete: "
                    f"{report.promoted_count} promoted, {report.archived_count} archived, "
                    f"{report.unchanged_count} unchanged "
                    f"({report.execution_time_ms:.0f}ms)"
                )
            else:
                logger.error("MemoryConsolidator not initialized")

        except Exception as e:
            logger.error(f"Memory consolidation job failed: {e}", exc_info=True)

    def start(self):
        """
        Start the scheduler and register all enabled jobs.

        Jobs are registered based on configuration flags:
        - consolidation_enabled: Daily memory consolidation at 3 AM (Session 14, US6)
        - type_clustering_enabled: Daily type clustering at 4 AM
        """
        if self.scheduler is not None:
            logger.warning("Scheduler already running")
            return

        self.scheduler = AsyncIOScheduler()
        self._initialize_services()

        # Register memory consolidation job (Session 14, US6)
        if self.consolidation_enabled:
            self.scheduler.add_job(
                self._run_consolidation_job,
                trigger=CronTrigger.from_crontab(self.consolidation_schedule),
                id="memory_consolidation",
                name="Memory Consolidation",
                replace_existing=True,
                misfire_grace_time=3600,  # 1 hour grace period
            )
            logger.info(
                f"Registered memory consolidation job: schedule='{self.consolidation_schedule}'"
            )

        # Register type clustering job
        if self.type_clustering_enabled:
            self.scheduler.add_job(
                self._run_type_clustering_job,
                trigger=CronTrigger.from_crontab(self.type_clustering_schedule),
                id="type_clustering",
                name="Type Clustering",
                replace_existing=True,
                misfire_grace_time=3600,  # 1 hour grace period
            )
            logger.info(
                f"Registered type clustering job: schedule='{self.type_clustering_schedule}'"
            )

        # Start scheduler
        self.scheduler.start()
        logger.info("HAIA Scheduler started successfully")

    def stop(self):
        """Stop the scheduler and shutdown all jobs."""
        if self.scheduler is None:
            logger.warning("Scheduler not running")
            return

        self.scheduler.shutdown(wait=True)
        self.scheduler = None
        logger.info("HAIA Scheduler stopped")

    def get_jobs(self) -> list[dict]:
        """
        Get list of all registered jobs.

        Returns:
            List of job info dictionaries
        """
        if self.scheduler is None:
            return []

        jobs = []
        for job in self.scheduler.get_jobs():
            jobs.append(
                {
                    "id": job.id,
                    "name": job.name,
                    "next_run": job.next_run_time,
                    "trigger": str(job.trigger),
                }
            )
        return jobs

    async def run_job_now(self, job_id: str):
        """
        Manually trigger a job execution (for testing/debugging).

        Args:
            job_id: ID of job to run (e.g., "memory_consolidation", "type_clustering")
        """
        if job_id == "memory_consolidation":
            await self._run_consolidation_job()
        elif job_id == "type_clustering":
            await self._run_type_clustering_job()
        else:
            logger.error(f"Unknown job ID: {job_id}")
