"""Performance tests for Neo4j CRUD operations.

Measures latency of create, read, update, and delete operations
to ensure they meet performance requirements.
"""

import os
import subprocess
import time

import pytest


class TestNeo4jPerformance:
    """Performance tests for Neo4j operations."""

    @pytest.fixture(scope="class")
    def neo4j_password(self):
        """Get Neo4j password from environment."""
        return os.getenv("NEO4J_PASSWORD", "haia_neo4j_secure_2024")

    @pytest.fixture(autouse=True)
    def cleanup_perf_test_nodes(self, neo4j_password):
        """Clean up performance test nodes before and after each test."""
        cleanup_query = """
        MATCH (n)
        WHERE n.user_id STARTS WITH 'perf_test_'
           OR n.interest_id STARTS WITH 'perf_test_'
           OR n.interest_id STARTS WITH 'perf_bulk_'
        DETACH DELETE n
        """
        # Cleanup before test
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
                cleanup_query,
            ],
            capture_output=True,
        )

        yield  # Test runs here

        # Cleanup after test
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
                cleanup_query,
            ],
            capture_output=True,
        )

    def test_person_create_performance(self, neo4j_password):
        """Test Person node creation latency (T072)."""
        test_id = "perf_test_person_create"

        # Measure create time
        start_time = time.time()

        query = f"""
        CREATE (p:Person {{
            user_id: '{test_id}',
            name: 'Performance Test Person',
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
                query,
            ],
            capture_output=True,
            text=True,
        )

        create_time = time.time() - start_time

        assert result.returncode == 0, "Create operation failed"
        assert create_time < 3.0, f"Create took {create_time:.3f}s (expected < 3.0s)"

        print(f"\nPerson CREATE latency: {create_time:.3f}s")

        # Cleanup
        cleanup = f"MATCH (p:Person {{user_id: '{test_id}'}}) DELETE p"
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
                cleanup,
            ],
        )

    def test_person_read_performance(self, neo4j_password):
        """Test Person node read latency (T072)."""
        test_id = "perf_test_person_read"

        # Create test data first
        create_query = f"""
        CREATE (p:Person {{
            user_id: '{test_id}',
            name: 'Performance Test Person',
            timezone: 'UTC',
            created_at: datetime()
        }})
        """
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
                create_query,
            ],
            check=True,
        )

        # Measure read time
        start_time = time.time()

        read_query = f"MATCH (p:Person {{user_id: '{test_id}'}}) RETURN p.name AS name"

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

        read_time = time.time() - start_time

        assert result.returncode == 0, "Read operation failed"
        assert read_time < 3.0, f"Read took {read_time:.3f}s (expected < 3.0s)"

        print(f"\nPerson READ latency: {read_time:.3f}s")

        # Cleanup
        cleanup = f"MATCH (p:Person {{user_id: '{test_id}'}}) DELETE p"
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
                cleanup,
            ],
        )

    def test_person_update_performance(self, neo4j_password):
        """Test Person node update latency (T072)."""
        test_id = "perf_test_person_update"

        # Create test data
        create_query = f"""
        CREATE (p:Person {{
            user_id: '{test_id}',
            name: 'Performance Test Person',
            created_at: datetime()
        }})
        """
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
                create_query,
            ],
            check=True,
        )

        # Measure update time
        start_time = time.time()

        update_query = f"""
        MATCH (p:Person {{user_id: '{test_id}'}})
        SET p.name = 'Updated Name', p.updated_at = datetime()
        RETURN p.name AS name
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
                update_query,
            ],
            capture_output=True,
            text=True,
        )

        update_time = time.time() - start_time

        assert result.returncode == 0, "Update operation failed"
        assert update_time < 3.0, f"Update took {update_time:.3f}s (expected < 3.0s)"

        print(f"\nPerson UPDATE latency: {update_time:.3f}s")

        # Cleanup
        cleanup = f"MATCH (p:Person {{user_id: '{test_id}'}}) DELETE p"
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
                cleanup,
            ],
        )

    def test_person_delete_performance(self, neo4j_password):
        """Test Person node delete latency (T072)."""
        test_id = "perf_test_person_delete"

        # Create test data
        create_query = f"""
        CREATE (p:Person {{
            user_id: '{test_id}',
            name: 'Performance Test Person',
            created_at: datetime()
        }})
        """
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
                create_query,
            ],
            check=True,
        )

        # Measure delete time
        start_time = time.time()

        delete_query = f"""
        MATCH (p:Person {{user_id: '{test_id}'}})
        DETACH DELETE p
        RETURN count(p) AS deleted
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
                delete_query,
            ],
            capture_output=True,
            text=True,
        )

        delete_time = time.time() - start_time

        assert result.returncode == 0, "Delete operation failed"
        assert delete_time < 3.0, f"Delete took {delete_time:.3f}s (expected < 3.0s)"

        print(f"\nPerson DELETE latency: {delete_time:.3f}s")

    def test_relationship_creation_performance(self, neo4j_password):
        """Test relationship creation latency (T072)."""
        person_id = "perf_test_rel_person"
        interest_id = "perf_test_rel_interest"

        # Create nodes
        create_nodes = f"""
        CREATE (p:Person {{
            user_id: '{person_id}',
            name: 'Test Person',
            created_at: datetime()
        }})
        CREATE (i:Interest {{
            interest_id: '{interest_id}',
            name: 'Test Interest',
            confidence: 0.9,
            created_at: datetime()
        }})
        """
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
                create_nodes,
            ],
            check=True,
        )

        # Measure relationship creation time
        start_time = time.time()

        create_rel = f"""
        MATCH (p:Person {{user_id: '{person_id}'}})
        MATCH (i:Interest {{interest_id: '{interest_id}'}})
        CREATE (p)-[:INTERESTED_IN]->(i)
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
                create_rel,
            ],
            capture_output=True,
            text=True,
        )

        rel_time = time.time() - start_time

        assert result.returncode == 0, "Relationship creation failed"
        assert rel_time < 3.0, f"Relationship creation took {rel_time:.3f}s (expected < 3.0s)"

        print(f"\nRelationship CREATE latency: {rel_time:.3f}s")

        # Cleanup
        cleanup = f"""
        MATCH (n)
        WHERE n.user_id = '{person_id}' OR n.interest_id = '{interest_id}'
        DETACH DELETE n
        """
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
                cleanup,
            ],
        )

    def test_bulk_operations_performance(self, neo4j_password):
        """Test bulk creation performance (T072)."""
        node_count = 100

        # Measure bulk creation time
        start_time = time.time()

        # Create 100 interest nodes in one query
        bulk_create = """
        UNWIND range(1, 100) AS i
        CREATE (int:Interest {
            interest_id: 'perf_bulk_' + toString(i),
            name: 'Bulk Interest ' + toString(i),
            confidence: 0.8,
            created_at: datetime()
        })
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
                bulk_create,
            ],
            capture_output=True,
            text=True,
        )

        bulk_time = time.time() - start_time
        per_node_time = bulk_time / node_count

        assert result.returncode == 0, "Bulk creation failed"
        assert bulk_time < 5.0, f"Bulk creation took {bulk_time:.3f}s (expected < 5.0s for 100 nodes)"
        assert per_node_time < 0.1, f"Per-node time {per_node_time:.4f}s (expected < 0.1s)"

        print(f"\nBulk CREATE (100 nodes): {bulk_time:.3f}s ({per_node_time:.4f}s per node)")

        # Cleanup
        cleanup = "MATCH (i:Interest WHERE i.interest_id STARTS WITH 'perf_bulk_') DELETE i"
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
                cleanup,
            ],
        )
