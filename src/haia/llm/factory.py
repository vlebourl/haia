"""Factory function for creating LLM clients."""

from typing import TYPE_CHECKING

from haia.llm.client import LLMClient

if TYPE_CHECKING:
    from pydantic_settings import BaseSettings


def create_client(config: "BaseSettings") -> LLMClient:
    """Create LLM client based on HAIA_MODEL configuration.

    Args:
        config: Application settings containing HAIA_MODEL and provider credentials

    Returns:
        Concrete LLM client instance (AnthropicClient, OllamaClient, etc.)

    Raises:
        ValueError: Invalid HAIA_MODEL format or unsupported provider

    Example:
        >>> from haia.config import settings
        >>> client = create_client(settings)
        >>> # HAIA_MODEL=anthropic:claude-haiku-4-5-20251001
    """
    # Parse provider:model format
    if not hasattr(config, "haia_model"):
        raise ValueError("Configuration missing 'haia_model' attribute")

    haia_model: str = config.haia_model
    parts = haia_model.split(":", 1)
    if len(parts) != 2:
        raise ValueError(f"Invalid HAIA_MODEL format: {haia_model}. Expected 'provider:model'")

    provider, model = parts

    # Validate provider and model are non-empty
    if not provider or not model:
        raise ValueError(
            f"Invalid HAIA_MODEL format: {haia_model}. Provider and model must be non-empty"
        )

    # Get timeout from config (default to 30.0 if not set)
    timeout = getattr(config, "llm_timeout", 30.0)

    # Instantiate appropriate provider
    if provider == "anthropic":
        from haia.llm.providers.anthropic import AnthropicClient

        if not hasattr(config, "anthropic_api_key") or config.anthropic_api_key is None:
            raise ValueError("Anthropic provider requires 'anthropic_api_key' in configuration")

        api_key: str = config.anthropic_api_key
        if not api_key:
            raise ValueError("Anthropic API key is empty")

        return AnthropicClient(api_key=api_key, model=model, timeout=timeout)

    elif provider == "ollama":
        from haia.llm.providers.ollama import OllamaClient

        # Get Ollama base URL from config (default to localhost)
        base_url = getattr(config, "ollama_base_url", None) or "http://localhost:11434"

        # Ollama timeout: if llm_timeout is set to the Anthropic default (30.0),
        # use Ollama's default (120.0) instead. Otherwise respect the custom value.
        config_timeout = getattr(config, "llm_timeout", 30.0)
        ollama_timeout = 120.0 if config_timeout == 30.0 else config_timeout

        return OllamaClient(model=model, base_url=base_url, timeout=ollama_timeout)

    elif provider == "openai":
        # Post-MVP: OpenAIClient implementation
        raise NotImplementedError("OpenAI provider not implemented in MVP")

    elif provider == "gemini":
        # Post-MVP: GeminiClient implementation
        raise NotImplementedError("Gemini provider not implemented in MVP")

    else:
        raise ValueError(f"Unsupported provider: {provider}")
