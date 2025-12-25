# Memory System Architecture Principles & Philosophy

**Version:** 2.0 (Enhanced)
**Date:** December 10, 2025
**Status:** 🎯 Implementation Guide

---

## 🎯 Core Vision

**"HAIA learns who you are, what you do, and what you work with through self-evolving, self-categorizing, self-organizing memory."**

This document defines the **immutable principles**, **strong guidelines**, and **implementation freedom** zones that guide the hybrid temporal memory system implementation.

---

## 📜 Tier 1: Immutable Principles (Never Violate)

These are the **constitutional laws** of the memory system. Implementation MUST follow these.

### P1: Emergence Over Prescription
**Principle:** *"Structure emerges from data, not from predefined schemas."*

**What This Means:**
- ❌ **NEVER** hardcode entity types, relationship types, or categories in enums
- ❌ **NEVER** force data into predefined taxonomies
- ✅ **ALWAYS** let LLM extract types from natural language
- ✅ **ALWAYS** let clustering reveal patterns in the data

**Rationale:** Hardcoding prevents the system from adapting to user's vocabulary and evolving needs.

---

### P2: Temporal Truth
**Principle:** *"Memories capture what was said/believed at a time, not universal truth."*

**What This Means:**
- ❌ **NEVER** delete old memories because they're "wrong"
- ❌ **NEVER** assume latest information invalidates previous information
- ✅ **ALWAYS** track when information was learned (`learned_at`)
- ✅ **ALWAYS** track when information was valid (`valid_from`, `valid_until`)

**Example:**
```
User: "I have 3 Proxmox nodes" (Oct 2024)
Later: "I have 4 Proxmox nodes" (Dec 2024)

Result:
  Memory 1: {content: "3 nodes", valid_from: "2024-01", valid_until: "2024-12"}
  Memory 2: {content: "4 nodes", valid_from: "2024-12", valid_until: null}
```

**Rationale:** Users' infrastructure and preferences evolve. Temporal tracking enables point-in-time queries and understanding of change over time.

---

### P3: Semantic Retrieval
**Principle:** *"Retrieval finds meaning, not exact matches."*

**What This Means:**
- ❌ **NEVER** rely solely on exact string matching
- ❌ **NEVER** assume user will query using stored vocabulary
- ✅ **ALWAYS** use semantic similarity (embeddings) for retrieval
- ✅ **ALWAYS** expand queries to include semantic neighbors

**Example:**
```
Query: "container deployment preferences"
Should find:
  - "docker_container_tool" (semantic match)
  - "kubernetes_orchestration" (semantic match)
  - "deployment_strategy" (semantic match)
```

**Rationale:** Users don't know internal type names. Semantic search bridges vocabulary gaps.

---

### P4: Graceful Degradation
**Principle:** *"System must function when components fail, but indicate degradation."*

**What This Means:**
- ❌ **NEVER** crash if APOC unavailable, embeddings fail, or LLM times out
- ❌ **NEVER** silently degrade without logging
- ✅ **ALWAYS** provide fallback behavior (e.g., vector-only if BM25 fails)
- ✅ **ALWAYS** log degradation and warn user if critical features unavailable

**Rationale:** Reliability > Feature completeness. System should remain useful even when components fail.

---

### P5: Observability
**Principle:** *"Every decision the system makes must be observable and explainable."*

**What This Means:**
- ❌ **NEVER** make black-box decisions (why this type? why this cluster?)
- ❌ **NEVER** hide LLM reasoning or confidence scores
- ✅ **ALWAYS** log extraction decisions with confidence
- ✅ **ALWAYS** provide explanations for clustering, consolidation, archival

**Example:**
```
Memory archived:
  - ID: mem_123
  - Reason: Priority score 0.15 < threshold 0.20
  - Details: Last accessed 147 days ago, confidence 0.42, access_count 1
```

**Rationale:** Users must understand and trust system decisions. Observability enables debugging and tuning.

---

## 📐 Tier 2: Strong Guidelines (Follow Unless Good Reason)

These are **best practices** that should be followed in most cases, but developers can deviate with justification.

### G1: Semantic Clustering for Consistency
**Guideline:** *"Let types proliferate freely, cluster them semantically for organization."*

**Approach:**
1. **Extraction:** LLM generates any type it wants (no constraints)
2. **Clustering:** System groups similar types via embedding similarity
3. **Summarization:** LLM generates human-readable cluster labels
4. **Retrieval:** Query expansion includes cluster members

**Parameters:**
- Min cluster size: 3 similar types
- Similarity threshold: 0.80 cosine similarity
- Clustering schedule: Daily at 4 AM

**When to Deviate:**
- If clustering creates too many tiny clusters, increase min_cluster_size
- If clustering misses obvious relationships, lower similarity threshold
- If computational cost is prohibitive, run weekly instead of daily

**Why This Works:**
- Captures user's exact vocabulary
- Prevents vocabulary drift (similar types get clustered)
- Enables semantic retrieval across type variations

---

### G2: Hybrid Retrieval with Adaptive Weighting
**Guideline:** *"Use all three retrieval methods, weight by empirical performance."*

**Approach:**
1. **Parallel Execution:** Run vector + BM25 + graph simultaneously
2. **RRF Merging:** Combine with Reciprocal Rank Fusion (k=60)
3. **Weight Tuning:** Start with vector=1.0, BM25=0.8, graph=0.6
4. **Continuous Learning:** Adjust weights based on user feedback (clicks, dwell time)

**When to Deviate:**
- If one method consistently underperforms (precision <0.3), reduce weight
- If latency exceeds 500ms p95, disable slowest method
- If APOC unavailable, use vector + BM25 only

**Why This Works:**
- Vector: Good for semantic similarity
- BM25: Good for keyword precision
- Graph: Good for discovering related context
- RRF: Robust to individual method failures

---

### G3: Conservative Consolidation
**Guideline:** *"Promote aggressively, archive conservatively."*

**Approach:**
- **Promotion threshold:** 0.7 (promote 30% of short-term memories)
- **Archival threshold:** 0.2 (archive only bottom 20%)
- **Priority formula:** `0.40*access_freq + 0.30*recency + 0.30*confidence`

**When to Deviate:**
- If storage costs are high, lower archival threshold to 0.3
- If users complain about missing memories, raise archival threshold to 0.15
- If promotion doesn't correlate with usefulness, adjust priority weights

**Rationale:** Better to keep potentially useful memories than aggressively delete. Storage is cheap, memory loss is expensive.

---

### G4: High Confidence for Dynamic Types
**Guideline:** *"Require higher confidence for LLM-generated types than hardcoded types."*

**Approach:**
- Extraction confidence threshold: **0.6** (higher than original 0.4)
- Relationship inference confidence: **0.7**
- Type clustering confidence: **0.5** (lower, since it's offline verification)

**When to Deviate:**
- If LLM rarely generates confident types, lower to 0.5
- If type quality is poor despite high confidence, add post-processing validation
- If user prefers quantity over quality, lower threshold

**Rationale:** Dynamic types have more failure modes than hardcoded enums. Higher bar ensures quality.

---

### G5: Bi-Temporal Tracking Always
**Guideline:** *"Track both when event occurred and when we learned about it."*

**Properties:**
- `valid_from`: When the information became true (user's timeline)
- `valid_until`: When the information stopped being true (null = current)
- `learned_at`: When HAIA learned this information (system's timeline)
- `extraction_timestamp`: When extraction ran

**Why Two Timelines:**
- **Event time** (`valid_from/until`): "I migrated to Docker in October"
- **Ingestion time** (`learned_at`): "User told me this on December 10"

**When to Deviate:**
- If temporal overhead is too high (unlikely), track only `learned_at`
- If user never references past states, simplify to single timestamp

---

## 🎨 Tier 3: Implementation Freedom (Innovate Within Constraints)

These areas are **intentionally underspecified** to allow developer creativity.

### F1: Type Normalization Strategy
**Freedom:** *Choose how to prevent type proliferation chaos.*

**Options:**
1. **String Similarity:** Merge types with edit distance <3 (e.g., "docker_preference" + "docker-preference")
2. **LLM Clustering:** Ask LLM "are these types the same?" for ambiguous pairs
3. **Embedding Clustering:** Use stricter similarity threshold (0.90) for near-duplicates
4. **User Confirmation:** Show suggested merges, let user approve

**Constraints:**
- Must preserve semantic distinction (don't merge "docker" and "kubernetes")
- Must run efficiently (O(n²) comparison acceptable only if n < 10k types)

**Choose Based On:** Type proliferation rate, computational budget, user tolerance for messiness

---

### F2: Relationship Schema
**Freedom:** *Decide how to represent relationships between memories.*

**Options:**
1. **Flat Relationships:** All relationships are edges: `(memory_a)-[REL_TYPE]->(memory_b)`
2. **Reified Relationships:** Relationships are nodes: `(memory_a)-[:HAS_REL]->(rel)-[:POINTS_TO]->(memory_b)`
3. **Hypergraphs:** Multiple memories in one relationship: `(mem_a, mem_b, mem_c)-[CLUSTER]`

**Constraints:**
- Must support querying: "find all memories related to X"
- Must support temporal invalidation: "this relationship ended on date Y"
- Must be LLM-inferable (LLM must be able to suggest relationship type)

**Choose Based On:** Neo4j performance, query complexity, relationship cardinality

---

### F3: Decay Algorithm
**Freedom:** *Choose decay function for memory consolidation.*

**Options:**
1. **Exponential:** `score * e^(-λt)` (simple, fast)
2. **Ebbinghaus:** `score * (1 + 1.84*t)^-1.25` (models human forgetting)
3. **Access-Based:** Half-life increases with access frequency
4. **Learned:** ML model predicts usefulness from features

**Constraints:**
- Must be monotonic (older memories never become higher priority)
- Must be tuneable (ability to adjust aggressiveness)
- Must be efficient (O(1) per memory)

**Choose Based On:** User feedback, empirical validation, computational cost

---

### F4: Cluster Summarization Prompt
**Freedom:** *Design prompt for LLM to generate cluster labels.*

**Requirements:**
- Output must be concise (1-4 words)
- Output must be descriptive (human-understandable)
- Output must capture semantic commonality

**Example Approaches:**
```python
# Option 1: Few-shot
prompt = f"""
Generate a concise label for these memory types:
- docker_container_tool
- kubernetes_orchestration
- container_deployment_setup

Label: "container_orchestration_tools"

Now label these:
{type_names}

Label:
"""

# Option 2: Chain-of-thought
prompt = f"""
Analyze these memory types and find their common theme:
{type_names}

1. What do they have in common?
2. What category do they belong to?
3. Generate a 2-3 word label that captures this category.
"""
```

**Choose Based On:** LLM performance, cost, label quality

---

### F5: BM25 vs rank-bm25
**Freedom:** *Choose BM25 implementation.*

**Options:**
1. **Neo4j Full-Text Index:** Native, no dependencies, "BM25-like" but not exact
2. **rank-bm25 Library:** True BM25, tunable parameters (k1, b), but in-memory index
3. **Elasticsearch:** Industrial-strength, but adds external dependency

**Constraints:**
- Must support incremental updates (new memories indexed immediately)
- Must be fast (<100ms for search across 10k memories)
- Must not require full rebuild on every change

**Choose Based On:** Performance benchmarks, scalability needs, operational complexity

---

## 🔍 Tier 4: Decision Frameworks (When Plan Is Silent)

When encountering implementation choices not covered by principles or guidelines:

### Decision Framework 1: Emergence Test
**Question:** "Does this create or constrain structure?"

- If **creates structure** → Must be dynamic/emergent (e.g., LLM-driven)
- If **constrains structure** → Violates P1 (Emergence Over Prescription)

**Examples:**
- Adding a new entity type → ❌ Violates P1
- Adding a new algorithm to infer entity types → ✅ Supports P1

---

### Decision Framework 2: Temporal Test
**Question:** "Does this information change over time?"

- If **yes** → Must track temporal bounds (`valid_from`, `valid_until`)
- If **no** → Single timestamp sufficient

**Examples:**
- User's infrastructure setup → Changes over time (temporal)
- User's birth year → Doesn't change (single timestamp)

---

### Decision Framework 3: Observability Test
**Question:** "Can user understand why system made this decision?"

- If **no** → Must add logging/explanation
- If **yes** → Implementation is acceptable

**Examples:**
- Memory archived → Must log reason (priority score, thresholds)
- Embedding generated → Logging optional (straightforward operation)

---

### Decision Framework 4: Graceful Degradation Test
**Question:** "What happens if this component fails?"

- **Critical component** → Must have fallback behavior
- **Nice-to-have component** → Can fail gracefully

**Examples:**
- Vector search fails → CRITICAL → Fallback to BM25 only
- Graph traversal fails → Nice-to-have → Fallback to vector + BM25

---

## 🎯 Applied Examples

### Example 1: Should We Hardcode Relationship Types?

**Analysis:**
- **Emergence Test:** Hardcoding relationship types creates fixed structure → ❌ Violates P1
- **Decision:** Use LLM to infer relationship types dynamically

**Implementation:**
```python
# LLM prompt for relationship inference
"""
Given these two entities:
1. {entity_a.type}: {entity_a.content}
2. {entity_b.type}: {entity_b.content}

If they are related, suggest a relationship type (1-3 words, uppercase).
Examples: DEPENDS_ON, REPLACED_BY, INSPIRED_BY, CONTRADICTS

Relationship type (or "NONE" if unrelated):
"""
```

---

### Example 2: Should We Delete Contradictory Memories?

**Analysis:**
- **Temporal Test:** User's infrastructure changes over time → Temporal bounds needed
- **P2 (Temporal Truth):** Never delete old memories → ❌ Violates P2
- **Decision:** Mark old memory with `valid_until`, keep both

**Implementation:**
```python
# When contradiction detected
old_memory.valid_until = new_memory.learned_at
new_memory.valid_from = new_memory.learned_at
new_memory.metadata["supersedes"] = old_memory.memory_id
```

---

### Example 3: What Decay Algorithm to Use?

**Analysis:**
- **F3 (Implementation Freedom):** Decay algorithm is underspecified → Developer's choice
- **Constraint:** Must be monotonic, tunable, efficient
- **Guideline G3:** Conservative consolidation (archive <20%)

**Decision:** Start with exponential decay, tune half-life based on archival rate.

**Implementation:**
```python
# Exponential decay with adaptive half-life
def calculate_priority(memory, current_time):
    days_old = (current_time - memory.learned_at).days
    base_half_life = 43.3  # ~6 weeks

    # Adaptive: frequently accessed memories decay slower
    access_multiplier = 1 + math.log(1 + memory.access_count)
    effective_half_life = base_half_life * access_multiplier

    decay_rate = math.log(2) / effective_half_life
    recency_score = math.exp(-decay_rate * days_old)

    # Combine: access_freq (40%) + recency (30%) + confidence (30%)
    priority = (
        0.40 * normalize_frequency(memory.access_count) +
        0.30 * recency_score +
        0.30 * memory.confidence
    )
    return priority
```

---

## 📊 Summary Matrix

| Aspect | Principle/Guideline | Strictness | Deviation Allowed? |
|--------|-------------------|------------|-------------------|
| Entity types | P1: Emergence | Immutable | ❌ Never hardcode |
| Relationship types | P1: Emergence | Immutable | ❌ Never hardcode |
| Temporal tracking | P2: Temporal Truth | Immutable | ❌ Always track |
| Semantic retrieval | P3: Semantic Retrieval | Immutable | ❌ Always use embeddings |
| Graceful degradation | P4: Graceful Degradation | Immutable | ❌ Must handle failures |
| Observability | P5: Observability | Immutable | ❌ Must log decisions |
| Type clustering | G1: Semantic Clustering | Strong | ✅ If clustering fails |
| Hybrid retrieval | G2: Adaptive Weighting | Strong | ✅ If performance poor |
| Consolidation | G3: Conservative | Strong | ✅ If storage constrained |
| Confidence thresholds | G4: High Confidence | Strong | ✅ If quality/quantity trade-off |
| Bi-temporal | G5: Dual Timelines | Strong | ✅ If overhead high |
| Type normalization | F1: Freedom | Flexible | ✅ Developer's choice |
| Relationship schema | F2: Freedom | Flexible | ✅ Developer's choice |
| Decay algorithm | F3: Freedom | Flexible | ✅ Developer's choice |
| Cluster summarization | F4: Freedom | Flexible | ✅ Developer's choice |
| BM25 implementation | F5: Freedom | Flexible | ✅ Developer's choice |

---

## 🚀 Implementation Checklist

Before implementing any feature, ask:

- [ ] Does this violate any Tier 1 Principles? (If yes, redesign)
- [ ] Does this follow Tier 2 Guidelines? (If no, justify deviation)
- [ ] Is there Tier 3 Freedom here? (If yes, choose best approach)
- [ ] Does this decision fit a Tier 4 Framework? (If yes, apply framework)
- [ ] Is this decision observable? (Can user understand why?)
- [ ] Does this degrade gracefully? (What if it fails?)

---

**Document Status:** ✅ Ready for Implementation
**Next Review:** After Phase 2 completion (validate principles held up in practice)
