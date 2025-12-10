# Hybrid Temporal Memory System - Enhanced Implementation Plan

**Version:** 2.0 (Principle-Guided)
**Date:** December 10, 2025
**Companion Document:** `memory-system-principles.md` (READ FIRST)

---

## 📘 How to Use This Document

This plan provides **concrete technical specifications** guided by the **immutable principles** and **strong guidelines** defined in `memory-system-principles.md`.

### Legend
- 🔒 **IMMUTABLE** - Must follow principle exactly
- 📐 **GUIDELINE** - Follow unless justified deviation
- 🎨 **FREEDOM** - Developer's choice within constraints
- ⚠️ **DECISION NEEDED** - Apply decision framework

---

## Phase 1: Temporal Foundation & BM25 Search

**Effort:** 5 story points (3-4 days)
**Risk:** Low

### 🔒 Immutable Requirements (Principle-Driven)

#### 1.1 Bi-Temporal Properties (P2: Temporal Truth, G5: Bi-Temporal Tracking)
**Principle:** "Memories capture what was said/believed at a time, not universal truth."

**Implementation:**
```cypher
// database/schema/migrations/010-add-temporal-properties.cypher

// Add temporal properties to Memory nodes
MATCH (m:Memory)
SET m.valid_from = COALESCE(m.valid_from, m.created_at),
    m.valid_until = COALESCE(m.valid_until, null),  // null = still valid
    m.learned_at = COALESCE(m.learned_at, m.extraction_timestamp),
    m.superseded_by = null,
    m.supersedes = COALESCE(m.metadata.supersedes, null);

// Create temporal indexes for time-based queries
CREATE INDEX memory_valid_from IF NOT EXISTS
FOR (m:Memory) ON (m.valid_from);

CREATE INDEX memory_valid_until IF NOT EXISTS
FOR (m:Memory) ON (m.valid_until);

CREATE INDEX memory_learned_at IF NOT EXISTS
FOR (m:Memory) ON (m.learned_at);
```

**Why:** Enables point-in-time queries ("What was my setup in October?") and temporal conflict resolution.

---

#### 1.2 Update ExtractedMemory Model
**File:** `/home/vlb/Python/haia/src/haia/extraction/models.py`

```python
class ExtractedMemory(BaseModel):
    """Memory with bi-temporal tracking."""

    memory_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    memory_type: str  # 🔒 NO LONGER Literal - free-form string (P1)
    content: str
    confidence: float  # 0.4-1.0

    # Temporal properties (P2: Temporal Truth)
    valid_from: datetime | None = Field(
        None,
        description="When this information became true (user's timeline)"
    )
    valid_until: datetime | None = Field(
        None,
        description="When this information stopped being true (null = current)"
    )
    learned_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="When HAIA learned this (system's timeline)"
    )

    # Relationship tracking (for temporal conflicts)
    supersedes: str | None = Field(
        None,
        description="memory_id of memory this replaces"
    )
    superseded_by: str | None = Field(
        None,
        description="memory_id of memory that replaces this"
    )

    # Existing fields...
    source_conversation_id: str
    extraction_timestamp: datetime
    embedding: list[float] | None
    has_embedding: bool
    embedding_version: str | None
    embedding_updated_at: datetime | None
    last_accessed: datetime | None
    access_count: int = 0
```

**Changes:**
- ✅ Removed `Literal` constraint on `memory_type` (P1: Emergence)
- ✅ Added `valid_from`, `valid_until`, `learned_at` (P2: Temporal Truth)
- ✅ Added `supersedes`, `superseded_by` (temporal conflict tracking)

---

### 🎨 Implementation Freedom

#### 1.3 BM25 Search Implementation (F5: BM25 vs rank-bm25)
**Developer's Choice:** Select BM25 implementation based on performance testing.

**Option A: Neo4j Full-Text Index (Recommended Start)**

```cypher
// database/schema/migrations/011-create-bm25-fulltext-index.cypher

// Create full-text index on memory content
CREATE FULLTEXT INDEX memory_content_fulltext IF NOT EXISTS
FOR (m:Memory) ON EACH [m.content]
OPTIONS {indexConfig: {`fulltext.analyzer`: 'english'}};

// Optional: Also index memory_type for type-filtered searches
CREATE FULLTEXT INDEX memory_type_fulltext IF NOT EXISTS
FOR (m:Memory) ON EACH [m.memory_type]
OPTIONS {indexConfig: {`fulltext.analyzer`: 'standard'}};
```

**Python Implementation:**
```python
# src/haia/services/neo4j.py

async def search_memories_bm25(
    self,
    query_text: str,
    top_k: int = 10,
    min_confidence: float = 0.4,
    memory_types: list[str] | None = None,
) -> list[dict[str, Any]]:
    """
    BM25-like full-text search on memory content.

    Args:
        query_text: Search query
        top_k: Number of results
        min_confidence: Minimum extraction confidence
        memory_types: Optional type filter

    Returns:
        List of memory dicts with bm25_score
    """
    if not self.driver:
        raise RuntimeError("Not connected to Neo4j")

    # Build query with optional type filter
    query = """
    CALL db.index.fulltext.queryNodes('memory_content_fulltext', $query_text)
    YIELD node AS memory, score
    WHERE memory.confidence >= $min_confidence
    """

    if memory_types:
        query += " AND memory.memory_type IN $memory_types"

    query += """
    RETURN
      memory.memory_id AS memory_id,
      memory.memory_type AS memory_type,
      memory.content AS content,
      memory.confidence AS confidence,
      memory.valid_from AS valid_from,
      memory.valid_until AS valid_until,
      memory.learned_at AS learned_at,
      score AS bm25_score
    ORDER BY score DESC
    LIMIT $top_k
    """

    try:
        async with self.driver.session() as session:
            result = await session.run(
                query,
                query_text=query_text,
                top_k=top_k,
                min_confidence=min_confidence,
                memory_types=memory_types,
            )
            records = [record.data() async for record in result]
            logger.debug(f"BM25 search found {len(records)} memories")
            return records
    except Exception as e:
        logger.error(f"BM25 search failed: {e}", exc_info=True)
        return []  # Graceful degradation (P4)
```

**Option B: rank-bm25 Library (If Neo4j full-text insufficient)**
- See `docs/architecture/bm25-alternatives.md` for implementation
- Requires in-memory index, rebuild on startup
- Pro: True BM25 with tunable k1, b parameters
- Con: Memory overhead, rebuild latency

---

#### 1.4 MemoryStorageService Updates
**File:** `/home/vlb/Python/haia/src/haia/services/memory_storage.py`

```python
async def _store_memory(self, memory: ExtractedMemory) -> bool:
    """
    Store memory with temporal properties.

    🔒 IMMUTABLE: Must track valid_from, valid_until, learned_at (P2)
    """
    query = """
    // Create or merge conversation
    MERGE (c:Conversation {id: $conversation_id})
    ON CREATE SET c.created_at = datetime($extraction_time)

    // Create memory node with temporal properties
    CREATE (m:Memory {
        id: $memory_id,
        type: $memory_type,  // 🔒 Free-form string (P1)
        content: $content,
        confidence: $confidence,
        category: $category,
        created_at: datetime($extraction_time),

        // Temporal properties (P2)
        valid_from: datetime($valid_from),
        valid_until: CASE WHEN $valid_until IS NULL THEN null ELSE datetime($valid_until) END,
        learned_at: datetime($learned_at),
        supersedes: $supersedes,
        superseded_by: $superseded_by
    })

    // Link to conversation
    CREATE (c)-[:CONTAINS_MEMORY]->(m)

    // Link to superseded memory if applicable
    WITH m
    WHERE $supersedes IS NOT NULL
    MATCH (old:Memory {id: $supersedes})
    SET old.superseded_by = $memory_id,
        old.valid_until = datetime($learned_at)  // Temporal invalidation
    CREATE (m)-[:SUPERSEDES]->(old)

    RETURN m.id as memory_id
    """

    try:
        async with self.driver.session() as session:
            await session.run(
                query,
                memory_id=memory.memory_id,
                memory_type=memory.memory_type,  # 🔒 No enum constraint
                content=memory.content,
                confidence=memory.confidence,
                category=memory.category,
                conversation_id=memory.source_conversation_id,
                extraction_time=memory.extraction_timestamp.isoformat(),
                valid_from=memory.valid_from.isoformat() if memory.valid_from else memory.learned_at.isoformat(),
                valid_until=memory.valid_until.isoformat() if memory.valid_until else None,
                learned_at=memory.learned_at.isoformat(),
                supersedes=memory.supersedes,
                superseded_by=memory.superseded_by,
            )
            logger.info(f"Stored memory {memory.memory_id} (type: {memory.memory_type})")
            return True
    except Exception as e:
        logger.error(f"Failed to store memory: {e}", exc_info=True)
        return False
```

---

### 📐 Configuration (Guideline)

```bash
# config.py additions

# BM25 Search
BM25_SEARCH_ENABLED=True              # 📐 Enable by default (G2)
BM25_MIN_SCORE=0.1                    # 🎨 Tune based on testing (F5)

# Temporal Queries
TEMPORAL_QUERIES_ENABLED=True         # 🔒 Required for P2
DEFAULT_TEMPORAL_QUERY_MODE="current" # "current" | "at_time" | "all"
```

---

### ✅ Acceptance Criteria

- [ ] Temporal properties added to all Memory nodes
- [ ] BM25 full-text index created and functional
- [ ] `search_memories_bm25()` returns relevant results for test queries
- [ ] Temporal queries work: "Show memories valid on 2024-10-01"
- [ ] Superseding logic correctly invalidates old memories
- [ ] BM25 search gracefully falls back on failure (P4)
- [ ] All decisions logged (P5: Observability)

---

## Phase 2: Dynamic Schema - LLM Entity Extraction

**Effort:** 13 story points (8-10 days)
**Risk:** Medium

### 🔒 Immutable Requirements (Principle-Driven)

#### 2.1 Remove All Hardcoded Categories (P1: Emergence Over Prescription)
**Principle:** "Structure emerges from data, not from predefined schemas."

**Files to Modify:**

**A. extraction/models.py** (Line 15-23, 77-79)
```python
# ❌ DELETE THIS:
class MemoryCategory(str, Enum):
    PREFERENCE = "preference"
    PERSONAL_FACT = "personal_fact"
    TECHNICAL_CONTEXT = "technical_context"
    DECISION = "decision"
    CORRECTION = "correction"

# ❌ DELETE THIS:
memory_type: Literal["preference", "personal_fact", ...] = Field(...)

# ✅ REPLACE WITH:
memory_type: str = Field(
    ...,
    min_length=1,
    max_length=100,
    description="LLM-generated entity type (e.g., 'docker_container_preference')"
)
```

**B. config.py** (Lines 138-167)
```python
# ❌ DELETE THESE (type-specific weights):
memory_type_weight_preference: float = Field(1.2, ...)
memory_type_weight_technical_context: float = Field(1.1, ...)
# ... etc

# ✅ REPLACE WITH (semantic weights):
# Type weights now learned from clustering, not hardcoded
type_weight_learning_enabled: bool = Field(True, ...)
default_type_weight: float = Field(1.0, ...)  # Fallback for unclustered types
```

**C. services/neo4j.py** (Lines 116-124, repeated in 8 methods)
```python
# ❌ DELETE THIS (hardcoded ID mapping):
id_field_map = {
    "Person": "user_id",
    "Interest": "interest_id",
    # ...
}

# ✅ REPLACE WITH (dynamic property detection):
def _get_id_property(self, label: str) -> str:
    """
    Infer ID property from node label.

    🔒 IMMUTABLE: Must not hardcode label→property mappings (P1)

    Convention: {label}_id (lowercased) or fallback to 'id'
    """
    # Try convention first
    conventional_prop = f"{label.lower()}_id"

    # If node exists with this property, use it
    # Otherwise, fall back to generic 'id'
    return conventional_prop if self._property_exists(label, conventional_prop) else "id"
```

---

#### 2.2 Dynamic Extraction Prompt (P1: Emergence)

**File:** `/home/vlb/Python/haia/src/haia/extraction/prompts.py`

```python
def system_prompt() -> str:
    """
    System prompt for LLM memory extraction.

    🔒 IMMUTABLE: Must allow infinite entity types (P1)
    📐 GUIDELINE: Encourage specificity, reward descriptive types (G4)
    """
    return """
You are a memory extraction specialist for HAIA, a homelab AI assistant.

## Task
Extract factual memories from conversation transcripts.
Create specific, descriptive memory types that capture the user's vocabulary.

## Memory Type Guidelines
🔒 DO NOT limit yourself to predefined categories.
Create types that precisely describe the content.

### Good Examples:
- "docker_container_deployment_preference"
- "proxmox_cluster_storage_configuration"
- "backup_strategy_architecture_decision"
- "kubernetes_migration_correction"
- "monitoring_tool_evaluation"

### Bad Examples:
- "preference" (too vague)
- "thing" (meaningless)
- "docker" (incomplete - docker what?)

### Specificity Levels:
1. **Best:** Captures domain + aspect + type
   - "container_runtime_tool_preference"
   - "virtualization_platform_configuration"

2. **Good:** Captures domain + type
   - "docker_preference"
   - "proxmox_setup"

3. **Acceptable:** Captures type with context
   - "deployment_preference"
   - "infrastructure_decision"

## Temporal Awareness (P2)
If user mentions WHEN something was true, extract temporal bounds:

User: "I migrated to Docker in October 2024"
→ valid_from: "2024-10-01"

User: "I used Kubernetes until last month" (current date: 2024-12-10)
→ valid_from: Unknown, valid_until: "2024-11-01"

## Confidence Scoring (G4)
- 0.8-1.0: Explicit, direct statements
- 0.6-0.7: Strong implications or repeated mentions
- 0.4-0.5: Reasonable inferences from context
- <0.4: Do NOT extract (insufficient evidence)

## Output Format
Return JSON with:
{
  "memories": [
    {
      "memory_type": "specific_descriptive_type",
      "content": "Third-person summary",
      "confidence": 0.85,
      "valid_from": "2024-10-01" or null,
      "valid_until": null (or date if no longer true),
      "supersedes": "memory_id" (if this corrects previous memory)
    }
  ]
}
"""
```

**Why This Works:**
- ✅ No hardcoded categories (P1)
- ✅ Encourages specificity (prevents type explosion)
- ✅ Temporal awareness (P2)
- ✅ High confidence bar (G4)

---

### 📐 Strong Guidelines

#### 2.3 Semantic Type Clustering (G1: Semantic Clustering for Consistency)

**New Service:** `/home/vlb/Python/haia/src/haia/clustering/type_clusterer.py`

```python
"""
Semantic clustering of memory types to prevent proliferation.

🔒 IMMUTABLE: Types emerge freely, clustering organizes (P1)
📐 GUIDELINE: Cluster when 3+ similar types exist (G1)
"""

from sklearn.cluster import DBSCAN
from sentence_transformers import SentenceTransformer
import numpy as np

class TypeClusterer:
    """
    Clusters semantically similar memory types.

    Approach:
    1. LLM generates any type it wants (no constraints)
    2. System groups similar types via embedding similarity
    3. LLM generates human-readable cluster labels
    4. Retrieval expands queries to include cluster members
    """

    def __init__(
        self,
        neo4j_service: Neo4jService,
        ollama_client: OllamaClient,
        extraction_model: str = "anthropic:claude-haiku-4-5-20251001",
        min_cluster_size: int = 3,  # 📐 G1: Min 3 types
        similarity_threshold: float = 0.80,  # 📐 G1: Cosine similarity
    ):
        self.neo4j = neo4j_service
        self.ollama = ollama_client
        self.extraction_model = extraction_model
        self.min_cluster_size = min_cluster_size
        self.similarity_threshold = similarity_threshold

        # Sentence transformer for type embeddings
        self.type_encoder = SentenceTransformer('all-MiniLM-L6-v2')  # Fast, efficient

    async def cluster_all_types(self) -> list[TypeCluster]:
        """
        Cluster all memory types in database.

        Returns:
            List of TypeCluster objects with labels
        """
        # 1. Get all unique types from Neo4j
        types = await self._get_all_types()
        if len(types) < self.min_cluster_size:
            logger.info(f"Only {len(types)} types, skipping clustering")
            return []

        # 2. Generate embeddings for type names
        type_embeddings = self.type_encoder.encode(types)

        # 3. DBSCAN clustering (eps calculated from similarity threshold)
        # eps = 1 - similarity_threshold (for cosine distance)
        eps = 1.0 - self.similarity_threshold
        clusterer = DBSCAN(
            eps=eps,
            min_samples=self.min_cluster_size,
            metric='cosine'
        )
        cluster_labels = clusterer.fit_predict(type_embeddings)

        # 4. Group types by cluster
        clusters = {}
        for type_name, cluster_id in zip(types, cluster_labels):
            if cluster_id == -1:  # Noise point
                continue
            if cluster_id not in clusters:
                clusters[cluster_id] = []
            clusters[cluster_id].append(type_name)

        # 5. Generate LLM summaries for each cluster
        type_clusters = []
        for cluster_id, type_names in clusters.items():
            summary = await self._generate_cluster_label(type_names)
            type_clusters.append(TypeCluster(
                cluster_id=f"type_cluster_{cluster_id}",
                member_types=type_names,
                label=summary,
                created_at=datetime.utcnow(),
            ))

        logger.info(f"Created {len(type_clusters)} type clusters from {len(types)} types")
        return type_clusters

    async def find_semantic_neighbors(
        self,
        memory_type: str,
        threshold: float = 0.80
    ) -> list[tuple[str, float]]:
        """
        Find types semantically similar to given type.

        Used during retrieval to expand query.

        Returns:
            List of (type_name, similarity_score) tuples
        """
        # Get all types and their embeddings
        types = await self._get_all_types()
        type_embeddings = self.type_encoder.encode(types)

        # Encode query type
        query_embedding = self.type_encoder.encode([memory_type])[0]

        # Calculate cosine similarities
        from sklearn.metrics.pairwise import cosine_similarity
        similarities = cosine_similarity([query_embedding], type_embeddings)[0]

        # Filter by threshold, sort by similarity
        neighbors = [
            (types[i], float(sim))
            for i, sim in enumerate(similarities)
            if sim >= threshold and types[i] != memory_type
        ]
        neighbors.sort(key=lambda x: x[1], reverse=True)

        return neighbors[:10]  # Top 10 neighbors

    async def _generate_cluster_label(self, type_names: list[str]) -> str:
        """
        Generate human-readable label for type cluster using LLM.

        🎨 FREEDOM: Prompt design is developer's choice (F4)
        """
        prompt = f"""
Generate a concise, descriptive label for this group of related memory types:

Types: {', '.join(type_names)}

Requirements:
- 2-4 words maximum
- Captures common theme
- Human-readable
- Title case

Examples:
- "Container Runtime Tools"
- "Infrastructure Configuration"
- "Deployment Preferences"

Label:
"""

        # Use Haiku for cost efficiency
        from pydantic_ai import Agent

        agent = Agent[None, str](
            model=self.extraction_model,
            output_type=str,
            system_prompt="You generate concise category labels.",
        )

        result = await agent.run(prompt)
        label = result.output.strip().strip('"').strip("'")

        logger.debug(f"Generated cluster label: {label} for {len(type_names)} types")
        return label

    async def _get_all_types(self) -> list[str]:
        """Get all unique memory types from Neo4j."""
        query = """
        MATCH (m:Memory)
        RETURN DISTINCT m.memory_type AS type
        ORDER BY type
        """
        async with self.neo4j.driver.session() as session:
            result = await session.run(query)
            types = [record["type"] async for record in result]
        return types


class TypeCluster(BaseModel):
    """Cluster of semantically similar memory types."""

    cluster_id: str
    member_types: list[str]
    label: str  # Human-readable label (LLM-generated)
    created_at: datetime

    @property
    def size(self) -> int:
        return len(self.member_types)
```

---

#### 2.4 Relationship Inference Service (P1: Emergence)

**New Service:** `/home/vlb/Python/haia/src/haia/services/relationship_inference.py`

```python
"""
LLM-driven relationship inference between memories.

🔒 IMMUTABLE: Relationships emerge from context, not predefined (P1)
📐 GUIDELINE: Require high confidence (0.7+) for relationships (G4)
"""

from pydantic import BaseModel, Field
from pydantic_ai import Agent

class InferredRelationship(BaseModel):
    """Relationship inferred by LLM."""

    from_memory_id: str
    to_memory_id: str
    relationship_type: str = Field(
        ...,
        min_length=1,
        max_length=50,
        description="Uppercase, snake_case (e.g., 'DEPENDS_ON')"
    )
    confidence: float = Field(..., ge=0.0, le=1.0)
    reasoning: str = Field(..., description="Why this relationship exists")
    temporal_bounds: tuple[datetime | None, datetime | None] | None = None


class RelationshipInferenceService:
    """
    Infers relationships between memories using LLM.

    Approach:
    1. Candidate generation: Find memories from same conversation or with content overlap
    2. LLM evaluation: Ask "are these related? how?"
    3. Confidence threshold: Only create relationships with confidence >= 0.7
    4. Temporal tracking: Relationships can be time-bound
    """

    def __init__(
        self,
        model: str = "anthropic:claude-haiku-4-5-20251001",
        min_confidence: float = 0.7,  # 📐 G4: High confidence for dynamic structures
    ):
        self.model = model
        self.min_confidence = min_confidence

        # PydanticAI agent for relationship inference
        self.agent = Agent[None, InferredRelationship | None](
            model=model,
            output_type=InferredRelationship | None,
            system_prompt=self._relationship_prompt(),
        )

    async def infer_relationships(
        self,
        memories: list[ExtractedMemory]
    ) -> list[InferredRelationship]:
        """
        Infer relationships between memories.

        Args:
            memories: List of memories from same conversation

        Returns:
            List of inferred relationships (confidence >= min_confidence)
        """
        relationships = []

        # Pairwise comparison (O(n²), but n typically small in one conversation)
        for i, mem_a in enumerate(memories):
            for mem_b in memories[i+1:]:
                # Ask LLM if these are related
                relationship = await self._evaluate_pair(mem_a, mem_b)

                if relationship and relationship.confidence >= self.min_confidence:
                    relationships.append(relationship)
                    logger.info(
                        f"Inferred relationship: {mem_a.memory_type} "
                        f"-[{relationship.relationship_type}]-> {mem_b.memory_type} "
                        f"(confidence: {relationship.confidence:.2f})"
                    )

        return relationships

    async def _evaluate_pair(
        self,
        mem_a: ExtractedMemory,
        mem_b: ExtractedMemory,
    ) -> InferredRelationship | None:
        """
        Evaluate if two memories are related.

        🎨 FREEDOM: Prompt design is developer's choice (F2)
        """
        user_prompt = f"""
Analyze these two memories and determine if they are related:

Memory A:
- Type: {mem_a.memory_type}
- Content: {mem_a.content}
- Valid: {mem_a.valid_from} to {mem_a.valid_until or "present"}

Memory B:
- Type: {mem_b.memory_type}
- Content: {mem_b.content}
- Valid: {mem_b.valid_from} to {mem_b.valid_until or "present"}

If related, suggest a relationship type and explain why.

Common relationship types (but feel free to create new ones):
- DEPENDS_ON: B requires A to function
- REPLACED_BY: A was replaced by B
- SUPERSEDES: B overrides/corrects A
- CONTRADICTS: A and B conflict
- INSPIRED_BY: B was influenced by A
- COMPLEMENTS: A and B work together
- PART_OF: A is component of B

If unrelated, return null.
"""

        try:
            result = await self.agent.run(user_prompt)
            return result.output
        except Exception as e:
            logger.error(f"Relationship inference failed: {e}", exc_info=True)
            return None  # Graceful degradation (P4)

    @staticmethod
    def _relationship_prompt() -> str:
        """System prompt for relationship inference."""
        return """
You are a relationship inference specialist.

Your job: Determine if two memories are meaningfully related.

Guidelines:
- Be conservative: Only infer clear, meaningful relationships
- Confidence >= 0.7 for strong relationships
- Confidence 0.5-0.7 for possible relationships
- Confidence < 0.5 means unrelated (return null)
- Relationship types should be UPPERCASE_SNAKE_CASE
- Provide clear reasoning

Output format:
{
  "from_memory_id": "mem_123",
  "to_memory_id": "mem_456",
  "relationship_type": "DEPENDS_ON",
  "confidence": 0.85,
  "reasoning": "Docker setup requires Proxmox cluster to run containers"
}

Or null if unrelated.
"""
```

---

### 🔒 Temporal Conflict Resolution (P2: Temporal Truth)

**New Service:** `/home/vlb/Python/haia/src/haia/services/temporal_manager.py`

```python
"""
Temporal conflict resolution for memories.

🔒 IMMUTABLE: Never delete contradictory memories, mark temporal bounds (P2)
"""

class TemporalManager:
    """
    Manages temporal conflicts between memories.

    Principle: Memories capture what was said/believed at a time, not universal truth.

    When contradiction detected:
    1. Old memory: Set valid_until = new_memory.learned_at
    2. New memory: Set supersedes = old_memory.memory_id
    3. Create SUPERSEDES relationship
    4. Both memories remain in database
    """

    def __init__(self, neo4j_service: Neo4jService):
        self.neo4j = neo4j_service

    async def handle_contradiction(
        self,
        new_memory: ExtractedMemory,
        contradicting_memories: list[ExtractedMemory],
    ) -> None:
        """
        Handle temporal contradiction.

        🔒 IMMUTABLE: Must preserve old memories with temporal bounds (P2)

        Args:
            new_memory: Newly extracted memory
            contradicting_memories: Existing memories that contradict new one
        """
        for old_memory in contradicting_memories:
            # Mark old memory as superseded
            await self.neo4j.update_node(
                label="Memory",
                node_id=old_memory.memory_id,
                properties={
                    "valid_until": new_memory.learned_at.isoformat(),
                    "superseded_by": new_memory.memory_id,
                }
            )

            # Create SUPERSEDES relationship
            await self.neo4j.create_relationship(
                from_label="Memory",
                from_id=new_memory.memory_id,
                rel_type="SUPERSEDES",
                to_label="Memory",
                to_id=old_memory.memory_id,
                properties={
                    "superseded_at": new_memory.learned_at.isoformat(),
                    "reason": "temporal_correction",
                }
            )

            logger.info(
                f"Temporal resolution: {new_memory.memory_id} SUPERSEDES {old_memory.memory_id} "
                f"(old valid_until set to {new_memory.learned_at})"
            )

    async def detect_contradictions(
        self,
        new_memory: ExtractedMemory,
        existing_memories: list[ExtractedMemory],
    ) -> list[ExtractedMemory]:
        """
        Detect if new memory contradicts existing memories.

        🎨 FREEDOM: Contradiction detection algorithm (F2)

        Options:
        1. Semantic similarity + opposite sentiment
        2. LLM-based contradiction detection
        3. Keyword-based heuristics

        Returns:
            List of contradicting memories
        """
        # 🎨 Simple implementation: delegate to LLM
        # Developer can optimize this later

        contradictions = []
        for existing in existing_memories:
            if await self._are_contradictory(new_memory, existing):
                contradictions.append(existing)

        return contradictions

    async def _are_contradictory(
        self,
        mem_a: ExtractedMemory,
        mem_b: ExtractedMemory,
    ) -> bool:
        """
        Check if two memories contradict each other.

        🎨 FREEDOM: Implementation choice
        """
        # Quick heuristic: same type, different content, temporal overlap
        if mem_a.memory_type != mem_b.memory_type:
            return False

        # Check temporal overlap
        if not self._temporal_overlap(mem_a, mem_b):
            return False  # Different time periods, not contradictory

        # Semantic similarity check (high similarity = likely about same thing)
        if mem_a.embedding and mem_b.embedding:
            similarity = cosine_similarity(mem_a.embedding, mem_b.embedding)
            if similarity < 0.75:
                return False  # Different topics

        # If high similarity but different content, likely contradiction
        # (e.g., "3 nodes" vs "4 nodes")
        return True

    @staticmethod
    def _temporal_overlap(mem_a: ExtractedMemory, mem_b: ExtractedMemory) -> bool:
        """Check if two memories have overlapping temporal validity."""
        a_start = mem_a.valid_from or mem_a.learned_at
        a_end = mem_a.valid_until or datetime.max
        b_start = mem_b.valid_from or mem_b.learned_at
        b_end = mem_b.valid_until or datetime.max

        # Check for any overlap
        return max(a_start, b_start) < min(a_end, b_end)
```

---

### ✅ Acceptance Criteria

- [ ] MemoryCategory enum completely removed (P1)
- [ ] LLM generates diverse, specific memory types (95%+ are descriptive)
- [ ] Type clustering groups similar types (validated manually)
- [ ] Relationship inference creates meaningful connections (precision >80%)
- [ ] Temporal conflicts resolved correctly (old memories preserved)
- [ ] All hardcoded type weights removed from config
- [ ] Dynamic id_property detection works for all node types
- [ ] Extraction prompt encourages specificity (test with sample conversations)
- [ ] Type cluster labels are human-readable (manual review)

---

## Phase 3: Hybrid Retrieval (Vector + BM25 + Graph)

**Effort:** 8 story points (5-6 days)
**Risk:** Medium

### 🔒 Immutable Requirements (Principle-Driven)

#### 3.1 Semantic Retrieval Foundation (P3: Semantic Retrieval)
**Principle:** "Retrieval finds meaning, not exact matches."

**Implementation:**
All three retrieval methods (vector, BM25, graph) must:
- ✅ Support semantic query expansion (find related types via clustering)
- ✅ Return confidence scores for each result
- ✅ Handle temporal filtering (e.g., "memories valid on 2024-10-01")
- ✅ Gracefully degrade if method fails (P4)

---

#### 3.2 RRF Merger Implementation (G2: Hybrid Retrieval)

**New Service:** `/home/vlb/Python/haia/src/haia/retrieval/rrf_merger.py`

```python
"""
Reciprocal Rank Fusion (RRF) for combining retrieval methods.

🔒 IMMUTABLE: Must combine all available methods (P3)
📐 GUIDELINE: Start with vector=1.0, BM25=0.8, graph=0.6, tune empirically (G2)
🎨 FREEDOM: RRF constant k (F5)
"""

from typing import TypedDict
from collections import defaultdict

class RankedResult(TypedDict):
    memory_id: str
    score: float
    source: str  # "vector" | "bm25" | "graph"
    rank: int

class RRFMerger:
    """
    Reciprocal Rank Fusion for merging retrieval results.

    Formula: RRF_score(d) = Σ[1 / (k + rank(d))] across all methods
    where k is a constant (typically 60) to reduce impact of high ranks
    """

    def __init__(
        self,
        vector_weight: float = 1.0,   # 📐 G2: Default weights
        bm25_weight: float = 0.8,
        graph_weight: float = 0.6,
        k: int = 60,                  # 🎨 F5: RRF constant (tunable)
    ):
        self.weights = {
            "vector": vector_weight,
            "bm25": bm25_weight,
            "graph": graph_weight,
        }
        self.k = k

    def merge(
        self,
        vector_results: list[dict[str, Any]],
        bm25_results: list[dict[str, Any]],
        graph_results: list[dict[str, Any]],
        top_k: int = 10,
    ) -> list[dict[str, Any]]:
        """
        Merge results from multiple retrieval methods using RRF.

        Args:
            vector_results: Results from vector search (with 'memory_id', 'score')
            bm25_results: Results from BM25 search
            graph_results: Results from graph traversal
            top_k: Number of final results

        Returns:
            Merged results sorted by RRF score
        """
        # Calculate RRF scores for each memory
        rrf_scores = defaultdict(float)
        source_info = {}  # Track which methods contributed

        # Process each method's results
        for source, results, weight in [
            ("vector", vector_results, self.weights["vector"]),
            ("bm25", bm25_results, self.weights["bm25"]),
            ("graph", graph_results, self.weights["graph"]),
        ]:
            if not results:
                logger.debug(f"{source} returned no results")
                continue

            for rank, result in enumerate(results, start=1):
                memory_id = result["memory_id"]

                # RRF formula: weight / (k + rank)
                rrf_contribution = weight / (self.k + rank)
                rrf_scores[memory_id] += rrf_contribution

                # Track source contribution
                if memory_id not in source_info:
                    source_info[memory_id] = {
                        "sources": [],
                        "original_scores": {},
                        "ranks": {},
                    }
                source_info[memory_id]["sources"].append(source)
                source_info[memory_id]["original_scores"][source] = result.get("score", 0)
                source_info[memory_id]["ranks"][source] = rank

        # Sort by RRF score
        ranked_memories = sorted(
            rrf_scores.items(),
            key=lambda x: x[1],
            reverse=True
        )[:top_k]

        # Build final results with metadata
        merged_results = []
        for memory_id, rrf_score in ranked_memories:
            # Get full memory data (from any source that has it)
            memory_data = self._get_memory_data(memory_id, vector_results, bm25_results, graph_results)

            if memory_data:
                memory_data["rrf_score"] = float(rrf_score)
                memory_data["retrieval_sources"] = source_info[memory_id]["sources"]
                memory_data["source_scores"] = source_info[memory_id]["original_scores"]
                memory_data["source_ranks"] = source_info[memory_id]["ranks"]
                merged_results.append(memory_data)

        logger.info(
            f"RRF merged {len(vector_results)} vector + {len(bm25_results)} BM25 + "
            f"{len(graph_results)} graph → {len(merged_results)} results"
        )

        return merged_results

    @staticmethod
    def _get_memory_data(
        memory_id: str,
        *result_lists: list[dict[str, Any]]
    ) -> dict[str, Any] | None:
        """Find memory data from any result list."""
        for results in result_lists:
            for result in results:
                if result["memory_id"] == memory_id:
                    return result.copy()
        return None


# Pydantic models for type safety
class RetrievalResult(BaseModel):
    """Single retrieval result."""
    memory_id: str
    memory_type: str
    content: str
    confidence: float
    score: float  # Method-specific score
    valid_from: datetime | None
    valid_until: datetime | None
    learned_at: datetime

class MergedRetrievalResult(RetrievalResult):
    """Merged result with RRF metadata."""
    rrf_score: float
    retrieval_sources: list[str]  # ["vector", "bm25", "graph"]
    source_scores: dict[str, float]  # {"vector": 0.92, "bm25": 0.78}
    source_ranks: dict[str, int]  # {"vector": 1, "bm25": 3}
```

---

#### 3.3 Graph Traversal (P3: Semantic Retrieval, P4: Graceful Degradation)

**Extend Neo4jService:** `/home/vlb/Python/haia/src/haia/services/neo4j.py`

```python
async def traverse_related_memories(
    self,
    seed_memory_ids: list[str],
    max_hops: int = 2,
    relationship_types: list[str] | None = None,
) -> list[dict[str, Any]]:
    """
    Graph traversal to find related memories.

    🔒 IMMUTABLE: Must gracefully degrade if APOC unavailable (P4)
    📐 GUIDELINE: Default 2-hop traversal (G2)

    Args:
        seed_memory_ids: Starting memories
        max_hops: Maximum relationship hops (1-3)
        relationship_types: Optional filter (e.g., ["DEPENDS_ON", "RELATED_TO"])

    Returns:
        List of related memories with traversal path
    """
    if not self.driver:
        raise RuntimeError("Not connected to Neo4j")

    # Check if APOC is available
    apoc_available = await self._check_apoc()

    if apoc_available:
        return await self._traverse_with_apoc(seed_memory_ids, max_hops, relationship_types)
    else:
        logger.warning("APOC unavailable, using fallback traversal")
        return await self._traverse_fallback(seed_memory_ids, max_hops, relationship_types)

async def _check_apoc(self) -> bool:
    """
    Check if APOC plugin is available.

    🔒 IMMUTABLE: Must check before using APOC (P4)
    """
    try:
        async with self.driver.session() as session:
            result = await session.run("RETURN apoc.version() AS version")
            record = await result.single()
            version = record["version"] if record else None

            if version:
                logger.info(f"APOC version {version} available")
                return True
            return False
    except Exception as e:
        logger.debug(f"APOC check failed: {e}")
        return False

async def _traverse_with_apoc(
    self,
    seed_memory_ids: list[str],
    max_hops: int,
    relationship_types: list[str] | None,
) -> list[dict[str, Any]]:
    """
    Graph traversal using APOC.

    Uses: apoc.path.subgraphAll() for efficient multi-hop traversal
    """
    rel_filter = ">".join(relationship_types) if relationship_types else ">"

    query = f"""
    MATCH (seed:Memory)
    WHERE seed.memory_id IN $seed_ids

    CALL apoc.path.subgraphAll(seed, {{
        maxLevel: $max_hops,
        relationshipFilter: "{rel_filter}",
        labelFilter: "Memory"
    }})
    YIELD nodes, relationships

    UNWIND nodes AS related
    WHERE related.memory_id <> seed.memory_id

    RETURN DISTINCT
      related.memory_id AS memory_id,
      related.memory_type AS memory_type,
      related.content AS content,
      related.confidence AS confidence,
      related.valid_from AS valid_from,
      related.valid_until AS valid_until,
      related.learned_at AS learned_at,
      1.0 / (size([p IN relationships WHERE endNode(p) = related | p]) + 1) AS score
    ORDER BY score DESC
    LIMIT 20
    """

    try:
        async with self.driver.session() as session:
            result = await session.run(
                query,
                seed_ids=seed_memory_ids,
                max_hops=max_hops
            )
            records = [record.data() async for record in result]
            logger.debug(f"APOC traversal found {len(records)} related memories")
            return records
    except Exception as e:
        logger.error(f"APOC traversal failed: {e}", exc_info=True)
        return []

async def _traverse_fallback(
    self,
    seed_memory_ids: list[str],
    max_hops: int,
    relationship_types: list[str] | None,
) -> list[dict[str, Any]]:
    """
    Fallback traversal without APOC.

    🔒 IMMUTABLE: Must provide fallback when APOC unavailable (P4)
    🎨 FREEDOM: Fallback strategy (F2)

    Simple implementation: 1-hop only, less efficient
    """
    if max_hops > 1:
        logger.warning(f"Fallback traversal limited to 1 hop (requested {max_hops})")

    rel_pattern = "|".join(relationship_types) if relationship_types else ""
    rel_clause = f"[r:{rel_pattern}]" if rel_pattern else "[r]"

    query = f"""
    MATCH (seed:Memory)-{rel_clause}-(related:Memory)
    WHERE seed.memory_id IN $seed_ids
      AND related.memory_id <> seed.memory_id

    RETURN DISTINCT
      related.memory_id AS memory_id,
      related.memory_type AS memory_type,
      related.content AS content,
      related.confidence AS confidence,
      related.valid_from AS valid_from,
      related.valid_until AS valid_until,
      related.learned_at AS learned_at,
      0.5 AS score  // Lower score for 1-hop fallback
    LIMIT 20
    """

    try:
        async with self.driver.session() as session:
            result = await session.run(query, seed_ids=seed_memory_ids)
            records = [record.data() async for record in result]
            logger.debug(f"Fallback traversal found {len(records)} related memories (1-hop)")
            return records
    except Exception as e:
        logger.error(f"Fallback traversal failed: {e}", exc_info=True)
        return []
```

---

#### 3.4 Hybrid Retrieval Service (P3: Semantic Retrieval)

**Extend RetrievalService:** `/home/vlb/Python/haia/src/haia/embedding/retrieval_service.py`

```python
async def retrieve_hybrid(
    self,
    query: str,
    top_k: int = 10,
    memory_types: list[str] | None = None,
    temporal_filter: datetime | None = None,
    enable_type_expansion: bool = True,
) -> list[MergedRetrievalResult]:
    """
    Hybrid retrieval: Vector + BM25 + Graph traversal merged via RRF.

    🔒 IMMUTABLE: Must use semantic retrieval (P3)
    📐 GUIDELINE: Run all three methods in parallel (G2)
    🔒 IMMUTABLE: Must gracefully degrade if methods fail (P4)

    Args:
        query: Search query
        top_k: Number of results
        memory_types: Optional type filter
        temporal_filter: Only return memories valid at this time
        enable_type_expansion: Use type clustering for query expansion

    Returns:
        Merged results sorted by RRF score
    """
    # 📐 G1: Semantic type expansion
    expanded_types = memory_types
    if enable_type_expansion and memory_types:
        expanded_types = await self._expand_query_types(memory_types)
        logger.debug(f"Expanded types: {memory_types} → {expanded_types}")

    # Parallel execution of all three methods
    vector_task = self._retrieve_vector(query, top_k * 2, expanded_types, temporal_filter)
    bm25_task = self._retrieve_bm25(query, top_k * 2, expanded_types, temporal_filter)
    graph_task = self._retrieve_graph(query, top_k * 2, expanded_types, temporal_filter)

    # Wait for all methods
    vector_results, bm25_results, graph_results = await asyncio.gather(
        vector_task,
        bm25_task,
        graph_task,
        return_exceptions=True  # Don't fail if one method fails
    )

    # Handle failures gracefully (P4)
    if isinstance(vector_results, Exception):
        logger.error(f"Vector search failed: {vector_results}")
        vector_results = []
    if isinstance(bm25_results, Exception):
        logger.error(f"BM25 search failed: {bm25_results}")
        bm25_results = []
    if isinstance(graph_results, Exception):
        logger.error(f"Graph traversal failed: {graph_results}")
        graph_results = []

    # Check if all methods failed
    if not any([vector_results, bm25_results, graph_results]):
        logger.error("All retrieval methods failed")
        return []

    # Merge using RRF
    rrf_merger = RRFMerger()
    merged = rrf_merger.merge(
        vector_results,
        bm25_results,
        graph_results,
        top_k=top_k
    )

    # Convert to MergedRetrievalResult models
    return [MergedRetrievalResult(**result) for result in merged]

async def _expand_query_types(self, memory_types: list[str]) -> list[str]:
    """
    Expand query types using semantic clustering.

    📐 G1: Semantic type expansion for retrieval
    """
    if not hasattr(self, "type_clusterer"):
        return memory_types  # Clustering not configured

    expanded = set(memory_types)
    for memory_type in memory_types:
        # Find semantic neighbors
        neighbors = await self.type_clusterer.find_semantic_neighbors(
            memory_type,
            threshold=0.80  # 📐 G1: Semantic similarity threshold
        )
        expanded.update([neighbor[0] for neighbor in neighbors[:5]])  # Top 5 neighbors

    return list(expanded)

async def _retrieve_vector(
    self,
    query: str,
    top_k: int,
    memory_types: list[str] | None,
    temporal_filter: datetime | None,
) -> list[dict[str, Any]]:
    """Vector search (existing implementation)."""
    # Use existing vector search from Session 8
    embedding = await self.ollama_client.embed_text(query)
    return await self.neo4j_service.vector_search(
        embedding=embedding,
        top_k=top_k,
        memory_types=memory_types,
        valid_at=temporal_filter,
    )

async def _retrieve_bm25(
    self,
    query: str,
    top_k: int,
    memory_types: list[str] | None,
    temporal_filter: datetime | None,
) -> list[dict[str, Any]]:
    """BM25 full-text search."""
    results = await self.neo4j_service.search_memories_bm25(
        query_text=query,
        top_k=top_k,
        memory_types=memory_types,
    )

    # Apply temporal filter if specified
    if temporal_filter:
        results = [
            r for r in results
            if self._is_valid_at_time(r, temporal_filter)
        ]

    return results

async def _retrieve_graph(
    self,
    query: str,
    top_k: int,
    memory_types: list[str] | None,
    temporal_filter: datetime | None,
) -> list[dict[str, Any]]:
    """
    Graph-based retrieval.

    Strategy:
    1. Find seed memories via vector search (top 3)
    2. Traverse relationships to find related memories
    3. Score by graph distance
    """
    # Get seed memories
    seeds = await self._retrieve_vector(query, top_k=3, memory_types=memory_types, temporal_filter=temporal_filter)
    if not seeds:
        return []

    seed_ids = [s["memory_id"] for s in seeds]

    # Traverse graph
    related = await self.neo4j_service.traverse_related_memories(
        seed_memory_ids=seed_ids,
        max_hops=2,
        relationship_types=None,  # All relationship types
    )

    # Apply temporal filter
    if temporal_filter:
        related = [
            r for r in related
            if self._is_valid_at_time(r, temporal_filter)
        ]

    return related[:top_k]

@staticmethod
def _is_valid_at_time(memory: dict[str, Any], time: datetime) -> bool:
    """Check if memory was valid at specified time."""
    valid_from = memory.get("valid_from")
    valid_until = memory.get("valid_until")

    if valid_from and time < valid_from:
        return False
    if valid_until and time > valid_until:
        return False
    return True
```

---

### 📐 Configuration (Guideline)

```bash
# config.py additions

# Hybrid Retrieval
HYBRID_RETRIEVAL_ENABLED=True          # 📐 G2: Enable by default
HYBRID_VECTOR_WEIGHT=1.0               # 📐 G2: Baseline
HYBRID_BM25_WEIGHT=0.8                 # 📐 G2: Slightly lower
HYBRID_GRAPH_WEIGHT=0.6                # 📐 G2: Context discovery
HYBRID_RRF_K=60                        # 🎨 F5: RRF constant

# Type Expansion
TYPE_EXPANSION_ENABLED=True            # 📐 G1: Semantic clustering
TYPE_EXPANSION_SIMILARITY=0.80         # 📐 G1: Neighbor threshold
TYPE_EXPANSION_MAX_NEIGHBORS=5         # 🎨 F5: Max neighbors per type

# Graph Traversal
GRAPH_TRAVERSAL_MAX_HOPS=2             # 📐 G2: 2-hop default
GRAPH_TRAVERSAL_REQUIRE_APOC=False     # 🔒 P4: Fallback allowed
```

---

### 🚀 Docker Compose Updates (APOC Plugin)

**File:** `/home/vlb/Python/haia/deployment/docker-compose.yml`

```yaml
services:
  neo4j:
    image: neo4j:5.15
    environment:
      - NEO4J_AUTH=neo4j/${NEO4J_PASSWORD}
      - NEO4J_PLUGINS=["apoc"]  # 🔒 Enable APOC plugin
      - NEO4J_dbms_security_procedures_unrestricted=apoc.*
      - NEO4J_dbms_security_procedures_allowlist=apoc.*
    volumes:
      - neo4j-data:/data
      - neo4j-logs:/logs
      - neo4j-plugins:/plugins  # APOC downloaded here
    ports:
      - "7474:7474"
      - "7687:7687"
```

---

### ✅ Acceptance Criteria

- [ ] RRF merger combines vector + BM25 + graph results correctly
- [ ] Vector search returns baseline results (from Session 8)
- [ ] BM25 search finds keyword matches
- [ ] Graph traversal discovers related memories (2-hop)
- [ ] Type expansion finds semantic neighbors (manual validation)
- [ ] APOC detection works (plugin present vs absent)
- [ ] Fallback traversal works when APOC unavailable
- [ ] All three methods run in parallel (<500ms p95 latency)
- [ ] Graceful degradation when methods fail (logs warning, continues)
- [ ] Temporal filtering works across all methods

---

## Phase 4: Memory Consolidation

**Effort:** 8 story points (5-6 days)
**Risk:** Medium

### 🔒 Immutable Requirements (Principle-Driven)

#### 4.1 Three-Tier Memory System (G3: Conservative Consolidation)
**Guideline:** "Promote aggressively, archive conservatively."

**Tier Definitions:**
1. **Short-term** (<7 days): All newly extracted memories start here
2. **Long-term** (promoted): High-priority memories worth keeping
3. **Archived** (low-priority): Rarely accessed, low confidence, kept for history

**Lifecycle Flow:**
```
Extraction → Short-term (7 days)
              ↓ Priority ≥ 0.7 (promote 30%)
            Long-term (indefinite)
              ↓ Priority < 0.2 (archive 20%)
            Archived (permanent)
```

---

#### 4.2 Priority Scoring (G3: Conservative Consolidation)

**New Service:** `/home/vlb/Python/haia/src/haia/consolidation/models.py`

```python
"""
Memory consolidation models.

📐 GUIDELINE: Priority = 40% access + 30% recency + 30% confidence (G3)
🎨 FREEDOM: Can adjust weights based on user feedback
"""

from pydantic import BaseModel, Field

class MemoryTier(str, Enum):
    """Memory tier classification."""
    SHORT_TERM = "short_term"    # <7 days
    LONG_TERM = "long_term"      # Promoted
    ARCHIVED = "archived"        # Low priority

class ConsolidationMetrics(BaseModel):
    """Metrics for consolidation decision."""
    access_frequency: float = Field(..., ge=0.0, le=1.0, description="Normalized access count")
    recency_score: float = Field(..., ge=0.0, le=1.0, description="Time-based decay")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Extraction confidence")
    priority_score: float = Field(..., ge=0.0, le=1.0, description="Weighted combination")

class ConsolidationDecision(BaseModel):
    """Consolidation decision for a memory."""
    memory_id: str
    current_tier: MemoryTier
    recommended_tier: MemoryTier
    metrics: ConsolidationMetrics
    reasoning: str  # 🔒 P5: Observability

class ConsolidationReport(BaseModel):
    """Daily consolidation report."""
    timestamp: datetime
    processed_count: int
    promoted_count: int
    archived_count: int
    unchanged_count: int
    decisions: list[ConsolidationDecision]
```

---

#### 4.3 Decay Algorithm (F3: Implementation Freedom)

**New Service:** `/home/vlb/Python/haia/src/haia/consolidation/decay.py`

```python
"""
Memory decay algorithms.

🎨 FREEDOM: Choice of decay function (F3)
📐 GUIDELINE: Use access-based adaptive decay (G3)
"""

import math
from datetime import datetime, timedelta

class DecayStrategy:
    """Base class for decay strategies."""

    def calculate_recency_score(
        self,
        learned_at: datetime,
        current_time: datetime,
        access_count: int = 0
    ) -> float:
        """
        Calculate recency score (0.0 to 1.0).

        Args:
            learned_at: When memory was learned
            current_time: Current timestamp
            access_count: Number of times accessed (for adaptive decay)

        Returns:
            Recency score (1.0 = very recent, 0.0 = very old)
        """
        raise NotImplementedError

class ExponentialDecay(DecayStrategy):
    """
    Exponential decay with adaptive half-life.

    🎨 FREEDOM: This is recommended, but developer can choose others (F3)
    """

    def __init__(self, base_half_life_days: float = 43.3):  # ~6 weeks
        """
        Args:
            base_half_life_days: Half-life for unaccessed memories
        """
        self.base_half_life_days = base_half_life_days

    def calculate_recency_score(
        self,
        learned_at: datetime,
        current_time: datetime,
        access_count: int = 0
    ) -> float:
        """
        Exponential decay with access-based adaptation.

        Formula: score = e^(-λt)
        where λ = ln(2) / half_life

        Adaptive: Frequently accessed memories decay slower
        half_life_effective = base_half_life * (1 + log(1 + access_count))
        """
        days_old = (current_time - learned_at).days

        # Adaptive half-life: more accesses = slower decay
        access_multiplier = 1 + math.log(1 + access_count)
        effective_half_life = self.base_half_life_days * access_multiplier

        # Exponential decay
        decay_rate = math.log(2) / effective_half_life
        recency_score = math.exp(-decay_rate * days_old)

        return max(0.0, min(1.0, recency_score))  # Clamp to [0, 1]

class EbbinghausDecay(DecayStrategy):
    """
    Ebbinghaus forgetting curve.

    🎨 FREEDOM: Alternative to exponential decay (F3)

    Formula: R = (100 * (1 + 1.84 * t))^-1.25
    where t = time in days
    """

    def calculate_recency_score(
        self,
        learned_at: datetime,
        current_time: datetime,
        access_count: int = 0
    ) -> float:
        days_old = (current_time - learned_at).days

        # Ebbinghaus formula
        retention = 100 * ((1 + 1.84 * days_old) ** -1.25)

        # Access boost: each access adds 10% retention
        access_boost = min(access_count * 0.10, 0.50)  # Max 50% boost
        retention = min(retention + retention * access_boost, 100.0)

        return retention / 100.0  # Normalize to [0, 1]

class LinearDecay(DecayStrategy):
    """
    Simple linear decay.

    🎨 FREEDOM: Simplest option, less realistic (F3)
    """

    def __init__(self, decay_days: int = 90):
        """
        Args:
            decay_days: Days until score reaches 0
        """
        self.decay_days = decay_days

    def calculate_recency_score(
        self,
        learned_at: datetime,
        current_time: datetime,
        access_count: int = 0
    ) -> float:
        days_old = (current_time - learned_at).days

        if days_old >= self.decay_days:
            return 0.0

        # Linear decay
        score = 1.0 - (days_old / self.decay_days)

        # Access boost
        access_multiplier = 1 + (access_count * 0.05)
        score = min(score * access_multiplier, 1.0)

        return score
```

---

#### 4.4 Consolidator Service (G3: Conservative Consolidation)

**New Service:** `/home/vlb/Python/haia/src/haia/consolidation/consolidator.py`

```python
"""
Memory consolidation orchestrator.

📐 GUIDELINE: Promote at 0.7, archive at 0.2 (G3)
🔒 IMMUTABLE: Must log all decisions (P5)
"""

class MemoryConsolidator:
    """
    Manages memory lifecycle: short-term → long-term → archived.
    """

    def __init__(
        self,
        neo4j_service: Neo4jService,
        decay_strategy: DecayStrategy = ExponentialDecay(),
        promotion_threshold: float = 0.7,    # 📐 G3: Conservative
        archival_threshold: float = 0.2,     # 📐 G3: Very conservative
        access_weight: float = 0.40,         # 📐 G3: Priority formula
        recency_weight: float = 0.30,
        confidence_weight: float = 0.30,
    ):
        self.neo4j = neo4j_service
        self.decay_strategy = decay_strategy
        self.promotion_threshold = promotion_threshold
        self.archival_threshold = archival_threshold
        self.weights = {
            "access": access_weight,
            "recency": recency_weight,
            "confidence": confidence_weight,
        }

    async def consolidate_daily(self) -> ConsolidationReport:
        """
        Daily consolidation run.

        🔒 IMMUTABLE: Must be scheduled (called by APScheduler) (G3)

        Process:
        1. Get all short-term memories (>7 days old)
        2. Calculate priority scores
        3. Promote high-priority (>0.7) to long-term
        4. Get all long-term memories
        5. Archive low-priority (<0.2) to archived

        Returns:
            Consolidation report with all decisions
        """
        current_time = datetime.utcnow()
        decisions = []

        # Step 1: Process short-term memories
        short_term_memories = await self._get_tier_memories(MemoryTier.SHORT_TERM)
        logger.info(f"Processing {len(short_term_memories)} short-term memories")

        for memory in short_term_memories:
            # Only consolidate if >7 days old
            age_days = (current_time - memory["learned_at"]).days
            if age_days < 7:
                continue

            decision = await self._evaluate_memory(memory, current_time)

            if decision.recommended_tier == MemoryTier.LONG_TERM:
                await self._promote_memory(memory["memory_id"])
                logger.info(
                    f"Promoted {memory['memory_id']} (priority={decision.metrics.priority_score:.2f}): "
                    f"{decision.reasoning}"
                )

            decisions.append(decision)

        # Step 2: Process long-term memories (archival)
        long_term_memories = await self._get_tier_memories(MemoryTier.LONG_TERM)
        logger.info(f"Evaluating {len(long_term_memories)} long-term memories for archival")

        for memory in long_term_memories:
            decision = await self._evaluate_memory(memory, current_time)

            if decision.recommended_tier == MemoryTier.ARCHIVED:
                await self._archive_memory(memory["memory_id"])
                logger.info(
                    f"Archived {memory['memory_id']} (priority={decision.metrics.priority_score:.2f}): "
                    f"{decision.reasoning}"
                )

            decisions.append(decision)

        # Generate report
        report = ConsolidationReport(
            timestamp=current_time,
            processed_count=len(decisions),
            promoted_count=sum(1 for d in decisions if d.recommended_tier == MemoryTier.LONG_TERM and d.current_tier == MemoryTier.SHORT_TERM),
            archived_count=sum(1 for d in decisions if d.recommended_tier == MemoryTier.ARCHIVED),
            unchanged_count=sum(1 for d in decisions if d.recommended_tier == d.current_tier),
            decisions=decisions,
        )

        logger.info(
            f"Consolidation complete: {report.promoted_count} promoted, "
            f"{report.archived_count} archived, {report.unchanged_count} unchanged"
        )

        return report

    async def _evaluate_memory(
        self,
        memory: dict[str, Any],
        current_time: datetime,
    ) -> ConsolidationDecision:
        """
        Evaluate a single memory for consolidation.

        📐 GUIDELINE: Priority = 40% access + 30% recency + 30% confidence (G3)
        """
        # Normalize access frequency (log scale)
        access_count = memory.get("access_count", 0)
        max_access = 100  # Normalization ceiling
        access_freq = min(math.log(1 + access_count) / math.log(1 + max_access), 1.0)

        # Calculate recency score using decay strategy
        recency_score = self.decay_strategy.calculate_recency_score(
            learned_at=memory["learned_at"],
            current_time=current_time,
            access_count=access_count,
        )

        # Confidence from extraction
        confidence = memory.get("confidence", 0.5)

        # Weighted priority score
        priority_score = (
            self.weights["access"] * access_freq +
            self.weights["recency"] * recency_score +
            self.weights["confidence"] * confidence
        )

        # Build metrics
        metrics = ConsolidationMetrics(
            access_frequency=access_freq,
            recency_score=recency_score,
            confidence=confidence,
            priority_score=priority_score,
        )

        # Determine tier
        current_tier = MemoryTier(memory.get("tier", MemoryTier.SHORT_TERM))

        if current_tier == MemoryTier.SHORT_TERM:
            # Promote if high priority
            if priority_score >= self.promotion_threshold:
                recommended_tier = MemoryTier.LONG_TERM
                reasoning = f"High priority ({priority_score:.2f}) - promoting to long-term"
            else:
                recommended_tier = MemoryTier.SHORT_TERM
                reasoning = f"Priority ({priority_score:.2f}) below promotion threshold ({self.promotion_threshold})"

        elif current_tier == MemoryTier.LONG_TERM:
            # Archive if very low priority
            if priority_score < self.archival_threshold:
                recommended_tier = MemoryTier.ARCHIVED
                reasoning = f"Low priority ({priority_score:.2f}) - archiving"
            else:
                recommended_tier = MemoryTier.LONG_TERM
                reasoning = f"Priority ({priority_score:.2f}) sufficient to remain long-term"

        else:  # Already archived
            recommended_tier = MemoryTier.ARCHIVED
            reasoning = "Already archived"

        return ConsolidationDecision(
            memory_id=memory["memory_id"],
            current_tier=current_tier,
            recommended_tier=recommended_tier,
            metrics=metrics,
            reasoning=reasoning,
        )

    async def _get_tier_memories(self, tier: MemoryTier) -> list[dict[str, Any]]:
        """Get all memories in a tier."""
        query = """
        MATCH (m:Memory)
        WHERE m.tier = $tier OR ($tier = 'short_term' AND m.tier IS NULL)
        RETURN
          m.memory_id AS memory_id,
          m.memory_type AS memory_type,
          m.content AS content,
          m.confidence AS confidence,
          m.tier AS tier,
          m.learned_at AS learned_at,
          m.access_count AS access_count,
          m.last_accessed AS last_accessed
        """
        async with self.neo4j.driver.session() as session:
            result = await session.run(query, tier=tier.value)
            return [record.data() async for record in result]

    async def _promote_memory(self, memory_id: str) -> None:
        """Promote memory to long-term tier."""
        await self.neo4j.update_node(
            label="Memory",
            node_id=memory_id,
            properties={"tier": MemoryTier.LONG_TERM.value, "promoted_at": datetime.utcnow().isoformat()}
        )

    async def _archive_memory(self, memory_id: str) -> None:
        """Archive memory."""
        await self.neo4j.update_node(
            label="Memory",
            node_id=memory_id,
            properties={"tier": MemoryTier.ARCHIVED.value, "archived_at": datetime.utcnow().isoformat()}
        )
```

---

### 📐 Scheduled Job (APScheduler)

**File:** `/home/vlb/Python/haia/src/haia/interfaces/scheduler.py`

```python
from apscheduler.schedulers.asyncio import AsyncIOScheduler

# Add consolidation job
scheduler.add_job(
    func=run_consolidation,
    trigger='cron',
    hour=3,  # Run at 3 AM daily (after type clustering at 4 AM)
    minute=0,
    id='memory_consolidation',
    replace_existing=True,
)

async def run_consolidation():
    """Daily consolidation job."""
    logger.info("Starting daily memory consolidation")
    try:
        consolidator = MemoryConsolidator(neo4j_service=neo4j_service)
        report = await consolidator.consolidate_daily()

        # Log summary
        logger.info(
            f"Consolidation report: {report.promoted_count} promoted, "
            f"{report.archived_count} archived from {report.processed_count} total"
        )

        # Optional: Store report in Neo4j for history
        await store_consolidation_report(report)

    except Exception as e:
        logger.error(f"Consolidation failed: {e}", exc_info=True)
```

---

### 📐 Configuration (Guideline)

```bash
# config.py additions

# Consolidation
CONSOLIDATION_ENABLED=True                      # 📐 G3: Enable by default
CONSOLIDATION_PROMOTION_THRESHOLD=0.7           # 📐 G3: Promote top 30%
CONSOLIDATION_ARCHIVAL_THRESHOLD=0.2            # 📐 G3: Archive bottom 20%
CONSOLIDATION_SHORT_TERM_DAYS=7                 # 📐 G3: Grace period
CONSOLIDATION_SCHEDULE="0 3 * * *"              # 🎨 F3: Daily at 3 AM

# Decay Strategy
DECAY_STRATEGY="exponential"                    # 🎨 F3: "exponential" | "ebbinghaus" | "linear"
DECAY_BASE_HALF_LIFE_DAYS=43.3                  # 🎨 F3: ~6 weeks for exponential

# Priority Weights
CONSOLIDATION_ACCESS_WEIGHT=0.40                # 📐 G3: Access frequency
CONSOLIDATION_RECENCY_WEIGHT=0.30               # 📐 G3: Temporal decay
CONSOLIDATION_CONFIDENCE_WEIGHT=0.30            # 📐 G3: Extraction confidence
```

---

### ✅ Acceptance Criteria

- [ ] Three tiers implemented (short-term, long-term, archived)
- [ ] Priority scoring formula works (40/30/30 weights)
- [ ] Decay algorithm calculates recency scores correctly
- [ ] Promotion threshold (0.7) promotes ~30% of short-term memories
- [ ] Archival threshold (0.2) archives ~20% of long-term memories
- [ ] Daily scheduled job runs at 3 AM
- [ ] Consolidation report logged with full details (P5)
- [ ] Access-based adaptive decay works (frequently accessed = slower decay)
- [ ] Manual validation: "Important" memories stay long-term, "noise" gets archived

---

## Phase 5: Self-Organization & Discovery

**Effort:** 8 story points (5-6 days)
**Risk:** Low

### 🔒 Immutable Requirements (Principle-Driven)

#### 5.1 DBSCAN Clustering on Memory Content (P1: Emergence)
**Principle:** "Structure emerges from data, not from predefined schemas."

**New Service:** `/home/vlb/Python/haia/src/haia/clustering/dbscan_clusterer.py`

```python
"""
DBSCAN clustering for discovering memory themes.

🔒 IMMUTABLE: Clustering reveals structure, doesn't impose it (P1)
📐 GUIDELINE: eps=0.15, min_samples=3, cosine metric (G1)
"""

from sklearn.cluster import DBSCAN
from sklearn.metrics import silhouette_score
import numpy as np

class MemoryClusterer:
    """
    Discovers emergent themes in memories using DBSCAN.

    Unlike type clustering (which clusters type names), this clusters
    memory content embeddings to find thematic patterns.
    """

    def __init__(
        self,
        neo4j_service: Neo4jService,
        extraction_model: str = "anthropic:claude-haiku-4-5-20251001",
        eps: float = 0.15,           # 📐 G1: Cosine distance threshold
        min_samples: int = 3,        # 📐 G1: Minimum cluster size
        metric: str = "cosine",      # 📐 G1: Semantic similarity
    ):
        self.neo4j = neo4j_service
        self.extraction_model = extraction_model
        self.eps = eps
        self.min_samples = min_samples
        self.metric = metric

    async def cluster_memories(
        self,
        min_confidence: float = 0.6,
        tier_filter: MemoryTier | None = None,
    ) -> list[MemoryCluster]:
        """
        Cluster memories by semantic similarity.

        Args:
            min_confidence: Only cluster high-confidence memories
            tier_filter: Optional tier filter (e.g., only long-term memories)

        Returns:
            List of discovered clusters with LLM-generated themes
        """
        # 1. Get memories with embeddings
        memories = await self._get_memories_with_embeddings(min_confidence, tier_filter)

        if len(memories) < self.min_samples:
            logger.info(f"Only {len(memories)} memories, skipping clustering")
            return []

        # 2. Extract embeddings
        memory_ids = [m["memory_id"] for m in memories]
        embeddings = np.array([m["embedding"] for m in memories])

        # 3. DBSCAN clustering
        clusterer = DBSCAN(eps=self.eps, min_samples=self.min_samples, metric=self.metric)
        cluster_labels = clusterer.fit_predict(embeddings)

        # 4. Calculate quality metrics
        if len(set(cluster_labels)) > 1:  # Need at least 2 clusters
            silhouette = silhouette_score(embeddings, cluster_labels, metric=self.metric)
            logger.info(f"Clustering silhouette score: {silhouette:.3f}")
        else:
            silhouette = None

        # 5. Group memories by cluster
        clusters_data = {}
        for memory_id, memory, cluster_id in zip(memory_ids, memories, cluster_labels):
            if cluster_id == -1:  # Noise point
                continue
            if cluster_id not in clusters_data:
                clusters_data[cluster_id] = []
            clusters_data[cluster_id].append(memory)

        # 6. Generate LLM themes for each cluster
        memory_clusters = []
        for cluster_id, cluster_memories in clusters_data.items():
            theme = await self._generate_theme(cluster_memories)

            cluster = MemoryCluster(
                cluster_id=f"memory_cluster_{cluster_id}",
                theme=theme,
                memory_ids=[m["memory_id"] for m in cluster_memories],
                size=len(cluster_memories),
                created_at=datetime.utcnow(),
                silhouette_score=silhouette,
            )
            memory_clusters.append(cluster)

            logger.info(f"Cluster {cluster_id}: '{theme}' ({cluster.size} memories)")

        # 7. Store clusters in Neo4j
        await self._store_clusters(memory_clusters)

        return memory_clusters

    async def _generate_theme(self, memories: list[dict[str, Any]]) -> str:
        """
        Generate theme description for cluster using LLM.

        🎨 FREEDOM: Prompt design is developer's choice (F4)
        """
        # Sample memories (max 10 for prompt)
        sample_memories = memories[:10]
        memory_summaries = [
            f"- [{m['memory_type']}] {m['content']}"
            for m in sample_memories
        ]

        prompt = f"""
Analyze these related memories and identify their common theme:

{chr(10).join(memory_summaries)}

Generate a concise theme description (3-8 words) that captures what these memories are about.

Examples of good themes:
- "Docker Container Deployment Workflow"
- "Proxmox Cluster Storage Management"
- "Home Assistant Device Automation"
- "Backup Strategy and Verification"

Theme:
"""

        # Use Haiku for cost efficiency
        from pydantic_ai import Agent

        agent = Agent[None, str](
            model=self.extraction_model,
            output_type=str,
            system_prompt="You identify common themes in memories.",
        )

        result = await agent.run(prompt)
        theme = result.output.strip().strip('"').strip("'")

        return theme

    async def _get_memories_with_embeddings(
        self,
        min_confidence: float,
        tier_filter: MemoryTier | None,
    ) -> list[dict[str, Any]]:
        """Get memories that have embeddings."""
        query = """
        MATCH (m:Memory)
        WHERE m.embedding IS NOT NULL
          AND m.confidence >= $min_confidence
        """

        if tier_filter:
            query += " AND m.tier = $tier"

        query += """
        RETURN
          m.memory_id AS memory_id,
          m.memory_type AS memory_type,
          m.content AS content,
          m.confidence AS confidence,
          m.embedding AS embedding,
          m.tier AS tier
        ORDER BY m.learned_at DESC
        """

        params = {"min_confidence": min_confidence}
        if tier_filter:
            params["tier"] = tier_filter.value

        async with self.neo4j.driver.session() as session:
            result = await session.run(query, **params)
            return [record.data() async for record in result]

    async def _store_clusters(self, clusters: list[MemoryCluster]) -> None:
        """
        Store clusters as nodes in Neo4j.

        Creates: (:Cluster)-[:CONTAINS]->(:Memory) relationships
        """
        for cluster in clusters:
            # Create cluster node
            await self.neo4j.create_node(
                label="Cluster",
                properties={
                    "cluster_id": cluster.cluster_id,
                    "theme": cluster.theme,
                    "size": cluster.size,
                    "created_at": cluster.created_at.isoformat(),
                    "silhouette_score": cluster.silhouette_score,
                }
            )

            # Link to memories
            for memory_id in cluster.memory_ids:
                await self.neo4j.create_relationship(
                    from_label="Cluster",
                    from_id=cluster.cluster_id,
                    rel_type="CONTAINS",
                    to_label="Memory",
                    to_id=memory_id,
                    properties={}
                )

class MemoryCluster(BaseModel):
    """Discovered memory cluster."""
    cluster_id: str
    theme: str  # LLM-generated theme
    memory_ids: list[str]
    size: int
    created_at: datetime
    silhouette_score: float | None  # Quality metric
```

---

#### 5.2 Discovery API (User-Facing)

**New Routes:** `/home/vlb/Python/haia/src/haia/api/routes/discovery.py`

```python
"""
Discovery API: Explore emergent themes and clusters.

🔒 IMMUTABLE: API must be observable and explainable (P5)
"""

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

router = APIRouter(prefix="/memories/discover", tags=["discovery"])

class ClusterResponse(BaseModel):
    """Cluster information for API response."""
    cluster_id: str
    theme: str
    size: int
    created_at: datetime
    silhouette_score: float | None
    sample_memories: list[dict[str, Any]]  # First 5 memories

class DiscoveryClustersResponse(BaseModel):
    """Response for cluster listing."""
    total_clusters: int
    clusters: list[ClusterResponse]

@router.post("/clusters", response_model=DiscoveryClustersResponse)
async def discover_clusters(
    min_confidence: float = Query(0.6, ge=0.0, le=1.0),
    tier_filter: MemoryTier | None = None,
) -> DiscoveryClustersResponse:
    """
    Run DBSCAN clustering to discover themes.

    This endpoint triggers clustering and returns discovered themes.

    Args:
        min_confidence: Only cluster high-confidence memories
        tier_filter: Optional tier filter

    Returns:
        List of discovered clusters with themes
    """
    try:
        clusterer = MemoryClusterer(neo4j_service=neo4j_service)
        clusters = await clusterer.cluster_memories(min_confidence, tier_filter)

        # Build response
        cluster_responses = []
        for cluster in clusters:
            # Get sample memories
            sample_memories = await _get_cluster_memories(cluster.cluster_id, limit=5)

            cluster_responses.append(ClusterResponse(
                cluster_id=cluster.cluster_id,
                theme=cluster.theme,
                size=cluster.size,
                created_at=cluster.created_at,
                silhouette_score=cluster.silhouette_score,
                sample_memories=sample_memories,
            ))

        return DiscoveryClustersResponse(
            total_clusters=len(clusters),
            clusters=cluster_responses,
        )

    except Exception as e:
        logger.error(f"Clustering failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Clustering failed")

@router.get("/clusters/{cluster_id}", response_model=ClusterResponse)
async def get_cluster(cluster_id: str) -> ClusterResponse:
    """
    Get details of a specific cluster.

    Returns cluster theme and all member memories.
    """
    cluster_node = await neo4j_service.read_node(label="Cluster", node_id=cluster_id)
    if not cluster_node:
        raise HTTPException(status_code=404, detail="Cluster not found")

    memories = await _get_cluster_memories(cluster_id, limit=None)

    return ClusterResponse(
        cluster_id=cluster_id,
        theme=cluster_node["theme"],
        size=cluster_node["size"],
        created_at=cluster_node["created_at"],
        silhouette_score=cluster_node.get("silhouette_score"),
        sample_memories=memories,
    )

@router.get("/themes", response_model=list[str])
async def list_themes() -> list[str]:
    """
    List all discovered themes.

    Returns:
        List of theme strings
    """
    query = """
    MATCH (c:Cluster)
    RETURN c.theme AS theme
    ORDER BY c.size DESC
    """
    async with neo4j_service.driver.session() as session:
        result = await session.run(query)
        themes = [record["theme"] async for record in result]

    return themes

async def _get_cluster_memories(cluster_id: str, limit: int | None) -> list[dict[str, Any]]:
    """Get memories in a cluster."""
    query = """
    MATCH (c:Cluster {cluster_id: $cluster_id})-[:CONTAINS]->(m:Memory)
    RETURN
      m.memory_id AS memory_id,
      m.memory_type AS memory_type,
      m.content AS content,
      m.confidence AS confidence,
      m.learned_at AS learned_at
    ORDER BY m.confidence DESC
    """

    if limit:
        query += f" LIMIT {limit}"

    async with neo4j_service.driver.session() as session:
        result = await session.run(query, cluster_id=cluster_id)
        return [record.data() async for record in result]
```

---

### 📐 Configuration (Guideline)

```bash
# config.py additions

# Memory Clustering
MEMORY_CLUSTERING_ENABLED=True                  # 📐 G1: Enable by default
MEMORY_CLUSTERING_EPS=0.15                      # 📐 G1: DBSCAN epsilon (cosine distance)
MEMORY_CLUSTERING_MIN_SAMPLES=3                 # 📐 G1: Minimum cluster size
MEMORY_CLUSTERING_MIN_CONFIDENCE=0.6            # 📐 G4: Only cluster high-quality memories
MEMORY_CLUSTERING_SCHEDULE="0 2 * * 0"          # 🎨 F3: Weekly (Sundays at 2 AM)

# Discovery API
DISCOVERY_API_ENABLED=True                      # 🔒 P5: Observability
DISCOVERY_MAX_CLUSTERS=50                       # 🎨 F5: API limit
```

---

### ✅ Acceptance Criteria

- [ ] DBSCAN clustering discovers meaningful themes (manual validation)
- [ ] Silhouette score >0.5 indicates good clustering quality
- [ ] LLM-generated themes are descriptive and accurate (manual review)
- [ ] Cluster nodes stored in Neo4j with CONTAINS relationships
- [ ] Discovery API `/memories/discover/clusters` works
- [ ] Discovery API `/memories/discover/themes` lists all themes
- [ ] Weekly clustering job runs (Sundays at 2 AM)
- [ ] Clustering handles edge cases (too few memories, all noise points)
- [ ] API responses include observability data (scores, sample memories)

---

## Implementation Timeline & Validation

### Timeline Summary

| Phase | Effort (SP) | Duration | Risk | Dependencies |
|-------|------------|----------|------|--------------|
| Phase 1: Temporal + BM25 | 5 | 3-4 days | Low | None |
| Phase 2: Dynamic Schema | 13 | 8-10 days | Medium | Phase 1 |
| Phase 3: Hybrid Retrieval | 8 | 5-6 days | Medium | Phase 1-2, APOC |
| Phase 4: Consolidation | 8 | 5-6 days | Medium | Phase 1-3 |
| Phase 5: Self-Organization | 8 | 5-6 days | Low | Phase 1-4 |
| **Total** | **42** | **6-7 weeks** | **Medium** | - |

### Quality Checkpoints

**After Phase 1:**
- ✅ Temporal queries work ("Show memories from October")
- ✅ BM25 search finds keyword matches
- ✅ All logs include temporal properties

**After Phase 2:**
- ✅ LLM generates diverse, specific memory types (>50 unique types in 100 extractions)
- ✅ Type clustering produces human-readable labels (manual review)
- ✅ Relationship inference creates meaningful connections (precision >80%)
- ✅ Temporal conflicts resolved automatically (no old memories deleted)

**After Phase 3:**
- ✅ Hybrid retrieval outperforms vector-only (recall improvement >15%)
- ✅ RRF merging weights methods correctly (visual inspection of result sources)
- ✅ APOC detection works (test with/without plugin)
- ✅ Graceful degradation when methods fail (manual failure injection)

**After Phase 4:**
- ✅ Consolidation promotes ~30% of short-term memories
- ✅ Consolidation archives ~20% of long-term memories
- ✅ "Important" memories stay long-term (manual validation with labeled test set)
- ✅ Decay algorithm reflects access patterns (frequently accessed = higher priority)

**After Phase 5:**
- ✅ Clustering discovers themes that make sense (manual review of 10 clusters)
- ✅ Silhouette score >0.5 (indicates good separation)
- ✅ Discovery API returns useful exploration results
- ✅ Weekly clustering job runs without errors

### Validation Strategy

1. **Unit Tests**: Each service has 80%+ code coverage
2. **Integration Tests**: End-to-end workflows (extraction → consolidation → retrieval)
3. **Manual Validation**: Human review of LLM outputs (types, relationships, themes)
4. **Benchmark Tests**: Compare against Session 9 baseline (recall, precision, latency)
5. **Production Simulation**: Run on real homelab conversation data (100+ conversations)

---

**Document Status:** ✅ Complete 5-Phase Specification
**Principles Applied:** All (P1-P5, G1-G5, F1-F5)
**Ready for:** Phase 1 implementation
