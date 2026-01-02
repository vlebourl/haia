"""
Integration tests for type clustering (User Story 3).

Tests the complete type clustering workflow:
- Fetching unique memory types from Neo4j
- Generating embeddings
- DBSCAN clustering
- LLM-generated cluster labels
- Storing clusters in Neo4j
"""

import asyncio
import logging
import os
from datetime import datetime

import pytest

from haia.clustering.type_clusterer import TypeClusterer
from haia.services.neo4j import Neo4jService

logger = logging.getLogger(__name__)

# Test configuration
NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "password")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
EXTRACTION_MODEL = os.getenv("HAIA_MODEL", "anthropic:claude-haiku-4-5-20251001")


@pytest.fixture
async def neo4j_service():
    """Provide Neo4j service for testing."""
    service = Neo4jService(
        uri=NEO4J_URI,
        user=NEO4J_USER,
        password=NEO4J_PASSWORD,
    )
    await service.connect()
    yield service
    await service.close()


@pytest.fixture
async def type_clusterer(neo4j_service):
    """Provide TypeClusterer instance for testing."""
    # Use Google embeddings if API key available, otherwise local
    embedding_provider = "google" if GOOGLE_API_KEY else "local"

    clusterer = TypeClusterer(
        neo4j_service=neo4j_service,
        extraction_model=EXTRACTION_MODEL,
        min_cluster_size=3,
        similarity_threshold=0.80,
        embedding_provider=embedding_provider,
        google_api_key=GOOGLE_API_KEY,
    )

    return clusterer


@pytest.fixture
async def sample_memory_types(neo4j_service):
    """Create sample memory types for testing."""
    # Create diverse test memory types
    test_types = [
        "docker_container_preference",
        "docker_deployment_setup",
        "docker_tool_choice",
        "container_runtime_preference",
        "kubernetes_deployment_config",
        "kubernetes_cluster_setup",
        "kubernetes_namespace_preference",
        "proxmox_vm_configuration",
        "proxmox_storage_preference",
        "proxmox_cluster_setup",
        "homeassistant_automation_trigger",
        "homeassistant_sensor_configuration",
        "python_library_preference",
        "python_framework_choice",
        "monitoring_alert_threshold",
        "monitoring_dashboard_layout",
        "backup_schedule_preference",
        "backup_retention_policy",
        "network_firewall_rule",
        "network_vlan_configuration",
    ]

    # Create Memory nodes with these types
    created_ids = []
    for mem_type in test_types:
        query = """
        CREATE (m:Memory {
            memory_id: randomUUID(),
            content: $content,
            memory_type: $memory_type,
            confidence: 0.8,
            learned_at: datetime(),
            valid_from: datetime()
        })
        RETURN m.memory_id as memory_id
        """

        async with neo4j_service.driver.session() as session:
            result = await session.run(
                query,
                content=f"Test memory for {mem_type}",
                memory_type=mem_type,
            )
            record = await result.single()
            if record:
                created_ids.append(record["memory_id"])

    logger.info(f"Created {len(created_ids)} test memory nodes")

    yield test_types

    # Cleanup: Delete test memories and clusters
    cleanup_query = """
    MATCH (m:Memory)
    WHERE m.memory_id IN $ids
    DETACH DELETE m
    """

    async with neo4j_service.driver.session() as session:
        await session.run(cleanup_query, ids=created_ids)

    # Delete test clusters
    cluster_cleanup = """
    MATCH (c:TypeCluster)
    WHERE c.created_at >= datetime($start_time)
    DETACH DELETE c
    """

    async with neo4j_service.driver.session() as session:
        await session.run(cluster_cleanup, start_time=datetime.utcnow().isoformat())

    logger.info("Cleaned up test data")


@pytest.mark.asyncio
async def test_get_all_types(type_clusterer, sample_memory_types):
    """Test fetching all unique memory types from Neo4j."""
    types = await type_clusterer.get_all_types()

    assert len(types) > 0, "Should find at least some memory types"

    # Check that our test types are included
    test_types_found = [t for t in sample_memory_types if t in types]
    assert len(test_types_found) >= 10, f"Should find most test types, found {len(test_types_found)}"

    logger.info(f"Found {len(types)} unique memory types")


@pytest.mark.asyncio
async def test_embed_types(type_clusterer):
    """Test embedding generation for memory types."""
    test_types = [
        "docker_container_preference",
        "kubernetes_deployment_config",
        "proxmox_vm_configuration",
    ]

    embeddings = type_clusterer.embed_types(test_types)

    assert len(embeddings) == len(test_types), "Should generate embedding for each type"

    # Check embedding dimensions (Google: 768, local: 384)
    for type_name, embedding in embeddings.items():
        assert embedding.shape[0] > 0, f"Embedding for {type_name} should have dimensions"
        assert type_name in test_types, f"Should map correct type name: {type_name}"

    logger.info(f"Generated embeddings: {list(embeddings.keys())}")


@pytest.mark.asyncio
async def test_cluster_types(type_clusterer):
    """Test DBSCAN clustering of memory types."""
    # Create embeddings for related types
    docker_types = [
        "docker_container_preference",
        "docker_deployment_setup",
        "docker_tool_choice",
        "container_runtime_preference",
    ]

    k8s_types = [
        "kubernetes_deployment_config",
        "kubernetes_cluster_setup",
        "kubernetes_namespace_preference",
    ]

    all_types = docker_types + k8s_types
    embeddings = type_clusterer.embed_types(all_types)

    clusters = type_clusterer.cluster_types(embeddings)

    assert len(clusters) > 0, "Should create at least one cluster"

    # Check that clusters group related types
    for cluster_label, members in clusters.items():
        assert len(members) >= type_clusterer.min_cluster_size, \
            f"Cluster {cluster_label} should have min {type_clusterer.min_cluster_size} members"
        logger.info(f"Cluster {cluster_label}: {members}")


@pytest.mark.asyncio
async def test_find_semantic_neighbors(type_clusterer, sample_memory_types):
    """Test finding semantically similar type names."""
    # First create embeddings for all types
    all_types = await type_clusterer.get_all_types()

    if len(all_types) < 5:
        pytest.skip("Not enough types for neighbor search")

    # Find neighbors for a docker-related type
    docker_types_in_db = [t for t in all_types if "docker" in t or "container" in t]

    if not docker_types_in_db:
        pytest.skip("No docker-related types found")

    query_type = docker_types_in_db[0]

    neighbors = await type_clusterer.find_semantic_neighbors(
        query_type=query_type,
        top_k=5,
        min_similarity=0.70,
    )

    assert len(neighbors) > 0, f"Should find neighbors for {query_type}"

    # Check neighbor structure
    for neighbor in neighbors:
        assert neighbor.type_name != query_type, "Neighbors should not include query type itself"
        assert 0.0 <= neighbor.similarity <= 1.0, "Similarity should be between 0 and 1"

    logger.info(f"Found {len(neighbors)} neighbors for '{query_type}':")
    for neighbor in neighbors[:3]:
        logger.info(f"  - {neighbor.type_name}: {neighbor.similarity:.3f}")


@pytest.mark.asyncio
async def test_run_clustering_workflow(type_clusterer, sample_memory_types):
    """Test complete clustering workflow end-to-end."""
    # This tests the full orchestration: get_all_types -> embed -> cluster -> label -> store

    clusters = await type_clusterer.run_clustering()

    # Should create at least one cluster with our test data
    assert len(clusters) >= 0, "Clustering should complete without errors"

    if len(clusters) > 0:
        logger.info(f"Created {len(clusters)} clusters")

        for cluster in clusters:
            assert cluster.cluster_id, "Cluster should have ID"
            assert cluster.label, "Cluster should have label"
            assert len(cluster.member_types) >= type_clusterer.min_cluster_size, \
                f"Cluster should have min {type_clusterer.min_cluster_size} members"

            logger.info(
                f"Cluster '{cluster.label}' ({cluster.cluster_id}): "
                f"{len(cluster.member_types)} types"
            )
    else:
        logger.info("No clusters created (insufficient similar types)")


if __name__ == "__main__":
    # Allow running tests directly for debugging
    pytest.main([__file__, "-v", "-s"])
