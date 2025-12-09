"""FastAPI application setup with lifespan management."""

import asyncio
import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from haia.agent import create_agent
from haia.api.deps import (
    set_agent,
    set_conversation_tracker,
    set_neo4j_service,
    set_retrieval_service,
)
from haia.api.routes import chat
from haia.config import settings
from haia.embedding.ollama_client import OllamaClient
from haia.embedding.retrieval_service import RetrievalService
from haia.extraction import ExtractionService
from haia.memory.tracker import ConversationTracker
from haia.services.memory_storage import MemoryStorageService
from haia.services.neo4j import Neo4jService

# Configure logging - simpler format without correlation_id for startup logs
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifespan (startup and shutdown).

    Args:
        app: FastAPI application instance

    Yields:
        Control to the application during its runtime
    """
    # Startup
    logger.info("Starting HAIA Chat API server...")

    # Set API keys in environment for PydanticAI provider initialization
    if settings.anthropic_api_key:
        os.environ["ANTHROPIC_API_KEY"] = settings.anthropic_api_key

    # Create PydanticAI agent with model from config
    logger.info(f"Creating PydanticAI agent with model: {settings.haia_model}")
    agent = create_agent(settings.haia_model)
    set_agent(agent)

    # Initialize Neo4j connection
    logger.info(f"Connecting to Neo4j at {settings.neo4j_uri}")
    neo4j_service = Neo4jService(
        uri=settings.neo4j_uri,
        user=settings.neo4j_user,
        password=settings.neo4j_password,
    )
    await neo4j_service.connect()
    set_neo4j_service(neo4j_service)
    logger.info("Neo4j connection established")

    # Initialize Ollama client and retrieval service (Session 8 - Memory Retrieval)
    # Graceful degradation: If Ollama unavailable, skip retrieval (conversations still work)
    try:
        logger.info(f"Initializing Ollama client at {settings.ollama_base_url}")
        ollama_client = OllamaClient(
            base_url=settings.ollama_base_url,
            model=settings.embedding_model.split(":")[-1],  # Extract model name from "ollama:model"
            timeout=30.0,
            max_retries=3,
        )

        # Health check Ollama
        if await ollama_client.health_check():
            logger.info(f"Initializing retrieval service (model: {settings.embedding_model})")

            # Load type weights from settings (Session 8 - User Story 3)
            type_weights = {
                "preference": settings.memory_type_weight_preference,
                "technical_context": settings.memory_type_weight_technical_context,
                "decision": settings.memory_type_weight_decision,
                "personal_fact": settings.memory_type_weight_personal_fact,
                "correction": settings.memory_type_weight_correction,
            }

            retrieval_service = RetrievalService(
                neo4j_service=neo4j_service,
                ollama_client=ollama_client,
                similarity_weight=0.5,  # 50%
                confidence_weight=0.3,  # 30%
                recency_weight=0.2,  # 20%
                type_weights=type_weights,
            )
            set_retrieval_service(retrieval_service)
            logger.info("Retrieval service initialized successfully")
        else:
            logger.warning(
                "Ollama health check failed - memory retrieval disabled. "
                "Conversations will continue without semantic memory injection."
            )
    except Exception as e:
        logger.warning(
            f"Failed to initialize retrieval service: {e}. "
            "Memory retrieval disabled. Conversations will continue normally."
        )

    # Initialize memory extraction service
    extraction_model = settings.extraction_model or settings.haia_model
    logger.info(f"Initializing memory extraction service (model: {extraction_model})")
    extraction_service = ExtractionService(
        model=extraction_model,
        min_confidence=settings.extraction_min_confidence,
    )

    # Initialize memory storage service
    logger.info("Initializing memory storage service")
    memory_storage_service = MemoryStorageService(neo4j_service=neo4j_service)

    # Initialize conversation tracker for boundary detection
    logger.info(
        f"Initializing conversation tracker (storage: {settings.transcript_storage_dir})"
    )

    # Inject ollama_client if available (for Session 8 embedding generation)
    tracker_ollama_client = None
    if "ollama_client" in locals() and ollama_client is not None:
        tracker_ollama_client = ollama_client
        logger.info("Embedding generation enabled for memory extraction")

    tracker = ConversationTracker(
        storage_dir=settings.transcript_storage_dir,
        idle_threshold_minutes=settings.boundary_idle_threshold_minutes,
        message_drop_threshold=settings.boundary_message_drop_threshold,
        max_tracked_conversations=settings.boundary_max_tracked_conversations,
        extraction_service=extraction_service,
        memory_storage_service=memory_storage_service,
        ollama_client=tracker_ollama_client,
        embedding_version=settings.embedding_model.split(":")[-1] + "-v1",
    )
    set_conversation_tracker(tracker)

    # Initialize backfill worker for existing memories without embeddings (Session 8)
    backfill_task = None
    if tracker_ollama_client:
        try:
            from haia.embedding.backfill_worker import EmbeddingBackfillWorker

            logger.info("Initializing embedding backfill worker")
            backfill_worker = EmbeddingBackfillWorker(
                neo4j_service=neo4j_service,
                ollama_client=tracker_ollama_client,
                memory_storage=memory_storage_service,
                batch_size=25,
                max_workers=2,
                embedding_version=settings.embedding_model.split(":")[-1] + "-v1",
                poll_interval=60.0,  # Check every 60 seconds
            )

            # Launch backfill worker in background (non-blocking)
            backfill_task = asyncio.create_task(backfill_worker.start())
            logger.info("Backfill worker started in background")

        except Exception as e:
            logger.warning(
                f"Failed to initialize backfill worker: {e}. "
                "Backfilling disabled, but embedding generation on new memories will continue."
            )

    logger.info("Server startup complete - ready to accept requests")

    yield  # Application runs here

    # Shutdown
    logger.info("Shutting down HAIA Chat API server...")

    # Stop backfill worker if running
    if backfill_task and not backfill_task.done():
        logger.info("Stopping backfill worker...")
        backfill_task.cancel()
        try:
            await backfill_task
        except asyncio.CancelledError:
            logger.info("Backfill worker stopped")

    await neo4j_service.close()
    logger.info("Neo4j connection closed")
    logger.info("Server shutdown complete")


# Create FastAPI app with lifespan manager
app = FastAPI(
    title="HAIA Chat API",
    description="OpenAI-compatible Chat Completions API for Homelab AI Assistant",
    version="1.0.0",
    lifespan=lifespan,
)


# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, restrict to actual origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
app.include_router(chat.router, tags=["Chat Completions"])
