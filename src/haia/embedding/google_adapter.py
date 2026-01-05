"""Adapter to make GoogleEmbeddingClient compatible with OllamaClient interface."""

import logging
from typing import List

from haia.embedding.google_embeddings import GoogleEmbeddingClient

logger = logging.getLogger(__name__)


class GoogleEmbeddingAdapter:
    """
    Adapter to make GoogleEmbeddingClient compatible with OllamaClient interface.

    This allows dropping in Google embeddings as a replacement for Ollama
    in RetrievalService and other components.
    """

    def __init__(self, api_key: str, model: str = "text-embedding-004"):
        """
        Initialize Google embedding adapter.

        Args:
            api_key: Google API key
            model: Google embedding model (default: text-embedding-004, 768 dims)
        """
        self.client = GoogleEmbeddingClient(
            api_key=api_key,
            model=model,
            timeout=30.0
        )
        self.model = model
        logger.info(f"GoogleEmbeddingAdapter initialized with model: {model}")

    async def embed(self, text: str) -> List[float]:
        """
        Generate embedding for a single text (compatible with OllamaClient).

        Args:
            text: Text to embed

        Returns:
            List of floats representing the embedding vector (768 dimensions)
        """
        try:
            # GoogleEmbeddingClient.aencode() returns numpy array
            embeddings = await self.client.aencode(text)

            if embeddings.size == 0:
                logger.error(f"Empty embedding returned for text: {text[:50]}...")
                return []

            # Convert numpy array to list of floats
            return embeddings[0].tolist()

        except Exception as e:
            logger.error(f"Failed to generate embedding: {e}", exc_info=True)
            return []

    async def health_check(self) -> bool:
        """
        Check if Google Embedding API is accessible.

        Returns:
            True if API is reachable and working, False otherwise
        """
        try:
            # Try to embed a simple test string
            test_embedding = await self.embed("test")

            # Verify we got a valid embedding (768 dimensions for text-embedding-004)
            if test_embedding and len(test_embedding) == 768:
                logger.info("Google Embedding API health check: SUCCESS")
                return True
            else:
                logger.warning(
                    f"Google Embedding API returned unexpected embedding size: "
                    f"{len(test_embedding) if test_embedding else 0}"
                )
                return False

        except Exception as e:
            logger.error(f"Google Embedding API health check FAILED: {e}")
            return False
