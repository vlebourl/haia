"""Google Gemini embeddings client for semantic similarity."""

import logging
from typing import Optional

import httpx
import numpy as np

logger = logging.getLogger(__name__)


class GoogleEmbeddingClient:
    """
    Client for Google Gemini embedding API.

    Uses text-embedding-004 model (768 dimensions, state-of-the-art quality).
    Cost: ~$0.0001 per 1K characters (very cheap).
    """

    def __init__(
        self,
        api_key: str,
        model: str = "text-embedding-004",
        timeout: float = 30.0,
    ):
        """
        Initialize Google embedding client.

        Args:
            api_key: Google API key
            model: Embedding model name (default: text-embedding-004)
            timeout: Request timeout in seconds
        """
        self.api_key = api_key
        self.model = model
        self.timeout = timeout
        self.base_url = "https://generativelanguage.googleapis.com/v1beta/models"

        logger.info(f"GoogleEmbeddingClient initialized with model: {model}")

    def encode(self, texts: list[str] | str) -> np.ndarray:
        """
        Generate embeddings for text(s).

        Compatible with sentence-transformers interface for drop-in replacement.

        Args:
            texts: Single text or list of texts to embed

        Returns:
            numpy array of embeddings (n_texts, embedding_dim)
        """
        # Handle single string input
        if isinstance(texts, str):
            texts = [texts]

        if not texts:
            return np.array([])

        try:
            embeddings = []

            # Google API supports batch requests, but we'll do sequential for simplicity
            # and to avoid rate limits
            for text in texts:
                embedding = self._get_embedding(text)
                embeddings.append(embedding)

            result = np.array(embeddings)
            logger.debug(
                f"Generated {len(embeddings)} embeddings with shape {result.shape}"
            )
            return result

        except Exception as e:
            logger.error(f"Failed to generate embeddings: {e}")
            # Return empty array to trigger fallback behavior
            return np.array([])

    def _get_embedding(self, text: str) -> np.ndarray:
        """
        Get embedding for a single text.

        Args:
            text: Text to embed

        Returns:
            numpy array of embedding vector
        """
        url = f"{self.base_url}/{self.model}:embedContent"
        params = {"key": self.api_key}

        payload = {
            "model": f"models/{self.model}",
            "content": {"parts": [{"text": text}]},
        }

        with httpx.Client(timeout=self.timeout) as client:
            response = client.post(url, params=params, json=payload)
            response.raise_for_status()

            data = response.json()
            embedding = data.get("embedding", {}).get("values", [])

            if not embedding:
                raise ValueError(f"No embedding returned for text: {text[:50]}...")

            return np.array(embedding, dtype=np.float32)

    async def aencode(self, texts: list[str] | str) -> np.ndarray:
        """
        Async version of encode (for compatibility).

        Args:
            texts: Single text or list of texts to embed

        Returns:
            numpy array of embeddings
        """
        # Handle single string input
        if isinstance(texts, str):
            texts = [texts]

        if not texts:
            return np.array([])

        try:
            embeddings = []

            async with httpx.AsyncClient(timeout=self.timeout) as client:
                for text in texts:
                    embedding = await self._aget_embedding(client, text)
                    embeddings.append(embedding)

            result = np.array(embeddings)
            logger.debug(
                f"Generated {len(embeddings)} embeddings async with shape {result.shape}"
            )
            return result

        except Exception as e:
            logger.error(f"Failed to generate embeddings (async): {e}")
            return np.array([])

    async def _aget_embedding(self, client: httpx.AsyncClient, text: str) -> np.ndarray:
        """
        Get embedding for a single text (async).

        Args:
            client: httpx async client
            text: Text to embed

        Returns:
            numpy array of embedding vector
        """
        url = f"{self.base_url}/{self.model}:embedContent"
        params = {"key": self.api_key}

        payload = {
            "model": f"models/{self.model}",
            "content": {"parts": [{"text": text}]},
        }

        response = await client.post(url, params=params, json=payload)
        response.raise_for_status()

        data = response.json()
        embedding = data.get("embedding", {}).get("values", [])

        if not embedding:
            raise ValueError(f"No embedding returned for text: {text[:50]}...")

        return np.array(embedding, dtype=np.float32)
