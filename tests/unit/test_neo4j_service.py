"""Unit tests for Neo4j service CRUD operations.

These tests mock the Neo4j driver to test business logic without requiring
a running Neo4j instance.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from haia.services.neo4j import Neo4jService


@pytest.fixture
def neo4j_service():
    """Create a Neo4jService instance for testing."""
    service = Neo4jService(uri="bolt://localhost:7687", user="neo4j", password="test")
    return service


@pytest.fixture
def mock_driver():
    """Create a mock Neo4j driver."""
    driver = AsyncMock()
    session = AsyncMock()
    driver.session.return_value.__aenter__.return_value = session
    driver.verify_connectivity = AsyncMock()
    return driver


class TestNeo4jServiceConnection:
    """Tests for Neo4j service connection and initialization."""

    @pytest.mark.asyncio
    async def test_connect_success(self, neo4j_service, mock_driver):
        """Test successful connection to Neo4j."""
        with patch("haia.services.neo4j.AsyncGraphDatabase.driver", return_value=mock_driver):
            await neo4j_service.connect()
            assert neo4j_service.driver is not None
            mock_driver.verify_connectivity.assert_called_once()

    @pytest.mark.asyncio
    async def test_connect_retry_on_failure(self, neo4j_service):
        """Test connection retry with exponential backoff."""
        mock_driver = AsyncMock()
        mock_driver.verify_connectivity.side_effect = [
            Exception("Connection failed"),
            Exception("Connection failed"),
            None,  # Success on third attempt
        ]

        with patch("haia.services.neo4j.AsyncGraphDatabase.driver", return_value=mock_driver):
            with patch("asyncio.sleep", new_callable=AsyncMock):  # Speed up test
                await neo4j_service.connect(max_retries=3)
                assert neo4j_service.driver is not None
                assert mock_driver.verify_connectivity.call_count == 3

    @pytest.mark.asyncio
    async def test_close(self, neo4j_service, mock_driver):
        """Test closing Neo4j connection."""
        neo4j_service.driver = mock_driver
        await neo4j_service.close()
        mock_driver.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_health_check_healthy(self, neo4j_service, mock_driver):
        """Test health check when connection is healthy."""
        neo4j_service.driver = mock_driver

        # Mock session and query result
        mock_result = AsyncMock()
        mock_record = {"health": 1}
        mock_result.single.return_value = mock_record

        session = AsyncMock()
        session.run.return_value = mock_result
        mock_driver.session.return_value.__aenter__.return_value = session

        healthy = await neo4j_service.health_check()
        assert healthy is True

    @pytest.mark.asyncio
    async def test_health_check_unhealthy(self, neo4j_service):
        """Test health check when driver is not initialized."""
        healthy = await neo4j_service.health_check()
        assert healthy is False


class TestNeo4jServiceCRUD:
    """Tests for CRUD operations."""

    @pytest.mark.asyncio
    async def test_create_person(self, neo4j_service, mock_driver):
        """Test creating a Person node."""
        neo4j_service.driver = mock_driver

        # Mock the transaction result
        mock_result = AsyncMock()
        mock_record = {"id": "person_test_001"}
        mock_result.single.return_value = mock_record

        session = AsyncMock()
        session.execute_write.return_value = "person_test_001"
        mock_driver.session.return_value.__aenter__.return_value = session

        person_data = {
            "user_id": "person_test_001",
            "name": "Test Person",
            "created_at": "2025-12-08T10:00:00",
        }

        node_id = await neo4j_service.create_person(person_data)
        assert node_id == "person_test_001"
        session.execute_write.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_interest(self, neo4j_service, mock_driver):
        """Test creating an Interest node."""
        neo4j_service.driver = mock_driver

        session = AsyncMock()
        session.execute_write.return_value = "interest_test_001"
        mock_driver.session.return_value.__aenter__.return_value = session

        interest_data = {
            "interest_id": "interest_test_001",
            "name": "Test Interest",
            "confidence": 0.9,
            "created_at": "2025-12-08T10:00:00",
        }

        node_id = await neo4j_service.create_interest(interest_data)
        assert node_id == "interest_test_001"

    @pytest.mark.asyncio
    async def test_read_person(self, neo4j_service, mock_driver):
        """Test reading a Person node."""
        neo4j_service.driver = mock_driver

        session = AsyncMock()
        expected_data = {
            "user_id": "person_test_001",
            "name": "Test Person",
            "timezone": "UTC",
        }
        session.execute_read.return_value = expected_data
        mock_driver.session.return_value.__aenter__.return_value = session

        node_data = await neo4j_service.read_person("person_test_001")
        assert node_data == expected_data
        session.execute_read.assert_called_once()

    @pytest.mark.asyncio
    async def test_read_nonexistent_node(self, neo4j_service, mock_driver):
        """Test reading a node that doesn't exist."""
        neo4j_service.driver = mock_driver

        session = AsyncMock()
        session.execute_read.return_value = None
        mock_driver.session.return_value.__aenter__.return_value = session

        node_data = await neo4j_service.read_person("nonexistent_id")
        assert node_data is None

    @pytest.mark.asyncio
    async def test_update_person(self, neo4j_service, mock_driver):
        """Test updating a Person node."""
        neo4j_service.driver = mock_driver

        session = AsyncMock()
        session.execute_write.return_value = True
        mock_driver.session.return_value.__aenter__.return_value = session

        success = await neo4j_service.update_person(
            "person_test_001", {"name": "Updated Name"}
        )
        assert success is True
        session.execute_write.assert_called_once()

    @pytest.mark.asyncio
    async def test_delete_person(self, neo4j_service, mock_driver):
        """Test deleting a Person node."""
        neo4j_service.driver = mock_driver

        session = AsyncMock()
        session.execute_write.return_value = True
        mock_driver.session.return_value.__aenter__.return_value = session

        success = await neo4j_service.delete_person("person_test_001")
        assert success is True
        session.execute_write.assert_called_once()

    @pytest.mark.asyncio
    async def test_crud_without_driver(self, neo4j_service):
        """Test CRUD operations fail gracefully when driver is not initialized."""
        # Create
        node_id = await neo4j_service.create_person({"user_id": "test", "name": "Test"})
        assert node_id is None

        # Read
        node_data = await neo4j_service.read_person("test")
        assert node_data is None

        # Update
        success = await neo4j_service.update_person("test", {"name": "Updated"})
        assert success is False

        # Delete
        success = await neo4j_service.delete_person("test")
        assert success is False


class TestNeo4jServiceRelationships:
    """Tests for relationship creation methods."""

    @pytest.mark.asyncio
    async def test_create_relationship(self, neo4j_service, mock_driver):
        """Test creating a generic relationship."""
        neo4j_service.driver = mock_driver

        session = AsyncMock()
        session.execute_write.return_value = True
        mock_driver.session.return_value.__aenter__.return_value = session

        success = await neo4j_service.create_relationship(
            from_label="Person",
            from_id="person_001",
            rel_type="INTERESTED_IN",
            to_label="Interest",
            to_id="interest_001",
        )
        assert success is True
        session.execute_write.assert_called_once()

    @pytest.mark.asyncio
    async def test_link_person_interest(self, neo4j_service, mock_driver):
        """Test linking Person to Interest."""
        neo4j_service.driver = mock_driver

        session = AsyncMock()
        session.execute_write.return_value = True
        mock_driver.session.return_value.__aenter__.return_value = session

        success = await neo4j_service.link_person_interest("person_001", "interest_001")
        assert success is True

    @pytest.mark.asyncio
    async def test_link_person_infrastructure(self, neo4j_service, mock_driver):
        """Test linking Person to Infrastructure."""
        neo4j_service.driver = mock_driver

        session = AsyncMock()
        session.execute_write.return_value = True
        mock_driver.session.return_value.__aenter__.return_value = session

        success = await neo4j_service.link_person_infrastructure("person_001", "infra_001")
        assert success is True

    @pytest.mark.asyncio
    async def test_link_with_properties(self, neo4j_service, mock_driver):
        """Test creating relationship with properties."""
        neo4j_service.driver = mock_driver

        session = AsyncMock()
        session.execute_write.return_value = True
        mock_driver.session.return_value.__aenter__.return_value = session

        properties = {"confidence": 0.95, "source": "conversation"}
        success = await neo4j_service.link_person_fact(
            "person_001", "fact_001", properties=properties
        )
        assert success is True

    @pytest.mark.asyncio
    async def test_relationship_without_driver(self, neo4j_service):
        """Test relationship creation fails gracefully without driver."""
        success = await neo4j_service.link_person_interest("person_001", "interest_001")
        assert success is False


class TestNeo4jServiceErrorHandling:
    """Tests for error handling in Neo4j service."""

    @pytest.mark.asyncio
    async def test_create_node_handles_exception(self, neo4j_service, mock_driver):
        """Test create_node handles exceptions gracefully."""
        neo4j_service.driver = mock_driver

        session = AsyncMock()
        session.execute_write.side_effect = Exception("Database error")
        mock_driver.session.return_value.__aenter__.return_value = session

        node_id = await neo4j_service.create_person(
            {"user_id": "test", "name": "Test"}
        )
        assert node_id is None

    @pytest.mark.asyncio
    async def test_read_node_handles_exception(self, neo4j_service, mock_driver):
        """Test read_node handles exceptions gracefully."""
        neo4j_service.driver = mock_driver

        session = AsyncMock()
        session.execute_read.side_effect = Exception("Database error")
        mock_driver.session.return_value.__aenter__.return_value = session

        node_data = await neo4j_service.read_person("test")
        assert node_data is None

    @pytest.mark.asyncio
    async def test_update_node_handles_exception(self, neo4j_service, mock_driver):
        """Test update_node handles exceptions gracefully."""
        neo4j_service.driver = mock_driver

        session = AsyncMock()
        session.execute_write.side_effect = Exception("Database error")
        mock_driver.session.return_value.__aenter__.return_value = session

        success = await neo4j_service.update_person("test", {"name": "Updated"})
        assert success is False

    @pytest.mark.asyncio
    async def test_delete_node_handles_exception(self, neo4j_service, mock_driver):
        """Test delete_node handles exceptions gracefully."""
        neo4j_service.driver = mock_driver

        session = AsyncMock()
        session.execute_write.side_effect = Exception("Database error")
        mock_driver.session.return_value.__aenter__.return_value = session

        success = await neo4j_service.delete_person("test")
        assert success is False

    @pytest.mark.asyncio
    async def test_relationship_handles_exception(self, neo4j_service, mock_driver):
        """Test relationship creation handles exceptions gracefully."""
        neo4j_service.driver = mock_driver

        session = AsyncMock()
        session.execute_write.side_effect = Exception("Database error")
        mock_driver.session.return_value.__aenter__.return_value = session

        success = await neo4j_service.link_person_interest("person_001", "interest_001")
        assert success is False
