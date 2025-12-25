# Implementation Kickoff Prompt: Hybrid Temporal Memory System

**Use this prompt with:** `/speckit.specify`

---

## 🎯 Feature Description

Implement HAIA's **Hybrid Temporal Memory System** - a revolutionary self-evolving, self-organizing memory architecture that replaces hardcoded categories with emergent structure.

**Core Vision:** "HAIA learns who you are, what you do, and what you work with through self-categorizing, self-organizing memory that adapts to your vocabulary and evolves with your infrastructure."

---

## 📚 Complete Specification References

All planning is complete. Implementation follows these documents **exactly**:

### 1. Philosophy & Principles (The Constitution)
**File:** `/home/vlb/Python/haia/docs/architecture/memory-system-principles.md`

**5 Immutable Principles:**
- **P1: Emergence Over Prescription** - Structure emerges from data, never hardcode types
- **P2: Temporal Truth** - Memories capture beliefs at a time, preserve history
- **P3: Semantic Retrieval** - Retrieval finds meaning, not exact matches
- **P4: Graceful Degradation** - System functions when components fail
- **P5: Observability** - Every decision must be explainable

**5 Strong Guidelines + 5 Freedom Zones + 4 Decision Frameworks** - All documented with examples.

### 2. Detailed Implementation Plan
**File:** `/home/vlb/Python/haia/docs/architecture/implementation-plan-enhanced.md`

Complete technical specifications for all 5 phases:
- **Phase 1:** Temporal Foundation & BM25 (5 SP, 3-4 days, LOW risk)
- **Phase 2:** Dynamic Schema - LLM Entity Extraction (13 SP, 8-10 days, MEDIUM risk)
- **Phase 3:** Hybrid Retrieval (Vector + BM25 + Graph) (8 SP, 5-6 days, MEDIUM risk)
- **Phase 4:** Memory Consolidation (3-tier lifecycle) (8 SP, 5-6 days, MEDIUM risk)
- **Phase 5:** Self-Organization (DBSCAN clustering) (8 SP, 5-6 days, LOW risk)

**Total:** 42 story points, 6-7 weeks

### 3. Master Index
**File:** `/home/vlb/Python/haia/docs/architecture/README.md`

Navigation guide, quick reference, workflow documentation.

### 4. Historical Context
**File:** `/home/vlb/Python/haia/docs/brainstorming/2025-12-10-hybrid-temporal-memory-architecture.md`

Research findings, rationale, user confirmations.

---

## 🎯 User Priorities (Validated)

1. **Accuracy** (highest priority)
2. **Adaptability** (self-organizing)
3. **Cost** (acceptable: ~$0.01/memory for relationships)
4. **Speed** (acceptable: <500ms p95 retrieval)

---

## 🏗️ Implementation Approach

### Phase-by-Phase Execution

**DO NOT implement all phases at once.** Execute sequentially:

1. **Complete Phase 1** → Validate acceptance criteria → Quality checkpoint → User approval
2. **Complete Phase 2** → Validate acceptance criteria → Quality checkpoint → User approval
3. **Complete Phase 3** → Validate acceptance criteria → Quality checkpoint → User approval
4. **Complete Phase 4** → Validate acceptance criteria → Quality checkpoint → User approval
5. **Complete Phase 5** → Validate acceptance criteria → Quality checkpoint → User approval

### Per-Phase Workflow

For each phase:

```
READ
├─ Relevant principles from memory-system-principles.md
├─ Phase specification from implementation-plan-enhanced.md
└─ Acceptance criteria for this phase

IMPLEMENT
├─ Create new services (use code examples from plan)
├─ Update existing services (follow migration guide)
├─ Add configuration (template provided)
├─ Log all decisions (P5: Observability)
└─ Handle failures gracefully (P4: Graceful Degradation)

VALIDATE
├─ Run acceptance tests
├─ Manual validation (where specified)
├─ Quality checkpoint
└─ User approval before next phase
```

---

## 📋 Tracking Requirements

### Create Tracking Structure

Use speckit to create:

1. **Feature Spec:** `specs/010-hybrid-temporal-memory/spec.md`
   - References all planning documents
   - Defines 5 phases as major milestones
   - Links to acceptance criteria

2. **Task Breakdown:** `specs/010-hybrid-temporal-memory/tasks.md`
   - One task per major deliverable
   - Dependencies clearly marked
   - Acceptance criteria per task

3. **Progress Dashboard:** Update after each phase
   - Checkboxes for acceptance criteria
   - Quality metrics (recall, precision, latency)
   - Blocker tracking

### Deliverables Per Phase

**Phase 1:**
- [ ] Migration: `database/schema/migrations/010-add-temporal-properties.cypher`
- [ ] Migration: `database/schema/migrations/011-create-bm25-fulltext-index.cypher`
- [ ] Updated: `src/haia/extraction/models.py` (ExtractedMemory with temporal properties)
- [ ] Updated: `src/haia/services/memory_storage.py` (temporal storage)
- [ ] New method: `src/haia/services/neo4j.py:search_memories_bm25()`
- [ ] Config: BM25_SEARCH_ENABLED, TEMPORAL_QUERIES_ENABLED
- [ ] Tests: Temporal queries, BM25 search, superseding logic

**Phase 2:**
- [ ] Deleted: `MemoryCategory` enum (P1: Emergence)
- [ ] Updated: `src/haia/extraction/prompts.py` (dynamic type prompt)
- [ ] New: `src/haia/clustering/type_clusterer.py` (TypeClusterer service)
- [ ] New: `src/haia/clustering/type_models.py` (TypeCluster models)
- [ ] New: `src/haia/services/relationship_inference.py` (RelationshipInferenceService)
- [ ] New: `src/haia/services/temporal_manager.py` (TemporalManager)
- [ ] Updated: `src/haia/services/neo4j.py` (dynamic id_property detection)
- [ ] Config: Type clustering schedule (daily 4 AM)
- [ ] Tests: Type diversity, clustering quality, relationship precision

**Phase 3:**
- [ ] New: `src/haia/retrieval/rrf_merger.py` (RRFMerger)
- [ ] New: `src/haia/retrieval/models.py` (RetrievalResult, MergedRetrievalResult)
- [ ] Updated: `src/haia/services/neo4j.py` (graph traversal + APOC fallback)
- [ ] Updated: `src/haia/embedding/retrieval_service.py` (retrieve_hybrid method)
- [ ] Updated: `deployment/docker-compose.yml` (APOC plugin)
- [ ] Config: Hybrid retrieval weights, RRF parameters
- [ ] Tests: RRF merging, APOC detection, graceful degradation

**Phase 4:**
- [ ] New: `src/haia/consolidation/models.py` (MemoryTier, ConsolidationMetrics)
- [ ] New: `src/haia/consolidation/decay.py` (3 decay strategies)
- [ ] New: `src/haia/consolidation/consolidator.py` (MemoryConsolidator)
- [ ] Updated: `src/haia/interfaces/scheduler.py` (consolidation job 3 AM)
- [ ] Config: Consolidation thresholds, decay parameters
- [ ] Tests: Promotion/archival rates, decay calculations, priority scoring

**Phase 5:**
- [ ] New: `src/haia/clustering/dbscan_clusterer.py` (MemoryClusterer)
- [ ] New: `src/haia/api/routes/discovery.py` (Discovery API)
- [ ] Updated: `src/haia/interfaces/scheduler.py` (clustering job weekly)
- [ ] Config: DBSCAN parameters, clustering schedule
- [ ] Tests: Silhouette score, theme quality, API endpoints

---

## ✅ Success Criteria

### After Phase 1
- [ ] Temporal queries work: "Show memories valid on 2024-10-01"
- [ ] BM25 finds keyword matches
- [ ] Superseding logic preserves old memories

### After Phase 2
- [ ] LLM generates >50 unique types in 100 extractions
- [ ] Type clustering produces human-readable labels
- [ ] Relationship inference precision >80%
- [ ] No old memories deleted (P2: Temporal Truth)

### After Phase 3
- [ ] Hybrid retrieval recall +15% vs vector-only baseline
- [ ] p95 latency <500ms
- [ ] APOC detection works (test with/without)
- [ ] All methods degrade gracefully

### After Phase 4
- [ ] ~30% of short-term memories promoted
- [ ] ~20% of long-term memories archived
- [ ] Frequently accessed memories decay slower

### After Phase 5
- [ ] Silhouette score >0.5
- [ ] Cluster themes make sense (manual review)
- [ ] Discovery API returns useful results

---

## 🚨 Critical Constraints

### Must Follow
- **NEVER hardcode entity types, relationship types, or categories** (P1)
- **NEVER delete old memories** (P2)
- **ALWAYS log decisions** (P5)
- **ALWAYS handle failures gracefully** (P4)
- **ALWAYS use semantic retrieval** (P3)

### Dependencies
- **Phase 2** depends on Phase 1 (temporal foundation)
- **Phase 3** depends on Phase 1-2 (requires APOC plugin)
- **Phase 4** depends on Phase 1-3 (requires retrieval + access tracking)
- **Phase 5** depends on Phase 1-4 (requires consolidation tiers)

### No Migration Needed
- Memory system not in production
- Clean implementation from day one
- No backward compatibility required
- All features enabled by default

---

## 📊 Expected Outcomes

Based on research benchmarks (Mem0, Graphiti):

| Metric | Baseline | Target | Source |
|--------|----------|--------|--------|
| Accuracy | Session 9 | +26% | Mem0 |
| Retrieval Latency | ~1-2s | <300ms p95 | Graphiti |
| Token Cost | Baseline | -90% | Mem0 |
| Memory Types | 5 | Infinite | LLM-driven |
| Recall | Vector-only | +15-20% | Hybrid |

---

## 🎯 Starting Point: Phase 1

**Immediate Next Steps:**

1. Run `/speckit.specify` with this prompt
2. Review generated spec in `specs/010-hybrid-temporal-memory/spec.md`
3. Run `/speckit.tasks` to generate task breakdown
4. Begin Phase 1 implementation:
   - Start with temporal properties migration
   - Add BM25 full-text index
   - Update ExtractedMemory model
   - Test temporal queries

**Estimated Phase 1 Duration:** 3-4 days (5 story points, LOW risk)

---

## 📖 Reference During Implementation

### Daily Checklist
- [ ] Review relevant principles (5 min)
- [ ] Check acceptance criteria before starting (2 min)
- [ ] Reference code examples from enhanced plan
- [ ] Log all decisions (P5)
- [ ] Test graceful degradation (P4)

### When Stuck
1. **Principle conflict?** → Re-read `memory-system-principles.md` examples
2. **Implementation ambiguity?** → Check decision frameworks (Tier 4)
3. **Technical blocker?** → Review enhanced plan code examples
4. **Philosophy question?** → Consult brainstorming doc

---

## 🔄 Iteration Strategy

After each phase:

1. **Validate** acceptance criteria
2. **Run** quality checkpoints
3. **Manual review** (where specified)
4. **User approval** before next phase
5. **Update** progress tracking
6. **Document** any deviations from plan

If phase fails validation:
- Identify root cause
- Check if principle was violated
- Fix and re-validate
- Do NOT proceed to next phase

---

## 🎯 Final Goal

A production-ready memory system that:
- ✅ Learns user vocabulary dynamically
- ✅ Organizes itself without human intervention
- ✅ Adapts to infrastructure changes over time
- ✅ Retrieves semantically related memories
- ✅ Preserves temporal history
- ✅ Explains all decisions
- ✅ Functions gracefully under failure

**Timeline:** 6-7 weeks (42 story points across 5 phases)

---

**Ready to build!** 🚀

Use `/speckit.specify` with this prompt to generate the feature specification and begin Phase 1.
