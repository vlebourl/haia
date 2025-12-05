"""FastAPI application setup with startup/shutdown handlers."""

import logging
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from haia.agent import create_agent
from haia.api.deps import set_agent
from haia.api.routes import chat
from haia.config import settings

# Configure logging - simpler format without correlation_id for startup logs
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
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
    """Initialize agent on server startup."""
    logger.info("Starting HAIA Chat API server...")

    # Set API keys in environment for PydanticAI provider initialization
    if settings.anthropic_api_key:
        os.environ["ANTHROPIC_API_KEY"] = settings.anthropic_api_key

    # Create PydanticAI agent with model from config
    logger.info(f"Creating PydanticAI agent with model: {settings.haia_model}")
    agent = create_agent(settings.haia_model)
    set_agent(agent)

    logger.info("Server startup complete - ready to accept requests")


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup resources on server shutdown."""
    logger.info("Shutting down HAIA Chat API server...")
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
