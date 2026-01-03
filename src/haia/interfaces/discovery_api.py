"""
Discovery API endpoints for exploring discovered themes.

Provides REST API for querying theme clusters, viewing theme details,
and manually triggering clustering jobs.

Session 14 (US7): Theme Discovery
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from haia.discovery.models import ClusterStatus, Theme
from haia.discovery.theme_clusterer import ThemeClusterer
from haia.services.neo4j import Neo4jService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/discovery", tags=["discovery"])


# Dependency injection (will be configured in main.py)
async def get_neo4j_service() -> Neo4jService:
    """Dependency: Neo4j service instance."""
    # This will be overridden in main.py with actual service
    raise NotImplementedError("Neo4j service dependency not configured")


async def get_theme_clusterer() -> ThemeClusterer:
    """Dependency: Theme clusterer instance."""
    # This will be overridden in main.py with actual service
    raise NotImplementedError("ThemeClusterer dependency not configured")


@router.get("/themes", response_model=list[Theme])
async def list_themes(
    status: Optional[ClusterStatus] = Query(
        ClusterStatus.ACTIVE,
        description="Filter by theme status (active, stale, archived)"
    ),
    limit: int = Query(50, ge=1, le=200, description="Maximum themes to return"),
    neo4j: Neo4jService = Depends(get_neo4j_service),
) -> list[Theme]:
    """
    List all discovered themes (T127).

    Returns themes sorted by memory_count (most popular first).

    **Query Parameters:**
    - status: Filter by theme status (default: active)
    - limit: Maximum themes to return (default: 50, max: 200)

    **Response:**
    - List of Theme objects with labels, descriptions, and quality metrics
    """
    query = """
    MATCH (t:Theme)
    WHERE t.status = $status
    RETURN t.theme_id AS theme_id,
           t.label AS label,
           t.description AS description,
           t.cluster_id AS cluster_id,
           t.memory_count AS memory_count,
           t.silhouette_score AS silhouette_score,
           t.status AS status,
           t.created_at AS created_at,
           t.updated_at AS updated_at
    ORDER BY t.memory_count DESC
    LIMIT $limit
    """

    themes = []

    try:
        async with neo4j.driver.session() as session:
            result = await session.run(
                query,
                status=status.value if status else ClusterStatus.ACTIVE.value,
                limit=limit,
            )

            records = [record.data() async for record in result]

            for record in records:
                theme = Theme(
                    theme_id=record["theme_id"],
                    label=record["label"],
                    description=record["description"],
                    cluster_id=record["cluster_id"],
                    memory_count=record["memory_count"],
                    silhouette_score=record.get("silhouette_score"),
                    status=ClusterStatus(record["status"]),
                    created_at=record["created_at"].to_native(),
                    updated_at=record["updated_at"].to_native(),
                )
                themes.append(theme)

        logger.info(f"Retrieved {len(themes)} themes (status={status})")
        return themes

    except Exception as e:
        logger.error(f"Failed to list themes: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to retrieve themes: {e}")


@router.get("/themes/{theme_id}", response_model=Theme)
async def get_theme(
    theme_id: str,
    neo4j: Neo4jService = Depends(get_neo4j_service),
) -> Theme:
    """
    Get detailed information about a specific theme (T128).

    **Path Parameters:**
    - theme_id: Unique theme identifier

    **Response:**
    - Theme object with full details

    **Errors:**
    - 404: Theme not found
    """
    query = """
    MATCH (t:Theme {theme_id: $theme_id})
    RETURN t.theme_id AS theme_id,
           t.label AS label,
           t.description AS description,
           t.cluster_id AS cluster_id,
           t.memory_count AS memory_count,
           t.silhouette_score AS silhouette_score,
           t.status AS status,
           t.created_at AS created_at,
           t.updated_at AS updated_at
    """

    try:
        async with neo4j.driver.session() as session:
            result = await session.run(query, theme_id=theme_id)
            record = await result.single()

            if not record:
                raise HTTPException(status_code=404, detail=f"Theme {theme_id} not found")

            theme = Theme(
                theme_id=record["theme_id"],
                label=record["label"],
                description=record["description"],
                cluster_id=record["cluster_id"],
                memory_count=record["memory_count"],
                silhouette_score=record.get("silhouette_score"),
                status=ClusterStatus(record["status"]),
                created_at=record["created_at"].to_native(),
                updated_at=record["updated_at"].to_native(),
            )

            logger.info(f"Retrieved theme: {theme_id}")
            return theme

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get theme {theme_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to retrieve theme: {e}")


@router.get("/themes/{theme_id}/memories")
async def get_theme_memories(
    theme_id: str,
    limit: int = Query(20, ge=1, le=100, description="Maximum memories to return"),
    neo4j: Neo4jService = Depends(get_neo4j_service),
) -> list[dict]:
    """
    Get memories belonging to a specific theme (T129).

    Returns memories sorted by distance_to_centroid (closest first).

    **Path Parameters:**
    - theme_id: Unique theme identifier

    **Query Parameters:**
    - limit: Maximum memories to return (default: 20, max: 100)

    **Response:**
    - List of memory objects with content and cluster metadata

    **Errors:**
    - 404: Theme not found
    """
    # First verify theme exists
    theme_query = """
    MATCH (t:Theme {theme_id: $theme_id})
    RETURN t.theme_id
    """

    async with neo4j.driver.session() as session:
        result = await session.run(theme_query, theme_id=theme_id)
        if not await result.single():
            raise HTTPException(status_code=404, detail=f"Theme {theme_id} not found")

    # Fetch memories in theme
    query = """
    MATCH (m:Memory)-[r:BELONGS_TO_THEME]->(t:Theme {theme_id: $theme_id})
    RETURN m.memory_id AS memory_id,
           m.content AS content,
           m.memory_type AS memory_type,
           m.confidence AS confidence,
           m.created_at AS created_at,
           r.distance_to_centroid AS distance
    ORDER BY r.distance_to_centroid ASC
    LIMIT $limit
    """

    try:
        memories = []

        async with neo4j.driver.session() as session:
            result = await session.run(query, theme_id=theme_id, limit=limit)

            records = [record.data() async for record in result]

            for record in records:
                memories.append({
                    "memory_id": record["memory_id"],
                    "content": record["content"],
                    "memory_type": record["memory_type"],
                    "confidence": record["confidence"],
                    "created_at": record["created_at"].to_native().isoformat(),
                    "distance_to_centroid": record.get("distance"),
                })

        logger.info(f"Retrieved {len(memories)} memories for theme {theme_id}")
        return memories

    except Exception as e:
        logger.error(f"Failed to get memories for theme {theme_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to retrieve memories: {e}")


@router.post("/themes/refresh")
async def refresh_themes(
    clusterer: ThemeClusterer = Depends(get_theme_clusterer),
) -> dict:
    """
    Manually trigger theme discovery clustering (T130).

    Runs DBSCAN clustering on all memories with embeddings and updates
    theme database.

    **Response:**
    - ClusteringReport with execution summary

    **Note:** This is a manual trigger. Automatic clustering runs weekly
    (Sundays 2 AM by default).
    """
    try:
        logger.info("Manual theme clustering triggered via API")
        report = await clusterer.run_clustering()

        return {
            "status": "completed",
            "timestamp": report.timestamp.isoformat(),
            "memories_analyzed": report.memories_analyzed,
            "themes_discovered": report.themes_discovered,
            "outliers_count": report.outliers_count,
            "avg_silhouette_score": report.avg_silhouette_score,
            "execution_time_ms": report.execution_time_ms,
        }

    except Exception as e:
        logger.error(f"Theme clustering failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Clustering failed: {e}")


@router.get("/themes/{theme_id}/stats")
async def get_theme_stats(
    theme_id: str,
    neo4j: Neo4jService = Depends(get_neo4j_service),
) -> dict:
    """
    Get statistical information about a theme (T131).

    Returns:
    - Memory count by type
    - Confidence distribution
    - Temporal distribution

    **Path Parameters:**
    - theme_id: Unique theme identifier

    **Response:**
    - Theme statistics object

    **Errors:**
    - 404: Theme not found
    """
    # Verify theme exists
    theme_query = """
    MATCH (t:Theme {theme_id: $theme_id})
    RETURN t.theme_id
    """

    async with neo4j.driver.session() as session:
        result = await session.run(theme_query, theme_id=theme_id)
        if not await result.single():
            raise HTTPException(status_code=404, detail=f"Theme {theme_id} not found")

    # Get statistics
    stats_query = """
    MATCH (m:Memory)-[:BELONGS_TO_THEME]->(t:Theme {theme_id: $theme_id})
    RETURN
        count(m) AS total_memories,
        collect(DISTINCT m.memory_type) AS memory_types,
        avg(m.confidence) AS avg_confidence,
        min(m.created_at) AS earliest_memory,
        max(m.created_at) AS latest_memory
    """

    type_dist_query = """
    MATCH (m:Memory)-[:BELONGS_TO_THEME]->(t:Theme {theme_id: $theme_id})
    RETURN m.memory_type AS memory_type, count(m) AS count
    ORDER BY count DESC
    """

    try:
        stats = {}

        async with neo4j.driver.session() as session:
            # Overall stats
            result = await session.run(stats_query, theme_id=theme_id)
            record = await result.single()

            if record:
                stats["total_memories"] = record["total_memories"]
                stats["memory_types"] = record["memory_types"]
                stats["avg_confidence"] = record["avg_confidence"]
                stats["earliest_memory"] = record["earliest_memory"].to_native().isoformat()
                stats["latest_memory"] = record["latest_memory"].to_native().isoformat()

            # Type distribution
            result = await session.run(type_dist_query, theme_id=theme_id)
            type_dist = [record.data() async for record in result]
            stats["type_distribution"] = type_dist

        logger.info(f"Retrieved stats for theme {theme_id}")
        return stats

    except Exception as e:
        logger.error(f"Failed to get theme stats: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to retrieve stats: {e}")
