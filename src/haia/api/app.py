"""FastAPI application setup with lifespan management."""

import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from haia.agent import create_agent
from haia.api.deps import set_agent, set_conversation_tracker, set_neo4j_service
from haia.api.routes import chat
from haia.config import settings
from haia.memory.tracker import ConversationTracker
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

    # Initialize conversation tracker for boundary detection
    logger.info(
        f"Initializing conversation tracker (storage: {settings.transcript_storage_dir})"
    )
    tracker = ConversationTracker(
        storage_dir=settings.transcript_storage_dir,
        idle_threshold_minutes=settings.boundary_idle_threshold_minutes,
        message_drop_threshold=settings.boundary_message_drop_threshold,
        max_tracked_conversations=settings.boundary_max_tracked_conversations,
    )
    set_conversation_tracker(tracker)

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

    logger.info("Server startup complete - ready to accept requests")

    yield  # Application runs here

    # Shutdown
    logger.info("Shutting down HAIA Chat API server...")
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
