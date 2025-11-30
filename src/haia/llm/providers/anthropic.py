"""Anthropic Claude LLM client implementation."""

import logging
import time
from collections.abc import AsyncIterator
from typing import Any

import anthropic

from haia.llm.client import LLMClient
from haia.llm.errors import (
    AuthenticationError,
    InvalidRequestError,
    LLMError,
    RateLimitError,
    ResourceNotFoundError,
    ServiceUnavailableError,
    TimeoutError,
    ValidationError,
)
from haia.llm.models import LLMResponse, LLMResponseChunk, Message, TokenUsage

logger = logging.getLogger(__name__)


class AnthropicClient(LLMClient):
    """Anthropic Claude LLM client implementation."""

    def __init__(self, api_key: str, model: str, timeout: float = 30.0):
        """Initialize Anthropic client.

        Args:
            api_key: Anthropic API key
            model: Model identifier (e.g., "claude-haiku-4-5-20251001")
            timeout: Request timeout in seconds (default: 30.0)
        """
        self.model = model
        self.timeout = timeout
        self.client = anthropic.AsyncAnthropic(api_key=api_key, timeout=timeout)

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
        start_time = time.time()

        try:
            # Separate system messages from conversation messages
            system_message: str | None = None
            conversation_messages: list[dict[str, Any]] = []

            for msg in messages:
                if msg.role == "system":
                    # Anthropic handles system prompts as top-level parameter
                    system_message = msg.content
                else:
                    conversation_messages.append({"role": msg.role, "content": msg.content})

            # Call Anthropic API
            response = await self.client.messages.create(
                model=self.model,
                max_tokens=max_tokens,
                temperature=temperature,
                messages=conversation_messages,
                system=system_message if system_message else anthropic.NOT_GIVEN,
            )

            # Convert to unified response format
            llm_response = self._map_response(response)

            # Log successful request
            latency_ms = (time.time() - start_time) * 1000
            logger.info(
                "Anthropic API call successful",
                extra={
                    "provider": "anthropic",
                    "model": self.model,
                    "latency_ms": latency_ms,
                    "prompt_tokens": llm_response.usage.prompt_tokens,
                    "completion_tokens": llm_response.usage.completion_tokens,
                    "total_tokens": llm_response.usage.total_tokens,
                    "finish_reason": llm_response.finish_reason,
                },
            )

            return llm_response

        except anthropic.APIStatusError as e:
            # Map HTTP status codes to specific errors
            latency_ms = (time.time() - start_time) * 1000
            if e.status_code in (401, 403):
                error = AuthenticationError(
                    "Anthropic authentication failed",
                    provider="anthropic",
                    original_error=e,
                    status_code=e.status_code,
                )
            elif e.status_code == 429:
                error = RateLimitError(
                    "Anthropic rate limit exceeded",
                    provider="anthropic",
                    original_error=e,
                    status_code=e.status_code,
                )
            elif e.status_code == 404:
                error = ResourceNotFoundError(
                    f"Anthropic model not found: {self.model}",
                    provider="anthropic",
                    original_error=e,
                    status_code=e.status_code,
                )
            elif e.status_code == 400:
                error = InvalidRequestError(
                    "Invalid request to Anthropic API",
                    provider="anthropic",
                    original_error=e,
                    status_code=e.status_code,
                )
            elif e.status_code in (500, 502, 503):
                error = ServiceUnavailableError(
                    "Anthropic service unavailable",
                    provider="anthropic",
                    original_error=e,
                    status_code=e.status_code,
                )
            else:
                error = LLMError(
                    f"Anthropic API error: {e}",
                    provider="anthropic",
                    original_error=e,
                    status_code=e.status_code,
                )

            logger.error(
                "Anthropic API call failed",
                extra={
                    "provider": "anthropic",
                    "model": self.model,
                    "latency_ms": latency_ms,
                    "error_type": type(error).__name__,
                    "status_code": e.status_code,
                    "correlation_id": error.correlation_id,
                },
            )
            raise error from e

        except anthropic.APITimeoutError as e:
            latency_ms = (time.time() - start_time) * 1000
            error = TimeoutError(
                f"Anthropic API request timed out after {self.timeout}s",
                provider="anthropic",
                original_error=e,
            )
            logger.error(
                "Anthropic API timeout",
                extra={
                    "provider": "anthropic",
                    "model": self.model,
                    "latency_ms": latency_ms,
                    "timeout_seconds": self.timeout,
                    "correlation_id": error.correlation_id,
                },
            )
            raise error from e

        except ValidationError:
            # Re-raise ValidationError from response mapping
            raise

        except Exception as e:
            # Catch-all for unexpected errors
            latency_ms = (time.time() - start_time) * 1000
            error = LLMError(
                f"Unexpected error calling Anthropic API: {e}",
                provider="anthropic",
                original_error=e,
            )
            logger.error(
                "Anthropic API unexpected error",
                extra={
                    "provider": "anthropic",
                    "model": self.model,
                    "latency_ms": latency_ms,
                    "error_type": type(e).__name__,
                    "correlation_id": error.correlation_id,
                },
            )
            raise error from e

    def _map_response(self, response: anthropic.types.Message) -> LLMResponse:
        """Convert Anthropic response to unified LLMResponse format.

        Args:
            response: Anthropic API response

        Returns:
            Unified LLMResponse

        Raises:
            ValidationError: If response format is invalid
        """
        try:
            # Anthropic returns content as a list of blocks, extract text from first block
            if not response.content or len(response.content) == 0:
                raise ValueError("Empty content in Anthropic response")

            # Get text from first content block
            content_block = response.content[0]
            if not hasattr(content_block, "text"):
                raise ValueError("Content block has no text attribute")

            content = content_block.text

            # Map token usage
            usage = TokenUsage(
                prompt_tokens=response.usage.input_tokens,
                completion_tokens=response.usage.output_tokens,
                total_tokens=response.usage.input_tokens + response.usage.output_tokens,
            )

            # Create unified response
            return LLMResponse(
                content=content,
                model=response.model,
                usage=usage,
                finish_reason=response.stop_reason,
            )

        except Exception as e:
            raise ValidationError(
                f"Failed to parse Anthropic response: {e}",
                provider="anthropic",
                original_error=e,
            ) from e

    async def stream_chat(
        self,
        messages: list[Message],
        temperature: float = 0.7,
        max_tokens: int = 1024,
    ) -> AsyncIterator[LLMResponseChunk]:
        """Send chat messages and receive streaming response (not implemented in MVP).

        Args:
            messages: List of conversation messages
            temperature: Sampling temperature (0.0-1.0)
            max_tokens: Maximum tokens to generate

        Yields:
            Response chunks

        Raises:
            NotImplementedError: Streaming not implemented in MVP
        """
        raise NotImplementedError("Streaming not implemented in MVP")
        # Make the function async generator to satisfy type checker
        yield  # pragma: no cover
