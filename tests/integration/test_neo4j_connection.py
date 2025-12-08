"""Integration tests for Neo4j connection and schema validation.

Tests Neo4j connectivity, schema constraints, and basic operations.
Requires Neo4j container to be running.
"""

import os
import subprocess
from pathlib import Path

import pytest


class TestNeo4jConnection:
    """Integration tests for Neo4j database connection and schema."""

    @pytest.fixture(scope="class")
    def neo4j_password(self):
        """Get Neo4j password from environment."""
        password = os.getenv("NEO4J_PASSWORD", "haia_neo4j_secure_2024")
        return password

    @pytest.fixture(autouse=True)
    def cleanup_test_nodes(self, neo4j_password):
        """Clean up test nodes before each test."""
        # Cleanup before test runs
        cleanup_query = """
        MATCH (n)
        WHERE n.user_id STARTS WITH 'test_all_types_'
           OR n.interest_id STARTS WITH 'test_all_types_'
           OR n.infra_id STARTS WITH 'test_all_types_'
           OR n.pref_id STARTS WITH 'test_all_types_'
           OR n.fact_id STARTS WITH 'test_all_types_'
           OR n.decision_id STARTS WITH 'test_all_types_'
           OR n.conversation_id STARTS WITH 'test_all_types_'
           OR n.user_id STARTS WITH 'test_person_constraint_'
           OR n.interest_id STARTS WITH 'test_interest_constraint_'
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
                cleanup_query,
            ],
            capture_output=True,
        )

        yield  # Test runs here

        # Cleanup after test completes
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

    def test_neo4j_container_running(self):
        """Verify Neo4j container is running."""
        result = subprocess.run(
            ["docker", "ps", "--filter", "name=haia-neo4j", "--format", "{{.Names}}"],
            capture_output=True,
            text=True,
        )
        assert "haia-neo4j" in result.stdout, "Neo4j container not running"

    def test_neo4j_connectivity(self, neo4j_password):
        """Test basic connectivity to Neo4j."""
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

        assert result.returncode == 0, f"Neo4j connection failed: {result.stderr}"
        assert "test" in result.stdout.lower(), "Neo4j query failed"

    def test_schema_version_exists(self, neo4j_password):
        """Verify SchemaVersion node exists (T040: schema validation)."""
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
                "MATCH (sv:SchemaVersion) RETURN sv.version AS version",
            ],
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0, f"Schema version query failed: {result.stderr}"
        assert "version" in result.stdout.lower(), "SchemaVersion node not found"

    def test_all_constraints_exist(self, neo4j_password):
        """Verify all schema constraints are applied (T040: schema validation)."""
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
                "SHOW CONSTRAINTS",
            ],
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0, f"Constraints query failed: {result.stderr}"

        # Check for all required UNIQUE constraints
        expected_constraints = [
            "person_user_id",
            "interest_id",
            "infrastructure_id",
            "tech_pref_id",
            "fact_id",
            "decision_id",
            "conversation_id",
        ]

        for constraint in expected_constraints:
            assert (
                constraint in result.stdout.lower()
            ), f"Missing constraint: {constraint}"

    def test_all_indexes_exist(self, neo4j_password):
        """Verify all indexes are created (T040: schema validation)."""
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
                "SHOW INDEXES",
            ],
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0, f"Indexes query failed: {result.stderr}"

        # Verify indexes exist (created automatically from UNIQUE constraints)
        expected_indexes = [
            "person_user_id",
            "interest_id",
            "infrastructure_id",
            "tech_pref_id",
            "fact_id",
            "decision_id",
            "conversation_id",
        ]

        for index in expected_indexes:
            assert index in result.stdout.lower(), f"Missing index: {index}"

    def test_constraint_enforcement_person_uniqueness(self, neo4j_password):
        """Test Person.user_id uniqueness constraint (T041: constraint enforcement)."""
        test_user_id = "test_person_constraint_001"

        # Create first person
        create_query1 = f"""
        CREATE (p:Person {{
            user_id: '{test_user_id}',
            name: 'Test Person 1',
            created_at: datetime()
        }})
        RETURN p.user_id AS id
        """

        result1 = subprocess.run(
            [
                "docker",
                "exec",
                "haia-neo4j",
                "cypher-shell",
                "-u",
                "neo4j",
                "-p",
                neo4j_password,
                create_query1,
            ],
            capture_output=True,
            text=True,
        )

        assert result1.returncode == 0, "Failed to create first person"

        # Attempt to create duplicate (should fail)
        create_query2 = f"""
        CREATE (p:Person {{
            user_id: '{test_user_id}',
            name: 'Test Person 2',
            created_at: datetime()
        }})
        RETURN p.user_id AS id
        """

        result2 = subprocess.run(
            [
                "docker",
                "exec",
                "haia-neo4j",
                "cypher-shell",
                "-u",
                "neo4j",
                "-p",
                neo4j_password,
                create_query2,
            ],
            capture_output=True,
            text=True,
        )

        # Should fail due to constraint
        assert result2.returncode != 0, "Duplicate person creation should fail"
        assert (
            "constraint" in result2.stderr.lower()
            or "already exists" in result2.stderr.lower()
        ), "Expected constraint violation error"

        # Cleanup
        delete_query = f"MATCH (p:Person {{user_id: '{test_user_id}'}}) DELETE p"
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

    def test_constraint_enforcement_interest_uniqueness(self, neo4j_password):
        """Test Interest.interest_id uniqueness constraint (T041)."""
        test_interest_id = "test_interest_constraint_001"

        # Create first interest
        create_query1 = f"""
        CREATE (i:Interest {{
            interest_id: '{test_interest_id}',
            name: 'Test Interest',
            confidence: 0.9,
            created_at: datetime()
        }})
        RETURN i.interest_id AS id
        """

        result1 = subprocess.run(
            [
                "docker",
                "exec",
                "haia-neo4j",
                "cypher-shell",
                "-u",
                "neo4j",
                "-p",
                neo4j_password,
                create_query1,
            ],
            capture_output=True,
            text=True,
        )

        assert result1.returncode == 0, "Failed to create first interest"

        # Attempt duplicate
        result2 = subprocess.run(
            [
                "docker",
                "exec",
                "haia-neo4j",
                "cypher-shell",
                "-u",
                "neo4j",
                "-p",
                neo4j_password,
                create_query1,  # Same query
            ],
            capture_output=True,
            text=True,
        )

        # Should fail
        assert result2.returncode != 0, "Duplicate interest creation should fail"

        # Cleanup
        delete_query = f"MATCH (i:Interest {{interest_id: '{test_interest_id}'}}) DELETE i"
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

    def test_all_node_types_creatable(self, neo4j_password):
        """Test creating instances of all node types (T040: schema validation)."""
        # Person
        person_query = """
        CREATE (p:Person {
            user_id: 'test_all_types_person',
            name: 'Test Person',
            timezone: 'UTC',
            created_at: datetime()
        })
        RETURN p.user_id AS id
        """

        # Interest
        interest_query = """
        CREATE (i:Interest {
            interest_id: 'test_all_types_interest',
            name: 'Test Interest',
            confidence: 0.8,
            created_at: datetime()
        })
        RETURN i.interest_id AS id
        """

        # Infrastructure
        infra_query = """
        CREATE (infra:Infrastructure {
            infra_id: 'test_all_types_infra',
            name: 'Test Server',
            type: 'server',
            criticality: 'low',
            created_at: datetime()
        })
        RETURN infra.infra_id AS id
        """

        # TechPreference
        pref_query = """
        CREATE (tp:TechPreference {
            pref_id: 'test_all_types_pref',
            technology: 'Python',
            preference_type: 'prefers',
            confidence: 1.0,
            created_at: datetime()
        })
        RETURN tp.pref_id AS id
        """

        # Fact
        fact_query = """
        CREATE (f:Fact {
            fact_id: 'test_all_types_fact',
            content: 'Test fact content',
            fact_type: 'technical',
            confidence: 0.95,
            created_at: datetime()
        })
        RETURN f.fact_id AS id
        """

        # Decision
        decision_query = """
        CREATE (d:Decision {
            decision_id: 'test_all_types_decision',
            topic: 'Test decision',
            chosen_option: 'Option A',
            confidence: 0.9,
            created_at: datetime()
        })
        RETURN d.decision_id AS id
        """

        # Conversation
        conv_query = """
        CREATE (c:Conversation {
            conversation_id: 'test_all_types_conv',
            started_at: datetime(),
            created_at: datetime()
        })
        RETURN c.conversation_id AS id
        """

        queries = [
            person_query,
            interest_query,
            infra_query,
            pref_query,
            fact_query,
            decision_query,
            conv_query,
        ]

        for query in queries:
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
            assert result.returncode == 0, f"Failed to create node: {result.stderr}"

        # Cleanup all test nodes
        cleanup_query = """
        MATCH (n) WHERE
            n.user_id = 'test_all_types_person' OR
            n.interest_id = 'test_all_types_interest' OR
            n.infra_id = 'test_all_types_infra' OR
            n.pref_id = 'test_all_types_pref' OR
            n.fact_id = 'test_all_types_fact' OR
            n.decision_id = 'test_all_types_decision' OR
            n.conversation_id = 'test_all_types_conv'
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
                cleanup_query,
            ],
            check=True,
        )

    def test_schema_verification_script_exists(self):
        """Verify schema verification script exists (T042)."""
        project_root = Path(__file__).parent.parent.parent
        verify_script = project_root / "database" / "schema" / "verify-schema.cypher"
        assert verify_script.exists(), "verify-schema.cypher not found"


class TestNeo4jConcurrentOperations:
    """Integration tests for concurrent Neo4j operations (T056)."""

    @pytest.fixture(scope="class")
    def neo4j_password(self):
        """Get Neo4j password from environment."""
        password = os.getenv("NEO4J_PASSWORD", "haia_neo4j_secure_2024")
        return password

    def test_concurrent_person_creation(self, neo4j_password):
        """Test concurrent creation of multiple Person nodes."""
        import concurrent.futures

        test_ids = [f"test_concurrent_person_{i:03d}" for i in range(10)]

        def create_person(user_id: str) -> bool:
            """Create a person node."""
            query = f"""
            CREATE (p:Person {{
                user_id: '{user_id}',
                name: 'Concurrent Test {user_id}',
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
            return result.returncode == 0

        # Create 10 Person nodes concurrently
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(create_person, user_id) for user_id in test_ids]
            results = [f.result() for f in concurrent.futures.as_completed(futures)]

        # All creations should succeed
        assert all(results), "Some concurrent Person creations failed"

        # Verify all were created
        count_query = f"""
        MATCH (p:Person)
        WHERE p.user_id STARTS WITH 'test_concurrent_person_'
        RETURN count(p) AS count
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
                count_query,
            ],
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0
        assert "10" in result.stdout, "Expected 10 concurrent Person nodes"

        # Cleanup
        cleanup_query = """
        MATCH (p:Person)
        WHERE p.user_id STARTS WITH 'test_concurrent_person_'
        DELETE p
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
                cleanup_query,
            ],
            check=True,
        )

    def test_concurrent_interest_creation(self, neo4j_password):
        """Test concurrent creation of multiple Interest nodes."""
        import concurrent.futures

        test_ids = [f"test_concurrent_interest_{i:03d}" for i in range(10)]

        def create_interest(interest_id: str) -> bool:
            """Create an interest node."""
            query = f"""
            CREATE (i:Interest {{
                interest_id: '{interest_id}',
                name: 'Concurrent Interest {interest_id}',
                confidence: 0.8,
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
                    query,
                ],
                capture_output=True,
                text=True,
            )
            return result.returncode == 0

        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(create_interest, iid) for iid in test_ids]
            results = [f.result() for f in concurrent.futures.as_completed(futures)]

        assert all(results), "Some concurrent Interest creations failed"

        # Cleanup
        cleanup_query = """
        MATCH (i:Interest)
        WHERE i.interest_id STARTS WITH 'test_concurrent_interest_'
        DELETE i
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
                cleanup_query,
            ],
            check=True,
        )

    def test_concurrent_read_operations(self, neo4j_password):
        """Test concurrent read operations on same node."""
        import concurrent.futures

        # First create a test node
        test_id = "test_concurrent_read_person"
        create_query = f"""
        CREATE (p:Person {{
            user_id: '{test_id}',
            name: 'Concurrent Read Test',
            created_at: datetime()
        }})
        RETURN p.user_id AS id
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

        def read_person() -> bool:
            """Read the person node."""
            query = f"MATCH (p:Person {{user_id: '{test_id}'}}) RETURN p.name AS name"
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
            return result.returncode == 0 and "Concurrent Read Test" in result.stdout

        # Perform 20 concurrent reads
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(read_person) for _ in range(20)]
            results = [f.result() for f in concurrent.futures.as_completed(futures)]

        # All reads should succeed
        assert all(results), "Some concurrent read operations failed"

        # Cleanup
        cleanup_query = f"MATCH (p:Person {{user_id: '{test_id}'}}) DELETE p"
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
            check=True,
        )

    def test_concurrent_relationship_creation(self, neo4j_password):
        """Test concurrent creation of relationships."""
        import concurrent.futures

        # Create a person node
        person_id = "test_concurrent_rel_person"
        create_person = f"""
        CREATE (p:Person {{
            user_id: '{person_id}',
            name: 'Relationship Test Person',
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
                create_person,
            ],
            check=True,
        )

        # Create multiple interest nodes
        test_interest_ids = [f"test_concurrent_rel_interest_{i:03d}" for i in range(5)]
        for interest_id in test_interest_ids:
            create_interest = f"""
            CREATE (i:Interest {{
                interest_id: '{interest_id}',
                name: 'Interest {interest_id}',
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
                    create_interest,
                ],
                check=True,
            )

        def create_relationship(interest_id: str) -> bool:
            """Create INTERESTED_IN relationship."""
            query = f"""
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
                    query,
                ],
                capture_output=True,
                text=True,
            )
            return result.returncode == 0

        # Create relationships concurrently
        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
            futures = [executor.submit(create_relationship, iid) for iid in test_interest_ids]
            results = [f.result() for f in concurrent.futures.as_completed(futures)]

        assert all(results), "Some concurrent relationship creations failed"

        # Verify all relationships created
        count_query = f"""
        MATCH (p:Person {{user_id: '{person_id}'}})-[:INTERESTED_IN]->(i:Interest)
        RETURN count(i) AS count
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
                count_query,
            ],
            capture_output=True,
            text=True,
        )

        assert "5" in result.stdout, "Expected 5 concurrent relationships"

        # Cleanup
        cleanup_query = """
        MATCH (n)
        WHERE n.user_id = 'test_concurrent_rel_person' OR
              n.interest_id STARTS WITH 'test_concurrent_rel_interest_'
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
                cleanup_query,
            ],
            check=True,
        )
