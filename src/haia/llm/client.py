"""Abstract base class for LLM clients."""

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator

from haia.llm.models import LLMResponse, LLMResponseChunk, Message


class LLMClient(ABC):
    """Abstract base class defining common interface for all LLM providers."""

    @abstractmethod
    async def chat(
        self,
        messages: list[Message],
        temperature: float = 0.7,
        max_tokens: int = 1024,
    ) -> LLMResponse:
        """Send chat messages and receive non-streaming response.

        Args:
            messages: List of conversation messages (system, user, assistant)
            temperature: Sampling temperature for response generation (0.0-1.0)
            max_tokens: Maximum tokens to generate in response

        Returns:
            Unified response containing content, model, and token usage

        Raises:
            AuthenticationError: API authentication failed
            RateLimitError: API rate limit exceeded
            TimeoutError: Request timed out
            ValidationError: Response validation failed
            ServiceUnavailableError: Provider service unavailable
            LLMError: Generic LLM error
        """
        pass

    @abstractmethod
    async def stream_chat(
        self,
        messages: list[Message],
        temperature: float = 0.7,
        max_tokens: int = 1024,
    ) -> AsyncIterator[LLMResponseChunk]:
        """Send chat messages and receive streaming response (yields chunks).

        Args:
            messages: List of conversation messages
            temperature: Sampling temperature (0.0-1.0)
            max_tokens: Maximum tokens to generate

        Yields:
            Response chunks. Final chunk includes finish_reason and usage.

        Raises:
            AuthenticationError: API authentication failed
            RateLimitError: API rate limit exceeded
            TimeoutError: Request timed out
            ServiceUnavailableError: Provider service unavailable
            LLMError: Generic LLM error

        Note:
            MVP implementation may raise NotImplementedError.
            Required for post-MVP streaming feature.
        """
        pass
