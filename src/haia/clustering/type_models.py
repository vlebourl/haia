"""Pydantic models for memory type clustering."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class SemanticNeighbor(BaseModel):
    """A semantically similar memory type with similarity score."""

    type_name: str = Field(..., description="The similar memory type name")
    similarity: float = Field(
        ..., ge=0.0, le=1.0, description="Cosine similarity score (0.0-1.0)"
    )


class TypeHierarchy(BaseModel):
    """Semantic hierarchy information for a memory type.

    Tracks semantic neighbors and cluster membership for query expansion.
    """

    type_name: str = Field(..., description="The memory type name")
    neighbors: list[SemanticNeighbor] = Field(
        default_factory=list,
        description="Semantically similar types with similarity scores",
    )
    cluster_id: Optional[str] = Field(
        None, description="ID of cluster this type belongs to (if clustered)"
    )


class TypeCluster(BaseModel):
    """A cluster of semantically similar memory types.

    Created by DBSCAN clustering to group related types and prevent
    vocabulary explosion while preserving user's exact terminology.

    Example:
        Types: ["docker_container_tool", "docker_deployment_setup",
                "container_runtime_preference"]
        Label: "Container Technology Tools"
    """

    cluster_id: str = Field(..., description="Unique cluster identifier")
    member_types: list[str] = Field(
        ..., min_length=1, description="Memory types in this cluster"
    )
    label: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Human-readable cluster label (2-4 words, LLM-generated)",
    )
    similarity_threshold: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Minimum cosine similarity for cluster membership",
    )
    created_at: datetime = Field(
        default_factory=datetime.utcnow, description="Cluster creation timestamp"
    )
    member_count: int = Field(..., ge=1, description="Number of types in cluster")

    def model_post_init(self, __context) -> None:
        """Validate member_count matches member_types length."""
        if self.member_count != len(self.member_types):
            self.member_count = len(self.member_types)
