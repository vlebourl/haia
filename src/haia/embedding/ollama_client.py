"""Async HTTP client for Ollama embedding API.

This module provides a type-safe client for generating embeddings via Ollama's
HTTP API with retry logic, error handling, and batch support.
"""

import asyncio
import logging
from typing import Optional

import httpx

from haia.embedding.models import (
    EmbeddingRequest,
    EmbeddingResponse,
    EmbeddingException,
)

logger = logging.getLogger(__name__)


class OllamaClient:
    """Async HTTP client for Ollama embedding generation.

    This client handles:
    - Single and batch embedding generation
    - Automatic retry with exponential backoff
    - Connection pooling and timeout management
    - Error classification and recovery
    """

    def __init__(
        self,
        base_url: str = "http://localhost:11434",
        model: str = "nomic-embed-text",
        timeout: float = 30.0,
        max_retries: int = 3,
    ):
        """Initialize Ollama client.

        Args:
            base_url: Ollama service base URL
            model: Embedding model name
            timeout: Request timeout in seconds
            max_retries: Maximum retry attempts for failed requests
        """
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout
        self.default_max_retries = max_retries
        self._client: Optional[httpx.AsyncClient] = None

        logger.info(f"Initialized OllamaClient: {base_url}, model={model}")

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create async HTTP client with connection pooling."""
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                timeout=httpx.Timeout(self.timeout),
                limits=httpx.Limits(
                    max_connections=10,
                    max_keepalive_connections=5,
                ),
            )
        return self._client

    async def close(self) -> None:
        """Close HTTP client and release connections."""
        if self._client:
            await self._client.aclose()
            self._client = None
            logger.debug("Ollama client closed")

    async def embed(
        self,
        text: str,
        max_retries: Optional[int] = None,
    ) -> list[float]:
        """Generate embedding for single text input.

        Args:
            text: Text to embed
            max_retries: Override default retry count

        Returns:
            768-dimensional embedding vector

        Raises:
            EmbeddingException: If embedding generation fails
        """
        if not text or not text.strip():
            raise ValueError("Text cannot be empty")

        request = EmbeddingRequest(
            model=self.model,
            input=text,
            truncate=True,
            dimensions=768,
        )

        response = await self._request_with_retry(request, max_retries)

        # Extract first embedding from response
        if not response.embeddings or len(response.embeddings) == 0:
            raise EmbeddingException(
                error_type="validation_error",
                error_message="No embeddings in response",
                recoverable=False,
            )

        embedding = response.embeddings[0]

        # Validate dimensions
        if len(embedding) != 768:
            raise EmbeddingException(
                error_type="validation_error",
                error_message=f"Expected 768 dimensions, got {len(embedding)}",
                recoverable=False,
            )

        logger.debug(f"Generated embedding (latency: {response.latency_ms:.1f}ms)")
        return embedding

    async def embed_batch(
        self,
        texts: list[str],
        max_retries: Optional[int] = None,
    ) -> list[list[float]]:
        """Generate embeddings for batch of texts.

        Args:
            texts: List of texts to embed (max 10 per batch)
            max_retries: Override default retry count

        Returns:
            List of 768-dimensional embedding vectors

        Raises:
            EmbeddingException: If embedding generation fails
        """
        if not texts or len(texts) == 0:
            raise ValueError("Text batch cannot be empty")

        if len(texts) > 10:
            raise ValueError("Batch size cannot exceed 10 texts")

        request = EmbeddingRequest(
            model=self.model,
            input=texts,
            truncate=True,
            dimensions=768,
        )

        response = await self._request_with_retry(request, max_retries)

        # Validate embeddings
        if len(response.embeddings) != len(texts):
            raise EmbeddingException(
                error_type="validation_error",
                error_message=f"Expected {len(texts)} embeddings, got {len(response.embeddings)}",
                recoverable=False,
            )

        # Validate dimensions for all embeddings
        for i, embedding in enumerate(response.embeddings):
            if len(embedding) != 768:
                raise EmbeddingException(
                    error_type="validation_error",
                    error_message=f"Embedding {i}: expected 768 dimensions, got {len(embedding)}",
                    recoverable=False,
                )

        logger.debug(
            f"Generated {len(texts)} embeddings (latency: {response.latency_ms:.1f}ms)"
        )
        return response.embeddings

    async def _request_with_retry(
        self,
        request: EmbeddingRequest,
        max_retries: Optional[int] = None,
    ) -> EmbeddingResponse:
        """Execute embedding request with retry logic.

        Args:
            request: Embedding request
            max_retries: Override default retry count

        Returns:
            Embedding response

        Raises:
            EmbeddingError: If all retries fail
        """
        max_attempts = max_retries if max_retries is not None else self.default_max_retries
        retry_delay = 1.0  # Initial delay in seconds

        last_error: Optional[Exception] = None

        for attempt in range(1, max_attempts + 1):
            try:
                return await self._execute_request(request)
            except EmbeddingException as e:
                last_error = e

                # Don't retry non-recoverable errors
                if not e.recoverable:
                    logger.error(f"Non-recoverable error: {e.error_message}")
                    raise

                if attempt < max_attempts:
                    logger.warning(
                        f"Attempt {attempt}/{max_attempts} failed: {e.error_message}. "
                        f"Retrying in {retry_delay:.1f}s..."
                    )
                    await asyncio.sleep(retry_delay)
                    retry_delay *= 2  # Exponential backoff
                    retry_delay = min(retry_delay, 30.0)  # Cap at 30s
            except Exception as e:
                last_error = e
                logger.error(f"Unexpected error on attempt {attempt}: {e}")
                if attempt >= max_attempts:
                    raise EmbeddingException(
                        error_type="unknown",
                        error_message=str(e),
                        recoverable=False,
                    ) from e

        # All retries exhausted
        if last_error:
            if isinstance(last_error, EmbeddingException):
                raise last_error
            else:
                raise EmbeddingException(
                    error_type="unknown",
                    error_message=str(last_error),
                    recoverable=False,
                ) from last_error
        else:
            raise EmbeddingException(
                error_type="unknown",
                error_message="All retries failed",
                recoverable=False,
            )

    async def _execute_request(
        self,
        request: EmbeddingRequest,
    ) -> EmbeddingResponse:
        """Execute single embedding request.

        Args:
            request: Embedding request

        Returns:
            Embedding response

        Raises:
            EmbeddingError: If request fails
        """
        client = await self._get_client()

        try:
            response = await client.post(
                "/api/embed",
                json=request.model_dump(),
            )
            response.raise_for_status()
            data = response.json()
            return EmbeddingResponse(**data)

        except httpx.ConnectError as e:
            raise EmbeddingException(
                error_type="connection_error",
                error_message=f"Connection refused to {self.base_url}: {e}",
                recoverable=True,
            ) from e

        except httpx.TimeoutException as e:
            raise EmbeddingException(
                error_type="timeout",
                error_message=f"Request timeout after {self.timeout}s: {e}",
                recoverable=True,
            ) from e

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                raise EmbeddingException(
                    error_type="model_error",
                    error_message=f"Model '{self.model}' not found",
                    recoverable=False,
                ) from e
            elif 500 <= e.response.status_code < 600:
                raise EmbeddingException(
                    error_type="model_error",
                    error_message=f"Server error: {e.response.status_code}",
                    recoverable=True,
                ) from e
            else:
                raise EmbeddingException(
                    error_type="unknown",
                    error_message=f"HTTP {e.response.status_code}: {e}",
                    recoverable=False,
                ) from e

        except Exception as e:
            raise EmbeddingException(
                error_type="unknown",
                error_message=f"Unexpected error: {e}",
                recoverable=False,
            ) from e

    async def health_check(self) -> bool:
        """Check if Ollama service is available.

        Returns:
            True if service is healthy, False otherwise
        """
        try:
            client = await self._get_client()
            response = await client.get("/api/tags")
            response.raise_for_status()
            logger.debug("Ollama health check: OK")
            return True
        except Exception as e:
            logger.warning(f"Ollama health check failed: {e}")
            return False
