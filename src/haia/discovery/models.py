"""
Pydantic models for theme discovery and memory clustering.

Defines data structures for DBSCAN clustering, theme labels,
and discovery reports.

Session 14 (US7): Theme Discovery
"""

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, ConfigDict


class ClusterStatus(str, Enum):
    """Status of a discovered theme cluster (T120)."""

    ACTIVE = "active"  # Currently valid cluster
    STALE = "stale"  # Cluster needs re-clustering
    ARCHIVED = "archived"  # Historical cluster, no longer active


class Theme(BaseModel):
    """
    Discovered theme cluster with LLM-generated label (T120).

    Represents a group of semantically similar memories clustered by DBSCAN.
    """

    model_config = ConfigDict(json_schema_extra={
        "example": {
            "theme_id": "theme_abc123",
            "label": "Docker container management preferences",
            "description": "User preferences for Docker container orchestration, networking, and deployment strategies",
            "cluster_id": 2,
            "memory_count": 12,
            "silhouette_score": 0.68,
            "status": "active",
            "created_at": "2026-01-03T02:00:00Z",
            "updated_at": "2026-01-03T02:00:00Z",
        }
    })

    theme_id: str = Field(
        ...,
        description="Unique theme identifier"
    )
    label: str = Field(
        ...,
        min_length=3,
        max_length=80,
        description="LLM-generated theme label (3-8 words, human-readable)"
    )
    description: str = Field(
        ...,
        max_length=500,
        description="Detailed description of theme content and patterns"
    )
    cluster_id: int = Field(
        ...,
        ge=-1,
        description="DBSCAN cluster ID (-1 = outlier/noise)"
    )
    memory_count: int = Field(
        ...,
        ge=0,
        description="Number of memories in this theme cluster"
    )
    silhouette_score: Optional[float] = Field(
        None,
        ge=-1.0,
        le=1.0,
        description="Cluster quality score: -1 (poor) to 1 (excellent), None for outliers"
    )
    status: ClusterStatus = Field(
        default=ClusterStatus.ACTIVE,
        description="Current status of theme cluster"
    )
    created_at: datetime = Field(
        ...,
        description="When theme was first discovered"
    )
    updated_at: datetime = Field(
        ...,
        description="When theme was last updated (re-clustering)"
    )


class ClusteringConfig(BaseModel):
    """
    Configuration for DBSCAN clustering algorithm (T121).

    Controls clustering behavior and quality thresholds.
    """

    model_config = ConfigDict(json_schema_extra={
        "example": {
            "eps": 0.3,
            "min_samples": 3,
            "min_cluster_size": 3,
            "min_silhouette_score": 0.5,
            "metric": "cosine",
        }
    })

    eps: float = Field(
        default=0.3,
        gt=0.0,
        le=1.0,
        description="DBSCAN epsilon: maximum distance for cluster membership (cosine distance)"
    )
    min_samples: int = Field(
        default=3,
        ge=2,
        description="DBSCAN min_samples: minimum memories to form a dense region"
    )
    min_cluster_size: int = Field(
        default=3,
        ge=2,
        description="Minimum memories required to create a theme (post-clustering filter)"
    )
    min_silhouette_score: float = Field(
        default=0.5,
        ge=-1.0,
        le=1.0,
        description="Minimum silhouette score for cluster quality validation"
    )
    metric: str = Field(
        default="cosine",
        description="Distance metric for DBSCAN (cosine, euclidean, manhattan)"
    )


class ClusteringReport(BaseModel):
    """
    Summary report of theme discovery clustering execution (T122).

    Tracks clustering results, quality metrics, and execution stats.
    """

    model_config = ConfigDict(json_schema_extra={
        "example": {
            "timestamp": "2026-01-05T02:00:00Z",
            "memories_analyzed": 150,
            "themes_discovered": 8,
            "outliers_count": 12,
            "avg_silhouette_score": 0.64,
            "min_silhouette_score": 0.52,
            "max_silhouette_score": 0.78,
            "execution_time_ms": 2450.5,
        }
    })

    timestamp: datetime = Field(
        ...,
        description="When clustering job ran"
    )
    memories_analyzed: int = Field(
        ...,
        ge=0,
        description="Total memories analyzed during clustering"
    )
    themes_discovered: int = Field(
        ...,
        ge=0,
        description="Number of valid theme clusters discovered"
    )
    outliers_count: int = Field(
        ...,
        ge=0,
        description="Number of memories that didn't fit any cluster (noise)"
    )
    avg_silhouette_score: Optional[float] = Field(
        None,
        ge=-1.0,
        le=1.0,
        description="Average silhouette score across all clusters"
    )
    min_silhouette_score: Optional[float] = Field(
        None,
        ge=-1.0,
        le=1.0,
        description="Minimum silhouette score among clusters"
    )
    max_silhouette_score: Optional[float] = Field(
        None,
        ge=-1.0,
        le=1.0,
        description="Maximum silhouette score among clusters"
    )
    execution_time_ms: float = Field(
        ...,
        ge=0.0,
        description="Total execution time in milliseconds"
    )
    themes: list[Theme] = Field(
        default_factory=list,
        description="Detailed list of discovered themes"
    )

    def summary(self) -> str:
        """Generate human-readable summary of clustering run."""
        avg_score = f"{self.avg_silhouette_score:.2f}" if self.avg_silhouette_score else "N/A"
        return (
            f"Theme Discovery Report ({self.timestamp.isoformat()}):\n"
            f"  Analyzed:   {self.memories_analyzed} memories\n"
            f"  Discovered: {self.themes_discovered} themes\n"
            f"  Outliers:   {self.outliers_count} ({self.outliers_count/max(1, self.memories_analyzed)*100:.1f}%)\n"
            f"  Quality:    {avg_score} avg silhouette score\n"
            f"  Execution:  {self.execution_time_ms:.0f}ms"
        )


class MemoryClusterAssignment(BaseModel):
    """
    Assignment of a memory to a discovered theme (T123).

    Stored in Neo4j to track which memories belong to which themes.
    """

    model_config = ConfigDict(json_schema_extra={
        "example": {
            "memory_id": "mem_xyz789",
            "theme_id": "theme_abc123",
            "cluster_id": 2,
            "distance_to_centroid": 0.15,
            "assigned_at": "2026-01-05T02:00:00Z",
        }
    })

    memory_id: str = Field(
        ...,
        description="Memory unique identifier"
    )
    theme_id: str = Field(
        ...,
        description="Theme cluster identifier"
    )
    cluster_id: int = Field(
        ...,
        ge=-1,
        description="DBSCAN cluster ID (-1 = outlier)"
    )
    distance_to_centroid: Optional[float] = Field(
        None,
        ge=0.0,
        description="Distance from memory to cluster centroid (cosine distance)"
    )
    assigned_at: datetime = Field(
        ...,
        description="When memory was assigned to theme"
    )
