"""
Embedding service layer for HAIA Memory Retrieval System.

This module provides semantic search capabilities using Ollama embeddings
and Neo4j vector indexes for memory retrieval.

Components:
- models.py: Pydantic models for embedding workflow
- ollama_client.py: Async HTTP client for Ollama embedding API
- retrieval_service.py: Semantic search and relevance scoring service
"""

__all__ = [
    "EmbeddingRequest",
    "EmbeddingResponse",
    "RetrievalQuery",
    "RetrievalResult",
    "RetrievalResponse",
    "RelevanceScore",
    "BackfillProgress",
    "EmbeddingError",
    "EmbeddingException",
]
