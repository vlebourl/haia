"""LLM Factory Service for LiteLLM integration.

Session 16: LiteLLM Proxy Integration
Creates PydanticAI agents with LiteLLM routing based on feature context.
"""

import logging
from typing import Any

from pydantic_ai import Agent
from pydantic_ai.models.openai import OpenAIChatModel

try:
    from pydantic_ai.providers.litellm import LiteLLMProvider
except ImportError:
    # Fallback if LiteLLMProvider not available in this version
    LiteLLMProvider = None  # type: ignore

from haia.config import settings

logger = logging.getLogger(__name__)


class LLMFactory:
    """Factory for creating LiteLLM-backed PydanticAI agents.

    Provides centralized agent creation with feature-specific routing.
    All fallback logic is handled transparently by LiteLLM proxy.
    """

    # Feature to model name mapping
    # With unified model names in litellm_config.yaml, these match 1:1
    FEATURE_MODEL_MAP = {
        "chat": "chat",
        "premium": "premium",
        "extraction": "extraction",
        "relationships": "relationships",
        "themes": "themes",
    }

    def __init__(self):
        """Initialize factory."""
        if not settings.litellm_proxy_url:
            logger.warning(
                "LiteLLM proxy URL not configured - factory will use direct models"
            )
        else:
            logger.info(f"LiteLLM factory initialized: {settings.litellm_proxy_url}")

    def create_agent(
        self,
        feature: str,
        system_prompt: str | None = None,
        **agent_kwargs: Any,
    ) -> Agent:
        """Create PydanticAI agent with LiteLLM routing for specified feature.

        Args:
            feature: HAIA feature name ("chat", "extraction", "relationships", "themes", "premium")
            system_prompt: Optional system prompt override
            **agent_kwargs: Additional arguments passed to Agent constructor

        Returns:
            Configured Agent instance with LiteLLM provider

        Raises:
            ValueError: If feature is not recognized

        Note:
            All fallback logic is handled by LiteLLM proxy. When a model fails,
            LiteLLM automatically retries with the next priority model in the
            fallback chain configured in litellm_config.yaml.
        """
        # Get model name for this feature
        model_name = self.FEATURE_MODEL_MAP.get(feature)
        if not model_name:
            raise ValueError(
                f"Unknown feature '{feature}'. Valid features: {list(self.FEATURE_MODEL_MAP.keys())}"
            )

        logger.info(
            f"Creating agent for feature='{feature}' using model='{model_name}' "
            f"(fallback handled by LiteLLM)"
        )

        # Create LiteLLM provider if configured
        if settings.litellm_proxy_url and LiteLLMProvider:
            try:
                provider = LiteLLMProvider(
                    api_base=settings.litellm_proxy_url,
                    api_key=settings.litellm_master_key or "",
                )

                model = OpenAIChatModel(
                    model_name,
                    provider=provider,
                )

                logger.debug(
                    f"Using LiteLLM provider: {settings.litellm_proxy_url} "
                    f"for model '{model_name}'"
                )
            except Exception as e:
                logger.error(f"Failed to create LiteLLM provider: {e}", exc_info=True)
                raise
        else:
            # Fallback to direct model if LiteLLM not configured
            logger.warning(
                f"LiteLLM not configured, using direct model for feature '{feature}'"
            )
            model = OpenAIChatModel(model_name)

        # Create agent with model
        agent = Agent(
            model=model,
            system_prompt=system_prompt,
            **agent_kwargs,
        )

        logger.info(f"Agent created: feature={feature}, model={model_name}")

        return agent


# Global factory instance
llm_factory = LLMFactory()
