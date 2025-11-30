"""Ollama LLM client implementation."""

import logging
import time
from collections.abc import AsyncIterator
from typing import Any

import httpx

from haia.llm.client import LLMClient
from haia.llm.errors import (
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


class OllamaClient(LLMClient):
    """Ollama LLM client implementation."""

    def __init__(
        self, model: str, base_url: str = "http://localhost:11434", timeout: float = 120.0
    ):
        """Initialize Ollama client.

        Args:
            model: Model identifier (e.g., "qwen2.5-coder:7b", "llama3.1:8b")
            base_url: Ollama API base URL (default: "http://localhost:11434")
            timeout: Request timeout in seconds (default: 120.0 for local inference)
        """
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.client = httpx.AsyncClient(timeout=timeout)

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
                (Ollama doesn't use auth, but included for consistency)
            RateLimitError: API rate limit exceeded
            TimeoutError: Request timed out
            ValidationError: Response validation failed
            ServiceUnavailableError: Ollama service unavailable
            ResourceNotFoundError: Model not found
            LLMError: Generic LLM error
        """
        start_time = time.time()

        try:
            # Convert messages to Ollama format (includes system messages as role="system")
            ollama_messages: list[dict[str, str]] = []
            for msg in messages:
                ollama_messages.append({"role": msg.role, "content": msg.content})

            # Prepare request payload
            payload = {
                "model": self.model,
                "messages": ollama_messages,
                "stream": False,
                "options": {
                    "temperature": temperature,
                    "num_predict": max_tokens,
                },
            }

            # Call Ollama API
            response = await self.client.post(
                f"{self.base_url}/api/chat",
                json=payload,
            )

            # Handle HTTP errors
            if response.status_code != 200:
                self._handle_http_error(response, time.time() - start_time)

            # Parse response
            response_data = response.json()
            llm_response = self._map_response(response_data)

            # Log successful request
            latency_ms = (time.time() - start_time) * 1000
            logger.info(
                "Ollama API call successful",
                extra={
                    "provider": "ollama",
                    "model": self.model,
                    "latency_ms": latency_ms,
                    "prompt_tokens": llm_response.usage.prompt_tokens,
                    "completion_tokens": llm_response.usage.completion_tokens,
                    "total_tokens": llm_response.usage.total_tokens,
                    "finish_reason": llm_response.finish_reason,
                },
            )

            return llm_response

        except httpx.TimeoutException as e:
            latency_ms = (time.time() - start_time) * 1000
            error = TimeoutError(
                f"Ollama API request timed out after {self.timeout}s",
                provider="ollama",
                original_error=e,
            )
            logger.error(
                "Ollama API timeout",
                extra={
                    "provider": "ollama",
                    "model": self.model,
                    "latency_ms": latency_ms,
                    "timeout_seconds": self.timeout,
                    "correlation_id": error.correlation_id,
                },
            )
            raise error from e

        except httpx.ConnectError as e:
            latency_ms = (time.time() - start_time) * 1000
            error = ServiceUnavailableError(
                f"Cannot connect to Ollama at {self.base_url}",
                provider="ollama",
                original_error=e,
            )
            logger.error(
                "Ollama connection failed",
                extra={
                    "provider": "ollama",
                    "base_url": self.base_url,
                    "latency_ms": latency_ms,
                    "correlation_id": error.correlation_id,
                },
            )
            raise error from e

        except (
            ValidationError,
            ResourceNotFoundError,
            InvalidRequestError,
            ServiceUnavailableError,
        ):
            # Re-raise specific LLM errors from response validation or HTTP error handling
            raise

        except Exception as e:
            # Catch-all for unexpected errors
            latency_ms = (time.time() - start_time) * 1000
            error = LLMError(
                f"Unexpected error calling Ollama API: {e}",
                provider="ollama",
                original_error=e,
            )
            logger.error(
                "Ollama API unexpected error",
                extra={
                    "provider": "ollama",
                    "model": self.model,
                    "latency_ms": latency_ms,
                    "error_type": type(e).__name__,
                    "correlation_id": error.correlation_id,
                },
            )
            raise error from e

    def _handle_http_error(self, response: httpx.Response, elapsed_time: float) -> None:
        """Handle HTTP error responses from Ollama.

        Args:
            response: HTTP response object
            elapsed_time: Request elapsed time in seconds

        Raises:
            Appropriate LLM error based on status code
        """
        latency_ms = elapsed_time * 1000
        status_code = response.status_code

        try:
            error_data = response.json()
            error_message = error_data.get("error", response.text)
        except Exception:
            error_message = response.text

        # Map HTTP status codes to specific errors
        if status_code == 404:
            error = ResourceNotFoundError(
                f"Ollama model not found: {self.model}",
                provider="ollama",
                status_code=status_code,
            )
        elif status_code == 400:
            error = InvalidRequestError(
                f"Invalid request to Ollama API: {error_message}",
                provider="ollama",
                status_code=status_code,
            )
        elif status_code == 429:
            error = RateLimitError(
                "Ollama rate limit exceeded",
                provider="ollama",
                status_code=status_code,
            )
        elif status_code in (500, 502, 503):
            error = ServiceUnavailableError(
                f"Ollama service unavailable: {error_message}",
                provider="ollama",
                status_code=status_code,
            )
        else:
            error = LLMError(
                f"Ollama API error (HTTP {status_code}): {error_message}",
                provider="ollama",
                status_code=status_code,
            )

        logger.error(
            "Ollama API call failed",
            extra={
                "provider": "ollama",
                "model": self.model,
                "latency_ms": latency_ms,
                "error_type": type(error).__name__,
                "status_code": status_code,
                "correlation_id": error.correlation_id,
            },
        )
        raise error

    def _map_response(self, response_data: dict[str, Any]) -> LLMResponse:
        """Convert Ollama response to unified LLMResponse format.

        Args:
            response_data: Ollama API JSON response

        Returns:
            Unified LLMResponse

        Raises:
            ValidationError: If response format is invalid
        """
        try:
            # Extract message content
            message = response_data.get("message", {})
            content = message.get("content", "")

            if not content:
                raise ValueError("Empty content in Ollama response")

            # Map token usage (Ollama uses different field names)
            # prompt_eval_count = prompt tokens, eval_count = completion tokens
            prompt_tokens = response_data.get("prompt_eval_count", 0)
            completion_tokens = response_data.get("eval_count", 0)

            usage = TokenUsage(
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=prompt_tokens + completion_tokens,
            )

            # Map finish reason (Ollama uses "done_reason" or "done" field)
            finish_reason = response_data.get("done_reason")
            if not finish_reason:
                finish_reason = "stop" if response_data.get("done", False) else None

            # Create unified response
            return LLMResponse(
                content=content,
                model=response_data.get("model", self.model),
                usage=usage,
                finish_reason=finish_reason,
            )

        except Exception as e:
            raise ValidationError(
                f"Failed to parse Ollama response: {e}",
                provider="ollama",
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

    async def __aenter__(self):
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit - close HTTP client."""
        await self.client.aclose()
