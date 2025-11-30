"""FastAPI application setup with startup/shutdown handlers."""

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from haia.agent import create_agent
from haia.api.deps import set_agent
from haia.api.routes import chat
from haia.config import settings
from haia.db.session import close_db, init_db
from haia.llm.factory import create_client

# Configure logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - [%(correlation_id)s] - %(message)s",
    level=logging.INFO,
)

logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title="HAIA Chat API",
    description="OpenAI-compatible Chat Completions API for Homelab AI Assistant",
    version="1.0.0",
)


@app.on_event("startup")
async def startup_event():
    """Initialize database and agent on server startup."""
    logger.info("Starting HAIA Chat API server...")

    # Initialize database schema
    logger.info("Initializing database...")
    await init_db()

    # Create LLM client from config
    logger.info(f"Initializing LLM client with model: {settings.haia_model}")
    llm_client = create_client(settings)

    # Create and set agent
    logger.info("Creating PydanticAI agent...")
    agent = create_agent(llm_client)
    set_agent(agent)

    logger.info("Server startup complete - ready to accept requests")


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup resources on server shutdown."""
    logger.info("Shutting down HAIA Chat API server...")
    await close_db()
    logger.info("Server shutdown complete")


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
