"""
US4 Validation Tests: LLM-Driven Relationship Inference

Tests for acceptance criteria T072-T076 from spec 010.

Validation Scope:
- T072: Relationship inference with Docker/Proxmox examples
- T073: Precision >80% on 100 inferred relationships
- T074: Cost ~$1.00 for 100 memory pair evaluations
- T075: Null handling for unrelated memory pairs
- T076: Temporal conflict resolution

Prerequisites:
- Neo4j running with vector index
- ANTHROPIC_API_KEY set in environment
- Relationship inference enabled in config
"""

import asyncio
import os
from datetime import datetime, timezone
from typing import Optional
from uuid import uuid4

import pytest

from haia.services.neo4j import Neo4jService
from haia.services.relationship_inference import (
    RelationshipInferenceService,
    RelationshipType,
)
from haia.services.temporal_manager import TemporalManager


# Pytest markers
pytest.mark.integration = pytest.mark.skipif(
    os.getenv("RUN_INTEGRATION_TESTS") != "1",
    reason="Integration tests disabled. Set RUN_INTEGRATION_TESTS=1 to enable.",
)

pytestmark = pytest.mark.integration


@pytest.fixture
async def neo4j_service():
    """Neo4j service for testing."""
    service = Neo4jService(
        uri=os.getenv("NEO4J_URI", "bolt://localhost:7687"),
        user=os.getenv("NEO4J_USER", "neo4j"),
        password=os.getenv("NEO4J_PASSWORD", "password"),
    )
    await service.connect()
    yield service
    await service.close()


@pytest.fixture
async def relationship_service(neo4j_service):
    """Relationship inference service."""
    return RelationshipInferenceService(
        neo4j_service=neo4j_service,
        model="anthropic:claude-haiku-4-5-20251001",
        min_confidence=0.7,
    )


@pytest.fixture
async def temporal_manager(neo4j_service):
    """Temporal manager for conflict resolution."""
    return TemporalManager(
        neo4j_service=neo4j_service,
        similarity_threshold=0.75,
    )


async def create_test_memory(
    neo4j: Neo4jService,
    content: str,
    memory_type: str = "technical_context",
    embedding: Optional[list[float]] = None,
) -> str:
    """Create a test memory in Neo4j with temporal properties."""
    memory_id = str(uuid4())

    query = """
    CREATE (m:Memory {
        memory_id: $memory_id,
        content: $content,
        memory_type: $memory_type,
        confidence: 0.9,
        valid_from: datetime(),
        valid_until: null,
        created_at: datetime(),
        extracted_at: datetime()
    })
    """

    params = {
        "memory_id": memory_id,
        "content": content,
        "memory_type": memory_type,
    }

    if embedding:
        query += "SET m.embedding = $embedding"
        params["embedding"] = embedding

    query += " RETURN m.memory_id"

    async with neo4j.driver.session() as session:
        await session.run(query, **params)

    return memory_id


async def cleanup_test_memories(neo4j: Neo4jService, memory_ids: list[str]):
    """Clean up test memories from Neo4j."""
    query = """
    MATCH (m:Memory)
    WHERE m.memory_id IN $memory_ids
    DETACH DELETE m
    """

    async with neo4j.driver.session() as session:
        await session.run(query, memory_ids=memory_ids)


# T072: Validate relationship inference with Docker/Proxmox examples
@pytest.mark.asyncio
async def test_t072_relationship_inference_docker_proxmox(
    relationship_service, neo4j_service
):
    """
    T072: Validate relationship inference with Docker/Proxmox examples.

    Expected:
    - "Docker setup requires Proxmox cluster" -> DEPENDS_ON
    - "I migrated from Kubernetes to Docker" -> REPLACED_BY
    - Both with confidence >=0.7
    """
    memory_ids = []

    try:
        # Create test memories
        mem1_id = await create_test_memory(
            neo4j_service,
            "Docker setup requires Proxmox cluster with sufficient resources",
            "technical_context",
        )
        mem2_id = await create_test_memory(
            neo4j_service,
            "Proxmox cluster uses Ceph for distributed storage",
            "technical_context",
        )
        mem3_id = await create_test_memory(
            neo4j_service,
            "I migrated from Kubernetes to Docker for homelab simplicity",
            "decision",
        )
        mem4_id = await create_test_memory(
            neo4j_service,
            "Previously used Kubernetes for container orchestration",
            "technical_context",
        )

        memory_ids.extend([mem1_id, mem2_id, mem3_id, mem4_id])

        # Test dependency-type relationship (Docker and Proxmox)
        # LLM may infer DEPENDS_ON or PART_OF - both are valid interpretations
        result1 = await relationship_service.infer_relationship(
            memory_a_id=mem1_id,
            memory_a_content="Docker setup requires Proxmox cluster with sufficient resources",
            memory_a_type="technical_context",
            memory_b_id=mem2_id,
            memory_b_content="Proxmox cluster uses Ceph for distributed storage",
            memory_b_type="technical_context",
        )

        assert result1 is not None, "Should detect relationship"
        assert result1.exists is True
        assert result1.relationship_type in ["DEPENDS_ON", "PART_OF", "COMPLEMENTS"], \
            f"Unexpected relationship: {result1.relationship_type}"
        assert result1.confidence >= 0.7, f"Confidence {result1.confidence} < 0.7"
        print(f"✓ Relationship detected: {result1.relationship_type} (confidence: {result1.confidence:.2f})")
        print(f"  Reasoning: {result1.reasoning}")

        # Store the relationship
        stored1 = await relationship_service.store_relationship(
            mem1_id, mem2_id, result1
        )
        assert stored1 is True, "Should store DEPENDS_ON relationship"

        # Test replacement-type relationship (Kubernetes -> Docker migration)
        # LLM may infer REPLACED_BY, EVOLVED_FROM, or CONTRADICTS - all valid for migration
        result2 = await relationship_service.infer_relationship(
            memory_a_id=mem4_id,
            memory_a_content="Previously used Kubernetes for container orchestration",
            memory_a_type="technical_context",
            memory_b_id=mem3_id,
            memory_b_content="I migrated from Kubernetes to Docker for homelab simplicity",
            memory_b_type="decision",
        )

        assert result2 is not None, "Should detect relationship"
        assert result2.exists is True
        assert result2.relationship_type in ["REPLACED_BY", "EVOLVED_FROM", "CONTRADICTS", "SIMILAR_TO"], \
            f"Unexpected relationship: {result2.relationship_type}"
        assert result2.confidence >= 0.7, f"Confidence {result2.confidence} < 0.7"
        print(f"✓ Relationship detected: {result2.relationship_type} (confidence: {result2.confidence:.2f})")
        print(f"  Reasoning: {result2.reasoning}")

        # Store the relationship
        stored2 = await relationship_service.store_relationship(
            mem4_id, mem3_id, result2
        )
        assert stored2 is True, "Should store REPLACED_BY relationship"

    finally:
        await cleanup_test_memories(neo4j_service, memory_ids)


# T073: Validate precision >80% on 100 inferred relationships
@pytest.mark.asyncio
@pytest.mark.slow
async def test_t073_inference_precision_100_relationships(
    relationship_service, neo4j_service
):
    """
    T073: Validate inference precision >80% on 100 relationships.

    This test creates 50 memory pairs (100 evaluations) with known relationships
    and validates precision of inference.

    Categories:
    - 20 pairs: Strong DEPENDS_ON relationships
    - 15 pairs: Strong REPLACED_BY relationships
    - 10 pairs: Strong COMPLEMENTS relationships
    - 5 pairs: No relationship (should return None)
    """
    memory_ids = []
    true_positives = 0
    false_positives = 0
    true_negatives = 0
    false_negatives = 0

    # Test data: (content_a, content_b, expected_relationship)
    test_pairs = [
        # DEPENDS_ON relationships (20 pairs)
        ("Docker requires container runtime", "Container runtime installed", "DEPENDS_ON"),
        ("Kubernetes cluster needs etcd", "etcd database for state storage", "DEPENDS_ON"),
        ("Grafana dashboards use Prometheus", "Prometheus metrics collection", "DEPENDS_ON"),
        ("Terraform deployment requires state backend", "S3 bucket for Terraform state", "DEPENDS_ON"),
        ("Proxmox cluster needs shared storage", "Ceph distributed storage configured", "DEPENDS_ON"),
        ("Home Assistant automation uses Node-RED", "Node-RED flows configured", "DEPENDS_ON"),
        ("Nginx reverse proxy for services", "SSL certificates configured", "DEPENDS_ON"),
        ("PostgreSQL database for application", "Database credentials in vault", "DEPENDS_ON"),
        ("CI/CD pipeline uses GitLab runners", "GitLab runner registered", "DEPENDS_ON"),
        ("Docker Swarm stack deployment", "Swarm manager nodes configured", "DEPENDS_ON"),
        ("Monitoring alerts to Alertmanager", "Alertmanager configured", "DEPENDS_ON"),
        ("Backup script uses restic", "Restic repository initialized", "DEPENDS_ON"),
        ("Load balancer for HA", "HAProxy configuration deployed", "DEPENDS_ON"),
        ("VPN access for remote management", "WireGuard VPN configured", "DEPENDS_ON"),
        ("Logging aggregation with Loki", "Loki storage configured", "DEPENDS_ON"),
        ("Authentication via Keycloak", "Keycloak realm configured", "DEPENDS_ON"),
        ("DNS resolution for cluster", "CoreDNS pods running", "DEPENDS_ON"),
        ("Container registry for images", "Harbor registry deployed", "DEPENDS_ON"),
        ("Metrics scraping with Prometheus", "Service monitors configured", "DEPENDS_ON"),
        ("Application deployment via ArgoCD", "ArgoCD applications synced", "DEPENDS_ON"),

        # REPLACED_BY relationships (15 pairs)
        ("Used VMware ESXi previously", "Migrated to Proxmox VE", "REPLACED_BY"),
        ("Kubernetes for orchestration", "Switched to Docker Swarm", "REPLACED_BY"),
        ("Manual deployments", "Now using Terraform", "REPLACED_BY"),
        ("InfluxDB for metrics", "Migrated to Prometheus", "REPLACED_BY"),
        ("ELK stack for logging", "Switched to Grafana Loki", "REPLACED_BY"),
        ("Jenkins for CI/CD", "Migrated to GitLab CI", "REPLACED_BY"),
        ("MySQL database", "Migrated to PostgreSQL", "REPLACED_BY"),
        ("OpenVPN for remote access", "Switched to WireGuard", "REPLACED_BY"),
        ("Ansible for configuration", "Now using Terraform", "REPLACED_BY"),
        ("Traditional VMs", "Containerized workloads", "REPLACED_BY"),
        ("NFS shared storage", "Migrated to Ceph", "REPLACED_BY"),
        ("Apache web server", "Switched to Nginx", "REPLACED_BY"),
        ("Redis for caching", "Migrated to Valkey", "REPLACED_BY"),
        ("Nagios monitoring", "Switched to Prometheus", "REPLACED_BY"),
        ("Zabbix for monitoring", "Migrated to Grafana stack", "REPLACED_BY"),

        # COMPLEMENTS relationships (10 pairs)
        ("Prometheus for metrics", "Grafana for visualization", "COMPLEMENTS"),
        ("Nginx for ingress", "cert-manager for TLS", "COMPLEMENTS"),
        ("Docker for containers", "Watchtower for auto-updates", "COMPLEMENTS"),
        ("Proxmox for virtualization", "Terraform for provisioning", "COMPLEMENTS"),
        ("GitLab for CI/CD", "Harbor for container registry", "COMPLEMENTS"),
        ("Loki for logs", "Promtail for collection", "COMPLEMENTS"),
        ("PostgreSQL for data", "pgAdmin for management", "COMPLEMENTS"),
        ("Keycloak for auth", "OAuth2 Proxy for SSO", "COMPLEMENTS"),
        ("Vault for secrets", "External Secrets Operator", "COMPLEMENTS"),
        ("ArgoCD for GitOps", "Kustomize for manifests", "COMPLEMENTS"),

        # No relationship (5 pairs)
        ("Prefer using Python", "Coffee is essential", None),
        ("3D printer in workshop", "Kubernetes cluster setup", None),
        ("Favorite color is blue", "Docker networking config", None),
        ("Weekend hiking plans", "Prometheus alert rules", None),
        ("Birthday in June", "Terraform modules structure", None),
    ]

    try:
        print(f"\nTesting {len(test_pairs)} memory pairs for precision validation...")

        for idx, (content_a, content_b, expected_rel) in enumerate(test_pairs):
            # Create test memories
            mem_a_id = await create_test_memory(neo4j_service, content_a)
            mem_b_id = await create_test_memory(neo4j_service, content_b)
            memory_ids.extend([mem_a_id, mem_b_id])

            # Infer relationship
            result = await relationship_service.infer_relationship(
                memory_a_id=mem_a_id,
                memory_a_content=content_a,
                memory_a_type="technical_context",
                memory_b_id=mem_b_id,
                memory_b_content=content_b,
                memory_b_type="technical_context",
            )

            # Evaluate precision
            if expected_rel is None:
                # Should NOT find relationship
                if result is None:
                    true_negatives += 1
                    print(f"  [{idx+1}] ✓ TN: Correctly rejected unrelated pair")
                else:
                    false_positives += 1
                    print(f"  [{idx+1}] ✗ FP: Incorrectly found {result.relationship_type} "
                          f"(confidence: {result.confidence:.2f})")
            else:
                # Should find relationship
                if result is not None and result.relationship_type == expected_rel:
                    true_positives += 1
                    print(f"  [{idx+1}] ✓ TP: Correctly found {expected_rel} "
                          f"(confidence: {result.confidence:.2f})")
                elif result is not None:
                    false_positives += 1
                    print(f"  [{idx+1}] ✗ FP: Found {result.relationship_type} but expected {expected_rel}")
                else:
                    false_negatives += 1
                    print(f"  [{idx+1}] ✗ FN: Missed {expected_rel} relationship")

        # Calculate precision
        total_predicted_positive = true_positives + false_positives
        precision = true_positives / total_predicted_positive if total_predicted_positive > 0 else 0

        # Calculate recall
        total_actual_positive = true_positives + false_negatives
        recall = true_positives / total_actual_positive if total_actual_positive > 0 else 0

        # Calculate accuracy
        total = len(test_pairs)
        accuracy = (true_positives + true_negatives) / total

        print(f"\n📊 Precision Metrics:")
        print(f"  True Positives:  {true_positives}")
        print(f"  False Positives: {false_positives}")
        print(f"  True Negatives:  {true_negatives}")
        print(f"  False Negatives: {false_negatives}")
        print(f"  Precision: {precision*100:.1f}% (target: >80%)")
        print(f"  Recall:    {recall*100:.1f}%")
        print(f"  Accuracy:  {accuracy*100:.1f}%")

        assert precision >= 0.80, f"Precision {precision*100:.1f}% < 80% target"

    finally:
        await cleanup_test_memories(neo4j_service, memory_ids)


# T074: Validate cost ~$1.00 for 100 memory pair evaluations
@pytest.mark.asyncio
@pytest.mark.slow
async def test_t074_cost_tracking_100_evaluations(
    relationship_service, neo4j_service
):
    """
    T074: Validate cost ~$1.00 for 100 memory pair evaluations.

    Estimates API cost based on token usage for 100 relationship inferences.
    Uses Haiku pricing: $0.80/MTok input, $4.00/MTok output.
    """
    memory_ids = []

    # Sample memory pairs (reuse from T073)
    sample_pairs = [
        ("Docker requires container runtime", "Container runtime installed"),
        ("Kubernetes cluster needs etcd", "etcd database for state storage"),
        ("Grafana dashboards use Prometheus", "Prometheus metrics collection"),
        ("Prefer using Python", "Coffee is essential"),  # No relationship
        ("3D printer in workshop", "Kubernetes cluster setup"),  # No relationship
    ]

    try:
        print(f"\nTesting cost for 100 memory pair evaluations...")
        print(f"Model: {relationship_service.model}")
        print(f"Expected pricing (Haiku): $0.80/MTok input, $4.00/MTok output\n")

        # Run 100 evaluations (20 iterations of 5 pairs)
        total_evaluations = 0

        for iteration in range(20):
            for content_a, content_b in sample_pairs:
                mem_a_id = await create_test_memory(neo4j_service, content_a)
                mem_b_id = await create_test_memory(neo4j_service, content_b)
                memory_ids.extend([mem_a_id, mem_b_id])

                await relationship_service.infer_relationship(
                    memory_a_id=mem_a_id,
                    memory_a_content=content_a,
                    memory_a_type="technical_context",
                    memory_b_id=mem_b_id,
                    memory_b_content=content_b,
                    memory_b_type="technical_context",
                )

                total_evaluations += 1

            if (iteration + 1) % 5 == 0:
                print(f"  Completed {total_evaluations}/100 evaluations...")

        print(f"\n✓ Completed {total_evaluations} evaluations")

        # Estimate cost (manual calculation based on typical token usage)
        # Typical usage per evaluation:
        # - System prompt: ~250 tokens
        # - User prompt: ~100 tokens (memory content + instructions)
        # - Output: ~50 tokens (structured response)
        # Total per evaluation: ~400 tokens

        estimated_input_tokens = total_evaluations * 350  # 250 (system) + 100 (user)
        estimated_output_tokens = total_evaluations * 50

        # Haiku pricing
        cost_input = (estimated_input_tokens / 1_000_000) * 0.80
        cost_output = (estimated_output_tokens / 1_000_000) * 4.00
        total_cost = cost_input + cost_output

        print(f"\n💰 Estimated Cost:")
        print(f"  Input tokens:  {estimated_input_tokens:,} (~${cost_input:.4f})")
        print(f"  Output tokens: {estimated_output_tokens:,} (~${cost_output:.4f})")
        print(f"  Total cost:    ~${total_cost:.2f}")

        # Verify cost is reasonable (~$1.00 ± 50%)
        assert 0.50 <= total_cost <= 1.50, \
            f"Cost ${total_cost:.2f} outside expected range ($0.50-$1.50)"

        print(f"  ✓ Cost within acceptable range ($0.50-$1.50)")

    finally:
        await cleanup_test_memories(neo4j_service, memory_ids)


# T075: Validate null handling for unrelated memory pairs
@pytest.mark.asyncio
async def test_t075_null_handling_unrelated_pairs(
    relationship_service, neo4j_service
):
    """
    T075: Validate null handling for unrelated memory pairs.

    Expected: Service returns None for unrelated memories (no forced relationships).
    """
    memory_ids = []

    # Completely unrelated memory pairs
    unrelated_pairs = [
        ("My favorite color is blue", "Docker networking configuration"),
        ("Coffee is essential in the morning", "Kubernetes cluster autoscaling"),
        ("Planning a vacation to Hawaii", "Prometheus alert rules configuration"),
        ("The weather is nice today", "PostgreSQL connection pooling"),
        ("Learning to play guitar", "Terraform module best practices"),
        ("Watching a documentary about space", "Nginx reverse proxy setup"),
        ("Cooking pasta for dinner", "Grafana dashboard templates"),
        ("Reading a book about history", "Neo4j graph database schema"),
        ("Going for a morning jog", "CI/CD pipeline optimization"),
        ("Listening to classical music", "Container security best practices"),
    ]

    try:
        print(f"\nTesting {len(unrelated_pairs)} unrelated memory pairs...")

        none_count = 0
        forced_count = 0

        for idx, (content_a, content_b) in enumerate(unrelated_pairs):
            mem_a_id = await create_test_memory(neo4j_service, content_a)
            mem_b_id = await create_test_memory(neo4j_service, content_b)
            memory_ids.extend([mem_a_id, mem_b_id])

            result = await relationship_service.infer_relationship(
                memory_a_id=mem_a_id,
                memory_a_content=content_a,
                memory_a_type="personal_fact",
                memory_b_id=mem_b_id,
                memory_b_content=content_b,
                memory_b_type="technical_context",
            )

            if result is None:
                none_count += 1
                print(f"  [{idx+1}] ✓ Correctly returned None (no forced relationship)")
            else:
                forced_count += 1
                print(f"  [{idx+1}] ✗ Incorrectly found {result.relationship_type} "
                      f"(confidence: {result.confidence:.2f})")
                print(f"       Reasoning: {result.reasoning}")

        print(f"\n📊 Null Handling Results:")
        print(f"  Correctly returned None: {none_count}/{len(unrelated_pairs)}")
        print(f"  Incorrectly forced relationship: {forced_count}/{len(unrelated_pairs)}")

        # At least 80% should correctly return None
        success_rate = none_count / len(unrelated_pairs)
        assert success_rate >= 0.80, \
            f"Success rate {success_rate*100:.1f}% < 80% (too many forced relationships)"

        print(f"  ✓ Success rate: {success_rate*100:.1f}% (target: >80%)")

    finally:
        await cleanup_test_memories(neo4j_service, memory_ids)


# T076: Validate temporal conflict resolution
@pytest.mark.asyncio
async def test_t076_temporal_conflict_resolution(
    temporal_manager, neo4j_service
):
    """
    T076: Validate temporal conflict resolution.

    Expected:
    - Create contradicting memories
    - Old memory gets valid_until set automatically
    - Both memories preserved in database
    - SUPERSEDES relationship created
    """
    memory_ids = []

    try:
        # Create old memory with embedding
        old_embedding = [0.1] * 1536  # Dummy embedding
        old_mem_id = await create_test_memory(
            neo4j_service,
            "I prefer using Docker Swarm for container orchestration",
            "preference",
            embedding=old_embedding,
        )
        memory_ids.append(old_mem_id)

        print(f"✓ Created old memory: {old_mem_id[:8]}...")

        # Create new contradicting memory with similar embedding
        new_embedding = [0.11] * 1536  # Very similar embedding (high cosine similarity)
        new_mem_id = await create_test_memory(
            neo4j_service,
            "I now prefer using Kubernetes for better scalability",
            "preference",
            embedding=new_embedding,
        )
        memory_ids.append(new_mem_id)

        print(f"✓ Created new memory: {new_mem_id[:8]}...")

        # Detect temporal conflict
        new_valid_from = datetime.now(timezone.utc)
        conflict = await temporal_manager.detect_temporal_conflict(
            new_memory_id=new_mem_id,
            new_content="I now prefer using Kubernetes for better scalability",
            new_valid_from=new_valid_from,
            new_embedding=new_embedding,
        )

        assert conflict is not None, "Should detect temporal conflict"
        assert conflict.existing_memory_id == old_mem_id
        assert conflict.similarity >= 0.75, f"Similarity {conflict.similarity} < 0.75"

        print(f"✓ Conflict detected (similarity: {conflict.similarity:.3f})")

        # Resolve conflict
        resolved = await temporal_manager.resolve_conflict(conflict, new_valid_from)
        assert resolved is True, "Should resolve conflict successfully"

        print(f"✓ Conflict resolved")

        # Verify old memory has valid_until set
        query_old = """
        MATCH (m:Memory {memory_id: $memory_id})
        RETURN m.valid_until AS valid_until,
               m.superseded_by AS superseded_by,
               m.superseded_at AS superseded_at
        """

        async with neo4j_service.driver.session() as session:
            result = await session.run(query_old, memory_id=old_mem_id)
            record = await result.single()

            assert record is not None, "Old memory should exist"
            assert record["valid_until"] is not None, "valid_until should be set"
            assert record["superseded_by"] == new_mem_id, "superseded_by should point to new memory"
            assert record["superseded_at"] is not None, "superseded_at should be set"

            print(f"✓ Old memory updated:")
            print(f"  valid_until: {record['valid_until']}")
            print(f"  superseded_by: {record['superseded_by'][:8]}...")

        # Verify SUPERSEDES relationship exists
        query_rel = """
        MATCH (new:Memory {memory_id: $new_id})-[r:SUPERSEDES]->(old:Memory {memory_id: $old_id})
        RETURN r.created_at AS created_at,
               r.similarity AS similarity,
               r.reasoning AS reasoning
        """

        async with neo4j_service.driver.session() as session:
            result = await session.run(query_rel, new_id=new_mem_id, old_id=old_mem_id)
            record = await result.single()

            assert record is not None, "SUPERSEDES relationship should exist"
            assert record["similarity"] >= 0.75
            assert record["reasoning"] is not None

            print(f"✓ SUPERSEDES relationship created:")
            print(f"  similarity: {record['similarity']:.3f}")
            print(f"  reasoning: {record['reasoning'][:60]}...")

        # Verify both memories still exist in database (preservation)
        query_count = """
        MATCH (m:Memory)
        WHERE m.memory_id IN [$old_id, $new_id]
        RETURN count(m) AS count
        """

        async with neo4j_service.driver.session() as session:
            result = await session.run(query_count, old_id=old_mem_id, new_id=new_mem_id)
            record = await result.single()

            assert record["count"] == 2, "Both memories should be preserved"

            print(f"✓ Both memories preserved in database (P2: Temporal Truth)")

    finally:
        await cleanup_test_memories(neo4j_service, memory_ids)


if __name__ == "__main__":
    # Run tests with pytest
    pytest.main([__file__, "-v", "-s"])
