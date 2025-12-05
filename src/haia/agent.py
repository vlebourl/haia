"""PydanticAI agent initialization and configuration."""

import logging

from pydantic_ai import Agent

from haia.config import settings
from haia.profile import load_profile_context

logger = logging.getLogger(__name__)

# Minimal default system prompt (used only if HAIA_SYSTEM_PROMPT not set in .env)
# The comprehensive personality prompt should be configured in your .env file
DEFAULT_SYSTEM_PROMPT = """You are Haia, a homelab infrastructure assistant. You help manage Proxmox clusters, Home Assistant, Docker containers, and related infrastructure. Be helpful, concise, and warn before any destructive operations."""

# Legacy export for backwards compatibility
HOMELAB_ASSISTANT_PROMPT = DEFAULT_SYSTEM_PROMPT


def build_system_prompt() -> str:
    """Build complete system prompt from layers.

    Layers (in order):
    1. Base prompt (from HAIA_SYSTEM_PROMPT env var or default)
    2. Personal homelab profile (from YAML file if exists)

    Returns:
        Complete system prompt
    """
    # Layer 1: Base prompt (configurable via .env)
    base_prompt = settings.haia_system_prompt or DEFAULT_SYSTEM_PROMPT

    # Layer 2: Personal homelab profile context
    profile_context = load_profile_context(settings.haia_profile_path)

    # Combine layers
    if profile_context:
        logger.info("Using custom homelab profile in system prompt")
        return f"{base_prompt}\n\n{profile_context}"
    else:
        logger.debug("No custom profile found, using base prompt only")
        return base_prompt


def create_agent(model_name: str) -> Agent:
    """Create PydanticAI agent with layered system prompt.

    Args:
        model_name: Model identifier (e.g., "anthropic:claude-haiku-4-5-20251001")

    Returns:
        Configured PydanticAI agent

    Note:
        System prompt is built from multiple layers:
        1. Base prompt (from HAIA_SYSTEM_PROMPT or default)
        2. Personal profile (from haia_profile.yaml if exists)

        PydanticAI has native support for Anthropic and Ollama models.
        Pass the model string directly and PydanticAI will handle initialization.
    """
    system_prompt = build_system_prompt()
    return Agent(
        model=model_name,
        system_prompt=system_prompt,
    )
