"""Unit tests for TypeClusterer service."""

import numpy as np
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from haia.clustering.type_clusterer import TypeClusterer
from haia.clustering.type_models import TypeCluster, SemanticNeighbor


@pytest.fixture
def mock_neo4j_service():
    """Mock Neo4jService for testing."""
    service = MagicMock()
    service.driver = MagicMock()
    return service


@pytest.fixture
def type_clusterer(mock_neo4j_service):
    """Create TypeClusterer instance with mocked dependencies."""
    return TypeClusterer(
        neo4j_service=mock_neo4j_service,
        extraction_model="anthropic:claude-haiku-4-5-20251001",
        min_cluster_size=3,
        similarity_threshold=0.80,
    )


class TestTypeClustererInit:
    """Test TypeClusterer initialization."""

    def test_init_with_defaults(self, mock_neo4j_service):
        """Test initialization with default parameters."""
        clusterer = TypeClusterer(neo4j_service=mock_neo4j_service)

        assert clusterer.neo4j == mock_neo4j_service
        assert clusterer.extraction_model == "anthropic:claude-haiku-4-5-20251001"
        assert clusterer.min_cluster_size == 3
        assert clusterer.similarity_threshold == 0.80
        assert clusterer.type_encoder is not None

    def test_init_with_custom_params(self, mock_neo4j_service):
        """Test initialization with custom parameters."""
        clusterer = TypeClusterer(
            neo4j_service=mock_neo4j_service,
            extraction_model="anthropic:claude-sonnet-4-5-20250929",
            min_cluster_size=5,
            similarity_threshold=0.75,
        )

        assert clusterer.extraction_model == "anthropic:claude-sonnet-4-5-20250929"
        assert clusterer.min_cluster_size == 5
        assert clusterer.similarity_threshold == 0.75


class TestGetAllTypes:
    """Test get_all_types method."""

    @pytest.mark.asyncio
    async def test_get_all_types_success(self, type_clusterer, mock_neo4j_service):
        """Test successful retrieval of memory types."""
        # Mock session and result
        mock_session = AsyncMock()
        mock_result = AsyncMock()
        mock_result.__aiter__.return_value = iter(
            [
                {"type": "docker_container_preference"},
                {"type": "kubernetes_deployment_config"},
                {"type": "proxmox_cluster_setup"},
            ]
        )

        mock_session.run.return_value = mock_result
        mock_neo4j_service.driver.session.return_value.__aenter__.return_value = (
            mock_session
        )

        types = await type_clusterer.get_all_types()

        assert len(types) == 3
        assert "docker_container_preference" in types
        assert "kubernetes_deployment_config" in types
        assert "proxmox_cluster_setup" in types

    @pytest.mark.asyncio
    async def test_get_all_types_empty(self, type_clusterer, mock_neo4j_service):
        """Test retrieval when no types exist."""
        mock_session = AsyncMock()
        mock_result = AsyncMock()
        mock_result.__aiter__.return_value = iter([])

        mock_session.run.return_value = mock_result
        mock_neo4j_service.driver.session.return_value.__aenter__.return_value = (
            mock_session
        )

        types = await type_clusterer.get_all_types()

        assert len(types) == 0

    @pytest.mark.asyncio
    async def test_get_all_types_error(self, type_clusterer, mock_neo4j_service):
        """Test error handling during type retrieval."""
        mock_neo4j_service.driver.session.return_value.__aenter__.side_effect = (
            Exception("Database error")
        )

        types = await type_clusterer.get_all_types()

        assert types == []


class TestEmbedTypes:
    """Test embed_types method."""

    def test_embed_types_success(self, type_clusterer):
        """Test successful type embedding generation."""
        types = [
            "docker_container_tool",
            "docker_deployment_setup",
            "container_runtime_preference",
        ]

        embeddings = type_clusterer.embed_types(types)

        assert len(embeddings) == 3
        for type_name in types:
            assert type_name in embeddings
            assert isinstance(embeddings[type_name], np.ndarray)
            assert embeddings[type_name].shape[0] == 384  # all-MiniLM-L6-v2 dimension

    def test_embed_types_empty_list(self, type_clusterer):
        """Test embedding with empty type list."""
        embeddings = type_clusterer.embed_types([])

        assert embeddings == {}

    @patch("haia.clustering.type_clusterer.SentenceTransformer")
    def test_embed_types_error(self, mock_transformer, type_clusterer):
        """Test error handling during embedding."""
        # Make encode raise an exception
        type_clusterer.type_encoder.encode.side_effect = Exception("Encoding error")

        embeddings = type_clusterer.embed_types(["test_type"])

        assert embeddings == {}


class TestClusterTypes:
    """Test cluster_types method."""

    def test_cluster_types_success(self, type_clusterer):
        """Test successful DBSCAN clustering."""
        # Create synthetic embeddings for similar types
        types = [
            "docker_container_tool",
            "docker_deployment_tool",
            "docker_runtime_config",
            "kubernetes_cluster_setup",
            "kubernetes_pod_config",
            "kubernetes_deployment_manifest",
        ]

        # Generate embeddings
        embeddings = type_clusterer.embed_types(types)

        clusters = type_clusterer.cluster_types(embeddings)

        # Should create at least one cluster
        assert len(clusters) >= 1

        # Verify clusters contain at least min_cluster_size members
        for cluster_types in clusters.values():
            assert len(cluster_types) >= type_clusterer.min_cluster_size

    def test_cluster_types_insufficient_types(self, type_clusterer):
        """Test clustering with insufficient types."""
        types = ["type1", "type2"]  # Less than min_cluster_size (3)
        embeddings = type_clusterer.embed_types(types)

        clusters = type_clusterer.cluster_types(embeddings)

        assert clusters == {}

    def test_cluster_types_empty_dict(self, type_clusterer):
        """Test clustering with empty embeddings."""
        clusters = type_clusterer.cluster_types({})

        assert clusters == {}


class TestGenerateClusterLabel:
    """Test generate_cluster_label method."""

    @pytest.mark.asyncio
    @patch("haia.clustering.type_clusterer.Agent")
    async def test_generate_cluster_label_success(self, mock_agent, type_clusterer):
        """Test successful cluster label generation."""
        # Mock Agent response
        mock_result = MagicMock()
        mock_result.output = "Container Runtime Tools"
        mock_agent_instance = AsyncMock()
        mock_agent_instance.run.return_value = mock_result
        mock_agent.return_value = mock_agent_instance

        types = ["docker_tool", "container_runtime", "docker_config"]
        label = await type_clusterer.generate_cluster_label(types)

        assert label == "Container Runtime Tools"

    @pytest.mark.asyncio
    @patch("haia.clustering.type_clusterer.Agent")
    async def test_generate_cluster_label_strips_quotes(
        self, mock_agent, type_clusterer
    ):
        """Test label generation strips quotes."""
        mock_result = MagicMock()
        mock_result.output = '"Quoted Label"'
        mock_agent_instance = AsyncMock()
        mock_agent_instance.run.return_value = mock_result
        mock_agent.return_value = mock_agent_instance

        label = await type_clusterer.generate_cluster_label(["type1"])

        assert label == "Quoted Label"

    @pytest.mark.asyncio
    @patch("haia.clustering.type_clusterer.Agent")
    async def test_generate_cluster_label_error_fallback(
        self, mock_agent, type_clusterer
    ):
        """Test fallback when label generation fails."""
        mock_agent.side_effect = Exception("LLM error")

        types = ["docker_container_tool"]
        label = await type_clusterer.generate_cluster_label(types)

        # Should use fallback: first type name formatted
        assert label == "Docker Container Tool"


class TestFindSemanticNeighbors:
    """Test find_semantic_neighbors method."""

    @pytest.mark.asyncio
    async def test_find_semantic_neighbors_success(
        self, type_clusterer, mock_neo4j_service
    ):
        """Test finding semantic neighbors."""
        # Mock get_all_types
        mock_session = AsyncMock()
        mock_result = AsyncMock()
        mock_result.__aiter__.return_value = iter(
            [
                {"type": "docker_container_preference"},
                {"type": "docker_deployment_config"},
                {"type": "container_runtime_tool"},
                {"type": "kubernetes_cluster_setup"},
            ]
        )

        mock_session.run.return_value = mock_result
        mock_neo4j_service.driver.session.return_value.__aenter__.return_value = (
            mock_session
        )

        neighbors = await type_clusterer.find_semantic_neighbors(
            "docker_container_preference", threshold=0.50
        )

        # Should find similar "docker" and "container" types
        assert isinstance(neighbors, list)
        assert len(neighbors) > 0
        for neighbor in neighbors:
            assert isinstance(neighbor, SemanticNeighbor)
            assert neighbor.similarity >= 0.50

    @pytest.mark.asyncio
    async def test_find_semantic_neighbors_type_not_found(
        self, type_clusterer, mock_neo4j_service
    ):
        """Test when query type doesn't exist."""
        mock_session = AsyncMock()
        mock_result = AsyncMock()
        mock_result.__aiter__.return_value = iter([{"type": "other_type"}])

        mock_session.run.return_value = mock_result
        mock_neo4j_service.driver.session.return_value.__aenter__.return_value = (
            mock_session
        )

        neighbors = await type_clusterer.find_semantic_neighbors("nonexistent_type")

        assert neighbors == []

    @pytest.mark.asyncio
    async def test_find_semantic_neighbors_max_neighbors(
        self, type_clusterer, mock_neo4j_service
    ):
        """Test max_neighbors limit."""
        # Create many similar types
        types = [{"type": f"docker_type_{i}"} for i in range(20)]

        mock_session = AsyncMock()
        mock_result = AsyncMock()
        mock_result.__aiter__.return_value = iter(types)

        mock_session.run.return_value = mock_result
        mock_neo4j_service.driver.session.return_value.__aenter__.return_value = (
            mock_session
        )

        neighbors = await type_clusterer.find_semantic_neighbors(
            "docker_type_0", threshold=0.50, max_neighbors=5
        )

        # Should respect max_neighbors limit
        assert len(neighbors) <= 5


class TestRunClustering:
    """Test run_clustering orchestration method."""

    @pytest.mark.asyncio
    async def test_run_clustering_insufficient_types(
        self, type_clusterer, mock_neo4j_service
    ):
        """Test clustering with insufficient types."""
        # Mock only 2 types (less than min_cluster_size)
        mock_session = AsyncMock()
        mock_result = AsyncMock()
        mock_result.__aiter__.return_value = iter(
            [{"type": "type1"}, {"type": "type2"}]
        )

        mock_session.run.return_value = mock_result
        mock_neo4j_service.driver.session.return_value.__aenter__.return_value = (
            mock_session
        )

        clusters = await type_clusterer.run_clustering()

        assert clusters == []

    @pytest.mark.asyncio
    @patch("haia.clustering.type_clusterer.Agent")
    async def test_run_clustering_success(
        self, mock_agent, type_clusterer, mock_neo4j_service
    ):
        """Test successful full clustering pipeline."""
        # Mock get_all_types with docker-related types
        types = [
            {"type": "docker_container_tool"},
            {"type": "docker_deployment_config"},
            {"type": "docker_runtime_preference"},
            {"type": "kubernetes_cluster_setup"},
            {"type": "kubernetes_pod_config"},
            {"type": "kubernetes_deployment_config"},
        ]

        mock_session = AsyncMock()
        mock_result = AsyncMock()
        mock_result.__aiter__.return_value = iter(types)
        mock_session.run.return_value = mock_result
        mock_neo4j_service.driver.session.return_value.__aenter__.return_value = (
            mock_session
        )

        # Mock LLM label generation
        mock_result_llm = MagicMock()
        mock_result_llm.output = "Container Tools"
        mock_agent_instance = AsyncMock()
        mock_agent_instance.run.return_value = mock_result_llm
        mock_agent.return_value = mock_agent_instance

        clusters = await type_clusterer.run_clustering()

        # Should create clusters
        assert isinstance(clusters, list)
        for cluster in clusters:
            assert isinstance(cluster, TypeCluster)
            assert cluster.member_count >= type_clusterer.min_cluster_size
