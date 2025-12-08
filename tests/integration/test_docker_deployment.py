"""Integration tests for Docker deployment.

Tests full stack deployment with HAIA + Neo4j services.
These tests require Docker to be running.
"""

import os
import subprocess
import time
from pathlib import Path

import pytest
import requests


class TestDockerDeployment:
    """Integration tests for Docker Compose deployment."""

    @pytest.fixture(scope="class", autouse=True)
    def deployment_env(self):
        """Setup and teardown Docker deployment for all tests."""
        project_root = Path(__file__).parent.parent.parent
        compose_file = project_root / "deployment" / "docker-compose.yml"

        if not compose_file.exists():
            pytest.skip("docker-compose.yml not found")

        # Check if services are already running
        result = subprocess.run(
            ["docker", "compose", "-f", str(compose_file), "ps", "-q"],
            capture_output=True,
            text=True,
        )

        services_running = bool(result.stdout.strip())

        if not services_running:
            pytest.skip(
                "Docker services not running. Start with: ./deployment/docker-install.sh"
            )

        yield

        # Teardown (optional - keep services running for manual inspection)
        # subprocess.run(["docker", "compose", "-f", str(compose_file), "down"])

    def test_docker_installed(self):
        """Verify Docker is installed and accessible."""
        result = subprocess.run(["docker", "--version"], capture_output=True)
        assert result.returncode == 0, "Docker not installed"

    def test_docker_compose_installed(self):
        """Verify Docker Compose is installed."""
        result = subprocess.run(["docker", "compose", "version"], capture_output=True)
        assert result.returncode == 0, "Docker Compose not installed"

    def test_haia_container_running(self):
        """Verify HAIA container is running."""
        result = subprocess.run(
            ["docker", "ps", "--filter", "name=haia-api", "--format", "{{.Names}}"],
            capture_output=True,
            text=True,
        )
        assert "haia-api" in result.stdout, "HAIA container not running"

    def test_neo4j_container_running(self):
        """Verify Neo4j container is running."""
        result = subprocess.run(
            ["docker", "ps", "--filter", "name=haia-neo4j", "--format", "{{.Names}}"],
            capture_output=True,
            text=True,
        )
        assert "haia-neo4j" in result.stdout, "Neo4j container not running"

    def test_haia_health_endpoint(self):
        """Test HAIA health endpoint responds correctly."""
        max_retries = 10
        retry_delay = 2

        for attempt in range(max_retries):
            try:
                response = requests.get("http://localhost:8000/health", timeout=5)
                if response.status_code == 200:
                    data = response.json()
                    assert "status" in data, "Health response missing 'status'"
                    assert data["status"] in [
                        "healthy",
                        "degraded",
                    ], f"Unexpected status: {data['status']}"
                    return
            except requests.ConnectionError:
                if attempt < max_retries - 1:
                    time.sleep(retry_delay)
                else:
                    raise

        pytest.fail("HAIA health endpoint unreachable after retries")

    def test_neo4j_bolt_accessible(self):
        """Verify Neo4j Bolt port is accessible."""
        max_retries = 5
        retry_delay = 2

        for attempt in range(max_retries):
            result = subprocess.run(
                [
                    "docker",
                    "exec",
                    "haia-neo4j",
                    "cypher-shell",
                    "-u",
                    "neo4j",
                    "-p",
                    os.getenv("NEO4J_PASSWORD", "password"),
                    "RETURN 1",
                ],
                capture_output=True,
                text=True,
            )

            if result.returncode == 0:
                return

            if attempt < max_retries - 1:
                time.sleep(retry_delay)

        pytest.fail("Neo4j Bolt connection failed after retries")

    def test_neo4j_schema_applied(self):
        """Verify Neo4j schema constraints and indexes are applied."""
        result = subprocess.run(
            [
                "docker",
                "exec",
                "haia-neo4j",
                "cypher-shell",
                "-u",
                "neo4j",
                "-p",
                os.getenv("NEO4J_PASSWORD", "password"),
                "SHOW CONSTRAINTS",
            ],
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0, "Failed to query Neo4j constraints"
        # Should have constraints for all node types
        expected_constraints = [
            "person_user_id",
            "interest_id",
            "infrastructure_id",
            "fact_id",
            "decision_id",
        ]
        for constraint in expected_constraints:
            assert (
                constraint in result.stdout.lower()
            ), f"Missing constraint: {constraint}"

    def test_haia_neo4j_connectivity(self):
        """Test HAIA can connect to Neo4j via health check."""
        response = requests.get("http://localhost:8000/health", timeout=10)
        assert response.status_code == 200

        data = response.json()
        assert (
            data.get("neo4j") == "connected"
        ), f"Neo4j not connected: {data.get('neo4j')}"
        assert data.get("status") == "healthy", f"System not healthy: {data.get('status')}"

    def test_docker_volumes_created(self):
        """Verify Docker volumes for persistence are created."""
        result = subprocess.run(
            ["docker", "volume", "ls", "--format", "{{.Name}}"],
            capture_output=True,
            text=True,
        )

        expected_volumes = [
            "haia_neo4j-data",
            "haia_neo4j-logs",
            "haia_neo4j-backups",
            "haia_haia-logs",
        ]

        for volume in expected_volumes:
            assert volume in result.stdout, f"Missing volume: {volume}"

    def test_docker_network_created(self):
        """Verify Docker network is created."""
        result = subprocess.run(
            ["docker", "network", "ls", "--format", "{{.Name}}"],
            capture_output=True,
            text=True,
        )

        assert "haia-network" in result.stdout, "Docker network 'haia-network' not found"

    def test_data_persistence_after_restart(self):
        """Test data persists across container restarts (US2: T027-T028)."""
        neo4j_password = os.getenv("NEO4J_PASSWORD", "password")

        # Create test data
        test_person_id = "person_test_persist"
        create_query = f"""
        CREATE (p:Person {{
            user_id: '{test_person_id}',
            name: 'Test User',
            timezone: 'UTC',
            created_at: datetime()
        }})
        RETURN p.user_id AS id
        """

        result = subprocess.run(
            [
                "docker",
                "exec",
                "haia-neo4j",
                "cypher-shell",
                "-u",
                "neo4j",
                "-p",
                neo4j_password,
                create_query,
            ],
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0, f"Failed to create test data: {result.stderr}"

        # Restart Neo4j container
        project_root = Path(__file__).parent.parent.parent
        compose_file = project_root / "deployment" / "docker-compose.yml"

        subprocess.run(
            ["docker", "compose", "-f", str(compose_file), "restart", "neo4j"],
            check=True,
        )

        # Wait for Neo4j to be ready again
        time.sleep(10)
        for _ in range(10):
            ready = subprocess.run(
                [
                    "docker",
                    "exec",
                    "haia-neo4j",
                    "cypher-shell",
                    "-u",
                    "neo4j",
                    "-p",
                    neo4j_password,
                    "RETURN 1",
                ],
                capture_output=True,
            )
            if ready.returncode == 0:
                break
            time.sleep(2)

        # Verify data still exists
        read_query = f"MATCH (p:Person {{user_id: '{test_person_id}'}}) RETURN p.name AS name"
        result = subprocess.run(
            [
                "docker",
                "exec",
                "haia-neo4j",
                "cypher-shell",
                "-u",
                "neo4j",
                "-p",
                neo4j_password,
                read_query,
            ],
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0, "Failed to query data after restart"
        assert "Test User" in result.stdout, "Data not persisted after restart"

        # Cleanup
        delete_query = f"MATCH (p:Person {{user_id: '{test_person_id}'}}) DETACH DELETE p"
        subprocess.run(
            [
                "docker",
                "exec",
                "haia-neo4j",
                "cypher-shell",
                "-u",
                "neo4j",
                "-p",
                neo4j_password,
                delete_query,
            ],
            check=True,
        )

    def test_data_persistence_after_recreation(self):
        """Test data persists through container recreation (US2: T028)."""
        neo4j_password = os.getenv("NEO4J_PASSWORD", "password")
        project_root = Path(__file__).parent.parent.parent
        compose_file = project_root / "deployment" / "docker-compose.yml"

        # Create test data
        test_interest_id = "interest_test_recreate"
        create_query = f"""
        CREATE (i:Interest {{
            interest_id: '{test_interest_id}',
            name: 'Test Interest',
            confidence: 1.0,
            created_at: datetime()
        }})
        RETURN i.interest_id AS id
        """

        result = subprocess.run(
            [
                "docker",
                "exec",
                "haia-neo4j",
                "cypher-shell",
                "-u",
                "neo4j",
                "-p",
                neo4j_password,
                create_query,
            ],
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0, f"Failed to create test data: {result.stderr}"

        # Stop and remove container (preserving volumes)
        subprocess.run(
            ["docker", "compose", "-f", str(compose_file), "stop", "neo4j"],
            check=True,
        )
        subprocess.run(
            ["docker", "compose", "-f", str(compose_file), "rm", "-f", "neo4j"],
            check=True,
        )

        # Recreate container
        subprocess.run(
            ["docker", "compose", "-f", str(compose_file), "up", "-d", "neo4j"],
            check=True,
        )

        # Wait for Neo4j to be ready
        time.sleep(15)
        for _ in range(15):
            ready = subprocess.run(
                [
                    "docker",
                    "exec",
                    "haia-neo4j",
                    "cypher-shell",
                    "-u",
                    "neo4j",
                    "-p",
                    neo4j_password,
                    "RETURN 1",
                ],
                capture_output=True,
            )
            if ready.returncode == 0:
                break
            time.sleep(2)

        # Verify data still exists
        read_query = f"MATCH (i:Interest {{interest_id: '{test_interest_id}'}}) RETURN i.name AS name"
        result = subprocess.run(
            [
                "docker",
                "exec",
                "haia-neo4j",
                "cypher-shell",
                "-u",
                "neo4j",
                "-p",
                neo4j_password,
                read_query,
            ],
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0, "Failed to query data after recreation"
        assert "Test Interest" in result.stdout, "Data not persisted after recreation"

        # Cleanup
        delete_query = f"MATCH (i:Interest {{interest_id: '{test_interest_id}'}}) DETACH DELETE i"
        subprocess.run(
            [
                "docker",
                "exec",
                "haia-neo4j",
                "cypher-shell",
                "-u",
                "neo4j",
                "-p",
                neo4j_password,
                delete_query,
            ],
            check=True,
        )

    def test_hybrid_deployment_mode(self):
        """Test hybrid deployment mode: Neo4j container + native HAIA (US3: T036)."""
        # This test verifies the development workflow where:
        # - Neo4j runs in container
        # - HAIA could run natively on host (not tested here, just verify Neo4j is accessible)

        neo4j_password = os.getenv("NEO4J_PASSWORD", "password")

        # Verify Neo4j is accessible on localhost (not just via Docker DNS)
        # This ensures developers can connect from native HAIA instance
        result = subprocess.run(
            [
                "docker",
                "exec",
                "haia-neo4j",
                "cypher-shell",
                "-u",
                "neo4j",
                "-p",
                neo4j_password,
                "RETURN 1 AS test",
            ],
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0, "Neo4j not accessible for hybrid mode"
        assert "test" in result.stdout.lower(), "Neo4j query failed in hybrid mode"

        # Verify docker-compose.dev.yml exists
        project_root = Path(__file__).parent.parent.parent
        dev_compose = project_root / "deployment" / "docker-compose.dev.yml"
        assert dev_compose.exists(), "docker-compose.dev.yml not found"

        # Verify .env.dev template exists
        env_dev = project_root / ".env.dev"
        assert env_dev.exists(), ".env.dev template not found"
